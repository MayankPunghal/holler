"""Engine registry and `holler bench` scoring (no microphone, no real model)."""
import os
import sys
import tempfile

os.environ["HOLLER_HOME"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import types  # noqa: E402
sys.modules.setdefault("sounddevice", types.ModuleType("sounddevice"))   # no PortAudio needed for scoring
import numpy as np  # noqa: E402
from holler import bench, engines  # noqa: E402


def test_wer():
    assert bench.wer("Hello, world!", "hello world") == (0, 2)
    assert bench.wer("deploy the lambda function", "deploy a lambda") == (2, 4)      # 1 substitution + 1 deletion
    assert bench.wer("one two", "") == (2, 2)
    # how a number is written is not an error
    assert bench.wer("returns a four hundred and four", "returns a 404")[0] == 0
    assert bench.wer("p ninety nine latency of two thousand five hundred", "P99 latency of 2,500")[0] == 0
    assert bench.wer("at three thirty in the afternoon", "at 3.30 in the afternoon")[0] == 0
    assert bench.wer("at three thirty in the afternoon", "at 3:30 in the afternoon")[0] == 0
    assert bench.wer("two hundred milliseconds", "200 milliseconds")[0] == 0
    assert bench.wer("five attempts", "four attempts")[0] == 1


def test_wav_roundtrip_and_load_set():
    d = tempfile.mkdtemp()
    x = (np.sin(np.linspace(0, 200, 16000)) * 0.3).astype(np.float32)
    bench.save_wav(os.path.join(d, "01.wav"), x)
    open(os.path.join(d, "01.txt"), "w").write("a test sentence")
    bench.save_wav(os.path.join(d, "02.wav"), x)                                      # no .txt -> ignored
    clips = bench.load_set(d)
    assert len(clips) == 1 and clips[0][0] == "01" and clips[0][2] == "a test sentence"
    assert abs(clips[0][1] - x).max() < 1e-3


def test_registry():
    assert "whisper" in engines.ENGINES
    try:
        engines.make_engine("nope", "x")
        raise AssertionError("expected ValueError")
    except ValueError as e:
        assert "Available" in str(e)


def test_run_ranks_models():
    d = tempfile.mkdtemp()
    x = np.zeros(16000, dtype=np.float32)
    for i, ref in enumerate(["deploy the lambda function", "open claude desktop"], 1):
        bench.save_wav(os.path.join(d, f"{i:02d}.wav"), x)
        open(os.path.join(d, f"{i:02d}.txt"), "w").write(ref)

    class Fake:
        supports_hotwords = True

        def __init__(self, model, beam):
            self.good = model == "good"
            self.n = 0

        def __call__(self, audio, lang, keywords):
            refs = ["deploy the lambda function", "open claude desktop"]
            out = refs[self.n % 2] if self.good else "deploy a lambda"
            self.n += 1
            return out, "en"

        def unload(self):
            pass

    import holler.engines as E
    old = E.make_engine
    E.make_engine = lambda engine, model, beam=2: Fake(model, beam)
    try:
        res = bench.run(d, ["good", "bad"], pipeline=False, say=lambda *a: None)
    finally:
        E.make_engine = old
    by = {r["model"]: r for r in res}
    assert by["good"]["wer"] == 0 and by["bad"]["wer"] > 50
    text = bench.table(res)
    assert text.index("good") < text.index("bad")                  # best model listed first
    assert by["bad"]["worst"] and "path" not in text
    assert os.path.exists(bench.save_results(d, res))


if __name__ == "__main__":
    for t in (test_wer, test_wav_roundtrip_and_load_set, test_registry, test_run_ranks_models):
        t()
    print("ok")
