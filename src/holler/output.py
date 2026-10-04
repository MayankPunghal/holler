"""Getting text into the focused app (paste / type), reading the current selection, and the start/stop beeps."""
import sys
import threading
import time

import pyperclip
from pynput import keyboard

kb = keyboard.Controller()


def beep(kind: str):
    if sys.platform != "win32":
        return
    try:
        import winsound
        freq, ms = (1000, 55) if kind == "start" else (700, 55)
        threading.Thread(target=winsound.Beep, args=(freq, ms), daemon=True).start()
    except Exception:
        pass


def paste(text: str, mode: str = "ctrl+v", enter: bool = False):
    """Insert text at the cursor. Modes: ctrl+v (default), ctrl+shift+v (Linux terminals),
    type (keystroke by keystroke: slower, but works where paste is blocked)."""
    if mode == "type":
        kb.type(text)
    else:
        try:
            old = pyperclip.paste()
        except Exception:
            old = None
        pyperclip.copy(text)
        time.sleep(0.05)
        mod = keyboard.Key.cmd if sys.platform == "darwin" else keyboard.Key.ctrl
        if mode == "ctrl+shift+v":
            with kb.pressed(mod, keyboard.Key.shift):
                kb.press("v")
                kb.release("v")
        else:
            with kb.pressed(mod):
                kb.press("v")
                kb.release("v")
        time.sleep(0.15)
        if old is not None:
            pyperclip.copy(old)
    if enter:
        kb.press(keyboard.Key.enter)
        kb.release(keyboard.Key.enter)


def copy_selection(whole_line: bool = False) -> str:
    """Copy whatever is selected in the focused app (Ctrl+C) and restore the clipboard afterwards.
    With whole_line=True and nothing selected, select the current line (Home, Shift+End) and copy that."""
    try:
        old = pyperclip.paste()
    except Exception:
        old = None
    marker = "\x00teach-marker"
    mod = keyboard.Key.cmd if sys.platform == "darwin" else keyboard.Key.ctrl

    def copy():
        pyperclip.copy(marker)
        with kb.pressed(mod):
            kb.press("c")
            kb.release("c")
        time.sleep(0.25)
        try:
            got = pyperclip.paste()
        except Exception:
            got = marker
        return "" if got == marker else got

    sel = copy()
    if not sel and whole_line:
        kb.press(keyboard.Key.home)
        kb.release(keyboard.Key.home)
        with kb.pressed(keyboard.Key.shift):
            kb.press(keyboard.Key.end)
            kb.release(keyboard.Key.end)
        sel = copy()
        kb.press(keyboard.Key.end)       # drop the selection, cursor back at the end of the line
        kb.release(keyboard.Key.end)
    if old is not None:
        pyperclip.copy(old)
    return sel


MASK_VK = 0xE8        # an unassigned virtual key (the one AutoHotkey uses for the same trick)


def mask_win():
    """Windows opens the Start menu or search when the Win key is released alone. A keystroke sent while Win is
    held makes Windows treat it as a shortcut, so releasing Ctrl and Win unevenly no longer opens Start."""
    if sys.platform != "win32":
        return
    try:
        k = keyboard.KeyCode.from_vk(MASK_VK)
        kb.press(k)
        kb.release(k)
    except Exception:
        pass

