"""System-tray icon (Windows/macOS/most Linux desktops) with Settings, Pause and Quit. Optional: if pystray is
missing or unsupported the app simply runs without it."""
import os

from PIL import Image, ImageDraw

from . import process
from .paths import data_dir, log_error


def make_icon(paused: bool = False, size: int = 64) -> Image.Image:
    from .brand import make_logo
    return make_logo(size, paused)


class Tray:
    def __init__(self, app):
        import pystray
        self.app, self.pystray = app, pystray
        M, I = pystray.Menu, pystray.MenuItem
        self.icon = pystray.Icon("Holler", make_icon(), "Holler", M(
            I(lambda _: "Dictation paused" if app.paused else f"Hold {app.cfg.key} to dictate", None, enabled=False),
            M.SEPARATOR,
            I("Settings...", lambda: process.spawn("settings"), default=True),
            I("Pause dictation", self._toggle, checked=lambda _: app.paused),
            I(lambda _: f"Update to Holler {app.update['version']}..." if getattr(app, "update", None) else "",
              self._update, visible=lambda _: bool(getattr(app, "update", None))),
            I("Run setup wizard", lambda: process.spawn("setup")),
            I("Open data folder", self._open_folder),
            M.SEPARATOR,
            I("Quit", self._quit),
        ))

    def _update(self):
        from . import updates
        rel = self.app.update
        if not updates.can_self_install(rel):
            self.notify(f"Holler {rel['version']} is out. Update with: {updates.pip_hint()}")
        import threading
        threading.Thread(target=updates.install, args=(rel,), daemon=True).start()

    def notify(self, text):
        try:
            self.icon.notify(text, "Holler")
        except Exception:
            pass

    def update_found(self, rel):
        self.app.update = rel
        try:
            self.icon.update_menu()
        except Exception:
            pass
        self.notify(f"Holler {rel['version']} is available. Right-click the tray icon to update.")

    def _toggle(self):
        self.app.paused = not self.app.paused
        self.icon.icon = make_icon(self.app.paused)

    def _open_folder(self):
        try:
            if os.name == "nt":
                os.startfile(data_dir())          # noqa
            else:
                process.spawn("where")
        except Exception:
            log_error("open folder")

    def _quit(self):
        self.icon.stop()
        os._exit(0)

    def start(self):
        self.icon.run_detached()


def start_tray(app):
    try:
        t = Tray(app)
        t.start()
        return t
    except Exception:
        log_error("tray icon unavailable")
        return None
