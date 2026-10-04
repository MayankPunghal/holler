"""Settings: a JSON file in the data folder, with defaults. The settings window, the wizard and the command line
all read and write the same file."""
import json
import os
from types import SimpleNamespace

from .paths import data_dir

DEFAULTS = {
    "key": "ctrl+win",           # key or chord to hold while speaking
    "hold_ms": 350,              # hold time before recording starts (0 = instantly)
    "teach_key": "ctrl+shift+win",  # hold to learn from the correction on the current line
    "model": "small.en",
    "beam": 2,
    "unload_after": 10,          # idle minutes before the model's memory is freed (0 = never)
    "lang": None,                # None = auto (English-only models always use English)
    "device": None,              # microphone: None = system default, else the device name
    "paste": "ctrl+v",           # ctrl+v | ctrl+shift+v | type
    "enter": False,              # press Enter after each dictation
    "trailing_space": True,
    "cleanup": True,             # remove fillers, resolve spoken self-corrections
    "log": True,                 # keep a local history of dictations (needed for the History tab)
    "overlay": True,             # show the status pill
    "ui": "auto",                # auto | pill | classic
    "sound": True,               # start/stop beeps
    "extra_keywords": "",        # comma-separated, on top of the vocabulary list
    "setup_done": False,
}


def path() -> str:
    return os.path.join(data_dir(), "config.json")


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(path(), encoding="utf-8") as f:
            data = json.load(f)
        cfg.update({k: v for k, v in data.items() if k in DEFAULTS})
        if cfg["teach_key"] == "ctrl+alt+t":      # old default: Ctrl+Alt is AltGr on many layouts and typed a character
            cfg["teach_key"] = DEFAULTS["teach_key"]
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg: dict) -> None:
    data = {k: cfg.get(k, v) for k, v in DEFAULTS.items()}
    tmp = path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path())


def settings(overrides: dict | None = None) -> SimpleNamespace:
    """Saved settings with optional overrides (e.g. from the command line) applied on top."""
    cfg = load()
    cfg.update({k: v for k, v in (overrides or {}).items() if v is not None and k in DEFAULTS})
    return SimpleNamespace(**cfg)
