# Orvanta Video Downloader update

Developer: Ahmed Eladwy, eladwy.ahmed@gmail.com.

- Generated a Windows icon, including small taskbar/Explorer sizes, and added executable version metadata, window icon and About details.
- Reduced main-screen buttons. Secondary commands are under App and per-item overflow menus.
- Default downloads preserve source codecs and automatic containers. MP4 is an explicit remux option, without video re-encoding. Audio extraction to MP3 remains a conversion when requested.
- Removed the forced H.264/AAC preference. For supplied video u_G1NCwQZ4E the available 1080p H.264 video stream was 112.60 MiB; AV1 was 53.20 MiB before audio. Actual sizes depend on the source and selected streams.
- Default single-connection native downloads emit continuous progress. Multiple connections remain available per item, with real aria2 transfer counters and allocation disabled. A partial file's logical length is not a reliable transferred-byte count when chunks arrive out of order.
- Two files can download concurrently by default, configurable from one to four. Each worker has a unique config file, decoder, progress/error state and pause control. Duplicate destinations are serialized. Single/multiple connections are independent of the file concurrency limit.
- When switching a tracked aria2 partial to single-connection mode, preserve sparse parts as backups and restart safely instead of treating sparse length as completed bytes.
- Replaced full FFmpeg 8.1.2 binaries with checksum-verified essentials builds and excluded unused QML/Quick/PDF/software OpenGL binaries. Kept FFmpeg/ffprobe and bundled their license/readme.

FFmpeg source: https://www.gyan.dev/ffmpeg/builds/ (8.1.2 essentials).
ZIP SHA256: db580001caa24ac104c8cb856cd113a87b0a443f7bdf47d8c12b1d740584a2ec

Validation: 81 focused tests passed, including real native/aria2 intermediate progress, two simultaneous workers, independent pause, container settings, and Windows UTF-8 worker pipes. One existing POSIX-mode assertion was excluded on Windows. Packaged startup/download checks are recorded after the final build.

The existing executable was locked by Windows during replacement, so the update is delivered separately as `dist/OrvantaVideoDownloader.exe`. The previous executable is retained. Settings storage keeps the existing application identifier so saved jobs are preserved.

Final verification:

- Final executable: 121.6 MiB (previous 240.0 MiB), with embedded icon, Orvanta company/product metadata and GUI subsystem (no console).
- Packaged offscreen startup and the real Windows window both passed, with clean exits.
- Two packaged workers ran concurrently: supplied video u_G1NCwQZ4E completed as original WebM, 59275185 bytes (56.5 MiB), with 90 intermediate progress events; the short MP4 remux test completed with 14 intermediate events. Both exited 0, no errors, valid files and intact Arabic output paths.
- The earlier H.264/MP4 download of the supplied video was 120116122 bytes. The updated source-codec selection roughly halves that example's size while retaining 1080p.
- Three additional regression cases passed for excluded queued items, shared playlist cookies, and preserving sparse partial data when changing connection mode (84 distinct focused tests in total).
