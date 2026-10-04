"""Settings window: General, Vocabulary (your jargon), History (teach it from past dictations), About."""
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from .. import __version__, config, models, process
from ..keys import Combo
from ..paths import PACKAGE_DATA, data_dir
from ..vocab import Vocab
from .common import PAD, DownloadRow, HotkeyCapture, center, make_root, model_choices, wrap_label


class General(ttk.Frame):
    def __init__(self, parent, win):
        super().__init__(parent, padding=PAD * 1.5)
        self.win, c = win, win.cfg
        r = 0

        def row(label, widget, hint=""):
            nonlocal r
            ttk.Label(self, text=label).grid(row=r, column=0, sticky="w", pady=5, padx=(0, 14))
            widget.grid(row=r, column=1, sticky="w")
            if hint:
                ttk.Label(self, text=hint, style="Sub.TLabel", wraplength=230, justify="left").grid(row=r, column=2, sticky="w", padx=10)
            r += 1

        self.key = HotkeyCapture(self, c["key"])
        row("Hold to dictate", self.key)
        self.hold = tk.IntVar(value=c["hold_ms"])
        row("Hold time (ms)", ttk.Spinbox(self, from_=0, to=1000, increment=50, textvariable=self.hold, width=8),
            "0 = start instantly")
        self.teach = HotkeyCapture(self, c["teach_key"])
        row("Learn a correction", self.teach, "press after fixing a dictated word by hand")


        from ..audio import list_input_devices
        devs = ["System default"] + list_input_devices()
        self.dev = tk.StringVar(value=c["device"] if c["device"] in devs else "System default")
        row("Microphone", ttk.Combobox(self, textvariable=self.dev, values=devs, state="readonly", width=42))

        from ..engines import DEFAULT_MODELS, ENGINES
        self.engine = tk.StringVar(value=c["engine"] if c["engine"] in ENGINES else "whisper")
        ec = ttk.Combobox(self, textvariable=self.engine, values=list(ENGINES), state="readonly", width=14)
        ec.bind("<<ComboboxSelected>>", lambda e: self._engine_changed())
        row("Speech engine", ec, "whisper is built in; parakeet needs: pip install \"holler[parakeet]\"")
        self._default_models = DEFAULT_MODELS

        self.model = tk.StringVar(value=c["model"])
        mc = ttk.Combobox(self, textvariable=self.model, values=self._model_names(self.engine.get()), width=34)
        self.model_box = mc
        mc.bind("<<ComboboxSelected>>", lambda e: self._model_changed())
        mc.bind("<FocusOut>", lambda e: self._model_changed())
        mc.bind("<Return>", lambda e: self._model_changed())
        row("Speech model", mc)
        self.note = ttk.Label(self, text="", style="Sub.TLabel", wraplength=420, justify="left")
        self.note.grid(row=r, column=1, columnspan=2, sticky="w")
        r += 1
        self.dl = DownloadRow(self)
        self.dlbtn = ttk.Button(self, text="Download this model", command=self._download)
        self.dlrow = r
        r += 1
        self._model_changed()

        self.unload = tk.DoubleVar(value=c["unload_after"])
        row("Free memory after idle (min)", ttk.Spinbox(self, from_=0, to=120, increment=5, textvariable=self.unload, width=8),
            "0 = keep the model loaded")
        self.paste = tk.StringVar(value=c["paste"])
        row("Insert text by", ttk.Combobox(self, textvariable=self.paste, values=["ctrl+v", "ctrl+shift+v", "type"],
                                           state="readonly", width=14), "type = keystrokes, for apps that block paste")
        self.lang = tk.StringVar(value=c["lang"] or "")
        row("Language code", ttk.Entry(self, textvariable=self.lang, width=8),
            "blank = automatic (multilingual models only), e.g. hi, en")

        self.bools = {}
        for key, text in (("cleanup", "Remove fillers and resolve spoken corrections (\"Monday, no wait, Tuesday\")"),
                          ("voice_undo", "Say \"scratch that\" on its own to remove the last dictation"),
                          ("spoken_commands", "Spoken commands: a stand-alone \"new line\", \"question mark\", \"open bracket\"..."),
                          ("smart_format", "Smart formatting: 25%, \u20b9500, john@example.com, main.py"),
                          ("auto_vocab", "Add names and terms I say often to my vocabulary automatically"),
                          ("trailing_space", "Add a space after each dictation"),
                          ("enter", "Press Enter after each dictation"),
                          ("sound", "Beep when recording starts and stops"),
                          ("overlay", "Show the status pill"),
                          ("log", "Keep a local history of dictations (used by the History tab)")):
            v = tk.BooleanVar(value=bool(c[key]))
            self.bools[key] = v
            ttk.Checkbutton(self, text=text, variable=v).grid(row=r, column=0, columnspan=3, sticky="w", pady=2)
            r += 1
        self.auto = tk.BooleanVar(value=process.autostart_enabled())
        ttk.Checkbutton(self, text="Start with the computer", variable=self.auto).grid(row=r, column=0, columnspan=3,
                                                                                         sticky="w", pady=2)

    @staticmethod
    def _model_names(engine):
        from ..engines import ENGINE_MODELS
        return [n for n, _ in model_choices()] if engine == "whisper" else ENGINE_MODELS.get(engine, [])

    def _engine_changed(self):
        eng = self.engine.get()
        self.model_box.configure(values=self._model_names(eng))
        cur = self.model.get().strip()
        if eng != "whisper" and cur in models.MODELS:
            self.model.set(self._default_models.get(eng, cur))
        elif eng == "whisper" and cur not in models.MODELS and "/" not in cur and not models.is_local(cur):
            self.model.set(self._default_models["whisper"])
        self._model_changed()

    def _model_changed(self):
        name = self.model.get().strip()
        if self.engine.get() != "whisper":
            self.note.config(text=f"Engine {self.engine.get()}: the model downloads on first start (about 650 MB for Parakeet). "
                                  "No hotword biasing: your vocabulary applies through the replacement rules.")
            self.dl.grid_forget(); self.dlbtn.grid_forget()
            return
        have = models.is_downloaded(name)
        if name in models.MODELS:
            mb, ram, note = models.MODELS[name]
            text = f"{note}.  About {ram} MB RAM, {mb} MB download."
        else:
            text = ("Your own model: " + models.describe(name) + ". Type a Hugging Face repo id (owner/name) or a folder "
                    "holding a CTranslate2 Whisper model.")
        self.note.config(text=text + ("" if have else "  Not downloaded yet." if "/" in name or name in models.MODELS else ""))
        if have or not (name in models.MODELS or "/" in name):
            self.dl.grid_forget(); self.dlbtn.grid_forget()
        else:
            self.dlbtn.grid(row=self.dlrow, column=1, sticky="w", pady=4)

    def _download(self):
        self.dlbtn.grid_forget()
        self.dl.grid(row=self.dlrow, column=1, columnspan=2, sticky="w", pady=4)
        self.dl.start(self.model.get(), lambda ok, e: self._model_changed() if ok else None)

    def collect(self, cfg):
        Combo(self.key.get()), Combo(self.teach.get())
        cfg.update(key=self.key.get(), teach_key=self.teach.get(), hold_ms=int(self.hold.get()),
                   device=None if self.dev.get() == "System default" else self.dev.get(),
                   engine=self.engine.get(), model=self.model.get().strip(), unload_after=float(self.unload.get()), paste=self.paste.get(),
                   lang=self.lang.get().strip() or None)
        for k, v in self.bools.items():
            cfg[k] = bool(v.get())


