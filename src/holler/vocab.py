"""Personal vocabulary for the dictation tool: keywords, "wrong => right" replacements, and learning.

Files (next to this script, plain text, safe to edit by hand; changes are picked up automatically):

  keywords.txt       One term per line. Every term is (1) fed to Whisper as a glossary so it prefers that
                     spelling, and (2) if it looks like an identifier/acronym/proper name (xUnit, gRPC,
                     Program.cs, SQL Server, .NET 8), any case-insensitive match in the output is rewritten
                     to exactly that spelling. Start a line with ~ for glossary-only (no rewriting).
  replacements.txt   "wrong => right" per line. Whole-word/phrase, case-insensitive. Learned automatically
                     when you correct a dictation and press the teach key (see dictate.py).
  replacements_pending.json   single-word corrections seen once, waiting for a second confirmation.
"""
import difflib
import json
import os
import re
import shutil
import threading

from .cleanup import STOP1

EDGE = ".,;:!?\"'()[]{}"


def _phrase_re(s: str):
    return re.compile(r"(?<!\w)" + r"\s+".join(re.escape(t) for t in s.split()) + r"(?!\w)", re.I)


def _enforce(s: str) -> bool:
    """Rewrite output to this exact spelling only for identifier/acronym-like terms."""
    return any(c.isupper() for c in s[1:]) or any(c.isdigit() or c == "." for c in s)


