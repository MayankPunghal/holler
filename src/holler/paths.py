"""Where Holler keeps your files, and the shared error log."""
import os
import sys
import time
import traceback

PACKAGE_DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def data_dir() -> str:
    """Your settings, vocabulary, logs and models. Override with the HOLLER_HOME environment variable.
    Windows: %APPDATA%\\Holler    Linux/macOS: ~/.config/holler"""
    d = os.environ.get("HOLLER_HOME")
    if not d:
        if sys.platform == "win32":
            d = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "Holler")
        else:
            d = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"), "holler")
    os.makedirs(d, exist_ok=True)
    return d


def log_error(where: str) -> None:
    try:
        with open(os.path.join(data_dir(), "errors.log"), "a", encoding="utf-8") as f:
            f.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} {where}\n{traceback.format_exc()}\n")
    except OSError:
        pass
