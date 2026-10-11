import sys
import os
import traceback


def _log_startup_error() -> str:
    """Write a crash log next to the executable.

    Windowed (``--windowed``) builds have no console, so any import/startup
    error would otherwise be silent. This guarantees a diagnosable log file.
    """
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    log_path = os.path.join(base, "CodeAgent.log")
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("CodeAgent failed to start:\n")
            f.write(traceback.format_exc())
            f.write("\n" + "-" * 60 + "\n")
    except Exception:
        pass
    return log_path


def main():
    # Add project root to path for imports
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    from gui import CodeAgentApp

    app = CodeAgentApp()
    app.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        path = _log_startup_error()
        try:
            from tkinter import messagebox
            messagebox.showerror(
                "CodeAgent failed to start",
                f"{exc}\n\nDetails written to:\n{path}",
            )
        except Exception:
            pass
        sys.exit(1)
