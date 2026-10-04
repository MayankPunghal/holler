"""End-to-end test of the hotkey state machine and the dictate/learn pipeline with a fake keyboard, microphone
and Whisper (no hardware needed): python tests/test_app.py"""
import os
import sys
import tempfile
import threading
import time
import types

import numpy as np

os.environ["HOLLER_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

# ---------------------------------------------------------------- fakes
sd = types.ModuleType("sounddevice")
sd.PortAudioError = type("PortAudioError", (Exception,), {})
sd.query_devices = lambda device=None, kind=None: {"default_samplerate": 48000}


class FakeStream:
    last = None

    def __init__(self, samplerate, channels, dtype, blocksize, callback, device=None):
        self.bs, self.cb = blocksize, callback
        FakeStream.last = self

    def start(self):
        pass


sd.InputStream = FakeStream
sys.modules["sounddevice"] = sd

clip = {"v": "OLD"}
pc = types.ModuleType("pyperclip")
pc.copy = lambda t: clip.__setitem__("v", t)
pc.paste = lambda: clip["v"]
sys.modules["pyperclip"] = pc

LINE = {"v": ""}          # what Ctrl+C returns when the "line" is selected
EVENTS = []               # (time, what)


class KeyCode:
    def __init__(self, char=None, vk=None):
        self.char, self.vk = char, vk


class Key:
    pass


for n in ("ctrl", "ctrl_l", "ctrl_r", "alt", "alt_l", "alt_r", "alt_gr", "shift", "shift_l", "shift_r", "cmd", "cmd_l",
          "cmd_r", "esc", "enter", "home", "end", "left", "f9", "backspace"):
    setattr(Key, n, type("K_" + n, (), {"name": n})())


class Ctl:
    def pressed(self, *m):
        class C:
            def __enter__(s):
                EVENTS.append((time.time(), "down"))

            def __exit__(s, *a):
                EVENTS.append((time.time(), "up"))
        return C()

    def press(self, k):
        EVENTS.append((time.time(), "press " + str(getattr(k, "name", k))))
        if k == "c":
            clip["v"] = LINE["v"] or "\x00teach-marker"

    def release(self, k):
        pass

    def type(self, t):
        pass


kbm = types.ModuleType("pynput.keyboard")
kbm.Key, kbm.KeyCode, kbm.Controller = Key, KeyCode, Ctl
kbm.Listener = lambda **kw: None
pk = types.ModuleType("pynput")
pk.keyboard = kbm
sys.modules["pynput"], sys.modules["pynput.keyboard"] = pk, kbm
sx = types.ModuleType("soxr")
sx.resample = lambda a, r1, r2: np.interp(np.linspace(0, len(a) - 1, int(len(a) * r2 / r1)), np.arange(len(a)), a).astype(np.float32)
sys.modules["soxr"] = sx

RAW = {"v": ""}
fw = types.ModuleType("faster_whisper")


class Seg:
    def __init__(self, t):
        self.text = t


class WhisperModel:
    seen = {}

    def __init__(self, model, **kw):
        pass

    def transcribe(self, audio, **kw):
        WhisperModel.seen = dict(n=len(audio), kw=kw)
        time.sleep(0.1)
        return iter([Seg(RAW["v"])]), types.SimpleNamespace(language="en")


fw.WhisperModel = WhisperModel
sys.modules["faster_whisper"] = fw

from holler import app as appmod, config, audio, models  # noqa: E402

models.is_downloaded = lambda name: True          # no network in tests

audio.TAIL_S = 0.05
cfg = config.settings({"hold_ms": 200, "unload_after": 0.01, "overlay": False, "sound": False})
cfg.overlay, cfg.sound = False, False
app = appmod.App(cfg)
threading.Thread(target=app.boot, daemon=True).start()
threading.Thread(target=app.watchdog, daemon=True).start()
time.sleep(0.5)
st = FakeStream.last
bad = 0


def check(name, ok):
    global bad
    bad += not ok
    print("PASS" if ok else "FAIL", "|", name)


def feed(level, n):
    for _ in range(n):
        st.cb((np.random.randn(st.bs, 1) * level).astype(np.float32), st.bs, None, None)


def log_lines():
    p = os.path.join(app.home, "dictation_log.tsv")
    return open(p, encoding="utf-8").read().strip().split("\n") if os.path.exists(p) else []


CTRL, WIN, ALT = Key.ctrl_l, Key.cmd_l, Key.alt_l
T = KeyCode(char="\x14", vk=84)          # what Windows reports for T while Ctrl is held

# 1. Ctrl+Win held -> dictation pasted
RAW["v"] = "Hello world this is a test."
feed(0.0, 10)
app.on_press(CTRL); app.on_press(WIN); time.sleep(0.3); feed(0.1, 20)
app.on_release(WIN); app.on_release(CTRL); time.sleep(0.7)
check("chord dictation is pasted", log_lines() and log_lines()[-1].split("\t")[2] == "Hello world this is a test.")
check("hotwords/glossary passed to whisper", "hotwords" in WhisperModel.seen["kw"])
n = len(log_lines())

# 2. tap does nothing
app.on_press(CTRL); app.on_press(WIN); time.sleep(0.05); app.on_release(WIN); app.on_release(CTRL); time.sleep(0.4)
check("quick tap ignored", len(log_lines()) == n)

# 3. Ctrl+Win+Left (switch desktop) does nothing
app.on_press(CTRL); app.on_press(WIN); time.sleep(0.05); app.on_press(Key.left); time.sleep(0.4)
app.on_release(Key.left); app.on_release(WIN); app.on_release(CTRL); time.sleep(0.4)
check("Ctrl+Win+Left is not a dictation", len(log_lines()) == n)

# 4. Win+E / Ctrl+C alone do nothing
app.on_press(WIN); app.on_press(KeyCode("e", 69)); time.sleep(0.3); app.on_release(KeyCode("e", 69)); app.on_release(WIN)
app.on_press(CTRL); app.on_press(KeyCode("c", 67)); time.sleep(0.3); app.on_release(KeyCode("c", 67)); app.on_release(CTRL)
time.sleep(0.3)
check("Win+E and Ctrl+C are not dictations", len(log_lines()) == n)

# 5. Esc cancels
RAW["v"] = "should not appear"
app.on_press(CTRL); app.on_press(WIN); time.sleep(0.3); feed(0.1, 10); app.on_press(Key.esc)
app.on_release(WIN); app.on_release(CTRL); time.sleep(0.5)
check("Esc cancels", len(log_lines()) == n)

# 6. paste waits until Win is physically released (Ctrl+V with Win down would open clipboard history)
RAW["v"] = "Second dictation here."
del EVENTS[:]
feed(0.0, 10)
app.on_press(CTRL); app.on_press(WIN); time.sleep(0.3); feed(0.1, 20)
app.on_release(CTRL)
t_win = time.time() + 0.5
time.sleep(0.5); app.on_release(WIN); time.sleep(0.6)
paste_t = [t for t, w in EVENTS if w == "down"]
check("paste only after all chord keys are released", bool(paste_t) and paste_t[0] >= t_win - 0.02)

# 7. model unloaded when idle, reloaded while speaking
time.sleep(1.5)
check("model unloaded when idle", app.engine.m is None)
RAW["v"] = "After unload it still works."
feed(0.0, 10)
app.on_press(CTRL); app.on_press(WIN); time.sleep(0.3); feed(0.1, 20); app.on_release(WIN); app.on_release(CTRL); time.sleep(0.8)
check("works after reload", log_lines()[-1].split("\t")[2] == "After unload it still works.")

# 8. teach: hold Ctrl+Shift+Win, whole-line fallback, learned
RAW["v"] = "Please add a Zorb for the repository and run it."
feed(0.0, 10)
app.on_press(CTRL); app.on_press(WIN); time.sleep(0.3); feed(0.1, 20); app.on_release(WIN); app.on_release(CTRL); time.sleep(0.8)
LINE["v"] = "Earlier text. Please add a Quux for the repository and run it. More after"
calls = {"n": 0}
orig = appmod.copy_selection


def fake_copy(whole_line=False):
    return LINE["v"] if whole_line else ""


appmod.copy_selection = fake_copy
SHIFT = Key.shift_l
app.on_press(CTRL); app.on_press(SHIFT); app.on_press(WIN); time.sleep(0.6)
app.on_release(WIN); app.on_release(SHIFT); app.on_release(CTRL); time.sleep(0.6)
rep = open(os.path.join(app.home, "replacements.txt"), encoding="utf-8").read().lower()
pend = os.path.exists(os.path.join(app.home, "replacements_pending.json"))
check("holding Ctrl+Shift+Win learns from the line", "zorb" in rep or pend)
# a quick tap of the chord must not learn
pend_before = open(os.path.join(app.home, "replacements_pending.json")).read() if pend else ""
app.on_press(CTRL); app.on_press(SHIFT); app.on_press(WIN); time.sleep(0.05)
app.on_release(WIN); app.on_release(SHIFT); app.on_release(CTRL); time.sleep(0.6)
now = open(os.path.join(app.home, "replacements_pending.json")).read() if os.path.exists(os.path.join(app.home, "replacements_pending.json")) else ""
check("quick tap of the learn chord does nothing", now == pend_before)
check("data dir seeded from examples", "x unit => xunit" in rep)


# 9. spoken commands + smart formatting reach the pasted text
def dictate(text, wait=0.8):
    RAW["v"] = text
    feed(0.0, 10)
    app.on_press(CTRL); app.on_press(WIN); time.sleep(0.3); feed(0.1, 20); app.on_release(WIN); app.on_release(CTRL)
    time.sleep(wait)


dictate("Dear team, new paragraph, pay five hundred rupees.")
check("spoken command + smart format", app.pasted and app.pasted[-1][0] == "Dear team\n\nPay \u20b9500. ")

# 10. undo hotkey (hold Ctrl+Alt) deletes exactly the last paste
del EVENTS[:]
npaste = len(app.pasted)
app.on_press(CTRL); app.on_press(ALT); time.sleep(0.6)
app.on_release(ALT); app.on_release(CTRL); time.sleep(0.5)
n_bs = sum(1 for _, w in EVENTS if w == "press backspace")
check("undo hotkey sends one backspace per character", n_bs == len("Dear team\n\nPay \u20b9500. "))
check("undo pops the paste", len(app.pasted) == npaste - 1)

# 11. quick tap of the undo chord does nothing
dictate("Keep this sentence.")
del EVENTS[:]
app.on_press(CTRL); app.on_press(ALT); time.sleep(0.05)
app.on_release(ALT); app.on_release(CTRL); time.sleep(0.6)
check("quick tap of the undo chord does nothing", not any(w == "press backspace" for _, w in EVENTS))

# 12. saying "scratch that" on its own undoes, and is not pasted
del EVENTS[:]
dictate("Scratch that.")
n_bs = sum(1 for _, w in EVENTS if w == "press backspace")
check("spoken 'scratch that' undoes", n_bs == len("Keep this sentence. "))

# 12b. adding Alt while the dictation chord is already recording switches to undo and drops the recording
dictate("Another line for undo.")
del EVENTS[:]
RAW["v"] = "should not appear"
n_before = len(log_lines())
feed(0.0, 10)
app.on_press(CTRL); app.on_press(WIN); time.sleep(0.5); feed(0.1, 10)
app.on_press(ALT); time.sleep(0.6)
app.on_release(ALT); app.on_release(WIN); app.on_release(CTRL); time.sleep(0.6)
n_bs = sum(1 for _, w in EVENTS if w == "press backspace")
check("Alt during recording undoes and drops the recording", n_bs == len("Another line for undo. ") and len(log_lines()) == n_before)

# 13. undo + say it again: the same fix seen twice is learned; a different sentence is not
UNDO = lambda: (app.on_press(CTRL), app.on_press(ALT), time.sleep(0.6), app.on_release(ALT), app.on_release(CTRL), time.sleep(2.0))
for _ in range(2):
    dictate("Please review the Flurb module today.")
    UNDO()
    dictate("Please review the Blurb module today.")
    UNDO()
dictate("Line two.")
UNDO()
dictate("Line three.")
rep = open(os.path.join(app.home, "replacements.txt"), encoding="utf-8").read().lower()
check("different sentence after undo is not learned", "two =>" not in rep and "2nd" not in rep)
pending = rep
check("undo then redo teaches the correction (seen twice)", "flurb => blurb" in rep)

print("ALL OK" if not bad else f"{bad} FAILED")
os._exit(1 if bad else 0)
