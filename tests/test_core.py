"""Tests for the CodeAgent agent loop (no real API calls)."""

import json
import threading
import pytest
from types import SimpleNamespace

from agent import core
from agent.core import CodeAgent


TOOL_CALL = {
    "id": "call_1",
    "type": "function",
    "function": {"name": "create_directory", "arguments": json.dumps({"path": "src"})},
}


class FakeClient:
    """Scripted stand-in for DeepSeekClient.chat()."""

    def __init__(self, script):
        self.script = list(script)
        self.received = []

    def chat(self, messages, tools=None, temperature=None):
        # Record a deep-ish copy of the message roles/contents for assertions.
        snapshot = []
        for m in messages:
            entry = {"role": m["role"], "content": m.get("content", "")}
            if "tool_calls" in m:
                entry["tool_calls"] = m["tool_calls"]
            snapshot.append(entry)
        self.received.append(snapshot)

        # Regression guard: a null tool_calls key must never be sent to the API.
        for m in messages:
            assert "tool_calls" not in m or m["tool_calls"], (
                f"null tool_calls leaked into messages: {m}"
            )

        if not self.script:
            return {"content": ""}
        return self.script.pop(0)


def make_agent(script, monkeypatch, tmp_path):
    agent = CodeAgent.__new__(CodeAgent)
    client = FakeClient(script)
    agent.client = client
    agent.model = "fake"
    return agent, client


def run(agent, tmp_path, **callbacks):
    return agent.generate_project({}, str(tmp_path), **callbacks)


@pytest.fixture
def fast(monkeypatch):
    """Speed up: no backoff sleeps, small turn/idle budgets."""
    monkeypatch.setattr(core.time, "sleep", lambda s: None)
    monkeypatch.setattr(core, "MAX_TURNS", 8)
    monkeypatch.setattr(core, "NUDGE_AFTER_IDLE_TURNS", 2)
    monkeypatch.setattr(core, "ABORT_AFTER_IDLE_TURNS", 3)


class TestAgentLoop:
    def test_tools_then_done_succeeds(self, fast, monkeypatch, tmp_path):
        agent, client = make_agent(
            [
                {"content": "Planning.", "tool_calls": [TOOL_CALL]},
                {"content": "Writing files.", "tool_calls": [TOOL_CALL]},
                {"content": "All files written. DONE"},
            ],
            monkeypatch,
            tmp_path,
        )
        messages, errors = [], []
        ok = run(agent, tmp_path, on_message=messages.append, on_error=errors.append)
        assert ok is True
        assert errors == []
        assert "Agent has completed project generation." in messages
        # Tool executor actually created the requested directory.
        assert (tmp_path / "src").is_dir()

    def test_idle_turns_nudge_then_abort(self, fast, monkeypatch, tmp_path):
        agent, client = make_agent(
            [{"content": "Let me think about the structure."}] * 10,
            monkeypatch,
            tmp_path,
        )
        errors = []
        ok = run(agent, tmp_path, on_error=errors.append)
        assert ok is False
        assert errors and "no tool calls" in errors[-1]

        # The nudge must have been injected after NUDGE_AFTER_IDLE_TURNS.
        last_snapshot = client.received[-1]
        nudges = [m for m in last_snapshot
                  if m["role"] == "user" and "Continue: create the remaining files" in m["content"]]
        assert nudges, "expected a nudge message in the conversation"

    def test_complete_word_alone_does_not_finish(self, fast, monkeypatch, tmp_path):
        """The old bug: 'complete' anywhere in prose ended the run early."""
        agent, client = make_agent(
            [{"content": "The project is now complete."}] * 10,
            monkeypatch,
            tmp_path,
        )
        ok = run(agent, tmp_path)
        assert ok is False

    def test_done_token_is_word_bounded(self, fast, monkeypatch, tmp_path):
        """'undone' must not match; standalone DONE must."""
        agent, _ = make_agent([{"content": "undone"}] * 10, monkeypatch, tmp_path)
        assert run(agent, tmp_path) is False

        agent, _ = make_agent([{"content": "undone"}] * 2 + [{"content": "DONE"}],
                              monkeypatch, tmp_path)
        assert run(agent, tmp_path) is True

    def test_max_turns_returns_false(self, fast, monkeypatch, tmp_path):
        monkeypatch.setattr(core, "MAX_TURNS", 3)
        agent, _ = make_agent(
            [{"content": "", "tool_calls": [TOOL_CALL]}] * 10,
            monkeypatch,
            tmp_path,
        )
        errors = []
        ok = run(agent, tmp_path, on_error=errors.append)
        assert ok is False
        assert any("maximum conversation turns" in e for e in errors)

    def test_exception_recovery(self, fast, monkeypatch, tmp_path):
        class FlakyClient(FakeClient):
            calls = 0

            def chat(self, messages, tools=None, temperature=None):
                FlakyClient.calls += 1
                if FlakyClient.calls == 1:
                    raise RuntimeError("transient network error")
                return {"content": "recovered. DONE"}

        agent = CodeAgent.__new__(CodeAgent)
        agent.client = FlakyClient([])
        agent.model = "fake"
        errors = []
        ok = run(agent, tmp_path, on_error=errors.append)
        assert ok is True
        assert errors and "transient network error" in errors[0]

    def test_large_tool_results_truncated(self, fast, monkeypatch, tmp_path):
        monkeypatch.setattr(core, "MAX_TOOL_RESULT_CHARS", 50)
        big_file = tmp_path / "big.txt"
        big_file.write_text("y" * 500)

        class ReadThenDone(FakeClient):
            def chat(self, messages, tools=None, temperature=None):
                tool_msgs = [m for m in messages if m["role"] == "tool"]
                if tool_msgs:
                    assert "truncated" in tool_msgs[-1]["content"]
                    return {"content": "DONE"}
                return {
                    "content": "",
                    "tool_calls": [{
                        "id": "call_r",
                        "type": "function",
                        "function": {"name": "read_file",
                                     "arguments": json.dumps({"path": "big.txt"})},
                    }],
                }

        agent = CodeAgent.__new__(CodeAgent)
        agent.client = ReadThenDone([])
        agent.model = "fake"
        assert run(agent, tmp_path) is True

    def test_malformed_tool_arguments_do_not_crash(self, fast, monkeypatch, tmp_path):
        bad_call = {
            "id": "call_bad",
            "type": "function",
            "function": {"name": "create_file", "arguments": "{not valid json"},
        }
        agent, _ = make_agent(
            [
                {"content": "", "tool_calls": [bad_call]},
                {"content": "DONE"},
            ],
            monkeypatch,
            tmp_path,
        )
        tools_seen = []
        ok = run(agent, tmp_path, on_tool=lambda name, res: tools_seen.append(name))
        assert ok is True
        assert tools_seen == ["create_file"]


