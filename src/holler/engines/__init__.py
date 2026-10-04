"""Speech-to-text engines. An engine is any object with:

    ensure()                         load the model (downloading it first if needed)
    unload()                         free its memory
    __call__(audio, lang, keywords)  float32 mono 16 kHz -> (text, language)
    .last_used (epoch seconds), .name, .supports_hotwords

Add one by writing a class like `WhisperEngine` and registering it in ENGINES.
"""
import importlib

# name -> "module:Class" (imported lazily, so an engine's dependencies are only needed when it is chosen)
ENGINES = {
    "whisper": "holler.engines.whisper:WhisperEngine",
    "parakeet": "holler.engines.parakeet:ParakeetEngine",       # optional: pip install holler[parakeet]
}
DEFAULT_MODELS = {"whisper": "small.en", "parakeet": "nemo-parakeet-tdt-0.6b-v3"}


def make_engine(engine: str, model: str, beam: int = 2, initial_prompt: str = ""):
    try:
        target = ENGINES[engine]
    except KeyError:
        raise ValueError(f"Unknown engine {engine!r}. Available: {', '.join(ENGINES)}") from None
    mod, cls = target.split(":")
    return getattr(importlib.import_module(mod), cls)(model, beam, initial_prompt)
