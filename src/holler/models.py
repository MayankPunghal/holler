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
    "tiny":      (75,   120,  "multilingual, fastest, noticeably less accurate"),
    "base":      (145,  170,  "multilingual (Hindi, Hinglish, 90+ languages), light and quick"),
    "small":     (484,  320,  "multilingual (Hindi, Hinglish, 90+ languages)"),
    "medium":    (1530, 1300, "multilingual, most accurate of the standard sizes, needs a fast PC and 1.3 GB RAM"),
    "distil-small.en": (330, 250, "experimental: distilled small.en, faster, slightly less accurate"),
    "large-v3-turbo": (1620, 1700, "experimental: near large-v3 accuracy, multilingual, needs a fast PC and ~1.7 GB RAM"),
}
# Repos for catalogue names that are not Systran/faster-whisper-<name>.
REPOS = {
    "large-v3-turbo": "mobiuslabsgmbh/faster-whisper-large-v3-turbo",
    "distil-small.en": "Systran/faster-distil-whisper-small.en",
    "distil-large-v3": "Systran/faster-distil-whisper-large-v3",
}
OPTIONAL = ["preprocessor_config.json"]      # needed by some models (e.g. large-v3 family); skipped if absent
REQUIRED = ["config.json", "model.bin", "tokenizer.json"]
VOCAB_FILES = ["vocabulary.txt", "vocabulary.json"]       # one of them exists, depending on the model


def is_local(name: str) -> bool:
    """True when `name` is a folder on disk holding your own CTranslate2 Whisper model."""
    return os.path.isdir(os.path.expanduser(name))


def describe(name: str) -> str:
    """Where a model setting comes from: catalogue, Hugging Face repo id, or local folder."""
    if name in MODELS:
        return "catalogue"
    return "local folder" if is_local(name) else ("Hugging Face repo" if "/" in name else "unknown name")


def repo_id(name: str) -> str:
    if name in REPOS:
        return REPOS[name]
    if "/" in name:
        return name
    try:
        from faster_whisper.utils import _MODELS
        return _MODELS[name]
    except Exception:
        return f"Systran/faster-whisper-{name}"


def model_dir(name: str) -> str:
    if name not in MODELS and is_local(name):
        return os.path.abspath(os.path.expanduser(name))
    return os.path.join(data_dir(), "models", name.replace("/", "_"))


def is_downloaded(name: str) -> bool:
    d = model_dir(name)
    return all(os.path.exists(os.path.join(d, f)) for f in REQUIRED) and \
        any(os.path.exists(os.path.join(d, f)) for f in VOCAB_FILES)


HF_URL = "https://huggingface.co/{repo}/resolve/main/{file}"
# Safety net: the same files re-hosted as release assets named "<model>-<file>" (e.g. small.en-model.bin).
RELEASE_URL = "https://github.com/MayankPunghal/holler/releases/download/models/{name}-{file}"


def sources(name: str) -> list[str]:
    """URL templates to try, in order: your own mirror, Hugging Face, the GitHub release mirror.
    A template may use {repo}, {name} and {file}. Set `model_url` in config.json or HOLLER_MODEL_URL."""
    custom = os.environ.get("HOLLER_MODEL_URL", "").strip()
    if not custom:
        try:
            from . import config
            custom = (config.load().get("model_url") or "").strip()
        except Exception:
            custom = ""
    out = []
    if custom:
        out.append(custom if "{file}" in custom else custom.rstrip("/") + "/{name}/{file}")
    return out + [HF_URL, RELEASE_URL]


def _url(name, fname, template=None):
    return (template or HF_URL).format(repo=repo_id(name), name=name, file=fname)


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