class TestPauseCancel:
    def test_cancel_before_start_returns_false(self, fast, monkeypatch, tmp_path):
        cancel = threading.Event()
        cancel.set()
        agent, _ = make_agent([{"content": "DONE"}], monkeypatch, tmp_path)
        messages = []
        ok = agent.generate_project(
            {}, str(tmp_path), cancel_event=cancel, on_message=messages.append
        )
        assert ok is False
        assert any("cancel" in m.lower() for m in messages)

    def test_cancel_mid_run_stops_loop(self, fast, monkeypatch, tmp_path):
        cancel = threading.Event()

        class CancelAfterFirst(FakeClient):
            def chat(self, messages, tools=None, temperature=None):
                cancel.set()  # user hits Cancel while this turn is in flight
                return {"content": "", "tool_calls": [TOOL_CALL]}

        agent = CodeAgent.__new__(CodeAgent)
        agent.client = CancelAfterFirst([])
        agent.model = "fake"
        messages = []
        ok = agent.generate_project(
            {}, str(tmp_path), cancel_event=cancel, on_message=messages.append
        )
        assert ok is False
        assert any("cancel" in m.lower() for m in messages)

    def test_pause_then_resume_completes(self, fast, monkeypatch, tmp_path):
        pause = threading.Event()
        pause.set()
        agent, _ = make_agent([{"content": "All done. DONE"}], monkeypatch, tmp_path)
        messages = []

        def on_message(msg):
            messages.append(msg)
            if "Paused" in msg:
                pause.clear()  # simulate the user clicking Resume

        ok = agent.generate_project(
            {}, str(tmp_path), pause_event=pause, on_message=on_message
        )

        assert ok is True
        assert any("Paused" in m for m in messages)
        assert any("Resumed" in m for m in messages)

    def test_cancel_while_paused_exits(self, fast, monkeypatch, tmp_path):
        pause = threading.Event()
        cancel = threading.Event()
        pause.set()
        agent, _ = make_agent([{"content": "DONE"}], monkeypatch, tmp_path)
        messages = []

        def on_message(msg):
            messages.append(msg)
            if "Paused" in msg:
                cancel.set()  # simulate the user clicking Cancel while paused

        ok = agent.generate_project(
            {}, str(tmp_path), cancel_event=cancel, pause_event=pause,
            on_message=on_message,
        )
        assert ok is False
        assert any("cancel" in m.lower() for m in messages)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
