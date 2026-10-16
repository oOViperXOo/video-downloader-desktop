# Video Downloader Desktop v4

## What changed
- One main download screen: paste link, video list, Video/Audio and per-item quality, progress, actions, folder.
- Add link loads video/playlist entries without starting a transfer. Uncheck playlist rows to exclude them from Start all. Per-row Start ignores bulk checkboxes intentionally.
- X removes a waiting/finished/failed item. For active transfers it stops the subprocess first, then removes the row. Downloaded and partial files are not deleted.
- Advanced settings/history are optional and no longer part of the download flow.
- Optional aria2 missing notice is silent; supported built-in parallel-fragment fallback retained.
- Safari browser-cookie selection removed and old saved selections migrated to none. yt-dlp raises the exact "unsupported platform: win32" error in its Safari extractor. Actual user setting has not been inspected.
- Windows build uses compact QuickJS by default, excludes unused Qt components and removes automatic curl_cffi installation. yt-dlp-ejs remains included.
- ffmpeg AND ffprobe retained: removing ffprobe breaks some audio/metadata paths.
- Python 3.14-compatible PySide6 range preserved: >=6.8,<6.11.

## Windows
Extract into a NEW folder. Run run.bat for source, or build.bat to produce dist\VideoDownloaderDesktop.exe.
FFmpeg and ffprobe must be on PATH. Build downloads optional aria2c and QuickJS from official release repositories. Internet required on first build.
For a larger Deno compatibility build: run `set VD_JS_RUNTIME=deno` then `build.bat` in the same command prompt.
Source run.bat installs Deno so existing source behavior remains supported.

## Size
No Windows build is available from the Linux test environment. No final executable size or percentage saving is claimed. QuickJS replaces bundled Deno in compact builds; final size still depends heavily on the user's FFmpeg distribution. Do not delete ffprobe for size savings.

## Testing limits
Linux Python 3.10 + Qt 6.8.3: full tests run, including real local HTTP downloads/resume. aria2 integration tests skipped when binary absent. Windows Python 3.14, frozen executable, QuickJS YouTube extraction, browser-cookie decryption and public-site end-to-end transfers NOT tested here.
Visual checks: actual Qt screenshot at 1220x800, final row action text/dropdowns/progress inspected. This is not a Windows rendering check.

## Distribution
aria2 is GPLv2; bundling/redistributing requires applicable license/source obligations. QuickJS/Qt/FFmpeg/yt-dlp also retain their upstream licenses. The downloaded tools are build inputs, not included in this source ZIP.

Final test run: 160 passed / 3 skipped (aria2 binary absent). One earlier process-tree test race passed on retry.
