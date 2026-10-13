import json
import os
import re
import threading
import time
from typing import Callable, Optional, Dict, Any
import logging

from api.deepseek_client import DeepSeekClient
from .tools import TOOL_DEFINITIONS, ToolExecutor, ToolResult
from .prompts import SYSTEM_PROMPT, build_generation_prompt
from .desktop_validation import validate_desktop_output

logger = logging.getLogger(__name__)

MAX_TURNS = 60
# After this many consecutive assistant turns with no tool calls, remind the
# model that it must either create files or finish with DONE.
NUDGE_AFTER_IDLE_TURNS = 2
# After this many consecutive idle turns, abort instead of burning turns.
ABORT_AFTER_IDLE_TURNS = 5
# Completion requires a standalone DONE token (word-boundary match), not a
# substring check, so prose like "undone" can never trigger completion.
DONE_PATTERN = re.compile(r"\bDONE\b")
# Tool results (e.g. read_file of a large source file) are truncated before
# being sent back to the model to keep the context bounded.
MAX_TOOL_RESULT_CHARS = 4000
MAX_TOOL_REPAIR_TURNS = 3

class CodeAgent:
    """Main CodeAgent class orchestrating the code generation process."""
    
    def __init__(self, api_key: str, model: str = "deepseek-chat"):
        """Initialize agent with DeepSeek client"""
        self.client = DeepSeekClient(api_key=api_key, model=model)
        self.model = model
        
    def generate_project(self, 
                         architecture_data: Dict[str, Any], 
                         output_dir: str, 
                         on_message: Optional[Callable[[str], None]] = None, 
                         on_tool: Optional[Callable[[str, str], None]] = None,
                         on_error: Optional[Callable[[str], None]] = None,
                         cancel_event: Optional[threading.Event] = None,
                         pause_event: Optional[threading.Event] = None) -> bool:
        """Run the agent loop to generate a project.

        ``cancel_event``: when set, the loop stops at the next turn boundary and
        returns ``False``.
        ``pause_event``: when set, the loop waits (without consuming turns) until
        it is cleared or ``cancel_event`` is set. This lets the GUI pause an
        in-progress run and resume it, or cancel it entirely.
        """

        tool_executor = ToolExecutor(output_dir)
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_generation_prompt(architecture_data)}
        ]
        
        turn_count = 0
        idle_turns = 0
        completion_failures = 0
        tool_repair_turns = 0
        # A failed write with a known target must be retried for that same target.
        # If the arguments were unreadable, require a successful write on a later turn.
        pending_writes = {}

        def _request_tool_repair(details: str) -> bool:
            nonlocal tool_repair_turns
            tool_repair_turns += 1
            if tool_repair_turns >= MAX_TOOL_REPAIR_TURNS:
                if on_error:
                    on_error("Generation stopped after repeated tool failures:\n" + details)
                return False
            if on_message:
                on_message("Requesting corrected tool calls from the model "
                           f"(attempt {tool_repair_turns}/{MAX_TOOL_REPAIR_TURNS - 1}).")
            messages.append({
                "role": "user",
                "content": (
                    details + "\nRetry the failed operations before continuing or saying DONE. "
                    "Send one create_file call per response, using valid JSON with both "
                    "a non-empty string 'path' and the full string 'content'. Escape newlines "
                    "and quotes inside JSON strings. Split large modules into smaller complete "
                    "files if needed; never write placeholders or partial file contents."
                ),
            })
            return True

        def _cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        def _wait_while_paused() -> bool:
            """Block while paused. Returns False if cancelled during the pause."""
            if pause_event is None or not pause_event.is_set():
                return True
            if on_message:
                on_message("Paused. Click Resume to continue, or Cancel to stop.")
            while pause_event.is_set():
                if _cancelled():
                    return False
                time.sleep(0.2)
            if on_message:
                on_message("Resumed.")
            return True
        
        while turn_count < MAX_TURNS:
            if _cancelled():
                msg = "Generation cancelled by user."
                logger.info(msg)
                if on_message:
                    on_message(msg)
                return False

            if not _wait_while_paused():
                msg = "Generation cancelled by user while paused."
                logger.info(msg)
                if on_message:
                    on_message(msg)
                return False

            turn_count += 1
            
            try:
                # Call LLM
                response = self.client.chat(
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    temperature=0.1
                )
                
                content = response.get("content") or ""
                tool_calls = response.get("tool_calls") or []
                response_truncated = response.get("finish_reason") == "length"
                
                assistant_message = {
                    "role": "assistant",
                    "content": content,
                }
                if tool_calls:
                    assistant_message["tool_calls"] = tool_calls
                messages.append(assistant_message)
                
                # Check for tool calls
                if tool_calls:
                    idle_turns = 0
                    failures = []
                    previous_unknowns = {key for key in pending_writes if key[1] is None}
                    for tool_call in tool_calls:
                        if _cancelled():
                            msg = "Generation cancelled by user."
                            logger.info(msg)
                            if on_message:
                                on_message(msg)
                            return False
                        func = tool_call.get("function", {})
                        tool_name = func.get("name")
                        arguments = None
                        try:
                            arguments = json.loads(func.get("arguments", ""))
                        except (json.JSONDecodeError, TypeError):
                            outcome = ToolResult(
                                f"Error: {tool_name} arguments are not valid JSON. "
                                "No operation was performed. Resend the complete JSON object.",
                                is_error=True,
                            )
                        else:
                            outcome = None

                        # Even valid JSON can contain an incomplete file when the
                        # provider reports an output limit. Never execute that response.
                        if response_truncated:
                            outcome = ToolResult(
                                "Error: The model response reached its output limit "
                                "(finish_reason=length). No operation was performed. "
                                "Retry with one smaller, complete file per response.",
                                is_error=True,
                            )
                        if outcome is None:
                            outcome = tool_executor.execute_result(tool_name, arguments)

                        if outcome.is_error:
                            failures.append(outcome.content)
                        if tool_name in ("create_file", "create_directory"):
                            path = arguments.get("path") if isinstance(arguments, dict) else None
                            try:
                                target = os.path.normcase(tool_executor._validate_path(path))
                            except (ValueError, TypeError):
                                target = None
                            key = (tool_name, target)
                            if outcome.is_error:
                                pending_writes[key] = outcome.content
                                previous_unknowns.discard(key)
                            else:
                                pending_writes.pop(key, None)
                                unknown_key = (tool_name, None)
                                if unknown_key in previous_unknowns:
                                    pending_writes.pop(unknown_key, None)

                        result = outcome.content
                        if len(result) > MAX_TOOL_RESULT_CHARS:
                            result = result[:MAX_TOOL_RESULT_CHARS] + "\n...[truncated]"
                        
                        if on_tool:
                            on_tool(tool_name, result)
                            
                        # Append tool result
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.get("id"),
                            "name": tool_name,
                            "content": result
                        })
                    # Reply to every tool call before asking for a correction so the
                    # API conversation remains valid even when several calls fail.
                    if failures:
                        if not _request_tool_repair("\n".join(failures)):
                            return False
                    else:
                        tool_repair_turns = 0
                    # Loop continues to send tool results back to LLM
                    continue

                if response_truncated:
                    idle_turns = 0
                    if not _request_tool_repair(
                        "The model response reached its output limit (finish_reason=length); "
                        "generation is not complete."
                    ):
                        return False
                    continue
                
                # No tool calls: either a final message or a stalled turn.
                idle_turns += 1
                
                if content:
                    if on_message:
                        on_message(content)
                        
                    if DONE_PATTERN.search(content):
                        problems = validate_desktop_output(output_dir, tool_executor.created_files)
                        problems.extend("Unresolved write: " + error
                                        for error in pending_writes.values())
                        if problems:
                            completion_failures += 1
                            details = "Desktop output is incomplete:\n" + "\n".join(problems)
                            if completion_failures >= 3:
                                if on_error:
                                    on_error(details)
                                return False
                            if on_message:
                                on_message(details + "\nRequesting corrections from the model.")
                            messages.append({
                                "role": "user",
                                "content": details + "\nUse create_file to fix these issues before saying DONE.",
                            })
                            idle_turns = 0
                            continue
                        if on_message:
                            on_message("Agent has completed project generation.")
                            on_message("Desktop source checks passed. Run build.bat in the generated project to create the game .exe; build and gameplay have not been tested by the agent.")
                        return True
                
                if idle_turns >= ABORT_AFTER_IDLE_TURNS:
                    msg = (f"Aborting: model produced no tool calls for "
                           f"{idle_turns} consecutive turns without saying DONE.")
                    logger.error(msg)
                    if on_error:
                        on_error(msg)
                    return False
                
                if idle_turns >= NUDGE_AFTER_IDLE_TURNS:
                    messages.append({
                        "role": "user",
                        "content": ("Continue: create the remaining files with "
                                    "create_file/create_directory, or reply with "
                                    "the single word DONE if everything is complete.")
                    })
                
            except Exception as e:
                error_msg = f"Error in agent loop: {str(e)}"
                logger.error(error_msg)
                if on_error:
                    on_error(error_msg)
                
                # Try to continue if not a fatal error
                messages.append({
                    "role": "user",
                    "content": f"An error occurred: {str(e)}. Please try to recover or explain what went wrong."
                })
                time.sleep(2)  # Backoff
                
        msg = f"Reached maximum conversation turns ({MAX_TURNS})."
        logger.error(msg)
        if on_error:
            on_error(msg)
        return False
