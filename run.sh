#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
command -v python3 >/dev/null || { echo 'Install Python 3.10+ first.'; exit 1; }
if [ ! -d .venv ]; then python3 -m venv .venv || { echo 'Install python3-venv, then rerun.'; exit 1; }; fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
if ! command -v ffmpeg >/dev/null; then echo 'FFmpeg is required. Install it with your package manager (e.g. sudo apt install ffmpeg).'; fi
command -v aria2c >/dev/null || echo 'Optional: install aria2 (sudo apt install aria2) for faster multi-connection downloads.'
.venv/bin/python -m pip install deno
exec .venv/bin/python app.py
