"""Settings window: a sidebar with General, Speech, Models, Vocabulary, History and About pages."""
import os
import sys
import tkinter as tk
from tkinter import messagebox, ttk

from .. import __version__, config, models, process
from ..keys import Combo
from ..paths import PACKAGE_DATA, data_dir
from ..vocab import Vocab
from .common import PAD, DownloadRow, HotkeyCapture, center, make_root, wrap_label

LANGS = [("Automatic", None, ""), ("English", "en", ""), ("Hindi (Devanagari)", "hi", ""),
         ("Hinglish (Roman script)", "en", "hinglish")]


# --------------------------------------------------------------------------- building blocks

def scrollable(parent):
    """A vertically scrolling area. Returns (outer, inner): pack the outer, put content in the inner."""
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
        if outer.winfo_ismapped() and inner.winfo_height() > canvas.winfo_height():
            canvas.yview_scroll(int(-e.delta / 120) if e.delta else (1 if e.num == 5 else -1), "units")
    for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        outer.bind_all(seq, wheel, add="+")
    return outer, inner


class Page(ttk.Frame):
    """A page: a title, a one-line description, then cards."""

    def __init__(self, parent, title, subtitle, scroll=True):
        super().__init__(parent)
        head = ttk.Frame(self, padding=(28, 22, 28, 6))
        head.pack(fill="x")
        ttk.Label(head, text=title, style="Title.TLabel").pack(anchor="w")
        if subtitle:
            wrap_label(head, subtitle, "Sub.TLabel", width=600).pack(anchor="w", pady=(4, 0))
        if scroll:
            outer, self.body = scrollable(self)
            outer.pack(fill="both", expand=True)
        else:
            self.body = ttk.Frame(self)
            self.body.pack(fill="both", expand=True)
        self.body.configure(padding=(28, 8, 28, 20))

    def card(self, title, expand=False):
        wrap = ttk.Frame(self.body)
        wrap.pack(fill="both" if expand else "x", expand=expand, pady=(10, 0))
        if title:
            ttk.Label(wrap, text=title, style="CardTitle.TLabel").pack(anchor="w", pady=(0, 6))
        c = ttk.Frame(wrap, style="Card.TFrame", padding=(18, 10))
        c.pack(fill="both", expand=expand)
        c.columnconfigure(0, weight=1)
        c._rows = 0
        return c


def setting(card, label, desc, widget=None):
    """One row: label and description on the left, the control on the right, a divider below."""
    r = card._rows
    if r:
        ttk.Separator(card).grid(row=r, column=0, columnspan=2, sticky="ew", pady=2)
        r += 1
    text = ttk.Frame(card, style="CardBody.TFrame")
    text.grid(row=r, column=0, sticky="w", pady=8)
    ttk.Label(text, text=label, style="Card.TLabel").pack(anchor="w")
    if desc:
        ttk.Label(text, text=desc, style="CardSub.TLabel", wraplength=400, justify="left").pack(anchor="w")
    if widget is not None:
        widget.grid(row=r, column=1, sticky="e", padx=(16, 0))
    card._rows = r + 1
    return widget


def switch(card, label, desc, var):
    return setting(card, label, desc, ttk.Checkbutton(card, variable=var, style="Switch.TCheckbutton"))


# --------------------------------------------------------------------------- pages

