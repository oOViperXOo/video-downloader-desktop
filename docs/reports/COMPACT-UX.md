# Compact desktop interface

Implemented the selected Compact concept in the native Qt application.

- Top navigation for Downloads, History and Settings.
- Flat single-column download rows with source/format/quality information, full-width progress, transferred bytes, speed and ETA.
- One primary action per file; the overflow button expands media, quality, original/MP4 container and single/multiple connection choices.
- Add link opens a dialog. Less-used app actions remain in the top overflow menu.
- All / Active / Queued filters, empty states, download folder shortcut and aggregate transfer speed.
- Independent parallel workers and existing pause/resume, cookies, archives, UTF-8 handling and no-console worker transport are retained.
- Dark and light layouts rendered and visually inspected.

Validation: historical validation recorded 36 GUI/process/parallel passes. Current committee UX remediation: 7 focused offline Compact GUI tests passed using `test-temp/ux-fixes`. Coverage includes audio format/bitrate synchronization with Settings, multi-item selection/count confirmation and cancellation, single-item prompt bypass, keyboard focus restoration, Resume/Open folder labels and truthful selected-quality wording. Dropdown chevrons use palette text color in both themes; row heights derive from layout requirements. Native enlarged-text, narrow-window and packaged keyboard acceptance remain separate release checks.

The separate `OrvantaVideoDownloader-Compact.exe` output allows checking the new interface while the previous executable remains available. Both use the same saved application settings.
