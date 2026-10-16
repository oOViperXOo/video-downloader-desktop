# Source archive

The source ZIP contains Python application code, tests, UI assets, browser-extension sources, build/verification scripts, dependency lockfiles and documentation.

It excludes virtual environments, generated executables, media-engine binaries, build caches, test output, diagnostic logs and personal application data.

For development, install Python and follow README.md. On Windows, build.bat installs the locked Python dependencies and fetches required media/runtime tools. Building requires internet access for those dependencies. The source ZIP itself is not a standalone application; use the packaged EXE to run without a development environment.

After preparing dependencies, run `powershell -File tools/build_releases.ps1` to create one Setup EXE offering Portable (default) and Install, plus the source ZIP. The script downloads a checksum-pinned NSIS compiler into ignored `tools/vendor/` if needed. Compiler binaries are excluded from this ZIP. Setup contains two verified builds: a single-file Portable EXE and a folder bundle for installation. This makes the combined setup larger than either individual package. For unattended setup, use `/S /MODE=portable` (default) or `/S /MODE=installed`, followed by `/D=absolute destination` as the final argument. Both current modes use AppData settings/history. Earlier portable-folder builds with portable.ini remain supported by the app; their data is preserved, and setup requires a separate folder for the new format. Do not mix modes in the same folder.