class GeneralPage(Page):
    def __init__(self, parent, win):
        super().__init__(parent, "General", "Keys, how text is inserted, and what Holler does to your words.")
        c = win.cfg
        keys = self.card("Shortcuts")
        self.key = setting(keys, "Hold to dictate", "Hold, speak, let go. Modifier keys only never type anything.",
                           HotkeyCapture(keys, c["key"]))
        self.hold = tk.IntVar(value=c["hold_ms"])
        setting(keys, "Hold time", "Milliseconds before recording starts, so quick taps and shortcuts never record.",
                ttk.Spinbox(keys, from_=0, to=1000, increment=50, textvariable=self.hold, width=7))
        self.teach = setting(keys, "Learn a correction", "Fix a misheard word, select it, then press this.",
                             HotkeyCapture(keys, c["teach_key"]))

        text = self.card("Text")
        self.bools = {}

        def sw(card, key, label, desc):
            self.bools[key] = tk.BooleanVar(value=bool(c[key]))
            switch(card, label, desc, self.bools[key])
        sw(text, "cleanup", "Clean up speech", "Remove “um” and “uh”; “Monday, no wait, Tuesday” becomes “Tuesday”.")
        sw(text, "spoken_commands", "Spoken commands", "“new paragraph”, “question mark”, “open bracket”… become symbols.")
        sw(text, "smart_format", "Smart formatting", "25%, ₹500, john@example.com, main.py.")
        sw(text, "voice_undo", "Undo by voice", "Say “scratch that” on its own to remove the last dictation.")
        sw(text, "auto_vocab", "Learn new terms automatically", "Identifiers you say often (xUnit, order_id) join your vocabulary.")

        ins = self.card("Inserting text")
        self.paste = tk.StringVar(value=c["paste"])
        setting(ins, "Insert text by", "Paste works almost everywhere. “type” is for apps that block paste.",
                ttk.Combobox(ins, textvariable=self.paste, values=["ctrl+v", "ctrl+shift+v", "type"], state="readonly", width=13))
        sw(ins, "trailing_space", "Add a space after each dictation", "So the next dictation doesn't stick to this one.")
        sw(ins, "enter", "Press Enter after each dictation", "Sends chat messages straight away.")

        app = self.card("App")
        sw(app, "overlay", "Show the status pill", "The small indicator while you speak and while it transcribes.")
        sw(app, "sound", "Beeps", "A short beep when recording starts and stops.")
        sw(app, "check_updates", "Check for updates", "Once a day, asks GitHub if a newer Holler exists. Nothing else is sent.")
        sw(app, "log", "Keep a history on this computer", "Needed for the History page and for learning corrections.")
        self.auto = tk.BooleanVar(value=process.autostart_enabled())
        switch(app, "Start with the computer", "Holler starts in the background when you sign in.", self.auto)

    def collect(self, cfg):
        Combo(self.key.get()), Combo(self.teach.get())                 # raises ValueError on a bad key name
        cfg.update(key=self.key.get(), teach_key=self.teach.get(), hold_ms=int(self.hold.get()), paste=self.paste.get())
        for k, v in self.bools.items():
            cfg[k] = bool(v.get())


