"""Spoken commands and smart formatting, applied after vocabulary and cleanup.

Spoken commands: a command phrase that stands on its own (the speech engine usually sets it off with commas or a
full stop) becomes the symbol or break it names.

    "Dear team, new paragraph, thanks all."   ->  "Dear team\\n\\nThanks all."
    "Are you coming, question mark"           ->  "Are you coming?"
    "open bracket, see note, close bracket"   ->  "(see note)"

A phrase inside a sentence ("add a new line to the file") is left alone.

Smart formatting: "twenty five percent" -> "25%", "500 rupees" -> "₹500", "john at example dot com" ->
"john@example.com", "main dot py" -> "main.py".
"""
import re

# phrase -> (output, kind). kind: "end" = attaches to the previous word, "open" = attaches to the next word,
# "break" = line break, "sym" = attaches both sides.
COMMANDS = {
    "new line": ("\n", "break"), "newline": ("\n", "break"),
    "new paragraph": ("\n\n", "break"), "next paragraph": ("\n\n", "break"),
    "question mark": ("?", "end"),
    "exclamation mark": ("!", "end"), "exclamation point": ("!", "end"), "exclamation": ("!", "end"),
    "full stop": (".", "end"), "period": (".", "end"),
    "comma": (",", "end"), "colon": (":", "end"), "semicolon": (";", "end"), "semi colon": (";", "end"),
    "open bracket": ("(", "open"), "open parenthesis": ("(", "open"), "open paren": ("(", "open"),
    "close bracket": (")", "end"), "close parenthesis": (")", "end"), "close paren": (")", "end"),
    "open quote": ('"', "open"), "close quote": ('"', "end"), "end quote": ('"', "end"),
    "slash": ("/", "sym"), "backslash": ("\\", "sym"), "underscore": ("_", "sym"), "at sign": ("@", "sym"),
    "hashtag": ("#", "open"),
}
_PUNCT = ".,;:!?"
_PHRASES = sorted(COMMANDS, key=len, reverse=True)
_CLAUSE = re.compile(r"[.,;:!?]+(?=\s|$)|(?:[^.,;:!?]|[.,;:!?](?!\s|$))+")
_SEP = re.compile(r"[.,;:!?]+$")


_SQUASHED = {k.replace(" ", ""): v for k, v in COMMANDS.items()}


def _is_cmd(words: str):
    """A command phrase, however Whisper spelled it: "new paragraph", "New-Paragraph", "NewParagraph"."""
    w = words.strip().lower()
    return COMMANDS.get(w) or _SQUASHED.get(re.sub(r"[\s-]+", "", w))


_TRAILING = ("new paragraph", "new line", "question mark", "exclamation mark", "exclamation point")
_NOT_BEFORE = {"the", "a", "an", "this", "that", "my", "your", "no", "of", "with", "add", "insert", "type", "put",
               "use", "is", "as", "for", "called", "another", "one", "each", "every", "after", "before",
               "said", "say", "says", "saying", "word", "words", "typed", "write", "wrote", "named", "like"}


def _split_trailing(p: str):
    """'it grew by 25% new paragraph' -> ['it grew by 25%', 'new paragraph'] (a command that ends a clause).
    Skipped when the word before it shows it is being talked about ('add a new line', 'the question mark')."""
    low = p.strip().lower()
    for ph in _TRAILING:
        m = re.search(r"\s(" + r"[\s-]?".join(map(re.escape, ph.split())) + r")$", low)
        if m:
            head = p.strip()[: m.start(1)].rstrip()
            prev = head.split()[-1].lower().strip("\"'") if head.split() else ""
            if prev in _NOT_BEFORE:
                return [p]
            return [head, ph]
    return [p]


