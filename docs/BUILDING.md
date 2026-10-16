# Linux and macOS builds

The **Linux and macOS builds** GitHub Actions workflow runs on pushes to main,
pull requests and manual dispatch. Open the completed run and download
`Orvanta-linux-x64` or `Orvanta-macos-arm64` under Artifacts. Artifacts expire after seven days.

- Linux: Ubuntu 22.04 builder, x64 folder bundle in a `.tar.gz`. Extract the entire folder; run `OrvantaVideoDownloader` with `_internal` beside it. Requires glibc 2.35+ and desktop Qt/X11/OpenGL system libraries.
- macOS: macOS 15 Apple Silicon builder, `.app` distributed in a `.dmg`, targeting macOS 15+. Drag the app to Applications. The bundle is ad-hoc signed, not Developer ID signed or notarized; Gatekeeper may block a downloaded build. No Intel Mac package is produced.
- Dependencies: CPython 3.12, `requirements-posix.lock`, native FFmpeg/ffprobe and aria2. QuickJS-ng v0.17.0 is compiled from an immutable upstream commit for the builder's OS/architecture.

Each job runs the regression suite, compares embedded application sources, then
checks the extracted archive or mounted DMG. Package checks exercise native GUI
startup, worker output, a local download and MP3 conversion with the runtime PATH
restricted to system directories. The macOS bundle also passes strict ad-hoc signature verification.
These checks do not replace testing browser cookies, tray behavior and Gatekeeper on user machines.

## Build locally

Install Python 3.12, CMake, Git, FFmpeg/ffprobe and aria2 using the platform's package manager.
Linux also needs Qt X11/OpenGL libraries and Xvfb for automated GUI checks; see the workflow's apt package list.

```sh
bash build.sh
.venv/bin/python tools/package_posix.py
# Linux:
xvfb-run -a .venv/bin/python tools/verify_posix_release.py
# macOS:
.venv/bin/python tools/verify_posix_release.py
```

Outputs are in `dist/release-output/`, alongside tool/package build information
and SHA256 checksums. Windows continues to use its existing build scripts and lockfile.

## Release tags

A `v*` tag runs both jobs and prepares a **draft** GitHub release only after they
pass. The tag must match `release_updates.APP_VERSION`. Windows artifacts can be
added separately before publication. Existing public releases are not replaced.
The build jobs have read-only repository access; only the tag-only draft job has release write permission.

Developer ID signing/notarization requires a separate Apple signing setup;
this workflow needs no Apple credentials and does not claim notarized distribution.