class Vocabulary(ttk.Frame):
    def __init__(self, parent, win):
        super().__init__(parent, padding=PAD)
        self.v = win.vocab
        wrap_label(self, "Words you use that Whisper gets wrong or spells differently. Changes apply to your next "
                         "dictation, no restart needed.", "Sub.TLabel", width=700).grid(row=0, column=0, columnspan=2,
                                                                                         sticky="w", pady=(0, 8))
        # keywords
        left = ttk.LabelFrame(self, text="Keywords and jargon", padding=8)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 8))
        wrap_label(left, "Whisper is biased toward these. Names like xUnit or gRPC are also rewritten to this exact "
                         "spelling. Start with ~ to hint only.", "Sub.TLabel", width=300).pack(anchor="w")
        fr = ttk.Frame(left)
        fr.pack(fill="both", expand=True, pady=6)
        self.kw = tk.Listbox(fr, height=14, width=34, activestyle="none")
        sb = ttk.Scrollbar(fr, command=self.kw.yview)
        self.kw.config(yscrollcommand=sb.set)
        self.kw.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        add = ttk.Frame(left)
        add.pack(fill="x")
        self.kwe = ttk.Entry(add)
        self.kwe.pack(side="left", fill="x", expand=True)
        self.kwe.bind("<Return>", lambda e: self.add_kw())
        ttk.Button(add, text="Add", command=self.add_kw).pack(side="left", padx=4)
        ttk.Button(add, text="Remove", command=self.rm_kw).pack(side="left")
        # replacements
        right = ttk.LabelFrame(self, text="Corrections: what Whisper writes  →  what you meant", padding=8)
        right.grid(row=1, column=1, sticky="nsew")
        fr2 = ttk.Frame(right)
        fr2.pack(fill="both", expand=True, pady=(0, 6))
        self.tree = ttk.Treeview(fr2, columns=("w", "r"), show="headings", height=14)
        self.tree.heading("w", text="Whisper writes")
        self.tree.heading("r", text="You meant")
        self.tree.column("w", width=190)
        self.tree.column("r", width=190)
        sb2 = ttk.Scrollbar(fr2, command=self.tree.yview)
        self.tree.config(yscrollcommand=sb2.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        add2 = ttk.Frame(right)
        add2.pack(fill="x")
        self.we, self.re = ttk.Entry(add2, width=14), ttk.Entry(add2, width=14)
        self.we.pack(side="left")
        ttk.Label(add2, text=" → ").pack(side="left")
        self.re.pack(side="left")
        self.re.bind("<Return>", lambda e: self.add_rule())
        ttk.Button(add2, text="Add", command=self.add_rule).pack(side="left", padx=4)
        ttk.Button(add2, text="Remove", command=self.rm_rule).pack(side="left")
        self.columnconfigure(0, weight=1)
        self.columnconfigure(1, weight=2)
        self.rowconfigure(1, weight=1)
        self.reload()

    def reload(self):
        self.kw.delete(0, "end")
        for k in self.v.keyword_list():
            self.kw.insert("end", k)
        self.tree.delete(*self.tree.get_children())
        for w, r in self.v.rule_list():
            self.tree.insert("", "end", values=(w, r))

    def add_kw(self):
        t = self.kwe.get().strip()
        if t:
            have = {k.lower().lstrip("~") for k in self.v.keyword_list()}
            if t.lower().lstrip("~") not in have:
                self.v.set_keywords(self.v.keyword_list() + [t])
            self.kwe.delete(0, "end")
            self.reload()
            self.kw.see("end")

    def rm_kw(self):
        sel = {self.kw.get(i) for i in self.kw.curselection()}
        if sel:
            self.v.set_keywords([k for k in self.v.keyword_list() if k not in sel])
            self.reload()

    def add_rule(self):
        w, r = self.we.get().strip(), self.re.get().strip()
        if w and r:
            rules = [p for p in self.v.rule_list() if p[0].lower() != w.lower()] + [(w, r)]
            self.v.set_rules(rules)
            self.we.delete(0, "end"); self.re.delete(0, "end")
            self.reload()

    def rm_rule(self):
        sel = {tuple(self.tree.item(i, "values")) for i in self.tree.selection()}
        if sel:
            self.v.set_rules([p for p in self.v.rule_list() if p not in sel])
            self.reload()


class History(ttk.Frame):
    def __init__(self, parent, win):
        super().__init__(parent, padding=PAD)
        self.win = win
        wrap_label(self, "Pick a dictation, fix the text the way it should have been, and click Learn. Holler "
                         "works out which words were wrong and fixes them from now on.", "Sub.TLabel",
                   width=700).pack(anchor="w", pady=(0, 8))
        fr = ttk.Frame(self)
        fr.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(fr, columns=("t", "x"), show="headings", height=11)
        self.tree.heading("t", text="When")
        self.tree.heading("x", text="What was pasted")
        self.tree.column("t", width=140, stretch=False)
        self.tree.column("x", width=560)
        sb = ttk.Scrollbar(fr, command=self.tree.yview)
        self.tree.config(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.pick)
        ttk.Label(self, text="Corrected text:").pack(anchor="w", pady=(10, 2))
        self.edit = tk.Text(self, height=3, wrap="word", font=("TkDefaultFont", 11))
        self.edit.pack(fill="x")
        bar = ttk.Frame(self)
        bar.pack(fill="x", pady=8)
        ttk.Button(bar, text="Learn from this correction", style="Accent.TButton", command=self.learn).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.reload).pack(side="left", padx=8)
        self.msg = ttk.Label(bar, text="", style="Sub.TLabel")
        self.msg.pack(side="left", padx=8)
        self.rows = []
        self.original = ""
        self.reload()

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        self.rows = []
        p = os.path.join(data_dir(), "dictation_log.tsv")
        try:
            with open(p, encoding="utf-8") as f:
                lines = f.read().splitlines()[-200:]
        except OSError:
            lines = []
        for ln in reversed(lines):
            parts = ln.split("\t")
            if len(parts) >= 3:
                self.rows.append((parts[0], parts[2]))
                self.tree.insert("", "end", values=(parts[0], parts[2]))
        if not self.rows:
            self.msg.config(text="No dictations yet (history must be switched on in General).")

    def pick(self, _=None):
        sel = self.tree.selection()
        if sel:
            self.original = self.tree.item(sel[0], "values")[1]
            self.edit.delete("1.0", "end")
            self.edit.insert("1.0", self.original)
            self.msg.config(text="")

    def learn(self):
        fixed = self.edit.get("1.0", "end").strip()
        if not self.original:
            self.msg.config(text="Pick a dictation first.")
            return
        msgs = self.win.vocab.learn_from_edit(self.original, fixed)
        if msgs is None:
            self.msg.config(text="That is too different from the original to learn from.")
        elif not msgs:
            self.msg.config(text="No changes found.")
        else:
            self.msg.config(text="; ".join(m.replace("learned: ", "Learned: ") for m in msgs)[:140])
            self.win.tabs_vocab.reload()


