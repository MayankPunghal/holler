"""Update check: at most once a day, ask GitHub for the latest release (one small HTTPS request, nothing about you
is sent). Turn it off in Settings > General > "Check for updates".

The installed app (Holler.exe) downloads the new installer and runs it; a pip install is told the pip command."""
import json
import os
import re
import tempfile
import threading
import time
import urllib.request

from . import __version__, process
from .paths import data_dir, log_error

REPO = "MayankPunghal/holler"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases/latest"
DAY = 24 * 3600


def _parse(v: str) -> tuple:
    nums = re.findall(r"\d+", (v or "").split("+")[0])
    pre = bool(re.search(r"(a|b|rc|dev)\d*$", v or ""))
    return tuple(int(n) for n in nums[:3]) + ((0,) if pre else (1,))


def newer(candidate: str, current: str = __version__) -> bool:
    return _parse(candidate) > _parse(current)


def latest(timeout: float = 8.0):
    """{'version', 'page', 'installer'} of the newest published release, or None."""
    req = urllib.request.Request(API, headers={"Accept": "application/vnd.github+json",
                                               "User-Agent": f"holler/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    if data.get("draft") or data.get("prerelease"):
        return None
    tag = data.get("tag_name", "").lstrip("vV")
    inst = next((a["browser_download_url"] for a in data.get("assets", [])
                 if a.get("name", "").lower().endswith(".exe") and "setup" in a.get("name", "").lower()), None)
    return {"version": tag, "page": data.get("html_url") or PAGE, "installer": inst}


def _state_path():
    return os.path.join(data_dir(), "update.json")


def check(force: bool = False):
    """The newer release, or None. Without force, asks GitHub at most once a day (the answer is cached)."""
    try:
        st = json.load(open(_state_path(), encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    if not force and time.time() - st.get("checked", 0) < DAY:
        rel = st.get("release")
    else:
        rel = latest()
        try:
            json.dump({"checked": time.time(), "release": rel}, open(_state_path(), "w", encoding="utf-8"))
        except OSError:
            pass
    return rel if rel and rel.get("version") and newer(rel["version"]) else None


def check_in_background(on_found):
    def work():
        try:
            rel = check()
            if rel:
                on_found(rel)
        except Exception:
            pass                                    # offline, rate-limited... try again tomorrow
    threading.Thread(target=work, daemon=True).start()


def can_self_install(rel) -> bool:
    return process.frozen() and os.name == "nt" and bool(rel and rel.get("installer"))


def install(rel, progress=None) -> bool:
    """Installed app: download the new installer and start it (it closes Holler, updates, and starts it again).
    Otherwise open the release page. Returns True if the installer was started."""
    if not can_self_install(rel):
        import webbrowser
        webbrowser.open(rel.get("page") or PAGE)
        return False
    try:
        out = os.path.join(tempfile.gettempdir(), f"Holler-Setup-{rel['version']}.exe")
        req = urllib.request.Request(rel["installer"], headers={"User-Agent": f"holler/{__version__}"})
        with urllib.request.urlopen(req, timeout=30) as r, open(out + ".part", "wb") as f:
            total, done = int(r.headers.get("Content-Length") or 0), 0
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if progress and total:
                    progress(done / total)
        os.replace(out + ".part", out)
        os.startfile(out)                           # noqa: the normal installer window, the user clicks through
        return True
    except Exception:
        log_error("update download")
        import webbrowser
        webbrowser.open(rel.get("page") or PAGE)
        return False


def pip_hint() -> str:
    return "py -m pip install --upgrade holler" if os.name == "nt" else "pip install --upgrade holler"
