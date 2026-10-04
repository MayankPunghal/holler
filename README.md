<div align="center">

# Holler

**Hold a key. Holler it. It's typed.**

Free, offline, push-to-talk dictation for your desktop. Hold a key, speak, release, and your words appear at the cursor in any app. It learns your jargon, understands when you correct yourself mid-sentence, and runs Whisper on your own CPU: no account, no cloud, no subscription.

[![PyPI](https://img.shields.io/pypi/v/holler)](https://pypi.org/project/holler/)
[![Tests](https://github.com/MayankPunghal/holler/actions/workflows/tests.yml/badge.svg)](https://github.com/MayankPunghal/holler/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](https://github.com/MayankPunghal/holler/blob/main/LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20(experimental)-lightgrey)

![Holler status pill](https://raw.githubusercontent.com/MayankPunghal/holler/main/docs/pill-demo.gif)

</div>

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Requirements and platform support](#requirements-and-platform-support)
- [Installation](#installation)
- [Using Holler](#using-holler)
- [Teaching it your words](#teaching-it-your-words)
- [Configuration reference](#configuration-reference)
- [Command line reference](#command-line-reference)
- [Speech models](#speech-models)
- [Hinglish and Hindi](#hinglish-and-hindi)
- [Other engines](#other-engines-optional)
- [Benchmarking on your own voice](#benchmarking-on-your-own-voice)
- [If Hugging Face is unavailable](#if-hugging-face-is-unavailable)
- [How it works](#how-it-works)
- [Privacy and security](#privacy-and-security)
- [Troubleshooting and FAQ](#troubleshooting-and-faq)
- [Development](#development)
- [Roadmap](#roadmap)
- [Contributing, changelog, license](#contributing-changelog-license)

## Features

- **Works in every app.** Text is pasted at your cursor, so it works in editors, browsers, terminals, chat apps and anything else you can type into.
- **Private and free.** Audio is processed on your machine and never leaves it. There is no account, no usage limit and no telemetry. The only network use is the one-time model download.
- **Understands self-corrections.** *"Meet at 3, no wait, 4 pm"* becomes *"Meet at 4 pm"*. *"Today is Monday, no no wait, Tuesday"* becomes *"Today is Tuesday"*. Fillers such as "um" and "uh" are dropped.
- **Learns your words.** Add your jargon and names once, or fix a mistake and teach Holler with one chord. *"Mach"* becomes *"Moq"* from then on.
- **Stays out of the way.** A small always-on-top pill shows a live waveform while you speak and a check mark when the text is in. Idle CPU is near zero, and the model's memory is freed after you stop dictating for a while.
- **Resilient model downloads.** Downloads resume, fall back to `curl`, then to a GitHub mirror, and model weights are checked against known checksums. You can point it at your own mirror or load any compatible Whisper model.
- **Measure, don't guess.** `holler bench` scores speech models on your own voice and vocabulary.
- **Proper install.** One `pip` command, a setup wizard, a settings window, a tray icon and start-on-login.

## Quick start

On **Windows 10/11** with [Python 3.10 or newer](https://www.python.org/downloads/) (tick "Add python.exe to PATH" in the installer):

```powershell
py -m pip install holler
py -m holler
```

The first command installs Holler. The second opens the setup wizard, which checks prerequisites, tests your microphone, lets you pick a hotkey and speech model, downloads the model once, and starts Holler in the background. Then hold **Ctrl+`** (Ctrl and the key left of 1), speak, and release.

## Requirements and platform support

| Platform | Status | Notes |
|---|---|---|
| **Windows 10/11** | Supported | Developed and tested here: global hotkeys, the layered status pill, tray icon, paste and start-on-login. |
| **Linux (X11)** | Experimental | The core (audio pipeline, hotkey logic, Whisper, vocabulary, settings UI) is tested on Linux in CI with a fake keyboard and microphone. Real global hotkeys, paste and the tray have **not** been verified on a Linux desktop. Details below. |
| Linux (Wayland) | Not supported | Global key capture generally doesn't work under Wayland. Use an X11 session. |
| macOS | Not supported | Untested. Needs Accessibility and Input Monitoring permissions, and the code paths have not been exercised. |

**Everywhere:** Python 3.10 or newer, a microphone, about 1 GB of free disk for models, and roughly 300 MB of RAM while the default model is loaded (it is freed when idle).

**Linux extras:** install system packages first, for example on Debian or Ubuntu:

```bash
sudo apt install python3-tk libportaudio2 xclip
```

`python3-tk` is for the setup and settings windows, `libportaudio2` for microphone access and `xclip` (or `xsel`) for the clipboard. On Linux the "Win" key is the Super key, which many desktops already use, so choose another chord in Settings (for example `ctrl+shift+space` or `f9`) and use the `ctrl+shift+v` paste mode for terminals. The pill is drawn as a simple always-on-top window instead of the Windows layered pill, and the tray icon needs your desktop's AppIndicator support.

If you try Holler on Linux, please open an issue with what worked and what didn't.

## Installation

### From PyPI (recommended)

```powershell
py -m pip install holler
py -m holler
```

On Linux use `python3 -m pip install holler` (preferably inside a virtual environment or with `pipx`) and `python3 -m holler`.

`py -m holler` is the one command to remember:

- first time: opens the **setup wizard**;
- Holler running: opens **Settings**;
- otherwise: starts Holler **in the background** (you can close the terminal).

You can also click the tray icon, or use the **Holler** entry in the Start menu. If `holler` is on your PATH you can type that instead; `py -m holler` always works, even when Python's Scripts folder isn't on PATH.

### From source

```powershell
git clone https://github.com/MayankPunghal/holler
cd holler
py -m pip install .
py -m holler
```

Mind the dot after `install`: it means "this folder". If you see *"You must give at least one requirement to install"*, the dot is missing.

### Optional extras

```powershell
py -m pip install "holler[parakeet]"    # NVIDIA Parakeet engine (see "Other engines")
```

### Update and uninstall

```powershell
py -m pip install --upgrade holler
py -m holler stop
py -m pip uninstall holler
```

Your settings, vocabulary, history and downloaded models live in the data folder (`%APPDATA%\Holler` on Windows, `~/.config/holler` on Linux; `holler where` prints it). Updating or uninstalling never touches it; delete the folder to remove everything.

## Using Holler

| You do | What happens |
|---|---|
| Hold **Ctrl+`** for about a third of a second, speak, release | The text is pasted at your cursor |
| Quick tap | Nothing (that's what the hold delay is for) |
| Press **Esc** while holding | Cancels the recording |
| Fix a mistake by hand, then press **Ctrl+Shift+Space** | Holler learns the correction |
| Click the tray icon | Settings, pause, quit |

**The status pill** appears while you speak: a live waveform when listening, then "transcribing", and a check mark when the text is in. It also reports a muted or missing microphone instead of silently doing nothing.

**What cleanup does** (switch off with `cleanup: false`):

| You say | You get |
|---|---|
| "um so basically uh we should ship it" | "so basically we should ship it" |
| "Meet at 3, no wait, 4 pm" | "Meet at 4 pm" |
| "Today is Monday, no no wait, Tuesday" | "Today is Tuesday" |
| "the mach library" (with the replacement `mach => Moq`) | "the Moq library" |

**Spoken commands** (on by default; `spoken_commands: false` turns them off). A command works when it stands on its own, which the speech engine marks with commas or a full stop, so pause briefly before and after it:

| You say | You get |
|---|---|
| "Dear team, new paragraph, thanks all." | a blank line, then "Thanks all." |
| "Are you coming, question mark" | "Are you coming?" |
| "open bracket, see note, close bracket" | "(see note)" |
| "Total, colon, five hundred rupees" | "Total: ₹500" |

Also: `new line`, `exclamation mark`, `full stop`, `period`, `comma`, `semicolon`, `open/close quote`, `slash`, `underscore`, `at sign`, `hashtag`. `new line`, `new paragraph`, `question mark` and `exclamation mark` also work at the end of a clause ("it grew by 25% new paragraph, send it..."). A phrase being talked about ("add a new line to the file", "the question mark") is left alone.

**Smart formatting** (on by default; `smart_format: false` turns it off):

| You say | You get |
|---|---|
| "twenty five percent", "three point five percent" | `25%`, `3.5%` |
| "five hundred rupees", "two thousand dollars", "five lakh rupees" | `₹500`, `$2,000`, `₹5 lakh` |
| "john at example dot com", "john at the rate example dot com" | `john@example.com` |
| "github dot com slash holler" | `github.com/holler` |
| "edit main dot py" | `main.py` |

**Punctuation comes from how you speak.** Whisper decides between `.`, `?` and `!` from your wording and intonation, so a question needs a rising tone and a statement a falling one. Short, clearly paced sentences give the best results, and spoken commands give you exact control where it matters.

**Hotkeys.** Any key or chord works: ``ctrl+` ``, `f9`, `scroll_lock`, `right_ctrl`, `ctrl+shift`. The default ``ctrl+` `` (Ctrl and the key left of 1) does nothing in most apps and avoids the Win key (Windows opens the Start menu when Win is released) and Alt (which opens app menus). Holler can't stop a key reaching the app you're in, so if an app uses your chord (VS Code opens its terminal on Ctrl+`), pick another in Settings. Pressing another key within the first second of a recording cancels it, so shortcuts that share keys with your chord still work. Use `holler keys` to see how a key is named.

## Teaching it your words

Whisper itself doesn't learn, so Holler learns the words around it, three ways:

1. **Vocabulary tab.** Add jargon and names (`xUnit`, `Kubernetes`, `Priya`) and "wrong → right" corrections. Your vocabulary is also passed to Whisper as hotwords, which biases decoding toward your terms.
2. **Correct, then press Ctrl+Shift+Space.** Dictate, fix the wrong word in that line, leave the cursor on it, and press Ctrl+Shift+Space. Holler compares what it pasted with your fix and remembers it.
3. **History tab.** Pick a past dictation, fix the text and click *Learn*.

A fix that includes a neighbouring word ("null difference" → "null reference") is learned immediately. A fix to a single ordinary word is learned after you correct it twice, so one odd correction can't break a normal word everywhere.

**It also improves by itself.**
- **Automatic vocabulary.** Every 20 dictations (and at start-up) Holler looks at your local history for identifiers you dictate three or more times (mixed case, digits or underscores, such as `xUnit` or `order_id`) that your vocabulary lacks, and adds them as glossary-only entries (`~Name`), which steer the speech engine but never rewrite your text. At most 60 are added this way. Turn it off with `auto_vocab: false`. `holler suggest` shows what it would pick without adding anything.

**Ready out of the box.** On first run Holler seeds your vocabulary with the examples plus starter packs for web, cloud/DevOps, .NET, Python/data and general tech work (about 170 terms and 40 corrections, such as "cube control" → `kubectl`). They are plain text files in your data folder, so edit or delete anything you don't want. List the packs with `holler packs` and re-add one with `holler import --pack web`.

**How the vocabulary is built.** It is never rebuilt automatically. It starts from the seed above and grows only from what you add: the Vocabulary tab, corrections you teach (methods 2 and 3), and imports. Whisper only reads the *end* of a long glossary, so your own newest terms go last and always win.

**Moving from an older install?** Merge its vocabulary, safely repeatable:

```
holler import C:\Users\you\Documents\old-install-folder
```

It reads that folder's `keywords.txt` and `replacements.txt` and adds only what you don't already have.

## Configuration reference

Most settings are in the **Settings** window (open it with `py -m holler`). Everything lives in `config.json` in the data folder. Command-line flags on `holler run` override it for one session.

| Key | Default | Meaning |
|---|---|---|
| `key` | ``ctrl+` `` | Key or chord to hold while speaking |
| `hold_ms` | `350` | Hold time before recording starts (0 = instantly) |
| `teach_key` | `ctrl+shift+space` | Chord that learns from the correction on the current line |
| `engine` | `whisper` | Speech engine: `whisper`, or `parakeet` (optional extra) |
| `model` | `small.en` | Model name, Hugging Face repo id, or a local folder (see [Speech models](#speech-models)) |
| `beam` | `2` | Whisper beam size (higher is slower, slightly more accurate) |
| `lang` | auto | Language code such as `en` or `hi` (English-only models ignore it) |
| `initial_prompt` | empty | Whisper style hint, used for Hinglish (see [Hinglish and Hindi](#hinglish-and-hindi)) |
| `device` | system default | Microphone name |
| `paste` | `ctrl+v` | `ctrl+v`, `ctrl+shift+v` (Linux terminals) or `type` (keystroke by keystroke, for apps that block paste) |
| `enter` | `false` | Press Enter after each dictation |
| `trailing_space` | `true` | Add a space after each dictation |
| `spoken_commands` | `true` | Stand-alone "new line", "question mark" and similar become symbols |
| `smart_format` | `true` | `25%`, `₹500`, `john@example.com`, `main.py` |
| `auto_vocab` | `true` | Add terms you dictate often to the vocabulary automatically |
| `cleanup` | `true` | Remove fillers and resolve spoken self-corrections |
| `log` | `true` | Keep a local history of dictations (the History tab needs it) |
| `overlay` / `ui` | `true` / `auto` | Show the status pill; `ui` is `auto`, `pill` or `classic` |
| `sound` | `true` | Start and stop beeps (Windows) |
| `unload_after` | `10` | Idle minutes before the model's memory is freed (0 = keep loaded) |
| `extra_keywords` | empty | Comma-separated terms on top of your vocabulary |
| `model_url` | empty | Your own model mirror (see [mirrors](#if-hugging-face-is-unavailable)) |
| `mirror_dir` | empty | Also copy every downloaded model to this folder (for maintainers re-hosting models) |

Environment variables: `HOLLER_HOME` (data folder), `HOLLER_MODEL_URL`, `HOLLER_MIRROR_DIR`, `HOLLER_SKIP_VERIFY=1` (skip model checksum checks).

## Command line reference

| Command | What it does |
|---|---|
| `holler` | Setup wizard on first run; Settings if running; otherwise starts in the background |
| `holler run` | Run in this terminal until you close it (what start-on-login uses). Flags: `--key`, `--hold-ms`, `--teach-key`, `--engine`, `--model`, `--beam`, `--lang`, `--paste`, `--device`, `--no-overlay`, `--no-tray`, `--no-sound`, `--download-only` |
| `holler setup [--text]` | Setup wizard (`--text` for a terminal-only version) |
| `holler settings` | Settings window |
| `holler start` / `stop` / `restart` / `status` | Control the background instance |
| `holler autostart on\|off\|status` | Start with the computer |
| `holler suggest [--add]` | Show terms you dictate often that your vocabulary lacks (this also happens automatically) |
| `holler try TEXT` | Show what Holler would paste for a sentence, no microphone needed |
| `holler doctor [--pill]` | Check prerequisites, microphone, model and hotkey, with fixes (`--pill` plays the pill through its states) |
| `holler keys` | Print the name of each key you press |
| `holler where` | Print the data folder |
| `holler import FOLDER` | Merge vocabulary from an older install |
| `holler import --pack NAME` | Add a bundled starter pack |
| `holler packs` | List starter packs |
| `holler export-model FOLDER [--model NAME \| --all]` | Copy downloaded models out, named for re-hosting |
| `holler bench record\|run` | Compare models on your own voice (see below) |
| `holler --version` | Show the version |

## Speech models

Models download once into the data folder. The default balances accuracy, speed and memory.

| Model | Download | RAM | Notes |
|---|---|---|---|
| `tiny.en` | 75 MB | ~120 MB | Fastest, noticeably less accurate |
| `base.en` | 145 MB | ~170 MB | Light and quick; fine for clear speech |
| **`small.en`** | 484 MB | ~320 MB | **Default:** accurate on accents and jargon |
| `medium.en` | 1.5 GB | ~1.3 GB | Most accurate English; needs a fast PC |
| `tiny`, `base`, `small`, `medium` | as above | as above | Multilingual (Hindi, Hinglish, 90+ languages) |
| `distil-small.en`, `large-v3-turbo` | 330 MB, 1.6 GB | ~250 MB, ~1.7 GB | Experimental |

### Using your own model

Holler runs [faster-whisper](https://github.com/SYSTRAN/faster-whisper), so it accepts any Whisper model converted to CTranslate2 format: distilled models, fine-tunes for an accent or language, or one you converted yourself. In **Settings > Speech model** (an editable box) or `model` in `config.json`, enter either:

- a Hugging Face repo id such as `Systran/faster-distil-whisper-large-v3`, which downloads into the models folder like the built-in ones, or
- a folder on your PC containing `config.json`, `model.bin`, `tokenizer.json` and `vocabulary.txt` (or `vocabulary.json`).

Names containing `.en` or ending in `-en` are treated as English-only.

## Hinglish and Hindi

Use a **multilingual** model (`small`, `medium`; the `.en` models are English only). Whisper decides how to write Hindi words: left on automatic it may output Devanagari or force Hindi words into odd English spellings. Two settings steer it:

- `lang`: `en`, `hi`, or empty for automatic.
- `initial_prompt`: a short Roman-script sample such as `Haan bhai, main kal office aaunga. Meeting ke baad call kar lena, theek hai?` It nudges Whisper to write Hindi in English letters.

Which combination works best depends on your voice, so measure it:

```powershell
py -m holler bench record --set hinglish
py -m holler bench run --set hinglish --models small,small@en+hing,small@hi,medium@en+hing
```

(`@en` and `@hi` set the language; `+hing` adds the built-in Roman-Hinglish prompt.) Hinglish spelling varies a lot (`nahi` against `nahin`), so compare models against each other rather than reading the percentage as an absolute score. India-focused fine-tunes such as [Oriserve's Hindi2Hinglish](https://github.com/OriserveAI/Whisper-Hindi2Hinglish) exist, but they are large and not in the CTranslate2 format Holler loads, so they need converting first.

## Other engines (optional)

Whisper is built in. NVIDIA's Parakeet TDT is available as an extra:

```powershell
py -m pip install "holler[parakeet]"
```

Then pick **parakeet** under *Settings > Speech engine*. It is fast on CPU and does not invent text during silence, but it can't take hotwords, so rely on your replacement rules. In the author's own benchmark it was less accurate than `small.en` on jargon-heavy, Indian-accented English, so run `holler bench` before switching. Engines are plugins (`holler.engines`), so adding another is a small class.

## Benchmarking on your own voice

Leaderboards don't know your accent or your jargon. Measure instead:

```powershell
py -m holler bench record                       # read 24 sentences aloud (once; resumable)
py -m holler bench run --models small.en,base.en,small
py -m holler bench run --models small.en,parakeet:nemo-parakeet-tdt-0.6b-v3
```

It prints word error rate, speed and load time per model and shows the clips each one got wrong. Your vocabulary is included by default (`--no-hotwords` switches it off; `--raw` skips replacements and cleanup). How a number is written (`404` or "four hundred and four") is not counted as an error. You can add your own sentences as `NN.wav` plus `NN.txt` in the bench folder.

Example: one Indian-English speaker, 24 jargon-heavy sentences, CPU laptop. A small sample, so treat differences of a point or two as noise.

| Model | Word error rate | Speed |
|---|---|---|
| `small.en` (default) | 4.9% | 2.5x faster than speaking |
| `base.en` | 5.5% | 7.8x |
| Parakeet TDT 0.6B v3 | 7.9% | 5.6x |

## If Hugging Face is unavailable

Holler downloads a model once; after that it runs fully offline. If the download source ever disappears, these fallbacks apply, in order:

1. **Your own mirror.** Set `model_url` (or `HOLLER_MODEL_URL`) to any server hosting `<name>/<file>`, for example `https://my.host/models` serves `https://my.host/models/small.en/model.bin`. A template with `{name}` and `{file}` also works.
2. **Hugging Face.**
3. **The project mirror** on this repo's [`models` release](https://github.com/MayankPunghal/holler/releases/tag/models), with files named `<model>-<file>`.
4. **Manual install.** Put `config.json`, `model.bin`, `tokenizer.json` and `vocabulary.txt` (or `.json`) in the model's folder, such as `%APPDATA%\Holler\models\small.en\`.

Weights of `small.en`, `base.en` and `small` are checked against pinned SHA-256 checksums. A mirror serving different bytes is skipped; Hugging Face itself is trusted, so upstream updates still work. Maintainers can re-host models with `holler export-model FOLDER --all` or `mirror_dir`.

## How it works

```
 key chord ──▶ hotkey state machine ──▶ recorder ──▶ speech engine ──▶ cleanup ──▶ paste
 (hold 350 ms)  (taps and shortcuts     (always-open   (Whisper, int8,   (fillers,   (clipboard
                 are ignored)             mic, pre-roll) VAD, hotwords)    self-fix,    + Ctrl+V,
                                                                          vocabulary)  then restore)
```

| Technique | Why |
|---|---|
| `faster-whisper`, int8, CPU, beam 2 | Much faster than reference Whisper at nearly the same accuracy |
| Silero VAD | Cuts silence, the main source of hallucinated text ("Thank you.") |
| Temperature 0, no previous-text conditioning | No random fallbacks or repetition loops |
| `hotwords` from your vocabulary | Biases decoding toward your terms |
| Always-open mic, pre-roll and a short tail | First and last words aren't clipped; no start-up lag |
| Gain normalisation, silence detection | Quiet mics still work; a muted mic is reported, not guessed |
| Rule-based post-processing | Casing, replacements, fillers and self-corrections cost microseconds; no LLM needed |
| Idle unload | The model's memory is freed after `unload_after` minutes and reloaded while you speak |

## Privacy and security

- Audio is processed locally and discarded after transcription. It is never saved or sent anywhere.
- Holler makes no network requests except downloading a model (Hugging Face, the GitHub mirror, or a URL you configure). No telemetry, no accounts.
- A local history of your dictations is kept in `dictation_log.tsv` in the data folder so the History tab and learning work. Set `log: false` to stop it, or delete the file.
- To type for you, Holler needs a global keyboard hook, which some antivirus tools flag. It only watches for your chord, and the source is in this repository.
- Dictating into an app running as Administrator requires Holler to run as Administrator too (a Windows rule for all keyboard tools).

Report vulnerabilities as described in [SECURITY.md](https://github.com/MayankPunghal/holler/blob/main/SECURITY.md).

## Troubleshooting and FAQ

**Run `holler doctor` first.** It checks every prerequisite, tests the microphone and tells you how to fix what's wrong. Problems are also logged to `errors.log` in the data folder.

- **`pip install` says "You must give at least one requirement".** You left off the dot in `py -m pip install .`, or the name in `py -m pip install holler`.
- **`holler` is not recognised.** Use `py -m holler`.
- **The hotkey doesn't work in some app.** Choose a different chord in Settings. If the app runs as Administrator, run Holler as Administrator too.
- **The hotkey stops responding after a while, or the tray icon disappears.** Holler restarts itself if it crashes, renews its keyboard hook every 15 minutes and after sleep, and reopens the microphone if it stops delivering audio. If it still happens, send `holler.log` and `crash.log` from the data folder (`holler where`) in an issue. The hotkey also can't see keys typed into a window that runs as Administrator unless Holler does too, and it ignores keystrokes injected by software (so a key remapped by a tool such as AutoHotkey won't trigger it).
- **The Start menu opens when I dictate.** You are using a chord with the Win key (the default before 1.1). Windows opens Start whenever Win is released, so Holler no longer uses it by default; pick another key in Settings, such as ``ctrl+` ``.
- **A letter is typed when I use a chord.** Your layout treats that combination as a character (Ctrl+Alt is AltGr on many layouts). Use a modifier-only chord such as `ctrl+shift`.
- **Nothing is pasted.** Try `paste: "type"` for apps that block paste, or `ctrl+shift+v` for Linux terminals.
- **The pill doesn't show over some app.** Known issue: windows that pin themselves to the top (such as Claude Desktop on some setups) can hide it. Dictation still works.
- **The model download fails.** Holler retries with `curl`, then the project mirror. See [If Hugging Face is unavailable](#if-hugging-face-is-unavailable).
- **It recorded silence or nothing.** The pill says so. Check the microphone in Settings and Windows' privacy settings for microphone access.
- **Is it as good as paid dictation tools?** Accuracy depends on your voice and vocabulary, which is why `holler bench` exists. For many people it is good enough, with the benefit of being offline and free.
- **Does it use my GPU?** Not yet; it is built to be light on CPU.

## Development

```powershell
git clone https://github.com/MayankPunghal/holler
cd holler
py -m pip install -e .
```

Run the tests (they use a fake keyboard, microphone and Whisper, so they need no audio hardware):

```powershell
$env:PYTHONPATH="src"
python tests/test_cleanup.py; python tests/test_vocab.py; python tests/test_app.py; python tests/test_models.py; python tests/test_bench.py; python tests/test_spoken.py; python tests/test_supervise.py
```

CI runs them on Linux and Windows. Project layout:

```
src/holler/
  cli.py          command line and entry points      app.py       hotkey state machine and pipeline
  keys.py         chords and key names               audio.py     microphone capture
  engines/        speech engines (whisper, parakeet) models.py    catalogue, downloads, mirrors, checksums
  cleanup.py      fillers and self-corrections       vocab.py     vocabulary, replacements, learning
  output.py       paste and clipboard                overlay.py   the status pill
  bench.py        holler bench                       doctor.py    holler doctor
  process.py      background run, autostart          tray.py      tray icon
  config.py       settings                           ui/          setup wizard and settings window
tests/            unit and pipeline tests            docs/        images
```

Regenerate the pill images with `python -m holler.overlay --preview docs`.

**Releasing** (maintainers): update `CHANGELOG.md` and the version in `pyproject.toml` and `src/holler/__init__.py`, then publish a GitHub release tagged `vX.Y.Z`. The `publish` workflow builds and uploads to PyPI using trusted publishing.

## Roadmap

- Polish for Linux and the "pill over always-on-top windows" issue
- Hinglish mode as a one-click setting, once measured on real voices
- More optional engines (Moonshine, Qwen3-ASR) if `holler bench` shows they help
- Streaming partial text, GPU support, a Windows installer

## Contributing, changelog, license

Issues and pull requests are welcome; see [CONTRIBUTING.md](https://github.com/MayankPunghal/holler/blob/main/CONTRIBUTING.md). Release notes are in [CHANGELOG.md](https://github.com/MayankPunghal/holler/blob/main/CHANGELOG.md). If Holler saves you time, a star helps others find it.

Built on [faster-whisper](https://github.com/SYSTRAN/faster-whisper) and OpenAI Whisper (both MIT), with pynput, sounddevice, Pillow, pystray and pyperclip. Licensed under the [MIT License](https://github.com/MayankPunghal/holler/blob/main/LICENSE).
