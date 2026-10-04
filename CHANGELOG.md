# Changelog

## 1.1.0 (in development)
- New default keys: hold **Ctrl+Shift** to dictate, **Ctrl+Shift+Space** to learn a correction. The old Win-key defaults are switched over automatically: Windows opens the Start menu whenever Win is released, and no workaround was reliable.
- Spoken commands (`spoken_commands`): "new line", "new paragraph", "question mark", "open bracket" and more become symbols when they stand on their own or end a clause; a phrase being talked about ("add a new line") is left alone.
- Smart formatting (`smart_format`): `25%`, `₹500`, `john@example.com` (also from "at the rate", and "my email id is john.example.com" when Whisper drops the "at"), `github.com/holler`, `main.py`.
- Automatic vocabulary (`auto_vocab`): identifiers you dictate often (3+ times) are added as glossary-only entries. `holler suggest` previews them; `holler try TEXT` shows what a sentence would paste.
- Starter vocabulary packs (web, cloud-devops, dotnet, python-data, general-tech), merged once into every vocabulary. `holler packs`, `holler import --pack NAME`.
- Reliability: a supervisor restarts Holler if it crashes; after sleep the keyboard hook and microphone are renewed and any half-finished state is dropped; "ghost" keys (key-ups the hook never saw, such as after Win+L) are cleared by asking Windows for the real key state; keystrokes injected by software are ignored by the hotkey; a key pressed in the first second of a recording cancels it, so holding the chord before a shortcut doesn't record; output goes to `holler.log`, hard crashes to `crash.log`.
- Short clips (under 2.5 s) are decoded without the glossary, which skewed words such as "First line" into "FirstLine".
- Removed: undo (hotkey and "scratch that" on its own) and learning from undo + redo. Deleting text with simulated Backspaces could not be made reliable across apps (keys reaching the app, menus, focus), and a wrong undo erases good text. "scratch that" inside a dictation still drops what came before it, and at the end of a dictation it now drops the whole sentence before it (not just the last word).

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
