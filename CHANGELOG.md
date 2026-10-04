# Changelog

## 0.4.1
- Model weights are verified against pinned SHA-256 checksums (`small.en`, `base.en`, `small`); a source that serves different bytes is skipped and the next one is tried. `HOLLER_SKIP_VERIFY=1` turns it off.
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
