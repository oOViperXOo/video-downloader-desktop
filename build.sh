#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt pyinstaller
args=()
if command -v ffmpeg >/dev/null; then args+=(--add-binary "$(command -v ffmpeg):."); else echo 'Install FFmpeg before building for bundled conversion support.'; exit 1; fi
if command -v aria2c >/dev/null; then args+=(--add-binary "$(command -v aria2c):."); else echo 'Note: aria2c not found - building without the multi-connection engine (built-in fragment downloader is used instead). aria2 is GPLv2: bundling it means shipping its license/source offer.'; fi
if command -v ffprobe >/dev/null; then args+=(--add-binary "$(command -v ffprobe):."); else echo 'ffprobe required'; exit 1; fi
runtime=$(command -v qjs || command -v deno || true)
[ -n "$runtime" ] || { echo 'Install QuickJS (qjs) or Deno first'; exit 1; }
.venv/bin/python -m PyInstaller --noconfirm --clean --onefile --name VideoDownloaderDesktop --collect-all yt_dlp --collect-all yt_dlp_ejs --add-binary "$runtime:." --exclude-module tkinter --exclude-module unittest --exclude-module curl_cffi --hidden-import engine "${args[@]}" app.py
echo 'Built dist/VideoDownloaderDesktop. Linux system libraries and a graphical desktop are still required.'
