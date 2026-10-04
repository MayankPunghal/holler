<div align="center">

# Holler

**Hold a key. Holler it. It's typed.**

Free, offline, push-to-talk dictation for Windows. Works in every app, learns your jargon, understands when you correct yourself mid-sentence. Powered by Whisper running on your own CPU: no account, no cloud, no subscription.

[![PyPI](https://img.shields.io/pypi/v/holler)](https://pypi.org/project/holler/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)

![Holler status pill](docs/pill-demo.gif)

</div>

## Why Holler

- **Works everywhere.** It pastes at your cursor, so it works in your editor, browser, terminal, Claude, Slack, anywhere you can type.
- **Private and free.** Audio is processed on your machine and never leaves it. No subscription, no usage limits.
- **Understands self-corrections.** Say *"Meet at 3, no wait, 4 pm"* and you get *"Meet at 4 pm"*. *"Today is Monday, no no wait, Tuesday"* becomes *"Today is Tuesday"*. Fillers (um, uh) are dropped.
- **Learns your words.** Add your jargon and names once, or fix a mistake and teach it in one keystroke. *"Mach"* becomes *"Moq"* from then on.
- **Stays out of the way.** A small always-on-top pill shows a live waveform while you speak and a check mark when the text is in. Idle CPU is near zero, and the model's memory is freed when you haven't dictated for a while.
- **Proper install.** One `pip` command, a setup wizard, a settings window, a tray icon, start-with-Windows.

## Install

You need **Windows 10/11** and **Python 3.10 or newer** ([download](https://www.python.org/downloads/); tick "Add python.exe to PATH" in the installer).

**From PyPI** (once published):

```powershell
py -m pip install holler
py -m holler
```

**From source** (this repository):

1. Download or `git clone` the repository and open its folder in File Explorer.
2. Click the folder's address bar, type `cmd` and press Enter. A terminal opens in that folder.
3. Install it. Note the dot at the end: it means "this folder".

   ```powershell
   py -m pip install .
   ```
4. Start it. The setup wizard opens the first time; afterwards it runs quietly in the background and you can close the terminal.

   ```powershell
   py -m holler
   ```

The wizard checks prerequisites, tests your microphone, lets you pick your hotkey and speech model (downloaded once, 75 MB to 1.5 GB) and add your own jargon. When it finishes, hold **Ctrl+Win**, speak, and release. Holler keeps running in the system tray and, if you chose so, starts when you sign in.

`py -m holler` is the one command to remember: the first time it opens the wizard; if Holler is already running it opens **Settings**; otherwise it starts Holler in the background. You can also click the tray icon or use the **Holler** entry in the Start menu.

`py -m holler` is the most reliable way to run it. If `holler` is on your PATH you can type that instead.

Update: `py -m pip install --upgrade holler` (or `py -m pip install --upgrade .` from source). Remove: `py -m holler stop`, then `py -m pip uninstall holler`. Your settings stay in `%APPDATA%\Holler`; delete that folder to remove them too.

## Using it

| You do | What happens |
|---|---|
| Hold **Ctrl+Win** for a third of a second, speak, release | the text is pasted at your cursor |
| Quick tap, or a shortcut such as Ctrl+C / Ctrl+Win+Left | nothing (that's what the hold delay is for) |
| Press **Esc** while holding | cancels the recording |
| Fix a mistake by hand, then hold **Ctrl+Shift+Win** for a moment | Holler learns the correction |
| Click the tray icon | settings, pause, quit |

Everything is configurable in **Settings**: hotkeys, microphone, model, paste method, cleanup, and your vocabulary.

### Teaching it your words

Whisper itself doesn't learn, so Holler learns the words around it, three ways:

1. **Vocabulary tab.** Add jargon and names (`xUnit`, `Kubernetes`, `Priya`) and "wrong → right" corrections.
2. **Correct, then hold Ctrl+Shift+Win.** Dictate, fix the wrong word in that line, leave the cursor on it, hold the three keys for a moment (they only use modifier keys, so nothing is ever typed). Holler compares what it pasted with your fix and remembers it.
3. **History tab.** Pick a past dictation, fix the text, click *Learn*.

A fix that includes a neighbouring word ("null difference" → "null reference") is learned at once. A fix to a single ordinary word is learned after you correct it twice, so one odd correction can't break a normal word everywhere.

## Command line

```
holler                 open: wizard (first time) / settings / start in the background
holler setup           setup wizard             holler settings   settings window
holler start|stop|restart|status                run in the background / control it
holler autostart on|off                         start with Windows
holler doctor          check microphone, model, hotkey and pill, with fixes
holler keys            show the name of each key you press
```

Settings live in `%APPDATA%\Holler` (`holler where` prints the path): `config.json`, `keywords.txt`, `replacements.txt`, history and models. Updating Holler never touches them.

## How it stays accurate without being slow

| Technique | Why |
|---|---|
| `faster-whisper`, int8, CPU, beam 2 | much faster than reference Whisper at nearly the same accuracy |
| Silero VAD | cuts silence, the main source of hallucinated text ("Thank you.") |
| Temperature 0, no previous-text conditioning | no random fallbacks or repetition loops |
| `hotwords` from your vocabulary | biases decoding toward your terms |
| Always-open mic, pre-roll and a short tail | first and last words aren't clipped; no start-up lag |
| Gain normalisation, silence detection | quiet mics still work; a muted mic is reported, not guessed |
| Rule-based post-processing | casing, replacements, fillers and self-corrections cost microseconds, no LLM needed |

Models: `tiny.en`, `base.en`, `small.en` (default, recommended), `medium.en`, and multilingual `small` (Hindi, Hinglish and 90+ languages).

## Troubleshooting

- **`pip install` says "You must give at least one requirement".** You left off the dot: `py -m pip install .`
- **`holler` is not recognised.** Use `py -m holler` instead (it works even when Python's Scripts folder isn't on PATH).
- **Run `holler doctor`** (or `py -m holler doctor`). It checks every prerequisite, tests the microphone, and tells you how to fix what's wrong.
- **Hotkey doesn't work in some app.** Choose a different chord in Settings. Chords of left-side keys are the safest on laptops, many of which lack a Right Ctrl or hide keys behind Fn.
- **Dictating into an app running as Administrator** requires Holler to run as Administrator too (a Windows rule for all keyboard tools).
- **Model download blocked by your network.** Holler retries with Windows' own `curl.exe` and, as a last resort, shows the files to download by hand. See *If Hugging Face is unavailable* below.
- **Problems are logged** to `errors.log` in the data folder.

## If Hugging Face is unavailable

Holler downloads a Whisper model once; after that it runs fully offline. If the download source ever disappears, three fallbacks apply:

1. **Automatic mirror.** Downloads try Hugging Face first, then the copy in this repo's [`models` release](https://github.com/MayankPunghal/holler/releases/tag/models).
2. **Your own mirror.** Set `model_url` in Settings' `config.json`, or the `HOLLER_MODEL_URL` environment variable, to any server that hosts `<name>/<file>` (e.g. `https://my.host/models` serves `https://my.host/models/small.en/model.bin`). A template with `{name}` and `{file}` also works.
3. **Manual install.** Put `config.json`, `model.bin`, `tokenizer.json` and `vocabulary.txt` (or `vocabulary.json`) in the model's folder, e.g. `%APPDATA%\Holler\models\small.en\`. `holler where` prints the data folder. Any CTranslate2 Whisper model works the same way, including ones converted yourself with `ct2-transformers-converter`.

## Development

```powershell
git clone https://github.com/MayankPunghal/holler && cd holler
pip install -e .
python tests/test_cleanup.py && python tests/test_vocab.py && python tests/test_app.py
```

Layout: `src/holler/` has `cli`, `app` (hotkey state machine and pipeline), `keys`, `audio`, `engine`, `models`, `output`, `overlay` (the pill), `cleanup`, `vocab`, `config`, `process`, `tray`, `doctor`, and `ui/` (wizard and settings). The tests run anywhere using a fake keyboard, microphone and Whisper. Regenerate the pill images with `python -m holler.overlay --preview docs`.

## Status and roadmap

Holler is in beta and built for Windows 10/11. The logic is tested; the Windows-specific parts (hotkeys, pill, tray, paste) are checked by hand. macOS and Linux are untested. Ideas: NVIDIA Parakeet as an alternative engine, streaming partial text, GPU support, a Windows installer. Issues and pull requests are welcome, and a star helps others find it.

## Credits

[faster-whisper](https://github.com/SYSTRAN/faster-whisper) and OpenAI Whisper (both MIT), pynput, sounddevice, Pillow, pystray. MIT licensed.
