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


MAX_AUTO = 60


def auto_add(log_path: str, vocab, min_count: int = 3):
    """Add the suggested terms to the vocabulary as glossary-only entries (`~term`: they bias the speech engine
    but never rewrite your text). Capped so the list can't grow without bound. Returns the terms added."""
    have = vocab.keyword_list()
    if sum(1 for k in have if k.startswith("~") and k.lstrip("~") in _auto_marker(vocab)) >= MAX_AUTO:
        return []
    added = []
    for term, _ in suggest(log_path, have, min_count):
        if vocab.add_keyword("~" + term):
            added.append(term)
            _auto_marker(vocab, add=term)
    return added


def _auto_marker(vocab, add=None):
    """Terms added automatically, remembered next to the vocabulary files so the cap counts only them."""
    import os
    path = os.path.join(os.path.dirname(vocab.kw_path), "auto_vocab.txt")
    try:
        have = set(open(path, encoding="utf-8").read().split("\n"))
    except OSError:
        have = set()
    if add:
        have.add(add)
        try:
            open(path, "w", encoding="utf-8").write("\n".join(sorted(h for h in have if h)))
        except OSError:
            pass
    return have
