"""Shared bits for the setup wizard and the settings window (Tk/ttk, no extra dependencies)."""
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk

from .. import models
from ..keys import spec_from_keys

PAD = 14
BG = "#f6f6f8"
ACCENT = "#2563eb"


def make_root(title: str, size: str, resizable=False) -> tk.Tk:
    root = tk.Tk()
    root.title(title)
    root.geometry(size)
    root.resizable(resizable, resizable)
    root.configure(bg=BG)
    style = ttk.Style(root)
    try:
        style.theme_use("vista" if sys.platform == "win32" else "clam")
    except tk.TclError:
        pass
    base = ("Segoe UI", 10) if sys.platform == "win32" else ("TkDefaultFont", 10)
    style.configure(".", font=base, background=BG)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG)
    style.configure("TCheckbutton", background=BG)
    style.configure("TRadiobutton", background=BG)
    style.configure("TLabelframe", background=BG)
    style.configure("TLabelframe.Label", background=BG, font=base[:1] + (base[1], "bold"))
    style.configure("Title.TLabel", font=(base[0], 17, "bold"), background=BG)
    style.configure("Sub.TLabel", foreground="#555", background=BG)
    style.configure("Good.TLabel", foreground="#15803d", background=BG)
    style.configure("Bad.TLabel", foreground="#b91c1c", background=BG)
    style.configure("Accent.TButton", font=base[:1] + (base[1], "bold"))
    try:
        from PIL import ImageTk
        from ..tray import make_icon
        root._icon = ImageTk.PhotoImage(make_icon(size=64))
        root.iconphoto(True, root._icon)
    except Exception:
        pass
    return root


def center(root: tk.Tk):
    root.update_idletasks()
    w, h = root.winfo_width(), root.winfo_height()
    root.geometry(f"+{(root.winfo_screenwidth() - w) // 2}+{max(20, (root.winfo_screenheight() - h) // 3)}")


def wrap_label(parent, text, style="TLabel", width=520, **kw):
    return ttk.Label(parent, text=text, style=style, wraplength=width, justify="left", **kw)


class HotkeyCapture(ttk.Frame):
    """Shows a key/chord and a 'Change' button: press and hold the keys you want, then let go."""

    def __init__(self, parent, initial: str, on_change=None):
        super().__init__(parent)
        self.var = tk.StringVar(value=initial)
        self.on_change = on_change
        self.shown = ttk.Label(self, textvariable=self.var, relief="groove", anchor="center", width=22, padding=4)
        self.shown.pack(side="left")
        self.btn = ttk.Button(self, text="Change...", command=self.capture)
        self.btn.pack(side="left", padx=(8, 0))
        self._listener = None

    def get(self) -> str:
        return self.var.get()

    def capture(self):
        from pynput import keyboard
        if self._listener:
            return
        self.prev = self.var.get()
        self.var.set("press and hold your keys...")
        self.btn.state(["disabled"])
        held, best, q = set(), set(), queue.Queue()

        def press(k):
            if k == keyboard.Key.esc:
                q.put(None)
                return False
            held.add(k)
            if len(held) >= len(best):
                best.clear()
                best.update(held)

        def release(k):
            held.discard(k)
            if not held and best:
                q.put(spec_from_keys(best))
                return False

        self._listener = keyboard.Listener(on_press=press, on_release=release)
        self._listener.start()

        def poll():
            try:
                res = q.get_nowait()
            except queue.Empty:
                self.after(60, poll)
                return
            self._listener = None
            self.btn.state(["!disabled"])
            self.var.set(res or self.prev)
            if res and self.on_change:
                self.on_change(res)
        poll()


class DownloadRow(ttk.Frame):
    """Progress bar + status for downloading a model in a background thread."""

    def __init__(self, parent):
        super().__init__(parent)
        self.bar = ttk.Progressbar(self, length=360, maximum=100)
        self.bar.pack(side="left")
        self.msg = ttk.Label(self, text="", style="Sub.TLabel")
        self.msg.pack(side="left", padx=10)
        self.q, self.cancel, self.thread = queue.Queue(), threading.Event(), None

    def start(self, name, on_done):
        self.cancel.clear()
        self.bar["value"] = 0
        self.msg.config(text="starting...", style="Sub.TLabel")

        def work():
            try:
                models.download(name, lambda f, t: self.q.put(("p", f, t)), self.cancel)
                self.q.put(("ok", 1, ""))
            except InterruptedError:
                self.q.put(("err", 0, "cancelled"))
            except Exception as e:
                self.q.put(("err", 0, str(e)))
        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

        def poll():
            try:
                while True:
                    kind, f, t = self.q.get_nowait()
                    if kind == "p":
                        self.bar["value"] = f * 100
                        self.msg.config(text=t)
                    elif kind == "ok":
                        self.bar["value"] = 100
                        self.msg.config(text="downloaded", style="Good.TLabel")
                        on_done(True, "")
                        return
                    else:
                        self.msg.config(text="failed: " + t[:80], style="Bad.TLabel")
                        on_done(False, t)
                        return
            except queue.Empty:
                pass
            self.after(100, poll)
        poll()


def model_choices():
    """[(name, 'small.en - 484 MB download, ~320 MB RAM - recommended ...')]"""
    out = []
    for n, (mb, ram, note) in models.MODELS.items():
        out.append((n, f"{n}   ({mb} MB download, about {ram} MB RAM)   {note}"))
    return out
