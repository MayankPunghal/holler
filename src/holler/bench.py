"""`holler bench`: score speech models on YOUR voice and vocabulary.

    holler bench record          read prompts aloud; saved as NN.wav + NN.txt in the bench folder
    holler bench run --models small.en,base.en    transcribe every clip with each model and compare

Public leaderboards don't cover your accent or your jargon, so this is the fair way to pick a model.
"""
import json
import os
import re
import time
import wave

import numpy as np

from .audio import TARGET_SR
from .paths import data_dir

PROMPTS = [
    "Deploy the Lambda function to the Mumbai region and check the CloudWatch logs.",
    "Please mock the repository interface with Moq in the unit test.",
    "The Entity Framework migration failed because the connection string was wrong.",
    "Create a pull request for the feature branch and ask Priya to review it.",
    "We need to migrate this legacy ASP.NET application to dot net ten on Linux.",
    "Schedule the call for Tuesday at three thirty in the afternoon.",
    "The API returns a four hundred and four when the customer ID does not exist.",
    "Open Claude Desktop and paste the transcript into the chat window.",
    "Their Kubernetes cluster runs on Amazon EKS with Terraform managing the infrastructure.",
    "I think we should use PostgreSQL instead of SQL Server for the new service.",
    "Hey, can you send me the invoice for September before Friday?",
    "The quick brown fox jumps over the lazy dog, then reads the documentation.",
]


# ------------------------------------------------------------------ scoring
def normalise(text: str) -> list[str]:
    text = text.lower().replace("-", " ")
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return text.split()


def edit_distance(a: list[str], b: list[str]) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def wer(ref: str, hyp: str) -> tuple[int, int]:
    """(word errors, reference words) after lower-casing and dropping punctuation."""
    r, h = normalise(ref), normalise(hyp)
    return edit_distance(r, h), len(r)


# ------------------------------------------------------------------ clips
def default_folder() -> str:
    return os.path.join(data_dir(), "bench-set")


def save_wav(path: str, audio: np.ndarray):
    pcm = (np.clip(audio, -1, 1) * 32767).astype("<i2")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TARGET_SR)
        w.writeframes(pcm.tobytes())


def load_wav(path: str) -> np.ndarray:
    with wave.open(path, "rb") as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise ValueError(f"{path}: only 16-bit WAV is supported")
    x = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if rate != TARGET_SR:
        n = int(len(x) * TARGET_SR / rate)
        x = np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x).astype(np.float32)
    return x


def load_set(folder: str):
    """[(name, audio, reference text)] for every NN.wav that has an NN.txt beside it."""
    clips = []
    for f in sorted(os.listdir(folder)):
        base, ext = os.path.splitext(f)
        txt = os.path.join(folder, base + ".txt")
        if ext.lower() == ".wav" and os.path.exists(txt):
            with open(txt, encoding="utf-8") as fh:
                clips.append((base, load_wav(os.path.join(folder, f)), fh.read().strip()))
    return clips


def record(folder: str, device=None, prompts=None) -> int:
    """Interactive: show a sentence, record it, save it. Press Enter to start and again to stop; type s to skip, q to quit."""
    import sounddevice as sd
    from .audio import _resolve_device
    os.makedirs(folder, exist_ok=True)
    prompts = prompts or PROMPTS
    dev = _resolve_device(device)
    saved = 0
    print(f"Clips are saved in {folder}\nSpeak naturally, the way you dictate. You can also add your own sentences by "
          "putting NN.wav and NN.txt files in that folder.\n")
    for i, sentence in enumerate(prompts, 1):
        name = f"{i:02d}"
        print(f"[{i}/{len(prompts)}]  {sentence}")
        ans = input("   Enter = record, s = skip, q = quit > ").strip().lower()
        if ans == "q":
            break
        if ans == "s":
            continue
        chunks = []
        with sd.InputStream(samplerate=TARGET_SR, channels=1, dtype="float32", device=dev,
                            callback=lambda indata, f, t, s: chunks.append(indata.copy())):
            input("   Recording... press Enter when done > ")
        if not chunks:
            print("   (nothing recorded)")
            continue
        audio = np.concatenate(chunks)[:, 0]
        save_wav(os.path.join(folder, name + ".wav"), audio)
        with open(os.path.join(folder, name + ".txt"), "w", encoding="utf-8") as fh:
            fh.write(sentence)
        saved += 1
    print(f"\nSaved {saved} clip(s). Next: holler bench run --models small.en,base.en")
    return 0


# ------------------------------------------------------------------ running
def run(folder: str, model_names: list[str], engine: str = "whisper", beam: int = 2, hotwords: bool = True,
        pipeline: bool = True, say=print) -> list[dict]:
    """Transcribe every clip with each model. With `pipeline`, the result goes through your vocabulary
    replacements and Holler's cleanup, i.e. what would actually be pasted."""
    from . import models
    from .cleanup import clean
    from .engines import make_engine
    from .paths import PACKAGE_DATA
    from .vocab import Vocab

    clips = load_set(folder)
    if not clips:
        raise SystemExit(f"No clips in {folder}. Run: holler bench record")
    vocab = Vocab(data_dir(), PACKAGE_DATA)
    keywords = (vocab.prompt_terms() or None) if hotwords else None
    audio_seconds = sum(len(a) for _, a, _ in clips) / TARGET_SR
    results = []
    for name in model_names:
        say(f"\n== {name}")
        if name in models.MODELS and not models.is_downloaded(name):
            say("   downloading...")
            models.download(name, on_progress=lambda f, t: None)
        t0 = time.time()
        eng = make_engine(engine, name, beam)
        load_s = time.time() - t0
        errs = words = 0
        elapsed = 0.0
        worst = []
        for clip, audio, ref in clips:
            t1 = time.time()
            text, _ = eng(audio, None, keywords if getattr(eng, "supports_hotwords", True) else None)
            elapsed += time.time() - t1
            if pipeline:
                text = vocab.apply(text)
                text = clean(text)
            e, n = wer(ref, text)
            errs, words = errs + e, words + n
            if e:
                worst.append((e, clip, ref, text))
        eng.unload()
        worst.sort(reverse=True)
        results.append({
            "model": name, "engine": engine, "wer": round(100 * errs / max(words, 1), 2), "errors": errs, "words": words,
            "seconds_per_clip": round(elapsed / len(clips), 2), "rtf": round(elapsed / max(audio_seconds, 1e-9), 3),
            "load_seconds": round(load_s, 1), "worst": [{"clip": c, "expected": r, "got": g} for _, c, r, g in worst[:3]],
        })
    return results


def table(results: list[dict]) -> str:
    lines = [f"{'model':<18}{'WER %':>8}{'sec/clip':>10}{'xRealtime':>11}{'load s':>8}", "-" * 55]
    for r in sorted(results, key=lambda x: x["wer"]):
        speed = f"{1 / r['rtf']:.1f}x" if r["rtf"] else "-"
        lines.append(f"{r['model']:<18}{r['wer']:>8.2f}{r['seconds_per_clip']:>10.2f}{speed:>11}{r['load_seconds']:>8.1f}")
    lines.append("\nLower WER is better. xRealtime = how many times faster than speaking.")
    return "\n".join(lines)


def save_results(folder: str, results: list[dict]) -> str:
    path = os.path.join(folder, time.strftime("results-%Y%m%d-%H%M%S.json"))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    return path
