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
    assert bench.wer("rename customerOrderId to orderId", "rename customer order ID to order ID")[0] == 0


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
    E.make_engine = lambda engine, model, beam=2, prompt="": Fake(model, beam)
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


def test_variant_specs_and_prompt_reach_the_engine():
    seen = []
    from holler import models
    models.is_downloaded = lambda n: True                      # no downloads in tests

    class Spy:
        supports_hotwords = True

        def __init__(self, model, beam, prompt):
            seen.append(("init", model, prompt))

        def __call__(self, audio, lang, keywords):
            seen.append(("call", lang))
            return "x", lang or "auto"

        def unload(self):
            pass

    d = tempfile.mkdtemp()
    bench.save_wav(os.path.join(d, "01.wav"), np.zeros(16000, dtype=np.float32))
    open(os.path.join(d, "01.txt"), "w").write("x")
    import holler.engines as E
    old = E.make_engine
    E.make_engine = lambda engine, model, beam=2, prompt="": Spy(model, beam, prompt)
    try:
        bench.run(d, ["small", "small@en+hing", "small@hi"], pipeline=False, say=lambda *a: None)
    finally:
        E.make_engine = old
    assert ("init", "small", "") in seen and ("init", "small", bench.HINGLISH_PROMPT) in seen
    assert [s for s in seen if s[0] == "call"] == [("call", None), ("call", "en"), ("call", "hi")]
    assert len(bench.HINGLISH_PROMPTS) == 12 and bench.default_folder("hinglish").endswith("bench-set-hinglish")


def test_whisper_engine_initial_prompt_and_echo_filter():
    got = {"reply": ""}
    fw = types.ModuleType("faster_whisper")

    class Seg:
        def __init__(self, text):
            self.text = text

    class WM:
        def __init__(self, *a, **k):
            pass

        def transcribe(self, audio, **kw):
            got.update(kw)
            return iter([Seg(got["reply"])]), types.SimpleNamespace(language="hi")

    fw.WhisperModel = WM
    sys.modules["faster_whisper"] = fw
    from holler import models
    models.is_downloaded = lambda n: True
    from holler.engines.whisper import WhisperEngine
    try:
        eng = WhisperEngine("small", 2, initial_prompt="Haan bhai, main kal office aaunga.")
        got["reply"] = "Kal meeting hai"
        text, lang = eng(np.zeros(16000 * 3, dtype=np.float32), None, None)
        assert text == "Kal meeting hai" and got["initial_prompt"].startswith("Haan bhai") and lang == "hi"
        got["reply"] = "Haan bhai, main kal office aaunga."          # the model echoing the prompt back
        assert eng(np.zeros(16000, dtype=np.float32), None, None)[0] == ""
        plain = WhisperEngine("small", 2)
        got.pop("initial_prompt", None)
        got["reply"] = "hello"
        plain(np.zeros(16000, dtype=np.float32), None, None)
        assert "initial_prompt" not in got
    finally:
        del sys.modules["faster_whisper"]


def test_parakeet_engine_with_fake_onnx_asr():
    calls = []
    fake = types.ModuleType("onnx_asr")

    class M:
        def recognize(self, audio, sample_rate=16000):
            calls.append((audio.dtype.name, sample_rate))
            return "  hello world  "

    def load_model(name, quantization=None):
        calls.append(("load", name, quantization))
        return M()

    fake.load_model = load_model
    sys.modules["onnx_asr"] = fake
    try:
        eng = engines.make_engine("parakeet", "small.en")             # a leftover Whisper name -> default Parakeet model
        assert calls[0] == ("load", "nemo-parakeet-tdt-0.6b-v3", "int8")
        text, lang = eng(np.zeros(8000, dtype=np.float64), None, ["ignored"])
        assert text == "hello world" and lang == "auto" and calls[-1] == ("float32", 16000)
        assert eng.supports_hotwords is False
        eng.unload()
        assert eng.m is None
        eng(np.zeros(100, dtype=np.float32), "en", None)       # reloads on demand
        assert eng.m is not None
    finally:
        del sys.modules["onnx_asr"]


def test_parakeet_missing_dependency_message():
    sys.modules["onnx_asr"] = None                                     # import raises ImportError
    try:
        try:
            engines.make_engine("parakeet", "nemo-parakeet-tdt-0.6b-v3")
            raise AssertionError("expected RuntimeError")
        except RuntimeError as e:
            assert "holler[parakeet]" in str(e)
    finally:
        del sys.modules["onnx_asr"]


if __name__ == "__main__":
    test_variant_specs_and_prompt_reach_the_engine()
    test_whisper_engine_initial_prompt_and_echo_filter()
    test_parakeet_engine_with_fake_onnx_asr()
    test_parakeet_missing_dependency_message()
    for t in (test_wer, test_wav_roundtrip_and_load_set, test_registry, test_run_ranks_models):
        t()
    print("ok")
