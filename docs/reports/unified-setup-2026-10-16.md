# Unified setup and row removal

One Setup EXE offers Portable (default) or Install for the current Windows user. Both use a single folder payload and extract bundled dependencies once. Portable adds portable.ini and stores settings/history in Data beside the executable. Installed mode retains existing AppData, Start menu and Windows uninstall support. Setup rejects using the opposite mode in an existing app folder. Portable starts with independent data; existing AppData is preserved.

Rows support Ctrl/Shift selection and removal through Delete, the three-dot menu, or the table context menu. Downloaded files remain. Active workers stop before their records are removed.

Validation: 296 tests passed, 4 skipped. Packaged GUI startup and embedded source equality passed. Installer verification covers both extracted payloads, native Windows startup, portable data-directory selection, mode conflict rejection, installed uninstall preserving user files, and unchanged registration in test mode. Installed-mode registration and shortcuts are intentionally skipped in the automated test; no clean-PC or interactive wizard acceptance is claimed.

## Row interaction correction

The original selection test targeted the outer file cell and forced keyboard focus onto the table. This missed clicks on actual labels/status cells and the focus left in the link field. Selection was also obscured by opaque cell widget backgrounds.

The table now forwards passive cell/label presses and releases to its viewport, takes keyboard focus, and paints selected cell backgrounds consistently. Inline quality selectors and action buttons retain their interaction. A regression test clicks actual filename and status labels using Ctrl, then presses Delete on the current focus widget without forcing focus. It checks selection highlighting and remaining queue records.

Validation: 298 passed, 4 skipped; all four removal tests also pass with the native Windows Qt platform. Exit an older running instance, including the tray, before launching the updated build.

The final click filter targets passive cell roots, labels and progress bars, excluding combo popup frames. Inline quality popup mouse selection passes offscreen. Native popup automation did not reliably keep popups open, including existing standalone combo tests; native selection/Delete tests pass separately.

## Menu cleanup

Removed Move up/down, Prioritize selected, Stop after current downloads, Remove selected, Apply format and folder defaults, and Clear history from the three-dot menu. Row removal remains in the table context menu and Delete key. The context menu offers make MP4 copy only for one completed non-MP4 video with an existing source file, including archived history. Audio, missing files, MP4, unfinished items and multiple selections do not offer conversion.

Menu validation: 311 tests passed, 4 skipped. Cases cover uppercase MP4 extensions, unfinished and failed downloads, audio, missing files, multi-selection and starting conversion from archived history without modifying the original file.

## Selected row actions and single-file portable revision

The user selected Open downloaded file, Show in folder, Copy link, Open download page, Rename, Move to, Delete file, Change URL and Make MP3 copy. These are implemented alongside existing list removal and conditional MP4 copies. Unselected priority, tags, scheduling, mirrors, checksums, export, scanning and source-update actions were not added.

Double-clicking passive row cells opens completed files only after validating that the path is a file; missing files and shell-open failures show a message. File moves run on a QThread with exclusive destination creation and copy-failure cleanup. Rename and move update matching queue/history paths. Delete file requires an explicit confirmation and keeps the record. Change URL accepts HTTP(S), clears stale media/format/progress state and generates a fresh filename suffix, preserving previous partial files.

MP3 conversion uses the existing isolated worker and FFmpeg audio extraction at 192 kbps. The original stays intact; existing outputs receive a numbered name. Cancellation/failure returns to the completed original record. A local audio fixture verifies real MP3 codec output and collision preservation.

Portable mode now extracts exactly one EXE, with settings/history in AppData; it adds no marker, runtime folder, shortcuts or uninstall entry. The same setup also contains the installed folder build, increasing setup size. An updated standalone Portable EXE is provided too. Older portable-folder builds and their Data folders are preserved; use a separate destination for the new format.

Native Windows tests passed for double-click, rename, background move and MP3 worker setup. Packaging verification checks source equality for row_actions and media_conversion in both EXE formats. Automated installed-mode tests skip real registration/shortcut creation; clean-PC and signed release acceptance are not claimed.

Final selected-action validation: 323 passed, 4 skipped on the final source. Four native Windows action tests passed. Both packaged formats passed real MP3 worker conversion with original preservation, PE GUI/startup checks and embedded source equality. Setup verification checks that Portable extracts one EXE and still has only one EXE after smoke startup; AppData is used instead of a local Data directory.

Final setup verification passed: all 1,351 installed payload files matched their hashes; installed GUI/yt-dlp startup passed; uninstall preserved a user-created file. Default Portable extraction contained exactly one EXE before and after native smoke startup, matched the verified single-file build hash, used AppData, and created no Windows registration or uninstaller.

## Easier playlist numbering

Added a contextual Playlist numbering button beside Add for waiting playlist items, and Number files on the waiting-row context menu. Controls show an on/off checkbox, 01/001 formats and a live example. Apply affects waiting items only and remembers the future default; numbering can be changed or removed without stacking prefixes. New playlist jobs retain their source indices and unprefixed templates. Legacy selected rows can also be numbered. File/partial data remains intact; a changed destination resets displayed transfer progress. Add still queues directly without an additional mandatory dialog. Settings > Playlists now groups numbering and folder defaults separately from raw filename templates.

Focused checks cover original indices, two/three digit rendering, toggle-off, persistence, cancellation, single videos, old numbered jobs and partial preservation. Native Windows checks cover the contextual button, live example and Apply/Cancel dialog.

Numbering validation: 331 passed, 4 skipped on the final source; three native Windows checks passed. URL replacement retains its fresh destination when numbering is later changed or disabled. Existing original numbering and Add-without-modal behavior are covered by regression tests.

Numbering release setup verification passed for both modes. One initial silent uninstall aborted before deleting files during a transient executable-lock condition; a retry succeeded. A fresh full verification then passed payload hashes, native startup, uninstall preservation and one-EXE Portable checks. The verification tool now allows bounded retries while retaining all final assertions. The actual Fusion-style dialog preview is saved in docs/screenshots/playlist-numbering.png.

## Numbering clarification: settings only

The user requested automatic filename prefixes for new playlists rather than manual application to queued items. Removed the contextual numbering button, row-menu Number files action and manual Apply dialog. Settings > Playlists retains the automatic-prefix checkbox, two/three digit format choice and live example. Saved defaults are captured into each new playlist item; existing queued templates remain unchanged, including previously numbered jobs. Single-video filenames remain unprefixed. Removed the unused bulk-numbering helpers. Regression checks now cover saved defaults, subsequent playlists, persistence, cancellation and preservation of all existing queue templates.

Settings-only prefix validation: 330 tests passed, 4 skipped; three native Windows checks passed. Both new-playlist number formats are automatic after saving defaults, and existing ready/paused/completed templates remain unchanged, including previously numbered jobs. Toolbar and context-menu numbering controls are absent.

Settings-only release verification passed: both packaged GUIs start without a console and embedded sources match. Setup verified all 1351 installed payload files, preserves user files on uninstall, and Portable produces exactly one EXE before and after native startup with AppData state. Source archive verified by CRC and SHA256 manifest.