class SpeechPage(Page):
    def __init__(self, parent, win):
        super().__init__(parent, "Speech", "Microphone, speech engine, the model in use and its language.")
        self.win, c = win, win.cfg
        from ..audio import list_input_devices
        from ..engines import ENGINES
        mic = self.card("Input")
        devs = ["System default"] + list_input_devices()
        self.dev = tk.StringVar(value=c["device"] if c["device"] in devs else "System default")
        setting(mic, "Microphone", "“System default” follows Windows.",
                ttk.Combobox(mic, textvariable=self.dev, values=devs, state="readonly", width=34))

        rec = self.card("Recognition")
        self.engine = tk.StringVar(value=c["engine"] if c["engine"] in ENGINES else "whisper")
        ec = ttk.Combobox(rec, textvariable=self.engine, values=list(ENGINES), state="readonly", width=12)
        ec.bind("<<ComboboxSelected>>", lambda e: self.refresh())
        setting(rec, "Engine", "Whisper is built in. Parakeet needs: pip install \"holler[parakeet]\".", ec)
        self.model = tk.StringVar(value=c["model"])
        mrow = ttk.Frame(rec, style="CardBody.TFrame")
        self.model_box = ttk.Combobox(mrow, textvariable=self.model, state="readonly", width=30)
        self.model_box.pack(side="left")
        self.model_box.bind("<<ComboboxSelected>>", lambda e: self.describe())
        ttk.Button(mrow, text="Manage models…", command=lambda: win.show("models")).pack(side="left", padx=(8, 0))
        setting(rec, "Model", "Downloaded models. Get more or remove them under Models.", mrow)
        self.note = ttk.Label(rec, text="", style="CardSub.TLabel", wraplength=560, justify="left")
        self.note.grid(row=rec._rows, column=0, columnspan=2, sticky="w", pady=(0, 8))
        rec._rows += 1

        lang = self.card("Language")
        prompt = (c.get("initial_prompt") or "").strip()
        current = next((n for n, code, p in LANGS if code == c["lang"] and bool(p) == bool(prompt)), None)
        self.lang = tk.StringVar(value=current or (c["lang"] or "Automatic"))
        setting(lang, "Language", "English-only models (.en) always use English. For Hinglish, pick a multilingual "
                                  "model; Whisper's Hinglish is hit and miss.",
                ttk.Combobox(lang, textvariable=self.lang, values=[n for n, _, _ in LANGS], width=24))

        perf = self.card("Memory")
        self.unload = tk.DoubleVar(value=c["unload_after"])
        setting(perf, "Free memory after idle", "Minutes before the model is unloaded (0 = keep it loaded). "
                                                "It reloads while you start speaking.",
                ttk.Spinbox(perf, from_=0, to=120, increment=5, textvariable=self.unload, width=7))
        self.refresh()

    def refresh(self):
        from ..engines import DEFAULT_MODELS, ENGINE_MODELS
        eng = self.engine.get()
        if eng == "whisper":
            names = models.installed()
        else:
            names = ENGINE_MODELS.get(eng, [])
        cur = self.model.get()
        if cur not in names:
            cur = DEFAULT_MODELS.get(eng, "") if eng != "whisper" else (names[0] if names else cur)
            self.model.set(cur)
        self.model_box.configure(values=names or [cur])
        self.describe()

    def describe(self):
        name = self.model.get()
        if self.engine.get() != "whisper":
            text = "Downloads on first start (about 650 MB). Your vocabulary applies through replacement rules."
        elif name in models.MODELS:
            mb, ram, note = models.MODELS[name]
            text = f"{note[:1].upper() + note[1:]}. Uses about {ram} MB of memory."
        else:
            text = f"Your own model ({models.describe(name)})."
        if self.engine.get() == "whisper" and not models.is_downloaded(name):
            text += " Not downloaded: get it under Models."
        self.note.config(text=text)

    def collect(self, cfg):
        sel = self.lang.get().strip()
        match = next(((code, p) for n, code, p in LANGS if n == sel), None)
        if match:
            code, p = match
        else:
            code, p = (sel.lower() or None), ""
        prompt = ""
        if p == "hinglish":
            from ..bench import HINGLISH_PROMPT
            prompt = HINGLISH_PROMPT
        elif (cfg.get("initial_prompt") or "") and match is None:
            prompt = cfg["initial_prompt"]
        cfg.update(device=None if self.dev.get() == "System default" else self.dev.get(), engine=self.engine.get(),
                   model=self.model.get().strip(), unload_after=float(self.unload.get()), lang=code,
                   initial_prompt=prompt)


