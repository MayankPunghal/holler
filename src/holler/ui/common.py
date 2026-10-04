"""Shared bits for the setup wizard and the settings window (Tk/ttk, Sun Valley theme when available)."""
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
    style = ttk.Style(root)
    family = "Segoe UI" if sys.platform == "win32" else ("Helvetica Neue" if sys.platform == "darwin" else "DejaVu Sans")
    base = (family, 10)
    themed = False
    try:
        import sv_ttk                       # Windows 11 look (Sun Valley theme, MIT licence)
        sv_ttk.set_theme("light")
        themed = True
    except Exception:
        try:
            style.theme_use("vista" if sys.platform == "win32" else "clam")
        except tk.TclError:
            pass
    bg = (style.lookup("TFrame", "background") or BG) if themed else BG
    card = bg if themed else "#ffffff"           # the Sun Valley card is the page colour with a border
    side = "#eef0f4"
    root.configure(bg=bg)
    if not themed:
        style.configure(".", font=base, background=bg)
        for w in ("TFrame", "TLabel", "TCheckbutton", "TRadiobutton", "TLabelframe"):
            style.configure(w, background=bg)
        style.configure("Accent.TButton", font=base + ("bold",))
        style.configure("Switch.TCheckbutton", background=card)
        style.configure("Card.TFrame", background=card, relief="solid", borderwidth=1)
    style.configure("TLabelframe.Label", background=bg, font=base + ("bold",))
    style.configure("Title.TLabel", font=(family, 20, "bold"), background=bg)
    style.configure("Brand.TLabel", font=(family, 15, "bold"), background=side, foreground="#111111")
    style.configure("Sub.TLabel", foreground="#5f6368", background=bg)
    style.configure("CardTitle.TLabel", font=(family, 10, "bold"), foreground="#3c4043", background=bg)
    style.configure("Card.TLabel", font=(family, 10), **({} if themed else {"background": card}))
    style.configure("CardSub.TLabel", foreground="#6b6f76", font=(family, 9), **({} if themed else {"background": card}))
    style.configure("CardBody.TFrame", borderwidth=0, relief="flat", **({} if themed else {"background": card}))
    style.configure("Side.TFrame", background=side)
    style.configure("Bar.TFrame", background=bg)
    style.configure("Good.TLabel", foreground="#15803d", background=bg)
    style.configure("Bad.TLabel", foreground="#b91c1c", background=bg)
    style.configure("Nav.Toolbutton", anchor="w", padding=(14, 8), font=(family, 10), background=side)
    style.map("Nav.Toolbutton", background=[("selected", "#dde3ee"), ("active", "#e5e7ec")],
              foreground=[("selected", "#0b57d0")])
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
