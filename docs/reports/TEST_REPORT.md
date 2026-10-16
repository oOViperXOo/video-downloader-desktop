# Verification report (v3)

Environment: Linux x86_64, Python 3.10.12, PySide6 6.8.x, yt-dlp 2026.08.19, FFmpeg present, aria2c 1.37.0 (static build, placed on PATH for the aria2c tests), Node for extension tests. Real internet access was available.

## Passed

- **159 Python tests pass** (`pytest -q` with aria2c on PATH). Without aria2c the 3 aria2c tests skip; the others pass.
- **Real resume, local HTTP Range server** (tests/rangeserver.py, tests/test_resume_multi.py):
  - yt-dlp built-in downloader: process group SIGKILLed at >=25% (simulated crash), `.part` kept, rerun sent `Range: bytes=N-` with N close to the partial size, final SHA-256 identical to the source, engine emitted `partials_found` and `resuming` events.
  - Same with SIGTERM (what Pause/Cancel/close send).
  - Server without Range support: partial restarts and the final file is still byte-identical.
  - aria2c: SIGTERM and SIGKILL mid-download, rerun fetched only the remaining ranges (unique bytes fetched in run 2 <= total - 0.7x / 0.5x of run 1 progress) and the file was byte-identical. Finding: with a hard kill aria2c only keeps what it auto-saved, so the engine sets `--auto-save-interval=5` (default 60 s lost nearly all progress in an earlier failing run).
- **Multi-connection:** aria2c with 6 connections produced several ranged requests and a correct file; `--concurrent-fragments N` command-line check; fallback without aria2c emits the "aria2c was not found" notice and still downloads correctly; option validation (0, 17, bool, non-int rejected).
- **Multi-site URL validation:** 20 accepted URLs (YouTube, Vimeo, Facebook, Instagram, TikTok, X, Dailymotion, Twitch, Reddit, SoundCloud, generic) and 38 blocked forms (file/ftp/javascript/data, credentials, localhost and .local/.lan/.internal, 127.x, 10.x, 172.16.x, 192.168.x, 169.254.169.254, 100.64.x, 0.0.0.0, IPv6 loopback/link-local/ULA/v4-mapped, decimal/hex/octal IPs, multicast, whitespace/newline, bad port, non-strings), DNS-resolve check with a faked private answer, no `shell=True`/`os.system` in the engine.
- **Real sites (live, from this sandbox):** YouTube inspect + download via the engine CLI with 8 connections and aria2c on PATH, and the same through the **GUI** (offscreen: Load > Add to queue > done, MP4 produced). SoundCloud inspect OK; its download exposed an audio-only format bug that is now fixed and the file downloads. Vimeo inspect returned "only works when logged-in" for the test video (yt-dlp behaviour; app shows a login hint).
- **Receiver/extension:** 23 receiver tests (unchanged from the supplied patch, passing) + GUI integration test (unpaired 401, private target 422, bad Host 403, valid job fills URL box and never auto-queues, cookie file 0600 and not on the command line, removed on clear) + 17 extension logic tests (Node).
- **GUI pixels inspected** (offscreen screenshots 01-06 in the delivery): Download, Queue, Settings top/middle/bottom, light theme. New settings groups and notes are readable and scroll.
- Updated 2 old tests for intentional behaviour changes (generic URLs now allowed; format selector ends with `/ba`).

## Not checked / honest limits

- **Windows and macOS were not tested.** Windows scripts (`run.bat`, `build.bat`) were edited (rename, optional aria2c) but not run. Process-tree stop and aria2c behaviour on Windows are unverified.
- **No PyInstaller build was made for v3**; the optional aria2c bundling in `build.sh`/`build.bat` is untested.
- Instagram, Facebook, X/Twitter, TikTok, Dailymotion, Twitch, Reddit were validated at URL level only, not downloaded live. Many of them need login or break often.
- Real-world speed gains from multiple connections were not measured (the local server is not a throttled CDN). Some sites limit or ban heavy parallel use.
- Resume against real CDNs depends on server Range/ETag support and non-expiring URLs; tested only with a local server and YouTube downloading from scratch (not interrupted).
- GUI-level interrupted-and-resumed download (clicking Pause then Start) was tested at engine level and by unit tests of GUI state, not as one click-through run.
- Browser extension was not run in a real browser in this session (logic tests only; the supplied package reports an earlier headless Chrome run). Firefox untested.
- DNS rebinding after URL validation remains possible (documented in receiver.py); redirects to private addresses are handled by yt-dlp, not by this app.
- Not implemented from the research list: persistent multi-download concurrency, per-download speed limit, tray icon, scheduler, in-app yt-dlp update, per-playlist subfolders, SQLite queue.
