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
    "Mayank asked Harshita to reconcile the Kubernetes ingress with the Nginx reverse proxy.",
    "Our SourceFuse team is modernizing a legacy WCF service into a gRPC microservice on AWS Fargate.",
    "Why does the Dockerfile copy the csproj file before running dotnet restore?",
    "Set the retry policy to exponential backoff with a maximum of five attempts and add jitter.",
    "Could you please rename the variable from customerOrderId to orderId across the whole solution?",
    "Rotate the IAM access keys, then update the secrets in Parameter Store and restart the ECS tasks.",
    "In Visual Studio, enable nullable reference types and fix the warnings in the Razor pages.",
    "The Hindi word for tomorrow is kal, but it also means yesterday, which confuses everyone.",
    "Please summarize the quarterly report in three bullet points and email it to the team by end of day.",
    "Run the integration tests against the staging environment before merging to main.",
    "Whisper, Parakeet and Moonshine are all speech recognition models that can run offline.",
    "After the deployment, the p ninety nine latency dropped from eight hundred milliseconds to two hundred.",
]


# The default set: real dictation, built from the mistakes seen in daily use. Each entry is
# (what to SAY, word for word, what should be PASTED). Commands ("new paragraph", "scratch that"), emails,
# numbers, money, times and names are scored on the final text, exactly as Holler would paste it.
DICTATION_PROMPTS = [
    ("Hi, my name is Mayank and my email ID is john at the rate example dot com.",
     "Hi, my name is Mayank and my email ID is john@example.com."),
    ("Send the invoice to accounts at the rate sourcefuse dot com before Friday.",
     "Send the invoice to accounts@sourcefuse.com before Friday."),
    ("I was given a hike of twenty eight percent, which is around forty thousand rupees a year.",
     "I was given a hike of 28%, which is around \u20b940,000 a year."),
    ("I wake up at five fifteen AM and reach the gym by five fifty.",
     "I wake up at 5:15 AM and reach the gym by 5:50."),
    ("This is fun, scratch that, this is really fun.",
     "This is really fun."),
    ("Here is an apple, undo that, here is a mango.",
     "Here is a mango."),
    ("I am about seventy percent confident, actually scratch that, I am twenty percent confident this is production ready.",
     "I am 20% confident this is production ready."),
    ("Dear team, new paragraph, thanks for the quick turnaround on the release.",
     "Dear team\n\nThanks for the quick turnaround on the release."),
    ("Are you coming to the standup tomorrow, question mark",
     "Are you coming to the standup tomorrow?"),
    ("That was a great demo, exclamation mark",
     "That was a great demo!"),
    ("I am genuinely happy with the results, and generally the team agrees.",
     "I am genuinely happy with the results, and generally the team agrees."),
    ("I work at SourceFuse as a senior software engineer on dot net modernization.",
     "I work at SourceFuse as a senior software engineer on .NET modernization."),
    ("My birthday is on the twenty third of January, so I will turn twenty seven next year.",
     "My birthday is on the 23rd of January, so I will turn 27 next year."),
    ("Um, so basically, the meeting is moved to Thursday at three thirty PM.",
     "So basically, the meeting is moved to Thursday at 3:30 PM."),
    ("Save the export as report dot csv and share it on Slack.",
     "Save the export as report.csv and share it on Slack."),
    ("The source code is on github dot com slash holler.",
     "The source code is on github.com/holler."),
    ("Please mock the order repository with Moq and assert it was called once.",
     "Please mock the order repository with Moq and assert it was called once."),
    ("Deploy the Lambda function to the Mumbai region and check the CloudWatch logs.",
     "Deploy the Lambda function to the Mumbai region and check the CloudWatch logs."),
    ("Our Kubernetes cluster runs on Amazon EKS and Terraform manages the infrastructure.",
     "Our Kubernetes cluster runs on Amazon EKS and Terraform manages the infrastructure."),
    ("Mayank asked Harshita to review the Entity Framework migration before the release.",
     "Mayank asked Harshita to review the Entity Framework migration before the release."),
    ("The API returns a four hundred and four when the customer ID does not exist.",
     "The API returns a 404 when the customer ID does not exist."),
    ("Could you rename customerOrderId to orderId across the whole solution?",
     "Could you rename customerOrderId to orderId across the whole solution?"),
    ("Honestly, I think this tool will be production ready by the end of the month.",
     "Honestly, I think this tool will be production ready by the end of the month."),
    ("Okay, it has been a long day, I need to sleep because I have the gym at five fifteen tomorrow morning.",
     "Okay, it has been a long day, I need to sleep because I have the gym at 5:15 tomorrow morning."),
]

