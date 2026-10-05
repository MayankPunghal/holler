"""Update check and the installed-app (frozen) command lines. Run: python tests/test_updates.py"""
import json
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
os.environ["HOLLER_HOME"] = tempfile.mkdtemp()

from holler import process, updates  # noqa: E402


def check(name, cond):
    print(("PASS" if cond else "FAIL"), "|", name)
    if not cond:
        raise SystemExit(1)


check("newer minor", updates.newer("1.2.0", "1.1.0"))
check("same is not newer", not updates.newer("1.1.0", "1.1.0"))
check("pre-release is older than the release", not updates.newer("1.2.0b1", "1.2.0"))
check("numeric, not text, comparison", updates.newer("1.10.0", "1.9.3"))

# cached answer is used within a day, and only a newer version is reported
calls = []
updates.latest = lambda timeout=8.0: calls.append(1) or {"version": "99.0.0", "page": "p", "installer": None}
check("finds a newer release", updates.check(force=True)["version"] == "99.0.0")
check("second check today uses the cache", updates.check() and len(calls) == 1)
json.dump({"checked": time.time() - 2 * updates.DAY, "release": None}, open(updates._state_path(), "w"))
updates.check()
check("asks again after a day", len(calls) == 2)
updates.latest = lambda timeout=8.0: {"version": "0.1.0", "page": "p", "installer": None}
check("an older release is not an update", updates.check(force=True) is None)

# pip install: python -m holler; installed app: the exes next to Holler.exe
check("pip command", process.holler_cmd("run", console=True)[1:] == ["-m", "holler", "run"])
sys.frozen = True
try:
    gui, cli = process.holler_cmd("supervise"), process.holler_cmd("stop", console=True)
    check("app command", os.path.basename(gui[0]) == "Holler.exe" and gui[1:] == ["supervise"])
    check("app console command", os.path.basename(cli[0]) == "holler-cli.exe")
    check("autostart runs the app", "Holler.exe" in process._autostart_command() and
          process._autostart_command().endswith("supervise"))
    check("pip-only update hint off in the app", updates.can_self_install({"installer": "x"}) == (os.name == "nt"))
finally:
    del sys.frozen
check("pip install updates via pip", not updates.can_self_install({"installer": "x"}))
print("ALL OK")
