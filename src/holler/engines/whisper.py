"""Whisper through faster-whisper, with model download fallbacks and idle unloading."""
import os
import threading
import time

import numpy as np

from .. import models
from ..audio import TARGET_SR

class WhisperEngine:
    name = "whisper"
    supports_hotwords = True
    """Local Whisper through faster-whisper (CTranslate2, int8 on CPU). The model can be unloaded when idle
    (frees ~300 MB) and is re-loaded in the background while you are still speaking."""

    def __init__(self, model: str, beam: int):
        self.name, self.beam = model, beam
        base = os.path.basename(model.rstrip("/\\")).lower()
        self.english_only = ".en" in base or base.endswith("-en")
        self.m = None
        self.lock = threading.Lock()
        self.last_used = time.time()
        self.ensure(first=True)

    def ensure(self, first=False):
        with self.lock:
            if self.m is not None:
                return
            from faster_whisper import WhisperModel
            if not models.is_downloaded(self.name):
                models.download(self.name)
            m = WhisperModel(models.model_dir(self.name), device="cpu", compute_type="int8",
                             cpu_threads=min(8, os.cpu_count() or 4))
            if first:
                segs, _ = m.transcribe(np.zeros(TARGET_SR, dtype=np.float32), beam_size=1)
                list(segs)  # warm-up
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
        kwargs = {}
        if keywords:
            kwargs["hotwords"] = ", ".join(keywords)
        segs, info = self.m.transcribe(
            audio,
            language=("en" if self.english_only else lang),
            beam_size=self.beam,
            temperature=0.0,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 400, "speech_pad_ms": 250},
            condition_on_previous_text=False,
            **kwargs,
        )
        text = " ".join(s.text.strip() for s in segs).strip()
        self.last_used = time.time()
        low = text.lower().strip(" .!,")
        if len(audio) < TARGET_SR * 2 and low in HALLUCINATIONS:
            text = ""  # Whisper sometimes invents "Thank you." out of near-silence
        elif keywords and low in {k.lower() for k in keywords}:
            text = ""  # ... or echoes its own glossary back
        return text, info.language


HALLUCINATIONS = {"you", "thank you", "thanks", "thanks for watching", "bye", "thank you for watching"}