# The earlier, plainer sentences (`holler bench record --set basic`).
BASIC_PROMPTS = PROMPTS

HINGLISH_PROMPTS = [
    "Kal subah meeting hai, isliye aaj raat tak report bhej dena.",
    "Yaar, ye bug production mein kaise aa gaya, kisi ne test nahi kiya kya?",
    "Main abhi office se nikal raha hoon, thodi der mein call karta hoon.",
    "Server down ho gaya hai, pehle logs check karo phir restart karna.",
    "Mujhe lagta hai ki hum PostgreSQL use karein, SQL Server bahut mehenga hai.",
    "Aaj ka deployment successful raha, ab client ko email bhej do.",
    "Tum kal Mumbai jaa rahe ho kya, ya meeting online hogi?",
    "Ye function ko refactor karna padega, abhi bahut messy code hai.",
    "Chai peene chalte hain, uske baad hum sprint planning karenge.",
    "Mera laptop bahut slow chal raha hai, shayad RAM kam pad rahi hai.",
    "Pull request merge karne se pehle ek baar review kar lena please.",
    "Bhai, kal Tuesday ko call rakhte hain, haan, Wednesday ko, Tuesday nahi.",
]
# A Roman-script style hint: it nudges Whisper to write Hindi words in English letters instead of Devanagari.
HINGLISH_PROMPT = ("Haan bhai, main kal office aaunga. Meeting ke baad call kar lena, theek hai? "
                   "Abhi deploy kar do aur logs check karo.")


