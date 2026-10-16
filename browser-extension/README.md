# Orvanta Video Downloader Companion (browser extension) + app receiver patch

Manifest V3 extension for Chrome and Edge (Firefox notes below) that finds video/audio on a page and sends it to the
Orvanta Video Downloader app on the same computer. Not affiliated with, and uses no assets from, Internet Download Manager.

```
extension/        the extension (load this folder unpacked)
./   receiver.py + test_receiver.py + INTEGRATION.md for the app
popup-screenshot.png
```

## What it does
* **Popup**: lists "This page" (let the app/yt-dlp extract it), media streams seen on the page (HLS `.m3u8`, DASH `.mpd`, mp4/webm/mkv/mp3 etc.) and `<video>`/`og:video` URLs. Badge on the toolbar icon shows the count. Each row has **Send to app**.
* **Right-click** a link, video, audio or page -> **Download with app**. The badge shows OK or ! for a moment.
* Sends URL, page URL (as Referer), User-Agent and, only if you enable it, the site's cookies, to `http://127.0.0.1:17653`.
* Segments (.ts/.m4s), subtitles, tiny probe files and YouTube's googlevideo segment URLs are ignored; for YouTube send "This page".

## Permissions (kept small)
Required: `activeTab`, `scripting` (read video elements of the page you open the popup on), `contextMenus`, `storage`, `webRequest`, and host `http://127.0.0.1/*` (talk to the app).
Optional, requested only when you press the button: all http/https sites (so it can see network responses for automatic detection) and `cookies`. No `tabs`, `downloads`, `history`, no content scripts, no remote code.

## Install (Chrome / Edge)
1. App side first: start Orvanta Video Downloader, Settings > Browser extension.
2. Open `chrome://extensions` (Edge: `edge://extensions`), turn on **Developer mode**.
3. **Load unpacked** -> choose the `extension` folder.
4. Pin the extension. In the app click **Pair browser** to get a code like `1234-5678`.
5. Extension **Options** (popup -> Options) -> enter the code -> **Pair**. Status should read "Paired and connected".
6. Optional: Options -> **Enable detection** (grant site access), and the cookies checkbox if you need logged-in videos.
7. Open a page, press play, click the icon, press **Send to app**.

Re-pair after changing the app port or after "Forget browsers" in the app. Each browser pairs separately.

## Firefox
The manifest has `background.scripts` and `browser_specific_settings.gecko`. Install temporarily via `about:debugging` -> This Firefox -> Load Temporary Add-on -> pick `manifest.json` (Firefox 128+). Firefox treats optional host permissions as user-controlled: grant them in the extension's Permissions tab or via the buttons. Firefox pairing uses a random per-install `moz-extension://` origin, which the receiver accepts. **Not tested in Firefox.**

## Tests
```
node --test test/*.test.js        # 17 tests: detection, payload, client, manifest checks
(from the app folder) python -m pytest tests/test_receiver.py   # 23 tests: receiver security
```
`test/e2e/` holds the real-Chrome harness I used (server.py + CDP scripts, Chrome 154 headless, paths hardcoded to /tmp/e2e; test copy of the manifest has the optional host permissions moved to required because headless cannot click a permission prompt).

## What was verified
* Manifest loaded in real Chrome 154 (headless, `Extensions.loadUnpacked`) with no errors; service worker started.
* Real Chrome, real extension, real receiver: paired with a code, detected `clip.mp4` (400 KB) and `master.m3u8` on a demo page, ignored a `.ts` segment and a 500-byte mp4, badge showed 2, popup showed "App connected", and "Send to app" for the page and media rows plus the context-menu code path all arrived at the receiver with Referer, User-Agent and title. `file://` was refused client-side. Screenshot of the popup: `popup-screenshot.png`.

## Honest limits
* Not tested: Edge, Firefox, Chrome with a real UI (non-headless), the Chrome Web Store / Edge Add-ons / AMO review, Windows/macOS. Not packaged or signed for a store.
* The actual right-click menu click and the permission prompts (Enable detection, cookies) need a real user gesture; I tested their code paths (sendItem, permission checks) but did not click them.
* The receiver was tested against a stand-in `on_job`, not merged into the live app (the v3 agent is changing it). v2's `validate_url` is YouTube-only, so non-YouTube links need v3.
* Detection is by URL and response headers. HLS master vs. variant playlists are not told apart, and sites that hide streams behind blob/MSE with unusual URLs may only show "This page".
* No DRM circumvention: encrypted (DRM/Widevine/FairPlay) streams are listed like any other but the app/yt-dlp will fail on them, as intended.
* Cookies and tokens: the pairing token lives in `chrome.storage.local` (not encrypted; readable by someone with access to your browser profile). Cookies are read at send time, sent only to 127.0.0.1, never stored.
* DNS-rebinding caveat for the download target is described in INTEGRATION.md.
* Icons are original simple shapes made for this project.
