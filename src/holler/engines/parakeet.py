"""NVIDIA Parakeet TDT (CC-BY-4.0) through onnx-asr: ONNX Runtime on CPU, no PyTorch. Optional: pip install holler[parakeet]."""
import os
import threading
import time

import numpy as np

from ..audio import TARGET_SR
from ..paths import data_dir

DEFAULT_MODEL = "nemo-parakeet-tdt-0.6b-v3"


class ParakeetEngine:
    """Multilingual (25 European languages), fast on CPU, and it does not invent text in silence the way Whisper can.
    It has no hotword biasing, so your vocabulary works through the replacement rules and learning instead."""
    name = "parakeet"
    supports_hotwords = False

    def __init__(self, model: str, beam: int = 2, initial_prompt: str = ""):
        # a Whisper name left over in the settings (e.g. small.en) means "use the default Parakeet model"
        self.model_name = model if model.startswith(("nemo-", "t-tech/", "gigaam")) else DEFAULT_MODEL
        self.m = None
        self.lock = threading.Lock()
        self.last_used = time.time()
        self.ensure(first=True)

    def ensure(self, first=False):
        with self.lock:
            if self.m is not None:
                return
            try:
                import onnx_asr
            except ImportError as e:
                raise RuntimeError("The Parakeet engine needs onnx-asr: py -m pip install \"holler[parakeet]\"") from e
            # keep the download inside Holler's own data folder, like the Whisper models
            os.environ.setdefault("HF_HOME", os.path.join(data_dir(), "models", "huggingface"))
            try:
                m = onnx_asr.load_model(self.model_name, quantization="int8")
            except Exception:                       # no int8 build of this model: use the default precision
                m = onnx_asr.load_model(self.model_name)
            if first:
                m.recognize(np.zeros(TARGET_SR, dtype=np.float32), sample_rate=TARGET_SR)       # warm-up
            self.m = m
            self.last_used = time.time()

    def unload(self):
        with self.lock:
            self.m = None
        import gc
        gc.collect()

    def __call__(self, audio, lang, keywords):
        self.ensure()
        self.last_used = time.time()
        out = self.m.recognize(np.asarray(audio, dtype=np.float32), sample_rate=TARGET_SR)
        text = (out if isinstance(out, str) else getattr(out, "text", str(out))).strip()
        self.last_used = time.time()
        return text, lang or "auto"
