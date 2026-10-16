# Release signing and update setup

No signing certificate, signing provider or public update endpoint is configured. Builds remain unsigned unless explicitly enabled. These scripts do not create certificates, keys or secrets, and do not publish files.

## Optional trusted Windows signing

Obtain a trusted code-signing certificate through your chosen provider and install its certificate/private-key integration in the build account's Windows certificate store. Hardware token/provider credentials must be handled through that provider, never committed here. Install Windows SDK SignTool and configure its full path if it is not on PATH.

In the build shell, set `VD_SIGN_THUMBPRINT` to the certificate's 40-digit SHA1 thumbprint, `VD_TIMESTAMP_URL` to the provider's HTTPS RFC3161 timestamp endpoint, and optionally `VD_SIGNTOOL` to SignTool's full path. The thumbprint selects the certificate; the executable digest and timestamp digest use SHA256. The script uses the current user's certificate store. A provider requiring another interface needs its documented signing adapter before use.

Run `build.bat`. The order is PyInstaller, verification of the exact `dist\%VD_APP_NAME%.exe`, optional signing of that same file, SignTool trust verification plus Authenticode signer/timestamp verification, then the local release evidence/hash manifest. Any signing/verification failure stops the build. Without `VD_SIGN_THUMBPRINT`, signing is skipped. A valid signature is not a guarantee of immediate SmartScreen reputation.

Do not modify or rebuild the executable after generating its manifests. If you sign an existing artifact manually, regenerate all manifests afterwards:

```powershell
powershell -NoProfile -File tools/sign_release.ps1 -Artifact dist/OrvantaVideoDownloader.exe
.venv/Scripts/python.exe tools/release_manifest.py dist/OrvantaVideoDownloader.exe
```

## Optional read-only update checks

`release_updates.APP_VERSION` is the source version (`1.0.0` initially); bump it before packaging. Configure the GUI with your final HTTPS JSON manifest URL only after hosting exists. There is no default production URL. The check refuses redirects, limits response size to 64 KiB, validates the schema and compares semantic versions. It never downloads an executable or runs an installer. Its socket timeout defaults to 8 seconds (allowed 1–30); a separate caller deadline of twice that value covers stalled DNS/TLS/headers using a daemon fetch with one outstanding request allowed. Run it outside the GUI thread. Release notes are untrusted strings and must be rendered explicitly as plain text. A release page opens only after the user's click.

After building and optional signing, create the public metadata locally using your actual HTTPS release download URL:

```powershell
.venv/Scripts/python.exe tools/create_update_manifest.py dist/OrvantaVideoDownloader.exe --download-url https://YOUR-HOST/releases/OrvantaVideoDownloader.exe --notes-file release-notes.txt --output dist/update.json
```

Replace the placeholder before running. The output schema is:

```json
{
  "schema_version": 1,
  "version": "1.0.0",
  "download_url": "https://YOUR-HOST/releases/OrvantaVideoDownloader.exe",
  "notes": "Plain text release notes",
  "sha256": "SHA256 of final artifact",
  "size_bytes": 123
}
```

Host the final executable and update.json on infrastructure you control over HTTPS without redirects for the manifest. Publish only after reviewing the artifact, signature (if configured), hashes and URL. Hash metadata is informational; this browser-based release discovery does not independently authenticate or verify downloaded binaries. HTTPS manifest hosting is the trust boundary. Versions accept major.minor.patch and optional prerelease identifiers, e.g. `1.1.0-rc.1`; build metadata is intentionally unsupported. The local `.exe.manifest.json` is a separate builder evidence snapshot and is not the public update schema.
