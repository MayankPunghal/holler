"""Hotkeys: a key or a chord of keys, e.g. "ctrl+win", "f9", "ctrl+shift+win".

Modifier names match either side (ctrl = left or right). A few modifier names are specific: "ctrl_r", "alt_gr".
"""
from pynput import keyboard

K = keyboard.Key


def _group(*names):
    return {getattr(K, n) for n in names if hasattr(K, n)}


GROUPS = {
    "ctrl": _group("ctrl", "ctrl_l", "ctrl_r"),
    "alt": _group("alt", "alt_l", "alt_r"),
    "shift": _group("shift", "shift_l", "shift_r"),
    "win": _group("cmd", "cmd_l", "cmd_r"),
}
ALIASES = {"control": "ctrl", "cmd": "win", "windows": "win", "super": "win", "option": "alt"}


def key_id(key):
    """A comparable identity for a pynput key. Character keys become their lower-case letter, which also
    works while Ctrl is held (when the OS reports a control character instead)."""
    if isinstance(key, keyboard.KeyCode):
        ch = getattr(key, "char", None)
        if ch and ch.isprintable():
            return ch.lower()
        vk = getattr(key, "vk", None)
        if vk and 48 <= vk <= 90:
            return chr(vk).lower()
        return vk
    return key


class Combo:
    """All parts of the combo held at the same time."""

    def __init__(self, spec: str):
        self.spec = spec
        self.slots = []
        for part in spec.lower().replace(" ", "").split("+"):
            part = ALIASES.get(part, part)
            if part in GROUPS:
                self.slots.append(frozenset(GROUPS[part]))
            elif hasattr(K, part):
                self.slots.append(frozenset({getattr(K, part)}))
            elif len(part) == 1:
                self.slots.append(frozenset({part}))
            else:
                raise ValueError(f"Unknown key '{part}' in '{spec}'. Try f9, insert, scroll_lock, ctrl+win, "
                                 "ctrl+alt, ctrl+shift+space ... (run find_key.bat to see key names)")

    @property
    def modifier_only(self) -> bool:
        """True for chords like ctrl+shift+win: holding them never types a character in any app."""
        mods = set().union(*GROUPS.values())
        return all(slot <= mods for slot in self.slots)

    def complete(self, held) -> bool:
        return all(slot & held for slot in self.slots)

    def includes(self, kid) -> bool:
        return any(kid in slot for slot in self.slots)

    def __str__(self):
        return self.spec


def key_name(key) -> str:
    """The name to use in settings for a pynput key (the reverse of Combo parsing)."""
    kid = key_id(key)
    if isinstance(kid, str):
        return kid
    name = getattr(kid, "name", None)
    if name:
        for g, members in GROUPS.items():
            if kid in members:
                return g
        return name
    return repr(key)


def spec_from_keys(keys) -> str:
    """A settings string for a set of pressed keys: modifiers first (ctrl+alt+shift+win), then the rest."""
    names = [key_name(k) for k in keys]
    order = {"ctrl": 0, "alt": 1, "shift": 2, "win": 3}
    uniq = sorted(set(names), key=lambda n: (order.get(n, 9), n))
    return "+".join(uniq)
