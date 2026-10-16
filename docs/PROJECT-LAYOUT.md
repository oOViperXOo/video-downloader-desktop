# Project layout

- Root: application modules, launch/build scripts, dependency files and current user/release guides.
- `dist/`: current EXE and ZIP distribution, preserved unchanged during cleanup.
- `assets/`: app icon and version metadata.
- `browser-extension/`: browser companion source and tests.
- `tests/`: application regression suite.
- `tools/`: build/runtime/verification utilities and required bundled binaries; `tools/media/` is the retained FFmpeg/ffprobe distribution including license files.
- `tools/diagnostics/`: saved diagnostic configurations used by verification utilities.
- `docs/reports/`: historical implementation/test reports.
- `docs/screenshots/`: UI captures. Preview tools write here.
- `docs/archive/`: small historical logs, source recovery copies and release hashes saved before cleanup.
- `reviews/`: review briefs, findings and implementation evidence.
- `.venv/`: retained local development environment.

Run `./tools/clean_workspace.ps1 -WhatIf` to preview removal of generated build/test/cache artifacts, then omit `-WhatIf` to remove them. The script checks workspace containment and refuses linked directories; it preserves the development environment and release files. `.gitignore` excludes generated artifacts from future version control.

Cleanup on 2026-10-15 removed 30 generated targets (1,632,402,080 bytes, 1.52 GiB), including redundant FFmpeg archives/extractions whose binaries matched the retained copies. EXE/ZIP SHA256 values remained unchanged. Application settings/history outside the workspace were untouched.