def apply_commands(text: str) -> str:
    """Turn command phrases into symbols: a clause that is exactly one command, or a clause that ends with
    new line / new paragraph / question mark / exclamation mark."""
    parts = []
    for p in _CLAUSE.findall(text):
        parts.extend([p] if _SEP.match(p) else _split_trailing(p))
    if not any(_is_cmd(p) for p in parts if not _SEP.match(p)):
        return text
    out = ""            # built text
    cap = False         # capitalise the next letter
    glue_next = False   # an "open" symbol: next word attaches without a space
    for p in parts:
        if _SEP.match(p):
            # separators next to a command are swallowed by it; others kept
            out = out.rstrip(" ") if out and not out.endswith("\n") else out
            if glue_next and (not out or out[-1] in "(\"\n/_@#\\"):
                continue                                    # separator right after an opening symbol or break
            if not out.endswith(tuple(_PUNCT + "\n")) or p.startswith("..."):
                out += p
            if p[-1] in ".!?" and not p.startswith("..."):
                cap = True
            if glue_next and out and out[-1] in "(\"":       # "open bracket, see" -> "(see"
                out = out.rstrip(_PUNCT)
            continue
        cmd = _is_cmd(p)
        if cmd:
            sym, kind = cmd
            out = out.rstrip(" ")
            if kind == "break":
                out = out.rstrip(_PUNCT) if out.endswith(tuple(",;:")) else out
                out += sym
                cap = True
                glue_next = True
            elif kind == "end":
                if not out.endswith(tuple(_PUNCT)):
                    out += sym
                else:
                    if out[-1] in ",;:" or (sym in "!?" and out[-1] == "."):
                        out = out[:-1] + sym          # "fun. Exclamation." -> "fun!"
                if sym in ".!?":
                    cap = True
            elif kind == "open":
                out += (" " if out and not out.endswith(("\n", "(")) else "") + sym
                glue_next = True
            else:
                out += sym
                glue_next = True
            continue
        seg = p.strip()
        if not seg:
            continue
        if cap:
            seg = seg[0].upper() + seg[1:]
            cap = False
        if out and not glue_next and not out.endswith("\n"):
            out += " "
        out += seg
        glue_next = False
    return out


# ------------------------------------------------------------------ smart formatting
_ONES = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen".split())}
_TENS = {w: 10 * (i + 2) for i, w in enumerate("twenty thirty forty fifty sixty seventy eighty ninety".split())}
_SCALE = {"hundred": 100, "thousand": 1000, "million": 10**6, "billion": 10**9}
_KEEP_SCALE = {"lakh", "lakhs", "crore", "crores"}
_NUMWORDS = set(_ONES) | set(_TENS) | set(_SCALE) | _KEEP_SCALE | {"and", "point"}
CURRENCY = {"rupees": "₹", "rupee": "₹", "dollars": "$", "dollar": "$", "euros": "€", "euro": "€",
            "pounds": "£", "pound": "£"}


def _parse_int(words):
    """['twenty','five'] -> 25; ['two','thousand','and','five'] -> 2005; None if it isn't a clean number."""
    total = cur = 0
    seen = False
    for w in words:
        if w == "and":
            continue
        if w in _ONES:
            cur += _ONES[w]
        elif w in _TENS:
            cur += _TENS[w]
        elif w == "hundred":
            cur = max(cur, 1) * 100
        elif w in _SCALE:
            total += max(cur, 1) * _SCALE[w]
            cur = 0
        else:
            return None
        seen = True
    return total + cur if seen else None


def _number_value(words):
    """Words before/after 'point' -> a display string, e.g. 3.5; None if not a number."""
    if "point" in words:
        i = words.index("point")
        whole = _parse_int(words[:i]) if i else 0
        frac = words[i + 1:]
        if whole is None or not frac or not all(w in _ONES and _ONES[w] < 10 for w in frac):
            return None
        return f"{whole}." + "".join(str(_ONES[w]) for w in frac)
    n = _parse_int(words)
    if n is None:
        return None
    return f"{n:,}" if n >= 1000 else str(n)


def _unit_for(tok):
    t = tok.lower()
    if t in ("percent", "percentage") or t == "%":
        return "%"
    return CURRENCY.get(t)


