"""Self-improvement from your own history: find words you dictate often that look like names or identifiers
and are missing from your vocabulary, so the speech engine can be told about them."""
import re
from collections import Counter

_WORD = re.compile(r"[A-Za-z][A-Za-z0-9_.#+-]{2,}")


def _looks_special(w: str, start_of_sentence: bool) -> bool:
    if any(c.isupper() for c in w[1:]) or any(c.isdigit() for c in w) or "_" in w or "." in w.strip("."):
        return True                                   # xUnit, gRPC, order_id, Program.cs, utf8
    return w[0].isupper() and not start_of_sentence   # a name in the middle of a sentence


def suggest(log_path: str, known, min_count: int = 3, limit: int = 30):
    """Read dictation_log.tsv (time, raw, final) and return [(term, count)] not already known."""
    try:
        lines = open(log_path, encoding="utf-8").read().splitlines()
    except OSError:
        return []
    have = {k.lower().lstrip("~") for k in known}
    stop = {"the", "this", "that", "and", "but", "with", "for", "from", "have", "what", "when", "where", "okay"}
    count, spelling = Counter(), {}
    for ln in lines:
        parts = ln.split("\t")
        if len(parts) < 3:
            continue
        text = parts[2]
        for m in _WORD.finditer(text):
            w = m.group(0).rstrip(".")
            pre = text[:m.start()].rstrip()
            start = not pre or pre[-1] in ".!?\n"
            if len(w) < 3 or w.lower() in have or w.lower() in stop or not _looks_special(w, start):
                continue
            count[w.lower()] += 1
            spelling.setdefault(w.lower(), w)
    return [(spelling[w], n) for w, n in count.most_common(limit) if n >= min_count]
