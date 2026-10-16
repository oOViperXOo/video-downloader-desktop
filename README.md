# Orvanta Video Downloader

A compact Windows app for downloading videos, audio and playlists.
Developed by [oOViperXOo](https://github.com/oOViperXOo).

**[Download the latest release](https://github.com/oOViperXOo/video-downloader-desktop/releases/latest)**

- **Portable.exe** — recommended single-file app; no installation required.
- **Setup.exe** — choose Portable or install for the current Windows user.

Windows x64. Runtime dependencies are included; builds are currently unsigned.
Linux and macOS packages are not available.

![Orvanta Video Downloader](docs/screenshots/orvanta-downloads.png)

*Actual Windows interface with illustrative queue entries.*

## Use

1. Paste a video or playlist link and click **Add**.
2. Choose quality in the table, then **Start** or **Start all**.
3. Open **⋯ → Settings** for playlist numbering, folders and browser login.

Parallel downloads, pause/resume, single/multiple connections, MP3/MP4 copies,
row file actions and tray minimization are included. Settings and history stay
in your Windows AppData folder.

[Feature guide](FEATURES-GUIDE.md) · [Browser extension](browser-extension/README.md) · [Changelog](CHANGELOG.md)

## Development

Requires Python 3.11+ and FFmpeg/ffprobe on PATH. Run `run.bat` on Windows;
Linux source users can run `bash run.sh` with the required Qt system libraries.

```powershell
.venv\Scripts\python.exe -m pip install pytest
.venv\Scripts\python.exe -m pytest -q
node --test browser-extension/test/manifest.test.js browser-extension/test/logic.test.js
```

Build on Windows with `build.bat`. To create both release formats, run
`powershell -File tools/build_releases.ps1` after preparing dependencies.
See [source/build instructions](SOURCE-ARCHIVE.md) and [signing/update setup](RELEASE-SETUP.md).

Download only content you have permission to save. DRM-protected content is unsupported.
