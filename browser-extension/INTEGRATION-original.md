# Integrating receiver.py into the app (v2 or v3)

`receiver.py` is a new file. It imports nothing from app.py/engine.py and edits nothing. Copy it next to app.py,
and copy `test_receiver.py` into `tests/`. Only stdlib is used, so requirements.txt does not change.

## Wiring (about 15 lines in app.py, Qt)

```python
# top of app.py
from PySide6.QtCore import Signal, QObject
import receiver

class BrowserBridge(QObject):
    job = Signal(dict)            # emitted from a server thread; Qt queues it to the GUI thread

# in Window.__init__ (after self.store exists)
self.bridge = BrowserBridge()
self.bridge.job.connect(self.on_browser_job)
state = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation)) / 'receiver.json'
self.receiver = receiver.Receiver(self.bridge.job.emit, str(state), app_version='2')
try: self.receiver.start()
except OSError as exc: self.error(f'Browser receiver could not start (port busy?): {exc}')

# new methods on Window
def on_browser_job(self, job):
    # job keys: url, page_url, title, kind (page|hls|dash|video|audio|link), headers{Referer,User-Agent,Cookie}, id
    # v2: put job['url'] in the URL box / queue (v2 validate_url accepts YouTube only, so non-YouTube
    # links need the v3 multi-site validator). Ask the user before starting if you prefer.
    self.url.setText(job['url']); self.activateWindow(); self.inspect()
def pair_browser(self):
    QMessageBox.information(self, APP_NAME, f'Pairing code (valid 2 minutes):\n\n{self.receiver.new_pairing_code()}')
# add buttons "Pair browser" -> self.pair_browser, "Forget browsers" -> self.receiver.revoke_all
# in closeEvent: self.receiver.stop()
```

## Using headers/cookies with yt-dlp (no shell)

```python
import receiver, tempfile, os
cookie_file = None
if job['headers'].get('Cookie'):
    fd, cookie_file = tempfile.mkstemp(suffix='.txt'); os.close(fd)
    receiver.cookie_header_to_netscape(job['headers']['Cookie'], job['url'], cookie_file)   # 0600
args = receiver.ytdlp_args(job, cookie_file)   # ['--referer', ..., '--user-agent', ..., '--cookies', file]
# pass as a list to QProcess.start(program, argv) / the engine config. Never build a command string.
# Delete cookie_file when the download ends.
```
For v3 (aria2c): pass Referer/User-Agent as `--referer` / `--user-agent`; for Cookie prefer a cookies file or
`--load-cookies`, not `--header=Cookie:...` on the command line (visible to other local users in the process list).

## Behavior contract

| | |
|---|---|
| Bind | 127.0.0.1, port 17653 (`port=` to change; extension Options has a matching field) |
| Endpoints | all `POST`: `/v1/ping`, `/v1/pair`, `/v1/download`; `OPTIONS` preflight answered; `GET` -> 405 |
| Gate (every request) | Host must be `127.0.0.1:<port>` or `localhost:<port>`; Origin must be `chrome-extension://` or `moz-extension://` |
| Pairing | `new_pairing_code()` -> `NNNN-NNNN`, single use, 120 s, 5 wrong tries burn it; token is returned once and bound to the pairing extension origin; only its SHA-256 is stored (file mode 0600); max 5 browsers |
| Download body | `{v:1,url,page_url?,title?,kind?,headers?{Referer,User-Agent,Cookie}}`, JSON only, 64 KB cap |
| URL rules | http/https only, no `user:pw@`, no localhost/.local/.internal, every resolved IP must be globally routable (blocks 127/8, 10/8, 172.16/12, 192.168/16, 169.254/16, 100.64/10, ::1, fc00::/7, v4-mapped v6, decimal/hex IP forms). `allow_private=True` turns the IP check off (not recommended) |
| Rate limit | 10 downloads burst then 1/s; 5 pairing attempts/min; 60 requests burst, 20/s |
| Errors | JSON `{error: code}`: 401 not_paired, 403 bad_origin/bad_host/bad_pairing_code, 413, 415, 422 (url/header problems), 429, 500 app_error (no detail leaked) |
| Logging | The server logs nothing (URLs and cookies never hit logs). Do not log `job['headers']` in the app. |

## Known limits (be honest in the UI)
* DNS rebinding after validation: the app/yt-dlp resolves the host again later. The Host/Origin gate protects the receiver itself; for the download target, a malicious DNS name could answer public first and private second. Mitigation if wanted: resolve once and pass the IP, or run yt-dlp with a proxy that blocks private ranges.
* Any local process can still talk to the port, but without a paired token it gets 403 (no Origin) or 401.
* A malicious page cannot call the receiver (it cannot forge an extension Origin), but a malicious *extension* the user installs and pairs could.
* v2 `validate_url` is YouTube-only; the receiver validates for safety, not for site support. Site support belongs to the v3 engine.

## Tests
`python3 -m unittest test_receiver` (23 tests, loopback server on an ephemeral port, fake DNS). One test is slow (~10 s, the 64 KB oversize case waits on a socket timeout).
