"""Model download falls back across mirrors (no network: urls are faked)."""
import os
import sys
import tempfile

os.environ["HOLLER_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from holler import models  # noqa: E402


def test_source_order_and_custom_mirror():
    os.environ.pop("HOLLER_MODEL_URL", None)
    s = models.sources("small.en")
    assert s[0] == models.HF_URL and s[-1] == models.RELEASE_URL
    os.environ["HOLLER_MODEL_URL"] = "https://mirror.example/models"
    try:
        s = models.sources("small.en")
        assert models._url("small.en", "model.bin", s[0]) == "https://mirror.example/models/small.en/model.bin"
        assert s[1] == models.HF_URL
    finally:
        os.environ.pop("HOLLER_MODEL_URL")


def test_falls_back_when_huggingface_is_gone():
    tried = []

    def fake(url, out, progress, cancel):
        tried.append(url)
        if "huggingface.co" in url:
            raise RuntimeError("HTTP Error 404")
        with open(out, "wb") as f:
            f.write(b"x" * 10)
        progress(10)

    old = models._py_download
    models._py_download = fake
    try:
        d = models.download("tiny.en")
    finally:
        models._py_download = old
    assert models.is_downloaded("tiny.en") and os.path.isdir(d)
    assert any("releases/download/models/tiny.en-model.bin" in u for u in tried)
    assert "huggingface" in models.manual_instructions("tiny.en") and "releases" in models.manual_instructions("tiny.en")


def test_custom_models():
    d = tempfile.mkdtemp()
    for f in ("config.json", "model.bin", "tokenizer.json", "vocabulary.json"):
        open(os.path.join(d, f), "w").write("x")
    assert models.is_local(d) and models.is_downloaded(d) and models.model_dir(d) == os.path.abspath(d)
    assert models.download(d) == os.path.abspath(d)               # nothing to fetch for a local folder
    assert models.describe(d) == "local folder" and models.describe("small.en") == "catalogue"
    assert models.describe("owner/name") == "Hugging Face repo"
    assert models.repo_id("large-v3-turbo") == "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
    assert models.repo_id("owner/name") == "owner/name"
    assert models.model_dir("owner/name").endswith("owner_name")
    empty = tempfile.mkdtemp()
    try:
        models.download(empty)
        raise AssertionError("expected an error")
    except RuntimeError:
        pass


def test_auto_mirror_after_download():
    out = tempfile.mkdtemp()
    os.environ["HOLLER_MIRROR_DIR"] = out
    os.environ["HOLLER_SKIP_VERIFY"] = "1"          # fake bytes, real model name

    def fake(url, o, progress, cancel):
        open(o, "wb").write(b"x")
        progress(1)

    old = models._py_download
    models._py_download = fake
    try:
        models.download("base.en")
    finally:
        models._py_download = old
        os.environ.pop("HOLLER_MIRROR_DIR")
        os.environ.pop("HOLLER_SKIP_VERIFY")
    assert os.path.exists(os.path.join(out, "base.en-model.bin")) and os.path.exists(os.path.join(out, "base.en-vocabulary.txt"))


def test_checksum_rejects_bad_mirror_but_accepts_upstream_update():
    import hashlib
    models.expected_sha256 = lambda n, f: hashlib.sha256(b"good-weights").hexdigest() if f == "model.bin" else None
    old = models._py_download

    def run(name, serve):
        def fake(url, out, progress, cancel):
            data = serve(url)
            open(out, "wb").write(data)
            progress(len(data))
        models._py_download = fake
        try:
            return models.download(name)
        finally:
            models._py_download = old

    # 1) a custom mirror serves corrupt bytes -> rejected, Hugging Face is used
    os.environ["HOLLER_MODEL_URL"] = "https://mirror.example/m"
    try:
        d = run("medium.en", lambda u: b"corrupt" if "mirror.example" in u else b"good-weights")
    finally:
        os.environ.pop("HOLLER_MODEL_URL")
    assert open(os.path.join(d, "model.bin"), "rb").read() == b"good-weights"
    # 2) Hugging Face now serves a newer file than the pin -> accepted (upstream update)
    d = run("large-v3-turbo", lambda u: b"newer-upstream-weights")
    assert open(os.path.join(d, "model.bin"), "rb").read() == b"newer-upstream-weights"


def test_pinned_hashes_present():
    import importlib
    importlib.reload(models)
    for n in ("small.en", "base.en", "small"):
        assert len(models.expected_sha256(n, "model.bin")) == 64


def test_one_download_per_model():
    import subprocess, sys as _sys, tempfile as _t
    d = _t.mkdtemp()
    other = subprocess.Popen([_sys.executable, "-c", "import time; time.sleep(5)"])
    try:
        with open(os.path.join(d, ".downloading"), "w") as f:
            f.write(str(other.pid))
        try:
            with models._DownloadLock(d):
                raise AssertionError("a second download must not start while another process holds the lock")
        except RuntimeError as e:
            assert "already being downloaded" in str(e)
    finally:
        other.kill(); other.wait()
    with models._DownloadLock(d):                       # the other process is gone: its lock is stale
        assert os.path.exists(os.path.join(d, ".downloading"))
    assert not os.path.exists(os.path.join(d, ".downloading"))


if __name__ == "__main__":
    test_one_download_per_model()
    test_checksum_rejects_bad_mirror_but_accepts_upstream_update()
    test_pinned_hashes_present()
    test_auto_mirror_after_download()
    test_custom_models()
    test_source_order_and_custom_mirror()
    test_falls_back_when_huggingface_is_gone()
    print("ok")
