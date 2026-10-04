# Changelog

## 1.1.0

**Changed**
- Default keys: hold **Ctrl+Shift** to dictate (was Ctrl+Win, which opened the Start menu on release) and press **Ctrl+Shift+L** to learn a correction (was Ctrl+Shift+Win). Holler keeps the L from the app, so it can't replace the text you selected. Saved Win-key defaults switch over automatically.
- Pressing any other key while recording cancels the recording, so shortcuts that start with the same keys (Ctrl+Shift+T, Ctrl+Shift+Arrow) never paste anything.
- "scratch that" at the end of a dictation removes the whole sentence before it, not just the last word.
- Short clips (under 2.5 s) are transcribed without the vocabulary glossary, which skewed short phrases ("First line" became "FirstLine").

**Added**
- Undo by voice (`voice_undo`): "scratch that", "undo that", "delete that" and similar, said as a dictation on its own, remove the last dictation. It refuses if you typed, clicked or switched windows since the paste, so it never deletes the wrong text. Talking about the phrase ("say scratch that") is left as text.
- Spoken commands (`spoken_commands`, on by default): "new line", "new paragraph", "question mark", "exclamation (mark)", "full stop", "comma", "colon", "open/close bracket", "open/close quote" and more become symbols when said on their own or at the end of a clause. A phrase being talked about ("add a new line", "I said new paragraph") is left alone.
- Smart formatting (`smart_format`, on by default): "twenty five percent" → `25%`, "five hundred rupees" → `₹500`, "john at example dot com" or "john at the rate example dot com" → `john@example.com`, "github dot com slash holler" → `github.com/holler`, "main dot py" → `main.py`. Email addresses that Whisper writes oddly (`johnatexample.com`, `emailidjohnatexample.com`, `john.threadexample.com`, `mayank at theredgmail.com`, or `john.example.com` after "my email id is") are repaired, for any domain ending.
- Learning a correction works on a selected fragment, on a wrapped line holding several dictations, and for any of the last 10 dictations.
- Safer learning: a swap between two ordinary words ("generally" → "genuinely") is never applied to the bare word, only inside a phrase seen in two different dictations; the same fix taught twice in one dictation counts once; correcting a word back removes the earlier rule. Ordinary words are recognised with the speech model's own tokenizer.
- Starter vocabulary packs (web, cloud-devops, dotnet, python-data, general-tech), merged once into your vocabulary. `holler packs` lists them; `holler import --pack NAME` adds one again.
- Automatic vocabulary (`auto_vocab`): identifiers you dictate three or more times (`xUnit`, `order_id`) are added to the glossary. `holler suggest` previews them.
- `holler bench` now uses a real-dictation set by default: emails, "scratch that", "new paragraph", numbers, money, times, names and confusable words, scored on the final pasted text. The older sentences are `--set basic`.
- `holler try "TEXT"` shows what a sentence would be pasted as, without a microphone.
- Changelog link on the PyPI page.

**Fixed**
- Saving settings restarts Holler reliably, also when Settings was opened from the tray (the restart used to close Settings itself before Holler could start again); Settings confirms Holler is back up.
- A dictation containing ₹ or Hindi text could be lost: printing it to the log failed on Windows' default encoding.
- "…, actually scratch that, …" drops the whole phrase before it, so "my email is X, actually scratch that, it's Y" keeps only Y.
- Model downloads: only one download per model at a time (two at once could write a file of the right size with the wrong bytes), every downloaded file is checked against the SHA-256 that Hugging Face publishes, and the progress bar never moves backwards.
- Settings: the model list shows only the selected engine's models, the General tab scrolls and Save is always visible on small screens, and About shows the author and licence.
- Holler runs under a small supervisor that restarts it if it crashes. Output is written to `holler.log` and hard crashes to `crash.log` in the data folder.
- After sleep, the keyboard hook and microphone are renewed. The hotkey no longer stops working because of "ghost" keys (a key-up the hook never saw, such as after Win+L): Holler checks the real key state with Windows and ignores keystrokes injected by software.

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
