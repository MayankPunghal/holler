# Contributing to Holler

Thanks for helping. Bug reports, platform reports (especially Linux), docs fixes and pull requests are all welcome.

## Report a problem

Open an issue and include:

- your OS and Python version, and the output of `py -m holler --version` and `py -m holler doctor`
- what you did, what you expected and what happened
- the end of `errors.log` from the data folder (`py -m holler where` prints it). It never contains audio, but it can contain file paths; trim anything private.

## Set up

```
git clone https://github.com/MayankPunghal/holler
cd holler
py -m pip install -e .
```

## Run the tests

The tests use a fake keyboard, microphone and Whisper, so they need no audio hardware:

```
set PYTHONPATH=src          (PowerShell: $env:PYTHONPATH="src")
python tests/test_cleanup.py
python tests/test_vocab.py
python tests/test_app.py
python tests/test_models.py
python tests/test_bench.py
```

CI runs the same files on Linux and Windows. Please add or update a test with your change, and keep `python -m pyflakes src tests` clean.

## Pull requests

- Keep each pull request to one topic and explain the why in the description.
- Match the existing style: small functions, short comments that say why, no new dependency without a good reason (Holler should stay light).
- Windows-specific behaviour (hotkeys, the pill, tray, paste) can't be covered by CI, so say how you checked it by hand.
- User-visible changes need a line in `CHANGELOG.md`.

## Adding a speech engine

Engines live in `src/holler/engines/` and are registered in `ENGINES` in `engines/__init__.py`. An engine is a class with `ensure()`, `unload()`, `__call__(audio, lang, keywords) -> (text, language)`, `last_used`, `name` and `supports_hotwords`. Import its dependency lazily so it stays optional (see `engines/parakeet.py`), add an extra in `pyproject.toml`, test it with a fake module (see `tests/test_bench.py`), and compare it against `small.en` with `holler bench` before proposing it.
