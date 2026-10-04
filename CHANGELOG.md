# Changelog

## Unreleased
- Reliability: Holler now runs under a small supervisor that restarts it if it crashes; it renews the keyboard hook and reopens the microphone after sleep/resume or when they stop responding; output goes to `holler.log` and hard crashes to `crash.log` in the data folder.
- Undo: hold Ctrl+Alt+Win (`undo_key`) or say "scratch that" on its own to delete the last dictation.
- Spoken commands (`spoken_commands`): stand-alone "new line", "new paragraph", "question mark", "open bracket" and more become symbols.
- Smart formatting (`smart_format`): `25%`, `₹500`, `john@example.com`, `github.com/holler`, `main.py`.
- Self-improvement: undo + dictate again learns the correction (`auto_learn`); terms you say often (3+ times) are added to your vocabulary automatically as glossary-only entries (`auto_vocab`). `holler suggest` previews them and `holler try TEXT` shows what a sentence would paste.
- Starter vocabulary packs (web, cloud-devops, dotnet, python-data, general-tech) are seeded on first run, so Holler is useful out of the box. New `holler packs` and `holler import --pack NAME`.
- README: how the vocabulary is built, import example.

## 1.0.0
- First release on PyPI (`pip install holler`). Everything from 0.3 to 0.7: background mode with tray, setup wizard and Settings, model mirrors with checksums, custom models, engine plugins, `holler bench`, optional Parakeet engine, Hinglish prompt support.
- Known issue: the status pill can stay hidden behind Claude Desktop's window on some setups.

## 0.7.0
- Hinglish and Hindi: new `initial_prompt` setting (Whisper) to steer output into Roman script, plus a 12-sentence Hinglish bench set (`holler bench record --set hinglish`).
- `holler bench` variants: `small@en+hing` = model `small`, language en, with the Roman-Hinglish prompt (`@hi`, `@en`, `+hing` can be mixed per model).

## 0.6.1
- `holler bench`: identifiers like `customerOrderId` are compared as the words they are spoken as; example results added to the README.
- CI now runs the tests on Windows as well as Linux.

## 0.6.0
- New optional engine: NVIDIA Parakeet TDT 0.6B v3 through onnx-asr (`pip install "holler[parakeet]"`, ONNX Runtime on CPU, no PyTorch). Choose it in Settings > Speech engine, or `"engine": "parakeet"` in config.json. It has no hotword biasing, so vocabulary applies through the replacement rules.
- `holler bench` compares engines in one run: `--models small.en,parakeet:nemo-parakeet-tdt-0.6b-v3`.
- `holler doctor` checks the chosen engine.

## 0.5.1
- `holler bench`: how a number is written (`404` vs "four hundred and four", `3.30` vs "three thirty") no longer counts as an error; 12 harder prompts added (24 in all); `bench record` resumes and only asks for clips you haven't recorded.

## 0.5.0
- Engines are now plugins (`holler.engines`): Whisper is the first, others register in `ENGINES`. New `engine` setting (default `whisper`).
- `holler bench record` / `holler bench run --models small.en,base.en`: record a dozen sentences once, then score any models on your own voice and vocabulary (word error rate, speed, load time).

## 0.4.1
- Model weights are verified against pinned SHA-256 checksums (`small.en`, `base.en`, `small`); a mirror that serves different bytes is skipped and the next source is tried. Hugging Face itself is trusted: a changed file there is accepted (and noted in errors.log), so upstream updates still work. `HOLLER_SKIP_VERIFY=1` turns it off.
- `mirror_dir` setting: models you download are also copied to that folder, ready for the release mirror.
- Multilingual `tiny`, `base` and `medium` added to the catalogue (alongside `small`).
- `holler export-model FOLDER --all` exports every downloaded catalogue model for mirroring.

## 0.4.0
- Models no longer depend on one host: downloads try your own mirror (`model_url` / `HOLLER_MODEL_URL`), then Hugging Face, then the GitHub `models` release.
- Use your own model: the Settings model box is editable and accepts a Hugging Face repo id or a local folder.
- New experimental catalogue entries: `distil-small.en`, `large-v3-turbo`.
- `holler export-model FOLDER` copies a downloaded model out, named for re-hosting as a mirror.
- Downloads fetch `preprocessor_config.json` when present (needed by large-v3-family models).
- Docs: "Using your own model" and "If Hugging Face is unavailable".

## 0.3.0
- Renamed to Holler; pip-installable package; setup wizard, Settings window, tray icon, background mode.
- Learn chord changed to Ctrl+Shift+Win (Ctrl+Alt+T typed a character on AltGr layouts).
