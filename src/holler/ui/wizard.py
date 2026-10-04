"""First-run setup wizard: prerequisites -> microphone -> hotkey -> model -> your words -> done."""
import importlib
import time
import tkinter as tk
from tkinter import ttk

from .. import config, models, process
from ..keys import Combo, key_id
from ..paths import PACKAGE_DATA
from ..vocab import Vocab
from .common import PAD, DownloadRow, HotkeyCapture, center, make_root, model_choices, wrap_label

REQUIRED = [("faster_whisper", "speech recognition engine"), ("sounddevice", "microphone access"),
            ("pynput", "hotkeys and pasting"), ("pyperclip", "clipboard"), ("numpy", "audio processing"),
            ("PIL", "status pill")]


class Page(ttk.Frame):
    title, subtitle = "", ""

    def __init__(self, wiz):
        super().__init__(wiz.body)
        self.w = wiz

    def on_show(self):
        pass

    def on_hide(self):
        pass

    def can_next(self) -> bool:
        return True


class Welcome(Page):
    title, subtitle = "Welcome to Holler", "Hold a key, speak, release: your words appear wherever your cursor is."

    def build(self):
        wrap_label(self, "Everything runs on this computer: no account, no cloud, no subscription. "
                         "This wizard checks that everything needed is installed, then sets up your microphone, "
                         "hotkey and speech model. It takes about two minutes.").pack(anchor="w", pady=(0, PAD))
        box = ttk.LabelFrame(self, text="Prerequisites", padding=PAD)
        box.pack(fill="x")
        self.ok = True
        for mod, why in REQUIRED:
            try:
                importlib.import_module(mod)
                ttk.Label(box, text=f"✓  {why}", style="Good.TLabel").pack(anchor="w")
            except Exception:
                self.ok = False
                ttk.Label(box, text=f"✗  {why} ({mod}) is missing", style="Bad.TLabel").pack(anchor="w")
        if not self.ok:
            wrap_label(self, "Fix: close this window and run   pip install --upgrade holler", "Bad.TLabel"
                       ).pack(anchor="w", pady=PAD)

    def can_next(self):
        return self.ok


class Microphone(Page):
    title, subtitle = "Microphone", "Pick your microphone and say something: the bar should move."

    def build(self):
        from ..audio import list_input_devices
        self.devs = ["System default"] + list_input_devices()
        cur = self.w.cfg["device"] if self.w.cfg["device"] in self.devs else "System default"
        self.var = tk.StringVar(value=cur)
        cb = ttk.Combobox(self, textvariable=self.var, values=self.devs, state="readonly", width=58)
        cb.pack(anchor="w")
        cb.bind("<<ComboboxSelected>>", lambda e: self._restart())
        self.canvas = tk.Canvas(self, width=420, height=26, bg="#e5e7eb", highlightthickness=0)
        self.canvas.pack(anchor="w", pady=PAD)
        self.bar = self.canvas.create_rectangle(0, 0, 0, 26, fill="#22c55e", width=0)
        self.msg = ttk.Label(self, text="", style="Sub.TLabel")
        self.msg.pack(anchor="w")
        self.level, self.stream, self.heard = 0.0, None, False

    def _restart(self):
        self._stop()
        self._start()

    def _start(self):
        import sounddevice as sd
        from ..audio import _resolve_device
        dev = None if self.var.get() == "System default" else _resolve_device(self.var.get())
        try:
            import numpy as np

            def cb(indata, frames, t, status):
                self.level = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
            self.stream = sd.InputStream(channels=1, samplerate=16000, device=dev, callback=cb, blocksize=1024)
            self.stream.start()
            self.msg.config(text="Listening... say a few words.", style="Sub.TLabel")
        except Exception as e:
            self.msg.config(text=f"Could not open this microphone: {e}", style="Bad.TLabel")
        self._tick()

    def _tick(self):
        if self.stream is None:
            return
        w = min(1.0, self.level * 12) * 420
        self.canvas.coords(self.bar, 0, 0, w, 26)
        if self.level > 0.02 and not self.heard:
            self.heard = True
            self.msg.config(text="✓ I can hear you.", style="Good.TLabel")
        self.after(50, self._tick)

    def _stop(self):
        s, self.stream = self.stream, None
        if s:
            try:
                s.stop(); s.close()
            except Exception:
                pass

    def on_show(self):
        self._start()

    def on_hide(self):
        self._stop()
        self.w.cfg["device"] = None if self.var.get() == "System default" else self.var.get()