def installed() -> list[str]:
    """Every Whisper model on disk: catalogue names, Hugging Face ids you downloaded, and other model folders."""
    root = os.path.join(data_dir(), "models")
    out = [n for n in MODELS if is_downloaded(n)]
    try:
        entries = sorted(os.listdir(root))
    except OSError:
        entries = []
    for d in entries:
        path = os.path.join(root, d)
        if d in MODELS or d == "huggingface" or not os.path.isdir(path):
            continue
        try:
            with open(os.path.join(path, "source.txt"), encoding="utf-8") as f:
                name = f.read().strip()
        except OSError:
            name = d.replace("_", "/", 1) if "_" in d else path       # older downloads: owner_name
        if os.path.abspath(model_dir(name)) != os.path.abspath(path):
            name = path
        if is_downloaded(name):
            out.append(name)
    return out


def disk_mb(name: str) -> int:
    total = 0
    for root, _, files in os.walk(model_dir(name)):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return int(total / 1e6)


def delete(name: str) -> None:
    """Remove a downloaded model from the data folder (never a folder of your own outside it)."""
    d = os.path.abspath(model_dir(name))
    root = os.path.abspath(os.path.join(data_dir(), "models"))
    if not d.startswith(root + os.sep):
        raise RuntimeError("only models Holler downloaded can be deleted here")
    shutil.rmtree(d)


def upstream_sha256(name: str) -> dict:
    """{file: sha256} as published by Hugging Face for this model (best effort; {} when offline). Every large file
    on Hugging Face carries its SHA-256, so any model can be checked without a hand-kept list."""
    if os.environ.get("HOLLER_SKIP_VERIFY") or is_local(name):
        return {}
    try:
        import json
        req = urllib.request.Request(f"https://huggingface.co/api/models/{repo_id(name)}/tree/main",
                                     headers={"User-Agent": "holler"})
        with urllib.request.urlopen(req, timeout=10) as r:
            items = json.load(r)
        return {i["path"]: i["lfs"]["oid"] for i in items if isinstance(i, dict) and i.get("lfs", {}).get("oid")}
    except Exception:
        return {}


class _DownloadLock:
    """One download per model at a time. Two processes (say Settings and `holler bench`) writing the same
    partial file produce a file of the right size with the wrong bytes."""

    def __init__(self, dest):
        self.path = os.path.join(dest, ".downloading")

    def __enter__(self):
        from .process import _alive
        while True:
            try:
                fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                return self
            except FileExistsError:
                try:
                    pid = int(open(self.path).read().strip() or 0)
                except (OSError, ValueError):
                    pid = 0
                if pid and pid != os.getpid() and _alive(pid):
                    raise RuntimeError("this model is already being downloaded by another Holler window; "
                                       "wait for it to finish")
                try:
                    os.remove(self.path)                    # left over from a download that was killed
                except OSError:
                    pass

    def __exit__(self, *exc):
        try:
            os.remove(self.path)
        except OSError:
            pass


def download(name: str, on_progress=None, cancel: threading.Event | None = None) -> str:
    """Download a model into the data folder; returns its folder. on_progress(fraction 0..1, text).
    Python's own HTTPS first; if that is reset (some networks do) retries with curl. Resumes partial files."""
    dest = model_dir(name)
    if name not in MODELS and is_local(name):
        if not is_downloaded(name):
            raise RuntimeError(f"{dest} is missing model files (needs {', '.join(REQUIRED)} and a vocabulary file)")
        return dest
    os.makedirs(dest, exist_ok=True)
    with _DownloadLock(dest):
        return _download(name, dest, on_progress, cancel)


