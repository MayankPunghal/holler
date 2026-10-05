"""`holler selftest`: check that every part of this install loads (used by the installer build; handy for bug
reports too). With --model, also downloads that model and runs it on a second of silence."""
import importlib
import os
import sys
import time

from . import __version__, process
from .paths import PACKAGE_DATA


def run_selftest(model: str = "", gui: bool = True) -> int:
    fails = []

    def ok(msg):
        print(f"[ ok ] {msg}", flush=True)

    def bad(msg):
        fails.append(msg)
        print(f"[FAIL] {msg}", flush=True)

    print(f"Holler {__version__}  python {sys.version.split()[0]}  "
          f"{'installed app' if process.frozen() else 'python package'}", flush=True)
    for mod in ("numpy", "PIL", "pynput.keyboard", "pynput.mouse", "pyperclip", "pystray", "sounddevice",
                "soxr", "ctranslate2", "faster_whisper", "tokenizers", "onnxruntime", "sv_ttk",
                "holler.app", "holler.tray", "holler.overlay", "holler.ui.settings", "holler.ui.wizard",
                "holler.engines.whisper", "holler.updates"):
        try:
            m = importlib.import_module(mod)
            ok(f"{mod} {getattr(m, '__version__', '')}".rstrip())
        except Exception as e:
            bad(f"{mod}: {type(e).__name__}: {e}")
    try:
        importlib.import_module("onnx_asr")
        ok("onnx_asr (Parakeet engine)")
    except Exception as e:
        print(f"[warn] onnx_asr (Parakeet engine, optional): {e}", flush=True)
    for rel in ("keywords.example.txt", "model-sha256.json", "packs"):
        p = os.path.join(PACKAGE_DATA, rel)
        (ok if os.path.exists(p) else bad)(f"data: {rel}")
    try:
        import faster_whisper
        assets = os.path.join(os.path.dirname(faster_whisper.__file__), "assets")
        onnx = [f for f in os.listdir(assets) if f.endswith(".onnx")]
        (ok if onnx else bad)(f"voice-activity model: {', '.join(onnx) or 'missing'}")
    except Exception as e:
        bad(f"voice-activity model: {e}")
    if gui:
        try:
            import tkinter as tk
            import sv_ttk
            root = tk.Tk()
            root.withdraw()
            sv_ttk.set_theme("light")
            root.destroy()
            ok("window toolkit and theme")
        except Exception as e:
            bad(f"window toolkit: {e}")
        try:
            from .tray import make_icon
            make_icon(size=16), make_icon(True, 64)
            ok("logo")
        except Exception as e:
            bad(f"logo: {e}")
    if model:
        try:
            import numpy as np
            from .engines.whisper import WhisperEngine
            t = time.time()
            eng = WhisperEngine(model, beam=2)
            text = eng(np.zeros(32000, dtype=np.float32), "en", ["Holler"])
            ok(f"model {model} loads and runs ({time.time() - t:.1f}s): {text!r}")
        except Exception as e:
            bad(f"model {model}: {type(e).__name__}: {e}")
    print(f"\n{'All good.' if not fails else f'{len(fails)} problem(s).'}", flush=True)
    return 1 if fails else 0
