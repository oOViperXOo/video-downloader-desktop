#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
case "$(uname -s)" in Linux|Darwin) ;; *) echo 'Use build.bat on Windows.'; exit 1 ;; esac
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-posix.lock
for tool in ffmpeg ffprobe aria2c cmake git; do
  command -v "$tool" >/dev/null || { echo "Install $tool before building."; exit 1; }
done
.venv/bin/python tools/prepare_posix.py
export VD_FFMPEG="$(command -v ffmpeg)" VD_FFPROBE="$(command -v ffprobe)"
export VD_ARIA="$(command -v aria2c)" VD_JSBIN="$PWD/build/posix/qjs"
export PYINSTALLER_STRICT_BUNDLE_CODESIGN_ERROR=1
if [ "$(uname -s)" = Darwin ]; then export MACOSX_DEPLOYMENT_TARGET=15.0; fi
.venv/bin/python -m PyInstaller --noconfirm --clean OrvantaPosix.spec
echo 'Native bundle built. Verify it, then run tools/package_posix.py to create release files.'
