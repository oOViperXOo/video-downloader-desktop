# Changelog

## 1.0.1 - Orvanta branding

- Renamed the product to Orvanta Video Downloader, under the Orvanta app family.
- Updated the window, tray, About dialog, Windows metadata, setup, release filenames and browser companion branding.
- Kept existing settings, queue/history, browser pairing and single-instance activation compatible with earlier builds.
- Retained Ahmed Eladwy's developer credit and the existing text-free product icon.

## 1.0.0 - first public release

See [release notes](docs/releases/v1.0.0.md) for the current compact interface, automatic playlist prefixes, file actions, and portable/installed distribution. Earlier v2/v3 headings below describe internal development iterations rather than public semantic versions.

## v3 - multi-site, real resume, multi-connection, browser extension

- Renamed to **Video Downloader Desktop** (window title, build output, data folder). Settings/history from the old "YouTube Desktop" name are not migrated automatically (the app-data folder name changed).
- **Resume:** `--continue` made explicit and configurable; partials always kept; engine reports `partials_found` and `resuming` events (GUI log shows "Continuing from N MiB"); queue progress saved every 5 s so percent survives a crash; restored jobs say they continue from the partial file; **Pause all** button. Verified by tests that hard-kill (SIGKILL) and SIGTERM a real download and finish it with HTTP Range requests, for yt-dlp's built-in downloader and for aria2c.
- **Multi-connection:** new settings for 1-16 connections, aria2c mode (auto/aria2c/off), `--concurrent-fragments`, aria2c `-x/-s -k 1M --auto-save-interval=5`, aria2c auto-detect (explicit path, next to the app, `bin/`, PATH), graceful fallback with a visible notice, optional bundling in build scripts.
- **Many sites:** `validate_url` now accepts any public http(s) URL (yt-dlp decides support) and blocks non-http(s) schemes, credentials, localhost/.local/.internal/.lan names, IPv4/IPv6 private/loopback/link-local/reserved/multicast addresses including decimal/hex/octal and IPv4-mapped forms; optional DNS-resolve check (used when loading a link). No shell is used anywhere. Known-site names drive clipboard hints and per-site notes (login, DRM, rights).
- Audio-only sites (SoundCloud, Bandcamp...) now work in video mode: format selector ends with `/ba` (found while testing a real SoundCloud link).
- **Login/network:** optional cookies-from-browser (validated against a fixed browser list), optional proxy, referer/user-agent passthrough for the extension. Friendly error messages (login needed, DRM, unsupported) instead of raw output.
- **Browser extension + receiver** (`browser-extension/`, `receiver.py`): localhost-only, token-paired, Host/Origin gated, rate limited. Integrated with a "Browser extension" settings group, Pair browser / Forget browsers, links fill the URL box and load details (never auto-queue), cookie files 0600 and removed when done. Receiver checks were not weakened.
- Tests: 57 -> 159 Python tests (+23 receiver included) and 17 extension tests.
- Not done (suggested next): persistent concurrent-download limit, per-download speed limit, tray icon, scheduler, in-app yt-dlp update, per-playlist subfolders, Firefox verification.

## v2 - changes from the local-web-UI version

- Native PySide6 desktop GUI with dark/light themes, scrollable settings and no local HTTP server.
- Playlist checkbox selection, serial download queue, stream progress/speed/ETA and per-job option snapshots.
- Stop-and-resume pause, cancel with partial retention, retry, restart recovery, persistent settings and history.
- MP4 remux/merge, strict quality ceiling, MP3/M4A, subtitle/auto-subtitle options, thumbnail/metadata options, rate limit and filename template.
- Local clipboard suggestions with no auto-download and no overwrite of a typed URL.
- One-command Python dependency setup/run and native target-OS PyInstaller build scripts, including FFmpeg, ffprobe and Deno.
- English setup, usage, rights/terms, limitation and test documentation.

## Independent review fixes

- Fixed duplicate video ID keys that prevented enqueueing real metadata items.
- Added direct enqueue, malformed state, bad config, failed launch, Unicode chunking, archive-skip and 4K selection tests.
- No queue deadlock on invalid/restored configuration; validate before marking active.
- Preserve 4K resolution ahead of codec preference; keep height ceiling in every fallback.
- ASCII-safe NDJSON and incremental UTF-8 readers, including Arabic titles/errors.
- Validate stored settings/queue/history; back up corrupt state to state.json.bad.
- Distinguish archive skip from verified file completion, with instructions to redownload deleted files.
- Reject filename drive/URL prefixes and restrict desktop/CLI URLs to YouTube.
- Do not cancel finished-but-unreaped rows or overwrite terminal states accidentally.
- Update only the active progress row; provide Stop loading; document per-stream progress.
- Use tested PySide6 6.8 release line, preflight FFmpeg/ffprobe, include default yt-dlp extras and Deno.
