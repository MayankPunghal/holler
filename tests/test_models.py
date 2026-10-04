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


if __name__ == "__main__":
    test_source_order_and_custom_mirror()
    test_falls_back_when_huggingface_is_gone()
    print("ok")