def _plain_word(w: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z']+", w))


def _read(path):
    try:
        with open(path, encoding="utf-8") as f:
            return [ln.rstrip("\r\n") for ln in f]
    except OSError:
        return []


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0.0


def diff_pairs(old: str, new: str):
    """Compare the dictated text with its corrected version.
    Returns None if they are too different to be the same sentence, else (replacements, casing_terms);
    each replacement is (wrong, right, word_before, word_after)."""
    a, b = old.split(), new.split()
    norm = lambda t: t.strip(EDGE).lower()
    sm = difflib.SequenceMatcher(None, [norm(x) for x in a], [norm(x) for x in b], autojunk=False)
    if not a or not b or sm.ratio() < 0.5:
        return None
    repl, casing = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace" and i2 - i1 <= 4 and j2 - j1 <= 5:
            wrong = " ".join(x.strip(EDGE) for x in a[i1:i2]).strip()
            right = " ".join(x.strip(EDGE) for x in b[j1:j2]).strip()
            if wrong and right and wrong != right:
                before = b[j1 - 1].strip(EDGE) if j1 > 0 and i1 > 0 else ""
                after = b[j2].strip(EDGE) if j2 < len(b) and i2 < len(a) else ""
                repl.append((wrong, right, before, after))
        elif tag == "equal":
            for x, y in zip(a[i1:i2], b[j1:j2]):
                x, y = x.strip(EDGE), y.strip(EDGE)
                if x != y and _enforce(y):      # only identifier-style casing fixes (xUnit), not sentence case
                    casing.append(y)
    return repl, casing


def align(dictated: str, text: str) -> str:
    """The part of `text` (e.g. the whole line around the cursor) that best matches `dictated`.
    Lets the teach key work without selecting exactly the sentence."""
    a, t = dictated.split(), text.split()
    if len(t) <= len(a) + 2:
        return text.strip()
    norm = lambda x: x.strip(EDGE).lower()
    na = [norm(x) for x in a]
    best, span = 0.0, None
    for n in range(max(1, len(a) - 3), len(a) + 4):
        for i in range(0, len(t) - n + 1):
            r = difflib.SequenceMatcher(None, na, [norm(x) for x in t[i:i + n]], autojunk=False).ratio()
            if r > best:
                best, span = r, (i, i + n)
    return " ".join(t[span[0]:span[1]]) if span and best >= 0.5 else text.strip()


class Vocab:
    def __init__(self, folder: str, seed_dir: str = ""):
        self.kw_path = os.path.join(folder, "keywords.txt")
        self.rep_path = os.path.join(folder, "replacements.txt")
        self.pending_path = os.path.join(folder, "replacements_pending.json")
        self.lock = threading.RLock()
        self._stamp = None
        seeded = False
        for p in (self.kw_path, self.rep_path):          # first run: start from the shipped examples
            ex = os.path.join(seed_dir or folder, os.path.basename(p)[:-4] + ".example.txt")
            if not os.path.exists(p) and os.path.exists(ex):
                try:
                    shutil.copyfile(ex, p)
                    seeded = True
                except OSError:
                    pass
        self.reload()
        marker = os.path.join(folder, "packs_added.txt")
        if seed_dir and (seeded or not os.path.exists(marker)):   # ...plus every bundled starter pack, once
            packs = os.path.join(seed_dir, "packs")
            try:
                with open(marker, "w") as f:
                    f.write("starter packs were merged into your vocabulary once; delete this file to merge again\n")
            except OSError:
                pass
            for n in sorted(os.listdir(packs)) if os.path.isdir(packs) else []:
                try:
                    self.import_from(os.path.join(packs, n), front=True)   # glossary reads the END: yours stays last
                except OSError:
                    pass

    # ---- loading
    def _files_stamp(self):
        return (_mtime(self.kw_path), _mtime(self.rep_path))

    def refresh_if_changed(self):
        if self._files_stamp() != self._stamp:
            self.reload()

    def reload(self):
        with self.lock:
            self._stamp = self._files_stamp()
            self.keywords, self.canon, self.rules = [], [], []
            for ln in _read(self.kw_path):
                s = ln.strip()
                if not s or s.startswith("#"):
                    continue
                glossary_only = s.startswith("~")
                s = s.lstrip("~").strip()
                if not s:
                    continue
                self.keywords.append(s)
                if not glossary_only and _enforce(s):
                    self.canon.append((_phrase_re(s), s))
            for ln in _read(self.rep_path):
                s = ln.strip()
                if not s or s.startswith("#") or "=>" not in s:
                    continue
                wrong, right = (x.strip() for x in s.split("=>", 1))
                if wrong and right:
                    self.rules.append((len(wrong), _phrase_re(wrong), right))
            self.rules.sort(key=lambda r: -r[0])      # longest phrases first

    # ---- editing from the settings window (rewrites the files; comments are not kept)
    def keyword_list(self):
        with self.lock:
            return [ln.strip() for ln in _read(self.kw_path) if ln.strip() and not ln.strip().startswith("#")]

    def rule_list(self):
        out = []
        with self.lock:
            for ln in _read(self.rep_path):
                s = ln.strip()
                if s and not s.startswith("#") and "=>" in s:
                    w, r = (x.strip() for x in s.split("=>", 1))
                    if w and r:
                        out.append((w, r))
        return out

    def set_keywords(self, terms):
        with self.lock:
            with open(self.kw_path, "w", encoding="utf-8", newline="") as f:
                f.write("# One term per line. Start a line with ~ to only hint Whisper without rewriting the output.\r\n")
                f.write("".join(t.strip() + "\r\n" for t in terms if t.strip()))
            self.reload()

    def set_rules(self, pairs):
        with self.lock:
            with open(self.rep_path, "w", encoding="utf-8", newline="") as f:
                f.write("# wrong => right   (whole words/phrases, case-insensitive)\r\n")
                f.write("".join(f"{w.strip()} => {r.strip()}\r\n" for w, r in pairs if w.strip() and r.strip()))
            self.reload()

    def import_from(self, folder: str, front: bool = False):
        """Merge keywords and replacements from another folder (e.g. an older install). Returns (keywords, rules) added."""
        old = Vocab.__new__(Vocab)
        old.lock = threading.RLock()
        old.kw_path = os.path.join(folder, "keywords.txt")
        old.rep_path = os.path.join(folder, "replacements.txt")
        have_k = {k.lower().lstrip("~") for k in self.keyword_list()}
        new_k = [k for k in old.keyword_list() if k.lower().lstrip("~") not in have_k]
        have_r = {w.lower() for w, _ in self.rule_list()}
        new_r = [(w, r) for w, r in old.rule_list() if w.lower() not in have_r]
        if new_k:
            self.set_keywords(new_k + self.keyword_list() if front else self.keyword_list() + new_k)
        if new_r:
            self.set_rules(self.rule_list() + new_r)
        return len(new_k), len(new_r)

    # ---- using
    def prompt_terms(self, max_chars: int = 500):
        """Glossary for Whisper's prompt. Whisper keeps only the END of a long prompt, so the newest
        (last) terms win when the list is longer than the budget."""
        out, n = [], 0
        with self.lock:
            for k in reversed(self.keywords):
                n += len(k) + 2
                if n > max_chars:
                    break
                out.append(k)
        return list(reversed(out)) or None

    def apply(self, text: str) -> str:
        def sub(rx, right, text):
            def f(m):
                r = right
                if m.group(0)[:1].isupper() and r[:1].islower():
                    r = r[0].upper() + r[1:]        # keep sentence-start capital
                return r
            return rx.sub(f, text)
        with self.lock:
            for _, rx, right in self.rules:
                text = sub(rx, right, text)
            for rx, spelling in self.canon:
                text = rx.sub(lambda m, s=spelling: s, text)
        return text

    # ---- learning
    def _append(self, path, line):
        with self.lock:
            prefix = ""
            try:
                with open(path, "rb") as g:
                    data = g.read()
                if data and not data.endswith((b"\n", b"\r")):
                    prefix = "\r\n"
            except OSError:
                pass
            with open(path, "a", encoding="utf-8", newline="") as f:
                f.write(prefix + line + "\r\n")
            self.reload()

    def add_keyword(self, term: str) -> bool:
        term = term.strip()
        if not term or any(k.lower() == term.lower().lstrip("~") for k in self.keywords):
            # already present: if only the casing differs, the stored spelling wins (edit keywords.txt to change)
            return False
        self._append(self.kw_path, term)
        return True

    def _pending(self):
        try:
            with open(self.pending_path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            return {}

    def learn(self, wrong: str, right: str, before: str = "", after: str = "") -> str:
        """Record one correction. Returns a short human-readable result."""
        wrong, right = wrong.strip(), right.strip()
        with self.lock:
            if any(w == len(wrong) and rx.fullmatch(wrong) and r == right for w, rx, r in self.rules):
                return f"already known: {wrong} -> {right}"
            single_plain = " " not in wrong and _plain_word(wrong)
            note = ""
            if single_plain:
                # Learn the phrase with a neighbouring content word right away ("null difference" ->
                # "null reference"): narrow, so safe. The bare word needs a second confirmation.
                ctx = None
                first_time = self._pending().get(f"{wrong.lower()} => {right}", 0) < 1
                if before and before.lower() not in STOP1 and _plain_word(before):
                    ctx = (f"{before} {wrong}", f"{before} {right}")
                elif after and after.lower() not in STOP1 and _plain_word(after):
                    ctx = (f"{wrong} {after}", f"{right} {after}")
                if ctx and first_time and not any(len(ctx[0]) == w and rx.fullmatch(ctx[0]) for w, rx, r in self.rules):
                    self._append(self.rep_path, f"{ctx[0]} => {ctx[1]}")
                    note = f"learned: {ctx[0]} -> {ctx[1]}; "
            if single_plain:
                # a single ordinary word ("details") could be right elsewhere: wait for a second confirmation
                p = self._pending()
                key = f"{wrong.lower()} => {right}"
                p[key] = p.get(key, 0) + 1
                if p[key] < 2:
                    with open(self.pending_path, "w", encoding="utf-8") as f:
                        json.dump(p, f, indent=1)
                    return note + f"noted once: {wrong} -> {right} (applies on its own after you correct it a second time)"
                p.pop(key, None)
                with open(self.pending_path, "w", encoding="utf-8") as f:
                    json.dump(p, f, indent=1)
            self._append(self.rep_path, f"{wrong} => {right}")
            if _enforce(right) or not right.islower():
                self.add_keyword(right)           # also feed the right spelling to Whisper's glossary
            return note + f"learned: {wrong} -> {right}"

    def learn_from_edit(self, dictated: str, corrected: str):
        """Compare dictated text to its corrected version and learn every difference.
        Returns a list of messages, or None if the two texts are too different."""
        res = diff_pairs(dictated, corrected)
        if res is None:
            return None
        repl, casing = res
        msgs = [self.learn(w, r, b, a) for w, r, b, a in repl]
        for term in casing:
            if self.add_keyword(term):
                msgs.append(f"learned spelling: {term}")
        return msgs
