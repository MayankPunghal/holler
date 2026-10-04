"""Post-processing for dictated text: drop fillers and resolve spoken self-corrections.

    clean("Today is Monday, no, no, wait, today is Tuesday.")  ->  "Today is Tuesday."
    clean("Meet me at 3, no wait, 4 pm")                       ->  "Meet me at 4 pm"
    clean("Um, so uh that's it")                               ->  "So that's it"

Rule-based and offline, so it adds no latency. It works within ONE dictation.
How a correction is resolved, in order:
  1. If the words after the cue start like some earlier words ("today is ..."),
     everything from that earlier spot is replaced.
  2. Else if the replacement starts with a number / a Capitalised word, the last
     number / Capitalised word before the cue is replaced.
  3. Else the last few words of the clause are replaced (as many as were spoken).
"""
import re

FILLERS = {"um", "umm", "uh", "uhh", "uhm", "er", "erm", "hmm", "hmmm", "mm", "mmm", "eh"}

# Cues that nearly always mean "ignore what I just said".
STRONG_CUES = [
    "no no no wait", "no no wait", "no wait", "wait no", "actually no", "no sorry",
    "sorry i mean", "no i mean", "or rather", "i meant", "correction",
    "scratch that", "strike that", "let me rephrase", "let me correct that",
    "make that", "change that to", "no actually", "wait actually", "hang on",
    "oops", "my bad", "no it's", "no it is",
]
# Ambiguous in normal speech: only treated as a correction when the words that
# follow clearly line up with something said earlier.
WEAK_CUES = ["sorry", "i mean", "wait wait", "no no", "okay wait", "ok wait", "oh wait", "um wait",
             "hold on", "wait"]

SCRATCH = {"scratch that", "strike that"}
LITERAL_BEFORE = {"say", "says", "said", "saying", "phrase", "word", "words", "keyword", "keywords", "command",
                  "type", "typed", "write", "wrote"}
STOP1 = {"the", "a", "an", "to", "of", "in", "on", "at", "for", "and", "or", "but", "is", "it", "i", "we", "you",
         "so", "that", "this", "with", "as", "my", "be", "are", "was", "do", "if", "then", "from", "by"}
LOOSE_CUES = {"wait", "hold on", "okay wait", "ok wait", "oh wait", "um wait"}
STUTTER_OK = {"the", "a", "an", "to", "of", "in", "on", "at", "for", "and", "i", "we", "it", "is", "my", "so"}
PRONOUN_I = {"i", "i'm", "i'll", "i've", "i'd"}

_CUES = sorted(
    [(c.split(), True) for c in STRONG_CUES] + [(c.split(), False) for c in WEAK_CUES],
    key=lambda x: -len(x[0]),
)


def _norm(tok: str) -> str:
    return re.sub(r"[^\w']", "", tok.lower().replace("’", "'"))


def _ends_punct(tok: str) -> bool:
    return bool(tok) and tok[-1] in ",.;:?!"


_NUM = re.compile(r"^[^\w]*\d[\d.,:/%]*[a-z%]*[^\w]*$", re.I)


def _is_num(tok: str) -> bool:
    return bool(_NUM.match(tok))


def _unit(tok: str) -> str:
    """Alphabetic suffix of a number token ('9.35am' -> 'am'), else ''."""
    return re.sub(r"[^a-z]", "", re.sub(r"^[^\w]*\d[\d.,:/]*", "", tok.lower()))


def _number_anchor(pre, post):
    """'... 30 seconds, sorry, 300 seconds' -> index in `pre` of the number being corrected, or None.
    Requires the new number to be followed by the same unit word as the old one ('seconds'),
    or to carry the same suffix ('9.35am' / '9.52am')."""
    if not post or not _is_num(post[0]):
        return None
    new_unit = _unit(post[0]) or (_norm(post[1]) if len(post) > 1 else "")
    if not new_unit:
        return None
    for j in range(len(pre) - 1, max(-1, len(pre) - 7), -1):
        if _is_num(pre[j]):
            old_unit = _unit(pre[j]) or (_norm(pre[j + 1]) if j + 1 < len(pre) else "")
            if old_unit == new_unit:
                return j
            return None
    return None


def _find_cue(norms, start):
    for i in range(start, len(norms)):
        for cue, strong in _CUES:
            if norms[i : i + len(cue)] == cue:
                return i, len(cue), strong, " ".join(cue)
    return None


def _clause_start(pre):
    start = 0
    for j in range(len(pre) - 1):
        if _ends_punct(pre[j]):
            start = j + 1
    return start


_ABBREV = {"no.", "nos.", "mr.", "mrs.", "ms.", "dr.", "st.", "vs.", "etc.", "e.g.", "i.e.", "approx.", "dept."}


def _sentence_start(pre):
    """Index of the first word of the sentence that `pre` ends in ("Line No. 2" is one sentence)."""
    start = 0
    for j in range(len(pre) - 1):
        if pre[j][-1:] in ".?!" and pre[j].lower() not in _ABBREV:
            start = j + 1
    return start


