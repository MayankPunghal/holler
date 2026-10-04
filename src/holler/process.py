"""Running in the background: single instance, start/stop, and start-with-the-computer."""
import os
import signal
import subprocess
import sys
import time

from .paths import data_dir

APP_NAME = "Holler"


def _pidfile():
    return os.path.join(data_dir(), "holler.pid")


def _alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, pid)           # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return code.value == 259                        # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def running_pid():
    """PID of the running Holler, or None."""
    try:
        with open(_pidfile()) as f:
            pid = int(f.read().strip())
    except (OSError, ValueError):
        return None
    return pid if pid != os.getpid() and _alive(pid) else None


def claim() -> bool:
    """Register this process as THE running instance. False if another one is already running."""
    if running_pid():
        return False
    with open(_pidfile(), "w") as f:
        f.write(str(os.getpid()))
    import atexit
    atexit.register(release)
    return True


def release():
    try:
        with open(_pidfile()) as f:
            if int(f.read().strip()) == os.getpid():
                os.remove(_pidfile())
    except (OSError, ValueError):
        pass


def stop(timeout: float = 4.0) -> bool:
    """Stop the running instance. True if one was running."""
    pid = running_pid()
    if not pid:
        return False
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True,
                       creationflags=0x08000000)
    else:
        os.kill(pid, signal.SIGTERM)
    t0 = time.time()
    while time.time() - t0 < timeout and _alive(pid):
        time.sleep(0.1)
    try:
        os.remove(_pidfile())
    except OSError:
        pass
    return True


def _windowless_python() -> str:
    exe = sys.executable
    if sys.platform == "win32":
        w = os.path.join(os.path.dirname(exe), "pythonw.exe")
        if os.path.exists(w):
            return w
    return exe


def spawn(*args: str) -> subprocess.Popen:
    """Start `python -m holler <args>` detached from this process, without a console window."""
    cmd = [_windowless_python(), "-m", "holler", *args]
    kw = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if sys.platform == "win32":
        kw["creationflags"] = 0x00000008 | 0x08000000 | 0x00000200     # DETACHED | NO_WINDOW | NEW_GROUP
    else:
        kw["start_new_session"] = True
    return subprocess.Popen(cmd, **kw)


def start_background() -> bool:
    if running_pid():
        return False
    spawn("run")
    return True


def restart_background():
    stop()
    spawn("run")


# ------------------------------------------------------------------ start with the computer

def _autostart_command() -> str:
    return f'"{_windowless_python()}" -m holler run'


def autostart_enabled() -> bool:
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
                winreg.QueryValueEx(k, APP_NAME)
                return True
        except OSError:
            return False
    return os.path.exists(_desktop_file())


def set_autostart(on: bool) -> bool:
    try:
        if sys.platform == "win32":
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run", 0,
                                winreg.KEY_SET_VALUE) as k:
                if on:
                    winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, _autostart_command())
                else:
                    try:
                        winreg.DeleteValue(k, APP_NAME)
                    except OSError:
                        pass
            return True
        if sys.platform.startswith("linux"):
            p = _desktop_file()
            if on:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w") as f:
                    f.write(f"[Desktop Entry]\nType=Application\nName={APP_NAME}\nExec={_autostart_command()}\n")
            elif os.path.exists(p):
                os.remove(p)
            return True
    except OSError:
        pass
    return False


def _desktop_file():
    return os.path.join(os.path.expanduser("~/.config/autostart"), "holler.desktop")


def create_start_menu_shortcut() -> bool:
    """Windows: a Start-menu entry "Holler" that opens its settings (or starts it). Returns True on success."""
    if sys.platform != "win32":
        return False
    folder = os.path.join(os.environ.get("APPDATA", ""), "Microsoft", "Windows", "Start Menu", "Programs")
    link = os.path.join(folder, f"{APP_NAME}.lnk")
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut('%s');"
          "$s.TargetPath='%s';$s.Arguments='-m holler';$s.Description='Holler dictation';$s.Save()"
          % (link.replace("'", "''"), _windowless_python().replace("'", "''")))
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, creationflags=0x08000000)
        return r.returncode == 0
    except OSError:
        return False