def _download(name, dest, on_progress, cancel):
    total = MODELS.get(name, (500,))[0] * 1e6
    upstream = upstream_sha256(name)
    done = [0.0]

    def progress(n):
        if n <= 0:
            return                       # a restarted transfer never moves the bar backwards
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
            for tpl in sources(name):
                url = _url(name, c, tpl)
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
                    if upstream.get(c) and _sha256(out + ".part") != upstream[c]:
                        raise RuntimeError(f"{c} is corrupted (its SHA-256 does not match Hugging Face's)")
                    if not verify(name, c, out + ".part"):
                        if tpl == HF_URL:        # the upstream source: if it changed, that is an update, not an attack
                            log_error(f"{c} from Hugging Face differs from the pinned checksum (upstream updated?); using it")
                        else:
                            raise RuntimeError(f"checksum mismatch for {c} from {url}")
                    os.replace(out + ".part", out)
                    last_err = None
                    break
                except InterruptedError:
                    raise
                except Exception as e:
                    last_err = e
                    log_error(f"{url} failed: {e}")
                    if os.path.exists(out + ".part"):
                        os.remove(out + ".part")      # a different mirror may not support resuming the same bytes
            if last_err is None:
                break
        if last_err is not None:
            raise RuntimeError(f"Could not download {cands[0]}: {last_err}")
    for c in OPTIONAL:
        out = os.path.join(dest, c)
        if os.path.exists(out):
            continue
        for tpl in sources(name):
            try:
                _py_download(_url(name, c, tpl), out + ".part", lambda n: None, cancel)
                os.replace(out + ".part", out)
                break
            except InterruptedError:
                raise
            except Exception:
                if os.path.exists(out + ".part"):
                    os.remove(out + ".part")
    if name not in MODELS:
        try:
            with open(os.path.join(dest, "source.txt"), "w", encoding="utf-8") as f:
                f.write(name)                           # so Settings can show "owner/name", not a folder name
        except OSError:
            pass
    _auto_mirror(name)
    if on_progress:
        on_progress(1.0, "done")
    return dest


def expected_sha256(name: str, fname: str):
    """Known SHA-256 of a model file (only the weights, `model.bin`, are pinned), or None."""
    try:
        import json
        from .paths import PACKAGE_DATA
        with open(os.path.join(PACKAGE_DATA, "model-sha256.json"), encoding="utf-8") as f:
            return json.load(f).get(name, {}).get(fname)
    except Exception:
        return None


def _sha256(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify(name: str, fname: str, path: str) -> bool:
    """True if the file matches the pinned checksum (or none is pinned, or HOLLER_SKIP_VERIFY=1).
    Pins protect mirrors (yours, custom, GitHub release); a changed Hugging Face file is accepted with a log note."""
    want = expected_sha256(name, fname)
    if not want or os.environ.get("HOLLER_SKIP_VERIFY"):
        return True
    return _sha256(path) == want


def export(name: str, folder: str) -> list[str]:
    """Copy a downloaded catalogue model into `folder`, named <model>-<file> (the layout of the release mirror)."""
    src = model_dir(name)
    os.makedirs(folder, exist_ok=True)
    out = []
    for f in sorted(os.listdir(src)):
        if not f.endswith(".part"):
            shutil.copy2(os.path.join(src, f), os.path.join(folder, f"{name}-{f}"))
            out.append(f"{name}-{f}")
    return out


def _auto_mirror(name: str):
    """After a download, copy the model to `mirror_dir` (config.json or HOLLER_MIRROR_DIR) when one is set."""
    try:
        folder = os.environ.get("HOLLER_MIRROR_DIR", "").strip()
        if not folder:
            from . import config
            folder = (config.load().get("mirror_dir") or "").strip()
        if folder and name in MODELS:
            export(name, os.path.expanduser(folder))
    except Exception as e:
        log_error(f"mirror copy of {name} failed: {e}")


def manual_instructions(name: str) -> str:
    files = REQUIRED + VOCAB_FILES[:1]
    msg = "Download these files in your browser and put them in\n    " + model_dir(name) + "\n"
    msg += "".join(f"    {_url(name, f)}\n" for f in files)
    msg += "If Hugging Face is unavailable, the same files are mirrored here (named <model>-<file>):\n"
    msg += "".join(f"    {_url(name, f, RELEASE_URL)}\n" for f in files)
    return msg + "(for the mirror, save each file under its plain name, e.g. model.bin)\n"