class About(ttk.Frame):
    def __init__(self, parent, win):
        super().__init__(parent, padding=PAD * 1.5)
        ttk.Label(self, text=f"Holler {__version__}", style="Title.TLabel").pack(anchor="w")
        wrap_label(self, "Free, offline push-to-talk dictation. Speech recognition by OpenAI Whisper through "
                         "faster-whisper. Your audio never leaves this computer.", "Sub.TLabel", width=620
                   ).pack(anchor="w", pady=8)
        ttk.Label(self, text="Made by Mayank Punghal  \u00b7  MIT License  \u00b7  github.com/MayankPunghal/holler"
                  ).pack(anchor="w", pady=(0, 6))
        ttk.Button(self, text="Open the project page", command=lambda: __import__("webbrowser").open(
            "https://github.com/MayankPunghal/holler")).pack(anchor="w")
        ttk.Label(self, text="Your files (settings, vocabulary, history, models):").pack(anchor="w", pady=(10, 2))
        ttk.Label(self, text=data_dir(), relief="groove", padding=4).pack(anchor="w")
        ttk.Button(self, text="Open folder", command=self.open).pack(anchor="w", pady=8)
        pid = process.running_pid()
        ttk.Label(self, text="Status: " + (f"running (pid {pid})" if pid else "not running")).pack(anchor="w", pady=8)

    def open(self):
        try:
            if sys.platform == "win32":
                os.startfile(data_dir())          # noqa
            else:
                import subprocess
                subprocess.Popen(["xdg-open" if sys.platform != "darwin" else "open", data_dir()])
        except Exception:
            pass