def _format_numbers(text: str) -> str:
    pieces = re.split(r"(\s+|(?<=\w)-(?=\w))", text)
    words = [(k, p) for k, p in enumerate(pieces) if p and not p.isspace() and p != "-"]
    res = list(pieces)
    idx = 0
    while idx < len(words):
        k, w = words[idx]
        core = w.strip(".,;:!?").lower()
        if core in _NUMWORDS and core not in ("and", "point"):
            j = idx
            run = []
            while j < len(words):
                c = words[j][1].strip(".,;:!?").lower()
                if c in _NUMWORDS:
                    run.append(c)
                    if words[j][1][-1:] in ".,;:!?":
                        j += 1
                        break
                    j += 1
                else:
                    break
            while run and run[-1] in ("and", "point"):
                run.pop()
                j -= 1
            while run and run[0] in ("and", "point"):
                run.pop(0)
                idx += 1
            nxt = words[j][1] if j < len(words) else ""
            unit = _unit_for(nxt.strip(".,;:!?")) if nxt else None
            kept = [r for r in run if r in _KEEP_SCALE]
            if unit and run:
                base = [r for r in run if r not in _KEEP_SCALE]
                val = _number_value(base) if base else None
                if val is not None and (not kept or len(kept) == 1 and run[-1] in _KEEP_SCALE):
                    suffix = nxt[len(nxt.rstrip(".,;:!?")):]
                    lead = words[idx][1][:len(words[idx][1]) - len(words[idx][1].lstrip("(\"'"))]
                    scale = f" {kept[0]}" if kept else ""
                    text_out = (val + scale + "%" if unit == "%" else unit + val + scale) + suffix
                    first_k, last_k = words[idx][0], words[j][0]
                    res[first_k] = lead + text_out
                    for q in range(first_k + 1, last_k + 1):
                        res[q] = ""
                    # drop whitespace between the merged pieces
                    idx = j + 1
                    continue
            idx = max(j, idx + 1)
            continue
        idx += 1
    return "".join(res)


_DIGIT_UNIT = re.compile(r"(?<![\w.])(\d[\d,]*(?:\.\d+)?)\s+(percent|per cent|percentage|rupees?|dollars?|euros?|pounds?)\b",
                         re.I)


def _digit_unit(m):
    u = m.group(2).lower().replace("per cent", "percent")
    sym = "%" if u.startswith("percent") else CURRENCY[u]
    return m.group(1) + "%" if sym == "%" else sym + m.group(1)


_TLD = r"(?:com|org|net|io|dev|ai|app|in|co\.in|co\.uk|edu|gov|me|us|uk)"
_EXT = r"(?:py|js|ts|tsx|cs|json|txt|md|yaml|yml|html|css|csv|pdf|docx|xlsx|pptx|sql|sh|bat|exe|zip|png|jpg)"
_EMAIL = re.compile(rf"\b([A-Za-z0-9_.+-]+) at ([A-Za-z0-9-]+(?: dot [A-Za-z0-9-]+)*) dot ({_TLD})\b", re.I)
_DOMAIN = re.compile(rf"\b([A-Za-z0-9-]+(?: dot [A-Za-z0-9-]+)*) dot ({_TLD})\b(?=$|[\s/.,;:!?])", re.I)
_FILE = re.compile(rf"\b([A-Za-z0-9_-]+) dot ({_EXT})\b", re.I)


def _dots(s):
    return re.sub(r"\s+dot\s+", ".", s, flags=re.I)


_PATH = re.compile(rf"\b([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.{_TLD}) slash ([A-Za-z0-9_.-]+(?: slash [A-Za-z0-9_.-]+)*)", re.I)


_AT_RATE = re.compile(r"([^\s,]+),?\s+at[- ]the[- ]rate(?:[- ]of)?(?:[- ](?:sign|symbol))?,?\s+(\S+)", re.I)
_AT_SIGN = re.compile(r"(\S+)\s+at[- ]sign\s+(\S+)", re.I)
_AT_DOMAIN = re.compile(rf"\b([A-Za-z0-9_.+-]+) at ([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.{_TLD})\b", re.I)
_MAIL_WORDS = {"email", "e-mail", "mail", "send", "sent", "contact", "cc", "bcc", "write", "reach", "address",
               "to", "from", "forward"}


def _at_domain(m, text):
    before = text[: m.start()].lower().split()[-5:]
    local = m.group(1)
    if any(w.strip(",.") in _MAIL_WORDS for w in before) or re.search(r"[0-9_.+]", local):
        return f"{local}@{m.group(2)}".lower()
    return m.group(0)


