# Security policy

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use GitHub's private reporting instead: open the repository's **Security** tab and choose **Report a vulnerability**. You will get a reply within a few days.

## Scope

Holler runs locally, listens for a global keyboard chord, records from your microphone only while you hold it, and pastes text. Relevant concerns include: audio or text leaving the machine, unexpected network access, unsafe handling of downloaded model files, and the keyboard hook capturing more than it should.

Network access is limited to downloading models (Hugging Face, the project's GitHub release mirror, or a URL you configure). Model weights for the built-in models are verified against pinned SHA-256 checksums.

## Supported versions

Only the latest release receives fixes.
