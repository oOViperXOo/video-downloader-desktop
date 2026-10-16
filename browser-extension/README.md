# Orvanta Video Downloader Companion

Send the current page or detected media links to Orvanta on the same computer.
Links are added for review; the extension does not start downloads automatically.

## Setup

1. In Orvanta, open **Settings → Browser extension**, enable it and choose **Pair browser**.
2. In Chrome or Edge, open the extensions page, enable Developer mode and select **Load unpacked**.
3. Select this `browser-extension` folder, then enter the pairing code in the extension's Options page.
4. Open the popup and choose **Send to app**, or use the browser's **Download with app** context menu.

Pairing codes expire after two minutes and work once. Use **Forget browsers** in
Orvanta to revoke pairing. Firefox packaging and store distribution are unverified.

## Optional permissions

- **Media detection** observes response URLs/headers to find direct media and playlists.
- **Cookies** can send the current site's session to the local app when explicitly enabled.

For YouTube, send the page URL rather than individual media segments.
DRM-protected content is unsupported.

## Local connection

The receiver listens on `127.0.0.1:17653`, requires pairing and checks request origins.
The pairing token stays in browser-local storage; treat the browser profile as private.
Detection and site support vary. URL validation does not pin later DNS lookups.

## Tests

From the repository root, with Node.js installed:

```sh
node --test browser-extension/test/manifest.test.js browser-extension/test/logic.test.js
```

`test/e2e/` contains a manual Chrome/CDP harness with environment-specific paths.
