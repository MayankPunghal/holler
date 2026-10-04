"""System-tray icon (Windows/macOS/most Linux desktops) with Settings, Pause and Quit. Optional: if pystray is
missing or unsupported the app simply runs without it."""
import os

from PIL import Image, ImageDraw

from . import process
from .paths import data_dir, log_error


def make_icon(paused: bool = False, size: int = 64) -> Image.Image:
    s = 4
    img = Image.new("RGBA", (size * s, size * s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, size * s - 1, size * s - 1], radius=size * s // 4, fill=(24, 24, 27, 255))
    col = (142, 142, 147, 255) if paused else (255, 69, 58, 255)
    cx = size * s // 2
    for i, h in enumerate((0.22, 0.42, 0.62, 0.42, 0.22)):          # five waveform bars
        x = cx + (i - 2) * size * s // 7
        half = int(size * s * h / 2)
        d.rounded_rectangle([x - size * s // 22, size * s // 2 - half, x + size * s // 22, size * s // 2 + half],
                            radius=size * s // 22, fill=col)
    return img.resize((size, size), Image.LANCZOS)


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
            I("Run setup wizard", lambda: process.spawn("setup")),
            I("Open data folder", self._open_folder),
            M.SEPARATOR,
            I("Quit", self._quit),
        ))

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
