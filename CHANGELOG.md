# Changelog

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
