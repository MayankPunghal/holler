"""Microphone capture: an always-open stream with a rolling pre-roll buffer."""
import collections
import time

import numpy as np
import sounddevice as sd

TARGET_SR = 16000
MAX_SECONDS = 120     # longest single recording
MIN_SECONDS = 0.35    # ignore accidental taps
PRE_ROLL_S = 0.30     # audio kept from just BEFORE the key press (so the first word isn't clipped)
TAIL_S = 0.30         # keep recording just AFTER release (so the last word isn't clipped)
BLOCK_S = 0.064


def list_input_devices():
    """Names of the microphones, default first (de-duplicated: Windows lists each one once per audio API)."""
    names = []
    try:
        for d in sd.query_devices():
            if d.get("max_input_channels", 0) > 0 and d["name"] not in names:
                names.append(d["name"])
    except Exception:
        pass
    return names


def _resolve_device(device):
    """A saved microphone name -> device index; None (system default) if unset or unplugged."""
    if not device:
        return None
    try:
        for i, d in enumerate(sd.query_devices()):
            if d.get("max_input_channels", 0) > 0 and d["name"] == device:
                return i
    except Exception:
        pass
    return None


class Recorder:
    """Microphone stays open (audio is discarded unless recording) so there is no start-up lag
    and the moment around the key press is never lost."""

    def __init__(self, on_level, pre_s=PRE_ROLL_S, device=None):
        self.on_level = on_level
        self.device = device
        self.pre_s = pre_s
        self.recording = False
        self.chunks = []
        self.pre = None
        self.rate = TARGET_SR
        self.t0 = 0.0
        self.last_cb = time.time()
        self.stream = self._open()
        self.stream.start()

    def _open(self):
        dev = _resolve_device(self.device)
        for rate in (TARGET_SR, int(sd.query_devices(dev, kind="input")["default_samplerate"])):
            try:
                self.rate = rate
                self.pre = collections.deque(maxlen=max(1, int(self.pre_s / BLOCK_S)))
                return sd.InputStream(samplerate=rate, channels=1, dtype="float32", device=dev,
                                      blocksize=int(rate * BLOCK_S), callback=self._cb)
            except sd.PortAudioError:
                continue
        raise RuntimeError("Could not open the microphone")

    def _cb(self, indata, frames, t, status):
        self.last_cb = time.time()
        x = indata[:, 0].copy()
        if self.recording:
            self.chunks.append(x)
            self.on_level(float(np.sqrt(np.mean(x * x))))
        else:
            self.pre.append(x)

    def healthy(self) -> bool:
        """False if the microphone stream stopped delivering audio (sleep/resume, unplugged or switched device)."""
        return time.time() - self.last_cb < 3.0 and getattr(self.stream, "active", True)

    def reopen(self):
        try:
            self.stream.close()
        except Exception:
            pass
        self.last_cb = time.time()
        self.stream = self._open()
        self.stream.start()

    def start(self):
        self.chunks = list(self.pre)
        self.t0 = time.time()
        self.recording = True

    def discard(self):
        self.recording = False
        self.chunks = []

    def stop(self):
        self.recording = False
        if not self.chunks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(self.chunks)
        self.chunks = []
        if self.rate != TARGET_SR:
            import soxr
            audio = soxr.resample(audio, self.rate, TARGET_SR)
        return audio[: TARGET_SR * MAX_SECONDS].astype(np.float32)


def prepare(audio: np.ndarray):
    """Remove DC offset and lift quiet recordings; return None if it is just silence."""
    if len(audio) == 0:
        return None
    audio = audio - float(np.mean(audio))
    peak = float(np.max(np.abs(audio)))
    if peak < 0.004:          # essentially silence / muted mic
        return None
    if peak < 0.5:            # quiet mic: bring up to a healthy level (max 10x)
        audio = audio * min(0.7 / peak, 10.0)
    return np.clip(audio, -1.0, 1.0).astype(np.float32)