# ------------------------------------------------------------------ scoring
_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
         "seventeen eighteen nineteen").split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _int_words(n: int) -> list[str]:
    if n < 20:
        return [_ONES[n]]
    if n < 100:
        return [_TENS[n // 10]] + ([_ONES[n % 10]] if n % 10 else [])
    if n < 1000:
        return [_ONES[n // 100], "hundred"] + (_int_words(n % 100) if n % 100 else [])
    if n < 1_000_000:
        return _int_words(n // 1000) + ["thousand"] + (_int_words(n % 1000) if n % 1000 else [])
    return [str(n)]


_ORD = {"one": "first", "two": "second", "three": "third", "five": "fifth", "eight": "eighth", "nine": "ninth",
        "twelve": "twelfth"}


def _ordinal(words: list[str]) -> list[str]:
    """['twenty', 'three'] -> ['twenty', 'third'] (23rd is spoken 'twenty third')."""
    last = words[-1]
    if last in _ORD:
        last = _ORD[last]
    elif last.endswith("y"):
        last = last[:-1] + "ieth"
    else:
        last += "th"
    return words[:-1] + [last]


def _spell_numbers(text: str) -> str:
    """'404' -> 'four hundred four', '3.30' / '3:30' -> 'three thirty', so "how a number is written" is not an error."""
    def clock(m):
        h, mm = int(m.group(1)), m.group(2)
        return " " + " ".join(_int_words(h) + ([] if mm == "00" else (["oh"] if mm[0] == "0" else []) + _int_words(int(mm)))) + " "
    text = re.sub(r"\b(\d{1,2})[:.](\d{2})\b", clock, text)
    text = re.sub(r"(?<=\d),(?=\d{3}\b)", "", text)                  # 2,500 -> 2500
    text = re.sub(r"\b(\d+)(st|nd|rd|th)\b", lambda m: " " + " ".join(_ordinal(_int_words(int(m.group(1))))) + " ", text)
    return re.sub(r"\d+", lambda m: " " + " ".join(_int_words(int(m.group()))) + " ", text)


def normalise(text: str) -> list[str]:
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)             # customerOrderId -> customer Order Id (identifiers are spoken as words)
    text = _spell_numbers(text.lower().replace("-", " "))
    text = re.sub(r"[^a-z' ]+", " ", text)
    words = text.split()
    return [w for i, w in enumerate(words) if not (w == "and" and i and words[i - 1] in ("hundred", "thousand"))]


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
def default_folder(kind: str = "english") -> str:
    return os.path.join(data_dir(), "bench-dictation" if kind == "english" else f"bench-set-{kind}")


def prompts_for(kind: str = "english"):
    return {"english": DICTATION_PROMPTS, "basic": BASIC_PROMPTS, "hinglish": HINGLISH_PROMPTS}[kind]


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
    """Interactive: show a sentence, record it, save it. Enter starts and stops; s skips, q quits. Already-recorded prompts are skipped, so you can resume."""
    import sounddevice as sd
    from .audio import _resolve_device
    os.makedirs(folder, exist_ok=True)
    prompts = prompts or DICTATION_PROMPTS
    dev = _resolve_device(device)
    saved = 0
    print(f"Clips are saved in {folder}\nSpeak naturally, the way you dictate. You can also add your own sentences by "
          "putting NN.wav and NN.txt files in that folder.\n")
    print("Read each line exactly as written, including the commands (\"new paragraph\", \"scratch that\", "
          "\"at the rate\"). Clips are scored on what Holler would paste.\n")
    for i, item in enumerate(prompts, 1):
        say, sentence = item if isinstance(item, tuple) else (item, item)
        name = f"{i:02d}"
        if os.path.exists(os.path.join(folder, name + ".wav")):
            continue                                      # already recorded: only the new prompts are asked
        print(f"[{i}/{len(prompts)}]  SAY:  {say}")
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
    """Transcribe every clip with each model. With `pipeline`, the result goes through everything Holler does
    before pasting (vocabulary, cleanup, spoken commands, smart formatting), so it is scored on what you'd get."""
    from . import models
    from .cleanup import clean
    from .engines import make_engine
    from .spoken import apply_commands, smart_format
    from .paths import PACKAGE_DATA
    from .vocab import Vocab

    clips = load_set(folder)
    if not clips:
        raise SystemExit(f"No clips in {folder}. Run: holler bench record")
    vocab = Vocab(data_dir(), PACKAGE_DATA)
    keywords = (vocab.prompt_terms() or None) if hotwords else None
    audio_seconds = sum(len(a) for _, a, _ in clips) / TARGET_SR
    results = []
    for spec in model_names:
        from .engines import ENGINES
        # spec = [engine:]model[@lang][+hing]   e.g. small, small@en+hing, parakeet:nemo-parakeet-tdt-0.6b-v3
        body, plus, flag = spec.partition("+")
        body, at, lang = body.partition("@")
        head, _, tail = body.partition(":")
        eng_name, name = (head, tail) if head in ENGINES else (engine, body)         # (a path like C:\\models has a colon too)
        prompt = HINGLISH_PROMPT if flag == "hing" else ""
        lang = lang or None
        say(f"\n== {spec}")
        if eng_name == "whisper" and name in models.MODELS and not models.is_downloaded(name):
            say("   downloading...")
            models.download(name, on_progress=lambda f, t: None)
        t0 = time.time()
        eng = make_engine(eng_name, name, beam, prompt)
        load_s = time.time() - t0
        errs = words = 0
        elapsed = 0.0
        worst = []
        for clip, audio, ref in clips:
            t1 = time.time()
            text, _ = eng(audio, lang, keywords if getattr(eng, "supports_hotwords", True) else None)
            elapsed += time.time() - t1
            if pipeline:
                text = smart_format(apply_commands(clean(vocab.apply(text))))
            e, n = wer(ref, text)
            errs, words = errs + e, words + n
            if e:
                worst.append((e, clip, ref, text))
        eng.unload()
        worst.sort(reverse=True)
        results.append({
            "model": spec, "engine": eng_name, "wer": round(100 * errs / max(words, 1), 2), "errors": errs, "words": words,
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
