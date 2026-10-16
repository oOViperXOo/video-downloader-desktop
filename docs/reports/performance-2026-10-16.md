# Local performance and release verification - 2026-10-16

The portable EXE is the primary release; Setup is optional. The QTreeWidget table remains in place.

## Source UI measurement

One before/after run with 200 synthetic ready items, Fusion/offscreen rendering and an isolated store. Memory is process working-set growth after constructing the queue. These numbers are machine-specific measurements, not guaranteed savings or network-throughput claims.

| Measurement | Before | After |
|---|---:|---:|
| Queue construction | 3378.8 ms | 923.3 ms |
| Unchanged refresh | 5703.0 ms | 96.9 ms |
| 500-event progress burst | 418.9 ms | 16.3 ms |
| Queue memory growth | 332.0 MiB | 72.6 MiB |
| Widget count | 19619  | 4619  |
| Upfront options dialogs | 200  | 0  |

The empty-window source startup was essentially unchanged (about 130 ms). The larger optimized 500-row sample is recorded in the accompanying JSON.

## Frozen startup

Three native Windows launch-and-close samples for each new format; each includes the same fixed 750 ms smoke timer. Disk caches and antivirus state were not controlled. The first portable sample was slower; all samples are retained in the JSON.
- OrvantaVideoDownloader-Portable.exe: [19197.6, 7988.6, 8541.6] ms; median 8541.6 ms.
- OrvantaVideoDownloader.exe: [2199.1, 2162.6, 2168.4] ms; median 2168.4 ms.

## Verification

- Final regression suite: 290 passed, 4 platform skips.
- Both bundles: no-console GUI startup and matching embedded source modules.
- Primary portable: native Windows GUI and hidden yt-dlp worker passed.
- Optional Setup: isolated installation verified SHA256 for all 1351 payload files; installed GUI/worker passed.
- Isolated uninstall removed every payload file and the uninstaller, preserved a user-created note, and left the checked registration keys unchanged.
- Installer QA mode intentionally skips normal Start menu/registration writes; those standard NSIS actions were compiled but were not exercised on the user profile.
- No live account/private-playlist or clean-machine test was performed as part of this performance change.