class Hotkey(Page):
    title, subtitle = "Hotkey", "Choose the keys you hold while speaking. A chord of left-side keys is safest on laptops."

    def build(self):
        row = ttk.Frame(self)
        row.pack(anchor="w")
        ttk.Label(row, text="Hold to dictate:", width=18).pack(side="left")
        self.cap = HotkeyCapture(row, self.w.cfg["key"], lambda s: self._reset())
        self.cap.pack(side="left")
        row2 = ttk.Frame(self)
        row2.pack(anchor="w", pady=PAD)
        ttk.Label(row2, text="Hold time (ms):", width=18).pack(side="left")
        self.hold = tk.IntVar(value=self.w.cfg["hold_ms"])
        ttk.Scale(row2, from_=0, to=800, variable=self.hold, length=220,
                  command=lambda v: self.hold.set(int(float(v) // 50 * 50))).pack(side="left")
        self.holdlbl = ttk.Label(row2, textvariable=self.hold, width=5)
        self.holdlbl.pack(side="left")
        wrap_label(self, "The hold time stops a quick tap or a shortcut like Ctrl+C from starting a recording. "
                         "Esc cancels a recording.", "Sub.TLabel").pack(anchor="w")
        box = ttk.LabelFrame(self, text="Try it: hold your keys now", padding=PAD)
        box.pack(fill="x", pady=PAD)
        self.state = ttk.Label(box, text="waiting...", font=("TkDefaultFont", 12))
        self.state.pack(anchor="w")
        self.listener = None

    def _reset(self):
        self._stop()
        self._start()

    def _start(self):
        from pynput import keyboard
        try:
            combo = Combo(self.cap.get())
        except ValueError:
            return
        held, t0 = set(), [None]

        def press(k):
            held.add(key_id(k))
            if combo.complete(held) and t0[0] is None:
                t0[0] = time.time()

        def release(k):
            held.discard(key_id(k))
            if not combo.complete(held):
                t0[0] = None
        self.listener = keyboard.Listener(on_press=press, on_release=release)
        self.listener.start()

        def poll():
            if self.listener is None:
                return
            if t0[0] is None:
                self.state.config(text="waiting...", style="TLabel")
            else:
                held_ms = (time.time() - t0[0]) * 1000
                if held_ms >= self.hold.get():
                    self.state.config(text="✓ recording would start now", style="Good.TLabel")
                else:
                    self.state.config(text=f"holding... {held_ms:.0f} ms", style="TLabel")
            self.after(50, poll)
        poll()

    def _stop(self):
        l, self.listener = self.listener, None
        if l:
            l.stop()

    def on_show(self):
        self._start()

    def on_hide(self):
        self._stop()
        self.w.cfg["key"], self.w.cfg["hold_ms"] = self.cap.get(), int(self.hold.get())

    def can_next(self):
        try:
            Combo(self.cap.get())
            return True
        except ValueError:
            return False


class Model(Page):
    title, subtitle = "Speech model", "A bigger model is more accurate but uses more memory. small.en suits most people."

    def build(self):
        self.var = tk.StringVar(value=self.w.cfg["model"])
        for name, text in model_choices():
            ttk.Radiobutton(self, text=text, value=name, variable=self.var, command=self._changed).pack(anchor="w", pady=2)
        self.row = DownloadRow(self)
        self.row.pack(anchor="w", pady=(PAD, 0))
        self.btn = ttk.Button(self, text="Download", command=self._download)
        self.btn.pack(anchor="w", pady=6)
        self.ready = False
        self._changed()

    def _changed(self):
        self.ready = models.is_downloaded(self.var.get())
        self.btn.state(["disabled"] if self.ready else ["!disabled"])
        self.row.msg.config(text="already downloaded" if self.ready else "not downloaded yet",
                            style="Good.TLabel" if self.ready else "Sub.TLabel")
        self.row.bar["value"] = 100 if self.ready else 0
        self.w.refresh()

    def _download(self):
        self.btn.state(["disabled"])

        def done(ok, err):
            self.ready = ok
            self.btn.state(["disabled"] if ok else ["!disabled"])
            if not ok:
                self.row.msg.config(text="Download failed. Check your connection and try again.", style="Bad.TLabel")
            self.w.refresh()
        self.row.start(self.var.get(), done)

    def on_hide(self):
        self.w.cfg["model"] = self.var.get()

    def can_next(self):
        return self.ready


class Words(Page):
    title, subtitle = "Your words", "Names and jargon you use often. Whisper will spell them the way you write them."

    def build(self):
        wrap_label(self, "One per line, for example: Kubernetes, xUnit, Priya, SourceFuse. "
                         "You can add more later in Settings > Vocabulary.", "Sub.TLabel").pack(anchor="w")
        self.text = tk.Text(self, height=8, width=60, font=("TkDefaultFont", 11))
        self.text.pack(anchor="w", pady=PAD)
        self.auto = tk.BooleanVar(value=True)
        ttk.Checkbutton(self, text="Start Holler when I sign in", variable=self.auto).pack(anchor="w")
        self.pill = tk.BooleanVar(value=self.w.cfg["overlay"])
        ttk.Checkbutton(self, text="Show the status pill at the bottom of the screen", variable=self.pill).pack(anchor="w")

    def on_hide(self):
        self.w.cfg["overlay"] = bool(self.pill.get())
        self.w.words = [l.strip() for l in self.text.get("1.0", "end").splitlines() if l.strip()]
        self.w.autostart = bool(self.auto.get())


class Done(Page):
    title, subtitle = "All set", ""

    def build(self):
        self.summary = wrap_label(self, "")
        self.summary.pack(anchor="w")

    def on_show(self):
        c = self.w.cfg
        self.subtitle_text = f"Hold  {c['key']}  and speak. Release to paste."
        self.summary.config(text=(
            f"Hotkey: hold {c['key']} for {c['hold_ms']} ms\nModel: {c['model']}\n"
            f"Microphone: {c['device'] or 'system default'}\nStart with sign-in: {'yes' if self.w.autostart else 'no'}\n\n"
            "Tip: after Whisper gets a word wrong, fix it by hand and press "
            f"{c['teach_key']} (cursor on that line). It learns the correction. "
            "You can also teach it from Settings > History.\n\n"
            "Holler lives in the system tray (bottom right): click its icon for Settings. You can also find "
            "Holler in the Start menu, or run  py -m holler  any time."))
        self.w.set_subtitle(self.subtitle_text)


class Wizard:
    def __init__(self, launch: bool):
        self.launch = launch
        self.finished = False
        self.cfg = config.load()
        self.words, self.autostart = [], True
        self.root = make_root("Holler setup", "640x540")
        head = ttk.Frame(self.root, padding=(PAD * 2, PAD * 2, PAD * 2, 0))
        head.pack(fill="x")
        self.title = ttk.Label(head, style="Title.TLabel")
        self.title.pack(anchor="w")
        self.sub = wrap_label(head, "", "Sub.TLabel", width=560)
        self.sub.pack(anchor="w", pady=(2, 0))
        self.body = ttk.Frame(self.root, padding=(PAD * 2, PAD, PAD * 2, PAD))
        self.body.pack(fill="both", expand=True)
        nav = ttk.Frame(self.root, padding=(PAD * 2, 0, PAD * 2, PAD * 2))
        nav.pack(fill="x", side="bottom")
        self.steps = ttk.Label(nav, text="", style="Sub.TLabel")
        self.steps.pack(side="left")
        self.next_btn = ttk.Button(nav, text="Next", style="Accent.TButton", command=self.next)
        self.next_btn.pack(side="right")
        self.back_btn = ttk.Button(nav, text="Back", command=self.back)
        self.back_btn.pack(side="right", padx=8)
        self.i = -1
        self.pages = [Welcome(self), Microphone(self), Hotkey(self), Model(self), Words(self), Done(self)]
        for p in self.pages:
            p.build()
        self.show(0)
        self.root.protocol("WM_DELETE_WINDOW", self.root.destroy)
        center(self.root)

    def set_subtitle(self, t):
        self.sub.config(text=t)

    def refresh(self):
        if self.i < 0:
            return
        p = self.pages[self.i]
        self.next_btn.config(text="Finish" if self.i == len(self.pages) - 1 else "Next")
        self.next_btn.state(["!disabled"] if p.can_next() else ["disabled"])
        self.back_btn.state(["disabled"] if self.i == 0 else ["!disabled"])

    def show(self, i):
        if self.i >= 0:
            self.pages[self.i].on_hide()
            self.pages[self.i].pack_forget()
        self.i = i
        p = self.pages[i]
        self.title.config(text=p.title)
        self.sub.config(text=p.subtitle)
        self.steps.config(text=f"Step {i + 1} of {len(self.pages)}")
        p.pack(fill="both", expand=True)
        p.on_show()
        self.refresh()

    def next(self):
        if self.i == len(self.pages) - 1:
            self.finish()
        else:
            self.show(self.i + 1)

    def back(self):
        if self.i > 0:
            self.show(self.i - 1)

    def finish(self):
        self.pages[self.i].on_hide()
        self.cfg["setup_done"] = True
        config.save(self.cfg)
        if self.words:
            v = Vocab(config_dir(), PACKAGE_DATA)
            have = {k.lower().lstrip("~") for k in v.keyword_list()}
            v.set_keywords(v.keyword_list() + [w for w in self.words if w.lower() not in have])
        process.set_autostart(self.autostart)
        process.create_start_menu_shortcut()
        self.finished = True
        self.root.destroy()
        if self.launch:
            process.restart_background()


def config_dir():
    from ..paths import data_dir
    return data_dir()


def run_wizard(launch: bool = True) -> bool:
    """Show the wizard. True if the user finished it. launch=True also (re)starts the background instance."""
    w = Wizard(launch)
    w.root.mainloop()
    return w.finished