def _anchor(pre, post):
    """Index in `pre` where the replacement should begin, or None."""
    pn, qn = [_norm(t) for t in pre], [_norm(t) for t in post]
    for k in (3, 2, 1):
        if len(qn) < k:
            continue
        gram = qn[:k]
        if k == 1 and gram[0] in STOP1:
            continue   # "the", "to", "and" ... appear everywhere: not evidence of a restatement
        for idx in range(len(pn) - k, -1, -1):
            if pn[idx : idx + k] == gram:
                if k == 1 and idx < len(pn) - 10:
                    break
                return idx, "overlap"
    return None


def _shape_anchor(pre, post):
    first = post[0]
    lo = max(0, len(pre) - 6)
    if re.search(r"\d", first):
        for j in range(len(pre) - 1, lo - 1, -1):
            if re.search(r"\d", pre[j]):
                return j
    if first[:1].isupper() and _norm(first) not in PRONOUN_I:
        for j in range(len(pre) - 1, -1, -1):
            if (j >= 1 or len(pre) == 1) and pre[j][:1].isupper() and _norm(pre[j]) not in PRONOUN_I:
                return j
    return None


def _strip_tail(tokens):
    if tokens:
        tokens[-1] = tokens[-1].rstrip(",;:")
    return tokens


def resolve_corrections(tokens):
    scan = 0
    while True:
        norms = [_norm(t) for t in tokens]
        hit = _find_cue(norms, scan)
        if not hit:
            return tokens
        i, n, strong, cue = hit
        if i > 0 and norms[i - 1] in LITERAL_BEFORE:      # "say scratch that to undo": talking about the phrase
            scan = i + n
            continue
        b = i
        while b > 0 and norms[b - 1] == "no":  # swallow "no no no ... wait"
            b -= 1
        pre, post = tokens[:b], tokens[i + n :]

        if not pre:  # nothing to correct before the cue
            if strong:
                tokens, scan = post, 0
            else:  # "I mean, ..." at the start is normal speech
                scan = i + n
            continue

        if not post:
            if cue in SCRATCH:  # "... scratch that" at the end deletes the whole sentence before it
                pre = pre[: _sentence_start(pre)]
            tokens, scan = _strip_tail(list(pre)), len(pre)
            continue

        found = _anchor(pre, post)
        if found and cue in LOOSE_CUES and len(pre) - found[0] > 4:
            found = None  # common words: only a restatement of the clause right before counts
        if not found and cue == "no no":
            # A mis-heard "wait" ("no, no, quick. Today is Monday"): skip up to 2 junk words
            # after the cue, but only if what follows restates something said earlier.
            for skip in (1, 2):
                if len(post) > skip:
                    f = _anchor(pre, post[skip:])
                    if f:
                        found, post = f, post[skip:]
                        break
        if not found and not strong:
            nj = _number_anchor(pre, post)
            if nj is not None:
                found = (nj, "number")
        if found:
            kept = pre[: found[0]]
            # Whisper capitalises the restart as if it began a sentence ("And It is 9:27");
            # give it the case of the words it replaces.
            old_w = pre[found[0]]
            if old_w[:1].islower() and post[0][:1].isupper() and _norm(post[0]) not in PRONOUN_I \
                    and _norm(post[0]) == _norm(old_w):
                post = list(post)
                post[0] = post[0][0].lower() + post[0][1:]
        elif strong:
            j = _shape_anchor(pre, post)
            if j is not None:
                kept = pre[:j]
            elif pre[-1][-1:] in ".?!":
                # A finished sentence plus a vague correction is too ambiguous to
                # rewrite safely: keep both, just drop the cue words.
                post = list(post)
                if post[0][:1].islower():
                    post[0] = post[0][0].upper() + post[0][1:]
                tokens, scan = pre + post, len(pre)
                continue
            else:
                m = 0
                for t in post:
                    m += 1
                    if t[-1:] in ".?!;":
                        break
                avail = len(pre) - _clause_start(pre)
                kept = pre[: len(pre) - min(m, avail)]
        else:  # weak cue without a matching anchor: leave the speech alone
            scan = i + n
            continue

        kept = _strip_tail(list(kept))
        post = list(post)
        if kept and kept[-1][-1:] in ".?!" and post[0][:1].islower():
            post[0] = post[0][0].upper() + post[0][1:]
        tokens, scan = kept + post, len(kept)


def drop_fillers(tokens):
    return [t for t in tokens if _norm(t) not in FILLERS]


def drop_stutters(tokens):
    out = []
    for t in tokens:
        if out and _norm(t) == _norm(out[-1]) and _norm(t) in STUTTER_OK:
            if _ends_punct(t):
                out[-1] = t
            continue
        out.append(t)
    return out


def clean(text: str) -> str:
    text = text.strip()
    if not text:
        return text
    was_cap = text[0].isupper()
    tokens = drop_fillers(text.split())
    tokens = resolve_corrections(tokens)
    tokens = drop_stutters(tokens)
    out = " ".join(tokens).strip()
    if out and was_cap and out[0].islower():
        out = out[0].upper() + out[1:]
    return out
