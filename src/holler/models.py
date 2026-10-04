"""Whisper model catalogue and download (with progress, resume, and a curl.exe fallback)."""
import os
import shutil
import subprocess
import threading
import time
import urllib.request

from .paths import data_dir, log_error

# name: (download MB, approx. RAM MB when loaded, speed/accuracy note)
MODELS = {
    "tiny.en":   (75,   120,  "fastest, noticeably less accurate"),
    "base.en":   (145,  170,  "light and quick; fine for clear speech"),
    "small.en":  (484,  320,  "recommended: accurate on accents and jargon"),
    "medium.en": (1530, 1300, "most accurate English, needs a fast PC and 1.3 GB RAM"),
    "small":     (484,  320,  "multilingual (Hindi, Hinglish, 90+ languages)"),
}
REQUIRED = ["config.json", "model.bin", "tokenizer.json"]
VOCAB_FILES = ["vocabulary.txt", "vocabulary.json"]       # one of them exists, depending on the model


def repo_id(name: str) -> str:
    if "/" in name:
        return name
    try:
        from faster_whisper.utils import _MODELS
        return _MODELS[name]
    except Exception:
        return f"Systran/faster-whisper-{name}"


def model_dir(name: str) -> str:
    return os.path.join(data_dir(), "models", name.replace("/", "_"))


def is_downloaded(name: str) -> bool:
    d = model_dir(name)
    return all(os.path.exists(os.path.join(d, f)) for f in REQUIRED) and \
        any(os.path.exists(os.path.join(d, f)) for f in VOCAB_FILES)


def _url(name, fname):
    return f"https://huggingface.co/{repo_id(name)}/resolve/main/{fname}"


def _py_download(url, out, progress, cancel):
    have = os.path.getsize(out) if os.path.exists(out) else 0
    req = urllib.request.Request(url, headers={"User-Agent": "holler"})
    if have:
        req.add_header("Range", f"bytes={have}-")
    with urllib.request.urlopen(req, timeout=30) as r:
        if have and r.status != 206:
            have = 0
        with open(out, "ab" if have else "wb") as f:
            while True:
                if cancel and cancel.is_set():
                    raise InterruptedError("cancelled")
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                progress(len(chunk))


def _curl_download(url, out, progress, cancel):
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        raise RuntimeError("curl not found")
    p = subprocess.Popen([curl, "-L", "--fail", "--silent", "--retry", "8", "--retry-delay", "3",
                          "--retry-all-errors", "-C", "-", "-o", out, url])
    last = os.path.getsize(out) if os.path.exists(out) else 0
    while p.poll() is None:
        if cancel and cancel.is_set():
            p.kill()
            raise InterruptedError("cancelled")
        time.sleep(0.3)
        now = os.path.getsize(out) if os.path.exists(out) else last
        progress(now - last)
        last = now
    if p.returncode != 0:
        raise RuntimeError(f"curl failed (exit {p.returncode}) for {url}")


def download(name: str, on_progress=None, cancel: threading.Event | None = None) -> str:
    """Download a model into the data folder; returns its folder. on_progress(fraction 0..1, text).
    Python's own HTTPS first; if that is reset (some networks do) retries with curl. Resumes partial files."""
    dest = model_dir(name)
    os.makedirs(dest, exist_ok=True)
    total = MODELS.get(name, (500,))[0] * 1e6
    done = [0.0]

    def progress(n):
        done[0] += n
        if on_progress:
            on_progress(min(0.99, done[0] / total), f"{done[0] / 1e6:,.0f} of {total / 1e6:,.0f} MB")

    wanted = REQUIRED + [None]            # None = whichever vocabulary file exists
    for f in wanted:
        cands = [f] if f else VOCAB_FILES
        if any(os.path.exists(os.path.join(dest, c)) for c in cands):
            done[0] += os.path.getsize(os.path.join(dest, next(c for c in cands if os.path.exists(os.path.join(dest, c)))))
            continue
        last_err = None
        for c in cands:
            out = os.path.join(dest, c)
            url = _url(name, c)
            try:
                try:
                    _py_download(url, out + ".part", progress, cancel)
                except InterruptedError:
                    raise
                except Exception as e:
                    if "404" in str(e):
                        raise
                    log_error(f"python download of {c} failed, trying curl")
                    _curl_download(url, out + ".part", progress, cancel)
                os.replace(out + ".part", out)
                last_err = None
                break
            except InterruptedError:
                raise
            except Exception as e:
                last_err = e
                if os.path.exists(out + ".part") and os.path.getsize(out + ".part") == 0:
                    os.remove(out + ".part")
        if last_err is not None:
            raise RuntimeError(f"Could not download {cands[0]}: {last_err}")
    if on_progress:
        on_progress(1.0, "done")
    return dest


def manual_instructions(name: str) -> str:
    return ("Download these files in your browser and put them in\n    " + model_dir(name) + "\n" +
            "".join(f"    {_url(name, f)}\n" for f in REQUIRED + VOCAB_FILES[:1]))
