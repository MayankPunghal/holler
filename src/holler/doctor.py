"""`holler doctor`: check every prerequisite and say how to fix what is missing."""
import importlib
import sys

from . import config, models, process
from .paths import data_dir

OK, BAD, WARN = "[ ok ]", "[FAIL]", "[warn]"


def _line(mark, text, hint=""):
    print(f"{mark} {text}")
    if hint:
        print(f"       -> {hint}")


def run_doctor() -> int:
    fails = 0
    print(f"Holler doctor    python {sys.version.split()[0]}    data folder: {data_dir()}\n")
    for mod, why, required in (("faster_whisper", "speech recognition", True), ("sounddevice", "microphone", True),
                               ("pynput", "hotkeys and pasting", True), ("pyperclip", "clipboard", True),
                               ("numpy", "audio maths", True), ("PIL", "status pill", True),
                               ("tkinter", "setup wizard and settings window", False),
                               ("pystray", "tray icon", False)):
        try:
            importlib.import_module(mod)
            _line(OK, f"{mod} ({why})")
        except Exception as e:
            if required:
                fails += 1
            _line(BAD if required else WARN, f"{mod} ({why}) is missing: {e}",
                  "pip install --upgrade holler" if required else "optional" + (
                      "; on Linux install your distribution's python3-tk package" if mod == "tkinter" else ""))
    cfg = config.settings()
    # microphone
    try:
        import numpy as np
        import sounddevice as sd
        from .audio import _resolve_device, list_input_devices
        devs = list_input_devices()
        if not devs:
            raise RuntimeError("no microphone found")
        dev = _resolve_device(cfg.device)
        _line(OK, f"microphones: {', '.join(devs[:4])}" + (" ..." if len(devs) > 4 else ""))
        print("       Say something for a second ...", flush=True)
        data = sd.rec(int(1.0 * 16000), samplerate=16000, channels=1, dtype="float32", device=dev)
        sd.wait()
        peak = float(np.max(np.abs(data)))
        if peak < 0.004:
            fails += 1
            _line(BAD, "the microphone delivers silence",
                  "Windows: Settings > Privacy & security > Microphone > allow desktop apps; check it isn't muted")
        else:
            _line(OK, f"microphone works (peak level {peak:.2f})")
    except Exception as e:
        fails += 1
        _line(BAD, f"microphone: {e}")
    # model
    if cfg.engine != "whisper":
        try:
            from .engines import ENGINES
            import importlib
            importlib.import_module(ENGINES[cfg.engine].split(":")[0])
            _line(OK, f"engine {cfg.engine} ({cfg.model}); the model downloads on first start")
        except Exception as e:
            fails += 1
            _line(BAD, f"engine {cfg.engine} is not available: {e}", "for parakeet: py -m pip install \"holler[parakeet]\"")
    elif models.is_downloaded(cfg.model):
        _line(OK, f"model {cfg.model} is downloaded")
    else:
        _line(WARN, f"model {cfg.model} is not downloaded yet", "run: holler setup   (or it downloads on first start)")
    # hotkeys
    try:
        from .keys import Combo
        Combo(cfg.key), Combo(cfg.teach_key)
        _line(OK, f"hotkey: hold {cfg.key} (hold time {cfg.hold_ms} ms); learn-from-correction: {cfg.teach_key}")
    except Exception as e:
        fails += 1
        _line(BAD, f"hotkey setting: {e}", "run: holler settings")
    _line(OK if process.running_pid() else WARN, "running in the background" if process.running_pid() else
          "not running", "" if process.running_pid() else "run: holler start")
    _line(OK if process.autostart_enabled() else WARN,
          "starts with the computer" if process.autostart_enabled() else "does not start with the computer",
          "" if process.autostart_enabled() else "run: holler autostart on")
    # pill
    try:
        from .overlay import make_overlay
        ov = make_overlay(True, cfg.key, cfg.ui, log=lambda m: print("       overlay:", m))
        kind = type(ov).__name__
        _line(OK if kind == "LayeredPill" else WARN, f"status indicator: {kind}",
              "" if kind == "LayeredPill" else "the modern pill needs Windows; elsewhere a plain box is used")
    except Exception as e:
        _line(WARN, f"status indicator: {e}")
    print("Everything needed is in place." if not fails else f"{fails} problem(s) above need fixing.")
    return 1 if fails else 0