_FUSED = re.compile(rf"\b([A-Za-z0-9_.+-]{{3,}}?)at([A-Za-z0-9-]{{3,}}(?:\.[A-Za-z0-9-]+)*\.{_TLD})\b", re.I)
_FUSE_CONTEXT = {"email", "e-mail", "mail", "send", "sent", "contact", "cc", "bcc", "reach", "address", "forward",
                 "write"}


def _strip_id_words(local: str) -> str:
    """Whisper glues the words before an address onto it: 'emailidjohn' -> 'john'."""
    low = local.lower()
    for w in ("emailaddress", "emailid", "mailid", "email"):
        if low.startswith(w) and len(local) - len(w) >= 2:
            return local[len(w):]
    return local


def _strip_rate(domain: str) -> str:
    """'at the rate' heard as part of the domain: 'threadexample.com', 'therateexample.com' -> 'example.com'."""
    low = domain.lower()
    for w in ("attherate", "therate", "thread", "atrate"):
        if low.startswith(w) and "." in domain[len(w):] and len(domain[len(w):].split(".")[0]) >= 3:
            return domain[len(w):]
    return domain


def _fused(m, text):
    """Whisper often writes a spoken address as one word: 'johnatexample.com'. Split it only in an email context."""
    before = [w.strip(",.:;").lower() for w in text[: m.start()].split()[-4:]]
    if not any(w in _FUSE_CONTEXT for w in before) or len(re.findall("at", m.group(0), re.I)) != 1:
        return m.group(0)
    return f"{_strip_id_words(m.group(1))}@{_strip_rate(m.group(2))}".lower()


_DOTTED = re.compile(rf"\b([A-Za-z][A-Za-z0-9_+-]{{1,30}})\.([A-Za-z0-9-]{{2,}}\.{_TLD})\b(?!@)", re.I)
_ID_CONTEXT = {"email", "e-mail", "mail", "id", "address"}


def _dotted(m, text):
    """'my email id is john.example.com': Whisper dropped the 'at'. Only right after email words."""
    before = [w.strip(",.:;").lower() for w in text[: m.start()].split()[-4:]]
    if "@" in text[max(0, m.start() - 1): m.end() + 1] or not any(w in _ID_CONTEXT for w in before):
        return m.group(0)
    return f"{_strip_id_words(m.group(1))}@{_strip_rate(m.group(2))}".lower()


def _smart_web(text: str) -> str:
    text = _DOTTED.sub(lambda m: _dotted(m, text), text)
    text = _FUSED.sub(lambda m: _fused(m, text), text)
    text = _AT_RATE.sub(lambda m: f"{m.group(1)}@{m.group(2)}", text)
    text = _AT_SIGN.sub(lambda m: f"{m.group(1)}@{m.group(2)}", text)
    text = _AT_DOMAIN.sub(lambda m: _at_domain(m, text), text)
    text = _EMAIL.sub(lambda m: f"{m.group(1)}@{_dots(m.group(2))}.{m.group(3)}".lower(), text)
    text = _DOMAIN.sub(lambda m: f"{_dots(m.group(1))}.{m.group(2)}".lower(), text)
    text = _PATH.sub(lambda m: f"{m.group(1)}/" + re.sub(r"\s+slash\s+", "/", m.group(2), flags=re.I), text)
    return _FILE.sub(lambda m: f"{m.group(1)}.{m.group(2).lower()}", text)


def smart_format(text: str) -> str:
    text = _format_numbers(text)
    text = _DIGIT_UNIT.sub(_digit_unit, text)
    return _smart_web(text)


# A whole dictation that is only an undo phrase removes the last dictation:
# "scratch that", "undo", "undo that line", "delete the last sentence", "remove that", "erase it"...
_UNDO = re.compile(r"(scratch|undo|delete|remove|erase|strike)( (that|it))?"
                   r"( (the )?(last )?(line|sentence|bit|part))?( please)?")


def is_undo(raw: str) -> bool:
    return bool(_UNDO.fullmatch(re.sub(r"[^a-z ]", "", raw.lower()).strip()))
