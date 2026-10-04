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


if __name__ == "__main__":
    test_custom_models()
    test_source_order_and_custom_mirror()
    test_falls_back_when_huggingface_is_gone()
    print("ok")