def _scrollable(parent):
    """A frame that scrolls vertically when the window is shorter than its content. Returns (outer, inner)."""
    outer = ttk.Frame(parent)
    canvas = tk.Canvas(outer, highlightthickness=0, borderwidth=0)
    bar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    win = canvas.create_window((0, 0), window=inner, anchor="nw")
    inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.bind("<Configure>", lambda e: canvas.itemconfigure(win, width=e.width))
    canvas.configure(yscrollcommand=bar.set)
    canvas.pack(side="left", fill="both", expand=True)
    bar.pack(side="right", fill="y")
    try:
        bg = ttk.Style().lookup("TFrame", "background")
        if bg:
            canvas.configure(background=bg)
    except tk.TclError:
        pass

    def wheel(e):
        if inner.winfo_height() > canvas.winfo_height():
            canvas.yview_scroll(int(-e.delta / 120) if e.delta else (1 if e.num == 5 else -1), "units")
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        outer.bind_all(seq, wheel, add="+")
    return outer, inner


class SettingsWindow:
    def __init__(self):
        self.cfg = config.load()
        self.vocab = Vocab(data_dir(), PACKAGE_DATA)
        self.root = make_root("Holler settings", "860x700", resizable=True)
        h = min(820, self.root.winfo_screenheight() - 90)            # fits small laptop screens
        self.root.geometry(f"860x{h}")
        self.root.minsize(820, 480)
        bar = ttk.Frame(self.root, padding=PAD)
        bar.pack(side="bottom", fill="x")                            # packed first: Save stays visible at any size
        nb = ttk.Notebook(self.root)
        nb.pack(fill="both", expand=True, padx=PAD, pady=(PAD, 0))
        general_tab, inner = _scrollable(nb)
        self.general = General(inner, self)
        self.general.pack(fill="both", expand=True)
        self.tabs_vocab = Vocabulary(nb, self)
        self.history = History(nb, self)
        nb.add(general_tab, text="  General  ")
        nb.add(self.tabs_vocab, text="  Vocabulary  ")
        nb.add(self.history, text="  History  ")
        nb.add(About(nb, self), text="  About  ")
        self.status = ttk.Label(bar, text="Vocabulary changes save instantly. General settings need Save.", style="Sub.TLabel")
        self.status.pack(side="left")
        ttk.Button(bar, text="Close", command=self.root.destroy).pack(side="right")
        ttk.Button(bar, text="Save", style="Accent.TButton", command=self.save).pack(side="right", padx=8)
        center(self.root)

    def save(self):
        try:
            self.general.collect(self.cfg)
        except ValueError as e:
            messagebox.showerror("Holler", str(e))
            return
        if self.cfg["engine"] == "whisper" and not models.is_downloaded(self.cfg["model"]):
            if not messagebox.askyesno("Holler", f"The model {self.cfg['model']} is not downloaded yet. "
                                       "Save anyway? It will download when you next start dictation."):
                return
        config.save(self.cfg)
        process.set_autostart(bool(self.general.auto.get()))
        if process.running_pid():
            process.restart_background()
            self.status.config(text="Saved. Restarting Holler...", style="Sub.TLabel")
            self.root.after(4000, self._check_restart)
        else:
            self.status.config(text="Saved. Start Holler to use them.", style="Good.TLabel")


    def _check_restart(self):
        if process.running_pid():
            self.status.config(text="Saved. Holler restarted with the new settings.", style="Good.TLabel")
        else:
            self.status.config(text="Saved, but Holler did not come back up. Run: py -m holler", style="Bad.TLabel")


def run_settings() -> int:
    SettingsWindow().root.mainloop()
    return 0
