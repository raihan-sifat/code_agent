"""Static output checks; generated code is never executed by the agent."""

import ast
from pathlib import Path
from typing import Iterable, List

REQUIRED_FILES = (
    "main.py", "game.py", "storage.py", "requirements.txt",
    "requirements-build.txt", "run.bat", "build.bat", "README.md",
    "tests/test_game.py", "tests/test_storage.py",
)


def validate_desktop_output(output_dir: str, created_files: Iterable[str]) -> List[str]:
    """Reject missing/invalid desktop artifacts, including stale output from earlier runs.

    These are structural checks, not proof that the game or its build works.
    """
    base = Path(output_dir).resolve()
    written = set()
    for name in created_files:
        path = (base / name).resolve()
        if path.is_relative_to(base):
            written.add(path)
    roots = sorted({p.parent for p in written if p.name == "main.py"}, key=str)
    if not roots:
        return ["Create main.py and the required native desktop project files in this run."]
    best_errors = None
    for root in roots:
        errors = []
        for name in REQUIRED_FILES:
            path = root / name
            if path not in written or not path.is_file():
                errors.append(f"Missing file from this run: {path.relative_to(base).as_posix()}")
            elif not path.read_text(encoding="utf-8-sig").strip():
                errors.append(f"File must not be empty: {name}")
        has_tk = False
        for path in sorted(written):
            if path.suffix == ".py" and path.is_relative_to(root) and path.is_file():
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
                    has_tk |= any(
                        (isinstance(n, ast.Import) and any(
                            a.name in ("tkinter", "customtkinter") for a in n.names))
                        or (isinstance(n, ast.ImportFrom) and
                            (n.module or "").split(".")[0] in ("tkinter", "customtkinter"))
                        for n in ast.walk(tree)
                    )
                except (SyntaxError, UnicodeError) as exc:
                    errors.append(f"Invalid Python in {path.relative_to(root)}: {exc}")
        if not has_tk:
            errors.append("Implement the native window with tkinter; browser-only output is incomplete.")
        build = root / "build.bat"
        if build in written and build.is_file():
            content = build.read_text(encoding="utf-8-sig").lower()
            if not all(token in content for token in ("pyinstaller", "--onefile", "--windowed")):
                errors.append("build.bat must package the game with PyInstaller --onefile --windowed.")
        if not errors:
            return []
        if best_errors is None or len(errors) < len(best_errors):
            best_errors = errors
    return best_errors
