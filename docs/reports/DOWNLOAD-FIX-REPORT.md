# Download investigation, 2026-10-15

The exact `unsupported platform: win32` error was reproduced by invoking the packaged yt-dlp with Safari cookie extraction. yt-dlp's installed `cookies.py` rejects Safari extraction on Windows. This does not indicate an incompatible Windows executable.

The source already filtered the simplest Safari setting. The GUI now also normalizes old settings and queued jobs containing Safari case/profile variants, filters browser choices by platform, and explains the platform error. Partial downloads remain untouched.

Source launches now discover QuickJS in the project tools folder or Deno beside Python and pass the runtime to both inspection and downloads. Previously runtime discovery only worked in frozen builds.

A UX subagent implemented visible loading guidance, queue counts, action availability, selected failure details, a Download messages tab, and indeterminate conversion progress. The layout was rendered and visually checked with an explicitly loaded Windows font.

Validation:

- Rebuilt `dist/VideoDownloaderDesktop.exe` with the existing PyInstaller spec.
- 58 focused engine, GUI, process, and new runtime regression tests passed; one unrelated Windows permission test was deselected.
- Broader suite: 159 passed, 3 skipped, 3 failed. Failures are existing POSIX assumptions: cookie mode 0600 and two uses of `os.killpg` on Windows. New regression tests were added after that broad run and passed in the focused run.
- Rebuilt executable downloaded YouTube video `jNQXAC9IVRw` with stale Safari settings and the internal downloader. Merge and metadata completed, exit code 0, no engine errors.
- FFprobe confirmed the resulting 745939-byte MP4 contains video and audio and is 19.06 seconds long.
- Repeated the packaged download using the default aria2 multi-connection path: merge and metadata completed, exit code 0, no engine errors.

The saved application log also contained `Process crashed`, with no exit code or traceback. This separate historical failure has not been reproduced; the specific failing URL and launch method were requested. Existing saved settings currently have browser cookies disabled.

## Supplied video follow-up

The user supplied YouTube video `u_G1NCwQZ4E`. The rebuilt executable inspected it successfully and downloaded it with the default 1080p cap, four connections and aria2. Merge and metadata completed with exit code 0 and no engine errors. FFprobe verified 1920x1080 video plus audio, 228.16 seconds, 120116122 bytes. The historical process crash did not recur.

This Arabic-titled video exposed a separate Windows encoding mismatch: yt-dlp printed filenames in the system code page while the engine decoded UTF-8. The actual disk filename was correct, but reported paths contained replacement characters. Both inspection and download commands now explicitly select UTF-8 output; runtime regression tests cover this setting.

A regression run with process tests before GUI tests exposed an idle-window close callback accessing a deleted Qt window. Closing now marks idle windows as closing too, so pending queue callbacks return safely. After this fix, all 58 focused tests passed again (one unrelated POSIX-permission assertion deselected).

The packaged engine was rerun against the supplied video with explicit UTF-8 output and the completed file in place: exit code 0, no errors, reported path exists on disk, and no replacement characters in the path.

Close the old app and launch the rebuilt executable before retesting existing queue items.

## Packaged GUI startup follow-up

The user's black console followed by exit was reproduced. The executable failed before window creation with `ImportError: DLL load failed while importing QtCore: The specified procedure could not be found.` Earlier packaged download tests bypassed GUI imports, so they did not catch this release blocker.

The bundle selected Python's root VCRUNTIME140/VCRUNTIME140_1 version 14.42 while Qt shipped version 14.44 in its subdirectory. The spec now selects Qt's newer runtime at the bundle root, and build.bat explicitly includes the same DLLs. No system DLLs were changed.

That runtime adjustment alone did not resolve the startup error. PE import/export comparison identified the actual failure: the bundled root `icuuc.dll` came from the builder's Poppler tool directory. Every unversioned ICU function imported by Qt6Core was absent from that DLL, while Windows System32's `icuuc.dll` exported them all. The spec excludes this foreign ICU binary and its data dependency. A runtime hook explicitly loads ICU from System32, protecting builds against unrelated same-name DLLs on PATH.

Added `--smoke-test` with isolated temporary application state and `tools/verify_build.py`, which checks packaged Qt imports, window creation, clean exit, and absence of tracebacks. Windows builds now run this check before reporting success.

The ICU-corrected executable passed packaged GUI startup. The user then requested no black console window. The Windows build now uses the GUI subsystem (`--windowed`); worker modes restore inherited stdout/stderr pipes with UTF-8 without allocating a console, and engine subprocesses explicitly use CREATE_NO_WINDOW. Verification also checks the executable's PE subsystem. Engine/process regression checks passed (40 tests), and a Windows pipe-restoration regression passed with Arabic output.

Final windowed build passed the PE subsystem and packaged GUI startup checks. Its hidden download worker completed the supplied video request with exit code 0, no engine errors, and a reported output path that exists on disk.