class ModelsPage(Page):
    def __init__(self, parent, win):
        super().__init__(parent, "Models", "Download, use and remove speech models. Bigger models are more accurate "
                                           "and slower. Everything runs on this computer.", scroll=False)
        self.win = win
        top = ttk.Frame(self.body)
        top.pack(fill="x")
        self.q = tk.StringVar()
        self.q.trace_add("write", lambda *a: self.reload())
        ttk.Label(top, text="Search").pack(side="left")
        ttk.Entry(top, textvariable=self.q, width=28).pack(side="left", padx=(8, 0))
        self.only = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text="Downloaded only", variable=self.only, command=self.reload).pack(side="left", padx=14)

        fr = ttk.Frame(self.body)
        fr.pack(fill="both", expand=True, pady=10)
        self.tree = ttk.Treeview(fr, columns=("name", "size", "status", "about"), show="headings", height=12,
                                 selectmode="browse")
        for col, text, w, st in (("name", "Model", 290, False), ("size", "Size", 80, False),
                                 ("status", "Status", 110, False), ("about", "About", 330, True)):
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, stretch=st, anchor="w")
        sb = ttk.Scrollbar(fr, command=self.tree.yview)
        self.tree.config(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.update_buttons())
        self.tree.bind("<Double-1>", lambda e: self.use())

        acts = ttk.Frame(self.body)
        acts.pack(fill="x")
        self.b_use = ttk.Button(acts, text="Use this model", style="Accent.TButton", command=self.use)
        self.b_use.pack(side="left")
        self.b_dl = ttk.Button(acts, text="Download", command=self.download)
        self.b_dl.pack(side="left", padx=8)
        self.b_del = ttk.Button(acts, text="Delete", command=self.delete)
        self.b_del.pack(side="left")
        self.dl = DownloadRow(acts)

        add = self.card("Add a model from Hugging Face")
        row = ttk.Frame(add, style="CardBody.TFrame")
        self.repo = tk.StringVar()
        ttk.Entry(row, textvariable=self.repo, width=40).pack(side="left")
        ttk.Button(row, text="Download", command=self.add).pack(side="left", padx=8)
        setting(add, "Repository", "A Whisper model in faster-whisper (CTranslate2) format, e.g. "
                                   "itsskofficial/livewhisper-hinglish-swift. Its files must include model.bin, "
                                   "config.json, tokenizer.json and a vocabulary file.", row)
        self.reload()

    # ---- data
    def rows(self):
        have = set(models.installed())
        out = []
        for n, (mb, ram, note) in models.MODELS.items():
            out.append((n, f"{mb:,} MB", n in have, note))
        for n in have:
            if n not in models.MODELS:
                out.append((n, f"{models.disk_mb(n):,} MB", True, "your model (" + models.describe(n) + ")"))
        return out

    def reload(self):
        q = self.q.get().lower().strip()
        in_use = self.win.speech.model.get() if hasattr(self.win, "speech") else self.win.cfg["model"]
        self.tree.delete(*self.tree.get_children())
        for name, size, have, about in self.rows():
            if q and q not in name.lower() and q not in about.lower():
                continue
            if self.only.get() and not have:
                continue
            status = "In use" if name == in_use and have else ("Downloaded" if have else "Not downloaded")
            self.tree.insert("", "end", iid=name, values=(name, size, status, about))
        self.update_buttons()

    def selected(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def update_buttons(self):
        n = self.selected()
        have = bool(n) and models.is_downloaded(n)
        busy = self.dl.thread is not None and self.dl.thread.is_alive()
        self.b_use.state(["!disabled"] if have else ["disabled"])
        self.b_dl.state(["!disabled"] if (n and not have and not busy) else ["disabled"])
        self.b_del.state(["!disabled"] if (have and n != self.win.speech.model.get()) else ["disabled"])

    # ---- actions
    def use(self):
        n = self.selected()
        if n and models.is_downloaded(n):
            self.win.speech.engine.set("whisper")
            self.win.speech.model.set(n)
            self.win.speech.refresh()
            self.reload()
            self.win.status.config(text=f"{n} selected. Click Save to use it.", style="Sub.TLabel")

    def download(self, name=None):
        n = name or self.selected()
        if not n:
            return
        self.dl.pack(side="left", padx=12)
        self.b_dl.state(["disabled"])

        def done(ok, err):
            self.reload()
            if ok:
                self.win.speech.refresh()
        self.dl.start(n, done)

    def add(self):
        repo = self.repo.get().strip()
        if "/" not in repo:
            messagebox.showinfo("Holler", "Type a Hugging Face repository id, like owner/model-name.")
            return
        self.download(repo)

    def delete(self):
        n = self.selected()
        if not n or n == self.win.speech.model.get():
            return
        if not messagebox.askyesno("Holler", f"Delete {n} from this computer ({models.disk_mb(n):,} MB)? "
                                             "You can download it again later."):
            return
        try:
            models.delete(n)
        except Exception as e:
            messagebox.showerror("Holler", str(e))
        self.reload()
        self.win.speech.refresh()


class VocabularyPage(Page):
    def __init__(self, parent, win):
        super().__init__(parent, "Vocabulary", "Words Whisper gets wrong or spells differently. Changes apply to your "
                                               "next dictation, no restart needed.", scroll=False)
        self.v = win.vocab
        grid = ttk.Frame(self.body)
        grid.pack(fill="both", expand=True)
        left = ttk.Frame(grid)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        ttk.Label(left, text="Keywords and jargon", style="CardTitle.TLabel").pack(anchor="w")
        wrap_label(left, "Whisper is nudged toward these. Names like xUnit are also rewritten to this exact "
                         "spelling. Start a line with ~ to only nudge.", "Sub.TLabel", width=300).pack(anchor="w", pady=(2, 6))
        fr = ttk.Frame(left)
        fr.pack(fill="both", expand=True)
        self.kw = tk.Listbox(fr, height=14, width=30, activestyle="none", borderwidth=0, highlightthickness=1,
                             highlightbackground="#c9ccd1", background="#ffffff")
        sb = ttk.Scrollbar(fr, command=self.kw.yview)
        self.kw.config(yscrollcommand=sb.set)
        self.kw.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        add = ttk.Frame(left)
        add.pack(fill="x", pady=(8, 0))
        self.kwe = ttk.Entry(add)
        self.kwe.pack(side="left", fill="x", expand=True)
        self.kwe.bind("<Return>", lambda e: self.add_kw())
        ttk.Button(add, text="Add", command=self.add_kw).pack(side="left", padx=6)
        ttk.Button(add, text="Remove", command=self.rm_kw).pack(side="left")

        right = ttk.Frame(grid)
        right.grid(row=0, column=1, sticky="nsew")
        ttk.Label(right, text="Corrections", style="CardTitle.TLabel").pack(anchor="w")
        wrap_label(right, "What Whisper writes → what you meant. Learned corrections appear here too, and "
                          "you can remove any of them.", "Sub.TLabel", width=420).pack(anchor="w", pady=(2, 6))
        fr2 = ttk.Frame(right)
        fr2.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(fr2, columns=("w", "r"), show="headings", height=14)
        self.tree.heading("w", text="Whisper writes")
        self.tree.heading("r", text="You meant")
        self.tree.column("w", width=200)
        self.tree.column("r", width=200)
        sb2 = ttk.Scrollbar(fr2, command=self.tree.yview)
        self.tree.config(yscrollcommand=sb2.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb2.pack(side="right", fill="y")
        add2 = ttk.Frame(right)
        add2.pack(fill="x", pady=(8, 0))
        self.we, self.re = ttk.Entry(add2, width=16), ttk.Entry(add2, width=16)
        self.we.pack(side="left")
        ttk.Label(add2, text=" → ").pack(side="left")
        self.re.pack(side="left")
        self.re.bind("<Return>", lambda e: self.add_rule())
        ttk.Button(add2, text="Add", command=self.add_rule).pack(side="left", padx=6)
        ttk.Button(add2, text="Remove", command=self.rm_rule).pack(side="left")
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=2)
        grid.rowconfigure(0, weight=1)
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
            self.we.delete(0, "end")
            self.re.delete(0, "end")
            self.reload()

    def rm_rule(self):
        sel = {tuple(self.tree.item(i, "values")) for i in self.tree.selection()}
        if sel:
            self.v.set_rules([p for p in self.v.rule_list() if p not in sel])
            self.reload()


class HistoryPage(Page):
    def __init__(self, parent, win):
        super().__init__(parent, "History", "Pick a dictation, fix the text the way it should have been, and click "
                                            "Learn. Stored only on this computer.", scroll=False)
        self.win = win
        fr = ttk.Frame(self.body)
        fr.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(fr, columns=("t", "x"), show="headings", height=10)
        self.tree.heading("t", text="When")
        self.tree.heading("x", text="What was pasted")
        self.tree.column("t", width=150, stretch=False)
        self.tree.column("x", width=560)
        sb = ttk.Scrollbar(fr, command=self.tree.yview)
        self.tree.config(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.pick)
        ttk.Label(self.body, text="Corrected text", style="CardTitle.TLabel").pack(anchor="w", pady=(12, 4))
        self.edit = tk.Text(self.body, height=3, wrap="word", font=("Segoe UI", 11) if sys.platform == "win32" else None,
                            borderwidth=0, highlightthickness=1, highlightbackground="#c9ccd1",
                            highlightcolor="#2f60d8", background="#ffffff", padx=8, pady=6)
        self.edit.pack(fill="x")
        bar = ttk.Frame(self.body)
        bar.pack(fill="x", pady=10)
        ttk.Button(bar, text="Learn from this correction", style="Accent.TButton", command=self.learn).pack(side="left")
        ttk.Button(bar, text="Refresh", command=self.reload).pack(side="left", padx=8)
        self.msg = ttk.Label(bar, text="", style="Sub.TLabel")
        self.msg.pack(side="left", padx=8)
        self.original = ""
        self.reload()

    def reload(self):
        self.tree.delete(*self.tree.get_children())
        p = os.path.join(data_dir(), "dictation_log.tsv")
        try:
            with open(p, encoding="utf-8") as f:
                lines = f.read().splitlines()[-200:]
        except OSError:
            lines = []
        n = 0
        for ln in reversed(lines):
            parts = ln.split("\t")
            if len(parts) >= 3:
                self.tree.insert("", "end", values=(parts[0], parts[2]))
                n += 1
        if not n:
            self.msg.config(text="No dictations yet (the history switch on the General page must be on).")

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
            self.win.vocab_page.reload()


class AboutPage(Page):
    def __init__(self, parent, win):
        super().__init__(parent, f"Holler {__version__}", "Free, offline push-to-talk dictation. Speech recognition "
                         "by OpenAI Whisper through faster-whisper. Your audio never leaves this computer.")
        info = self.card("")
        setting(info, "Made by", "Mayank Punghal", None)
        setting(info, "Licence", "MIT: free to use, change and share.", None)
        setting(info, "Project page", "github.com/MayankPunghal/holler",
                ttk.Button(info, text="Open", command=lambda: __import__("webbrowser").open(
                    "https://github.com/MayankPunghal/holler")))
        upd = self.card("Updates")
        self.upd_msg = tk.StringVar(value=f"You have {__version__}.")
        setting(upd, "Holler version", None, ttk.Button(upd, text="Check now", command=self.check_updates))
        ttk.Label(upd, textvariable=self.upd_msg, style="CardSub.TLabel", wraplength=560).grid(
            row=upd._rows, column=0, columnspan=2, sticky="w", pady=(0, 8))
        upd._rows += 1
        files = self.card("Your files")
        setting(files, "Data folder", data_dir() + "\nSettings, vocabulary, history, logs and models.",
                ttk.Button(files, text="Open folder", command=self.open))
        pid = process.running_pid()
        setting(files, "Status", f"Running (process {pid})" if pid else "Not running", None)

    def check_updates(self):
        from .. import updates
        self.upd_msg.set("Checking...")
        self.update_idletasks()
        try:
            rel = updates.check(force=True)
        except Exception as e:
            self.upd_msg.set(f"Couldn't reach GitHub ({type(e).__name__}). Check your internet connection.")
            return
        if not rel:
            self.upd_msg.set(f"You have the latest version ({__version__}).")
            return
        if updates.can_self_install(rel):
            self.upd_msg.set(f"Holler {rel['version']} is available. Downloading the installer...")
            state = {"p": 0.0, "done": None}

            def work():
                state["done"] = updates.install(rel, progress=lambda f: state.update(p=f))

            def poll():
                if state["done"] is None:
                    self.upd_msg.set(f"Holler {rel['version']} is available. Downloading the installer... "
                                     f"{int(state['p'] * 100)}%")
                    self.after(300, poll)
                else:
                    self.upd_msg.set("The installer has started: follow its steps." if state["done"] else
                                     "Download failed; the release page is open in your browser.")
            import threading
            threading.Thread(target=work, daemon=True).start()
            poll()
        else:
            self.upd_msg.set(f"Holler {rel['version']} is available. Close Holler and run:  {updates.pip_hint()}")

    def open(self):
        try:
            if sys.platform == "win32":
                os.startfile(data_dir())          # noqa
            else:
                import subprocess
                subprocess.Popen(["xdg-open" if sys.platform != "darwin" else "open", data_dir()])
        except Exception:
            pass


# --------------------------------------------------------------------------- window

class SettingsWindow:
    PAGES = (("general", "General"), ("speech", "Speech"), ("models", "Models"), ("vocab", "Vocabulary"),
             ("history", "History"), ("about", "About"))

    def __init__(self):
        self.cfg = config.load()
        self.vocab = Vocab(data_dir(), PACKAGE_DATA)
        self.root = make_root("Holler settings", "980x720", resizable=True)
        h = min(760, self.root.winfo_screenheight() - 90)            # fits small laptop screens
        self.root.geometry(f"980x{h}")
        self.root.minsize(860, 480)

        bar = ttk.Frame(self.root, style="Bar.TFrame", padding=(PAD + 6, 10))
        bar.pack(side="bottom", fill="x")                            # packed first: Save stays visible at any size
        ttk.Separator(self.root).pack(side="bottom", fill="x")
        side = ttk.Frame(self.root, style="Side.TFrame", padding=(10, 18))
        side.pack(side="left", fill="y")
        ttk.Label(side, text="Holler", style="Brand.TLabel").pack(anchor="w", padx=12, pady=(0, 14))
        self.content = ttk.Frame(self.root)
        self.content.pack(side="left", fill="both", expand=True)

        self.status = ttk.Label(bar, text="Vocabulary changes save instantly. Other settings need Save.",
                                style="Sub.TLabel")
        self.status.pack(side="left")
        ttk.Button(bar, text="Close", command=self.root.destroy).pack(side="right")
        ttk.Button(bar, text="Save", style="Accent.TButton", command=self.save).pack(side="right", padx=8)

        self.general = GeneralPage(self.content, self)
        self.speech = SpeechPage(self.content, self)
        self.models = ModelsPage(self.content, self)
        self.vocab_page = VocabularyPage(self.content, self)
        self.history = HistoryPage(self.content, self)
        self.about = AboutPage(self.content, self)
        self.pages = {"general": self.general, "speech": self.speech, "models": self.models, "vocab": self.vocab_page,
                      "history": self.history, "about": self.about}
        self.page = tk.StringVar(value="general")
        for key, label in self.PAGES:
            ttk.Radiobutton(side, text=label, value=key, variable=self.page, style="Nav.Toolbutton",
                            command=lambda k=key: self.show(k)).pack(fill="x", pady=1)
        self.show("general")
        center(self.root)

    def show(self, key):
        self.page.set(key)
        for k, p in self.pages.items():
            if k == key:
                p.pack(fill="both", expand=True)
            else:
                p.pack_forget()
        if key == "models":
            self.models.reload()

    def save(self):
        try:
            self.general.collect(self.cfg)
            self.speech.collect(self.cfg)
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
            self.status.config(text="Saved. Restarting Holler…", style="Sub.TLabel")
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
