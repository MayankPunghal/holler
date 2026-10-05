"""Entry point of the Windows app build (Holler.exe without a console, holler-cli.exe with one)."""
import multiprocessing
import os
import sys


def _fix_stdio():
    # A windowed exe has no console: sys.stdout/stderr are None and any library that writes to them would crash.
    # Under the supervisor, output belongs in holler.log; otherwise it is discarded.
    if sys.stdout is not None and sys.stderr is not None:
        return
    sink = None
    if os.environ.get("HOLLER_SUPERVISED"):
        try:
            from holler.paths import data_dir
            sink = open(os.path.join(data_dir(), "holler.log"), "a", encoding="utf-8", errors="replace", buffering=1)
        except OSError:
            sink = None
    sink = sink or open(os.devnull, "w", encoding="utf-8")
    if sys.stdout is None:
        sys.stdout = sink
    if sys.stderr is None:
        sys.stderr = sink


if __name__ == "__main__":
    multiprocessing.freeze_support()
    _fix_stdio()
    from holler.cli import main
    sys.exit(main())
