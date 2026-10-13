"""Acceptance checks and correction loops for the new desktop output contract."""

import json
import pytest

from agent import core
from agent.desktop_validation import REQUIRED_FILES, validate_desktop_output
from tests.test_core import make_agent, run


def desktop_files(prefix=""):
    contents = {name: "# Sample artifact\n" for name in REQUIRED_FILES}
    contents["main.py"] = "import tkinter as tk\nif __name__ == '__main__':\n    tk.Tk().mainloop()\n"
    contents["build.bat"] = "python -m PyInstaller --onefile --windowed --name SpaceFractions main.py\n"
    return {prefix + name: content for name, content in contents.items()}


def write_files(tmp_path, files):
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


@pytest.mark.parametrize("prefix", ["", "Space Fractions/"])
def test_valid_desktop_structure(tmp_path, prefix):
    files = desktop_files(prefix)
    write_files(tmp_path, files)
    assert validate_desktop_output(str(tmp_path), files) == []


def test_browser_only_and_stale_files_cannot_pass(tmp_path):
    write_files(tmp_path, desktop_files())
    assert validate_desktop_output(str(tmp_path), ["frontend/index.html"])
    assert validate_desktop_output(str(tmp_path), ["main.py"])


@pytest.mark.parametrize("name,content,expected", [
    ("main.py", "print('use a browser')", "native window"),
    ("game.py", "def broken(:", "Invalid Python"),
    ("build.bat", "python main.py", "PyInstaller"),
    ("storage.py", "", "empty"),
])
def test_incomplete_or_invalid_desktop_output(tmp_path, name, content, expected):
    files = desktop_files()
    files[name] = content
    write_files(tmp_path, files)
    assert any(expected in issue for issue in validate_desktop_output(str(tmp_path), files))


def test_agent_repairs_browser_only_completion(monkeypatch, tmp_path):
    files = desktop_files("SpaceFractions/")
    calls = [{"id": f"desktop_{i}", "type": "function", "function": {
        "name": "create_file", "arguments": json.dumps({"path": path, "content": content})}}
        for i, (path, content) in enumerate(files.items())]
    agent, client = make_agent([{"content": "DONE"}, {"tool_calls": calls},
                                {"content": "DONE"}], monkeypatch, tmp_path)
    assert run(agent, tmp_path)
    assert any("Desktop output is incomplete" in m["content"] for m in client.received[1])
    assert validate_desktop_output(str(tmp_path), files) == []


def test_repeated_false_completion_aborts(monkeypatch, tmp_path):
    agent, client = make_agent([{"content": "DONE"}] * 5, monkeypatch, tmp_path)
    errors = []
    assert not run(agent, tmp_path, on_error=errors.append)
    assert len(client.received) == 3
    assert "Desktop output is incomplete" in errors[-1]
