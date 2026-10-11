import json
import re
import threading
import time
from typing import Callable, Optional, Dict, Any
import logging

from api.deepseek_client import DeepSeekClient
from .tools import TOOL_DEFINITIONS, ToolExecutor
from .prompts import SYSTEM_PROMPT, build_generation_prompt

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
                    for tool_call in tool_calls:
                        if _cancelled():
                            msg = "Generation cancelled by user."
                            logger.info(msg)
                            if on_message:
                                on_message(msg)
                            return False
                        func = tool_call.get("function", {})
                        tool_name = func.get("name")
                        try:
                            arguments = json.loads(func.get("arguments", "{}"))
                        except json.JSONDecodeError:
                            arguments = {}
                            
                        # Execute tool
                        result = tool_executor.execute(tool_name, arguments)
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
                    # Loop continues to send tool results back to LLM
                    continue
                
                # No tool calls: either a final message or a stalled turn.
                idle_turns += 1
                
                if content:
                    if on_message:
                        on_message(content)
                        
                    if DONE_PATTERN.search(content):
                        if on_message:
                            on_message("Agent has completed project generation.")
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
