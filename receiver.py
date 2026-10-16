"""Localhost receiver for the browser extension (patch module, stdlib only).

Drop this file next to app.py / engine.py. It does not import them and does not
touch their state. See INTEGRATION.md for the ~15 lines that wire it in.

Security model (all enforced in code, all covered by test_receiver.py):
  * binds 127.0.0.1 only (refuses any other host)
  * Host header must be 127.0.0.1:<port> or localhost:<port> (DNS rebinding)
  * Origin must be chrome-extension:// or moz-extension:// (a web page can never
    pass this: browsers set Origin on cross-site requests and pages cannot forge it)
  * per-install random secret, exchanged once through a short-lived pairing
    code that the user reads in the app and types into the extension; the token
    is bound to the extension origin that paired; only its SHA-256 is stored
  * URL checks: http/https only, no credentials, no localhost / private / link-local
    / reserved addresses (after DNS resolution), length limits
  * header allowlist (Referer, User-Agent, Cookie, Origin); Cookie only if the
    extension sent it
  * body cap, JSON-only, rate limits, no command execution anywhere in this file
"""
import hashlib
import hmac
import ipaddress
import json
import os
import re
import secrets
import socket
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

APP_NAME = "video-downloader"
PROTOCOL = 1
DEFAULT_PORT = 17653
MAX_BODY = 64 * 1024
MAX_URL = 8192
MAX_HEADER_VALUE = 8192
MAX_TITLE = 300
MAX_PAIRINGS = 5
PAIR_CODE_TTL = 120.0
PAIR_MAX_FAILS = 5
ALLOWED_HEADERS = {"referer": "Referer", "user-agent": "User-Agent",
                   "cookie": "Cookie", "origin": "Origin"}
EXT_ORIGIN = re.compile(r"^(chrome-extension|moz-extension)://[A-Za-z0-9._-]{8,64}$")
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
BLOCKED_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home.arpa", ".localdomain")


class ValidationError(ValueError):
    pass


def _default_resolver(host):
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({i[4][0].split("%")[0] for i in infos})


def _ip_is_public(text):
    ip = ipaddress.ip_address(text)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def validate_media_url(url, allow_private=False, resolver=_default_resolver, check_host=True):
    """Return the url if acceptable, else raise ValidationError."""
    if not isinstance(url, str) or not url or len(url) > MAX_URL:
        raise ValidationError("bad_url")
    if _CTRL.search(url) or url != url.strip() or " " in url:
        raise ValidationError("bad_url")
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().rstrip(".")
        parts.port  # raises on invalid port
    except ValueError:
        raise ValidationError("bad_url")
    if parts.scheme not in ("http", "https"):
        raise ValidationError("scheme_not_allowed")
    if parts.username is not None or parts.password is not None:
        raise ValidationError("credentials_not_allowed")
    if not host:
        raise ValidationError("bad_url")
    if not check_host or allow_private:
        return url
    if host == "localhost" or host.endswith(BLOCKED_SUFFIXES):
        raise ValidationError("private_address")
    try:  # literal IP (also catches things like [::1])
        addrs = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            host.encode("idna")
            addrs = resolver(host)
        except (OSError, UnicodeError):
            raise ValidationError("unresolvable_host")
    if not addrs:
        raise ValidationError("unresolvable_host")
    for a in addrs:
        try:
            ok = _ip_is_public(a)
        except ValueError:
            ok = False
        if not ok:
            raise ValidationError("private_address")
    return url


def _clean_text(value, limit):
    if not isinstance(value, str):
        return ""
    return _CTRL.sub(" ", value).strip()[:limit]


def sanitize_headers(raw):
    if raw is None:
        return {}
    if not isinstance(raw, dict) or len(raw) > 20:
        raise ValidationError("bad_headers")
    out = {}
    for k, v in raw.items():
        name = ALLOWED_HEADERS.get(str(k).lower())
        if name is None:
            continue  # silently drop everything not on the allowlist
        if not isinstance(v, str) or len(v) > MAX_HEADER_VALUE or _CTRL.search(v):
            raise ValidationError("bad_headers")
        if v:
            out[name] = v
    return out


def parse_download_request(obj, allow_private=False, resolver=_default_resolver):
    if not isinstance(obj, dict):
        raise ValidationError("bad_body")
    if obj.get("v", PROTOCOL) != PROTOCOL:
        raise ValidationError("unsupported_version")
    url = validate_media_url(obj.get("url"), allow_private, resolver)
    page = obj.get("page_url")
    if page not in (None, ""):
        validate_media_url(page, check_host=False)  # only used as Referer: scheme check
    else:
        page = ""
    kind = obj.get("kind") if obj.get("kind") in ("page", "hls", "dash", "video", "audio", "link") else "link"
    return {"url": url, "page_url": page, "title": _clean_text(obj.get("title"), MAX_TITLE),
            "kind": kind, "headers": sanitize_headers(obj.get("headers"))}


class TokenBucket:
    def __init__(self, capacity, per_second, clock=time.monotonic):
        self.capacity, self.rate, self.clock = float(capacity), float(per_second), clock
        self.tokens, self.last, self.lock = float(capacity), clock(), threading.Lock()

    def allow(self):
        with self.lock:
            now = self.clock()
            self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False


def _hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Receiver:
    """on_job(job: dict) is called from a server thread for every accepted request.
    In a Qt app emit a signal from it; do not touch widgets directly."""

    def __init__(self, on_job, state_path, port=DEFAULT_PORT, allow_private=False,
                 resolver=_default_resolver, clock=time.monotonic, app_version="0"):
        self.on_job, self.state_path = on_job, state_path
        self.port, self.allow_private, self.resolver = port, allow_private, resolver
        self.clock, self.app_version = clock, app_version
        self.download_limit = TokenBucket(10, 1.0, clock)
        self.request_limit = TokenBucket(60, 20.0, clock)
        self.pair_limit = TokenBucket(5, 5 / 60.0, clock)
        self._lock = threading.Lock()
        self._code = None  # (code, expires_at, fails)
        self._pairings = self._load()
        self._httpd = self._thread = None

    # ---- persistence: {origin: sha256(token)} ; file is 0600 ----
    def _load(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                data = json.load(f)
            return {o: h for o, h in data.get("pairings", {}).items() if EXT_ORIGIN.match(o)}
        except (OSError, ValueError, AttributeError):
            return {}

    def _save(self):
        os.makedirs(os.path.dirname(os.path.abspath(self.state_path)), exist_ok=True)
        tmp = self.state_path + ".tmp"
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"pairings": self._pairings}, f)
        os.replace(tmp, self.state_path)

    # ---- pairing ----
    def new_pairing_code(self):
        """Show this to the user in the app (e.g. 'Pair browser' button)."""
        code = "%04d-%04d" % (secrets.randbelow(10000), secrets.randbelow(10000))
        with self._lock:
            self._code = [code, self.clock() + PAIR_CODE_TTL, 0]
        return code

    def revoke_all(self):
        with self._lock:
            self._pairings = {}
            self._code = None
            self._save()

    def paired_origins(self):
        return sorted(self._pairings)

    def _pair(self, origin, code):
        with self._lock:
            c = self._code
            if not c or self.clock() > c[1]:
                self._code = None
                return None
            if not isinstance(code, str) or not hmac.compare_digest(code.strip(), c[0]):
                c[2] += 1
                if c[2] >= PAIR_MAX_FAILS:
                    self._code = None
                return None
            self._code = None  # single use
            if origin not in self._pairings and len(self._pairings) >= MAX_PAIRINGS:
                self._pairings.pop(next(iter(self._pairings)))
            token = secrets.token_urlsafe(32)
            self._pairings[origin] = _hash(token)
            self._save()
            return token

    def _token_ok(self, origin, header):
        if not header or not header.startswith("Bearer "):
            return False
        expected = self._pairings.get(origin)
        return bool(expected) and hmac.compare_digest(expected, _hash(header[7:].strip()))

    # ---- server ----
    def start(self):
        recv = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.0"
            timeout = 10
            server_version = "VDReceiver"
            sys_version = ""

            def log_message(self, *a):  # never log URLs/cookies
                pass

            def _send(self, status, obj=None, origin=None):
                body = json.dumps(obj if obj is not None else {}).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                if origin:  # exact echo of a validated extension origin, never "*"
                    self.send_header("Access-Control-Allow-Origin", origin)
                    self.send_header("Vary", "Origin")
                self.end_headers()
                self.wfile.write(body)

            def _gate(self):
                """Common checks. Returns origin or None (response already sent)."""
                port = self.server.server_address[1]
                if self.headers.get("Host", "").lower() not in ("127.0.0.1:%d" % port, "localhost:%d" % port):
                    self._send(403, {"error": "bad_host"})
                    return None
                origin = self.headers.get("Origin", "")
                if not EXT_ORIGIN.match(origin):
                    self._send(403, {"error": "bad_origin"})
                    return None
                if not recv.request_limit.allow():
                    self._send(429, {"error": "rate_limited"}, origin)
                    return None
                return origin

            def do_OPTIONS(self):
                origin = self._gate()
                if not origin:
                    return
                self.send_response(204)
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Access-Control-Allow-Methods", "POST")
                self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
                self.send_header("Access-Control-Allow-Private-Network", "true")
                self.send_header("Access-Control-Max-Age", "600")
                self.send_header("Vary", "Origin")
                self.send_header("Content-Length", "0")
                self.end_headers()

            def _json_body(self, origin):
                if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
                    self._send(415, {"error": "json_required"}, origin)
                    return None
                try:
                    n = int(self.headers.get("Content-Length", ""))
                except ValueError:
                    self._send(411, {"error": "length_required"}, origin)
                    return None
                if n < 0 or n > MAX_BODY:
                    self._send(413, {"error": "too_large"}, origin)
                    return None
                try:
                    return json.loads(self.rfile.read(n).decode("utf-8"))
                except (ValueError, UnicodeError):
                    self._send(400, {"error": "bad_json"}, origin)
                    return None

            def do_GET(self):
                # Browsers omit Origin on some extension GETs, so everything is POST.
                origin = self._gate()
                if origin:
                    self._send(405, {"error": "use_post"}, origin)

            def do_POST(self):
                origin = self._gate()
                if not origin:
                    return
                if self.path == "/v1/ping":
                    paired = recv._token_ok(origin, self.headers.get("Authorization", ""))
                    return self._send(200, {"ok": True, "app": APP_NAME, "protocol": PROTOCOL,
                                            "version": recv.app_version, "paired": paired}, origin)
                if self.path == "/v1/pair":
                    if not recv.pair_limit.allow():
                        return self._send(429, {"error": "rate_limited"}, origin)
                    body = self._json_body(origin)
                    if body is None:
                        return
                    token = recv._pair(origin, body.get("code") if isinstance(body, dict) else None)
                    if not token:
                        return self._send(403, {"error": "bad_pairing_code"}, origin)
                    return self._send(200, {"token": token, "app": APP_NAME, "protocol": PROTOCOL}, origin)
                if self.path == "/v1/download":
                    if not recv._token_ok(origin, self.headers.get("Authorization", "")):
                        return self._send(401, {"error": "not_paired"}, origin)
                    if not recv.download_limit.allow():
                        return self._send(429, {"error": "rate_limited"}, origin)
                    body = self._json_body(origin)
                    if body is None:
                        return
                    try:
                        job = parse_download_request(body, recv.allow_private, recv.resolver)
                    except ValidationError as e:
                        return self._send(422, {"error": str(e)}, origin)
                    job.update(id=uuid.uuid4().hex, received_at=time.time(), origin=origin)
                    try:
                        recv.on_job(job)
                    except Exception:
                        return self._send(500, {"error": "app_error"}, origin)
                    return self._send(202, {"ok": True, "id": job["id"]}, origin)
                self._send(404, {"error": "not_found"}, origin)

        self._httpd = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)  # loopback only
        self._httpd.daemon_threads = True
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, name="vd-receiver", daemon=True)
        self._thread.start()
        return self.port

    def stop(self):
        if self._httpd:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None


# ---- helpers for the app side (no shell: always pass argv as a list) ----
def cookie_header_to_netscape(cookie_header, url, path):
    """Write a Netscape cookie file (0600) from a 'a=b; c=d' header for yt-dlp --cookies.
    Avoids putting cookies on a command line, where other local users can read them."""
    host = urlsplit(url).hostname or ""
    secure = "TRUE" if url.lower().startswith("https") else "FALSE"
    lines = ["# Netscape HTTP Cookie File"]
    for pair in cookie_header.split(";"):
        if "=" not in pair:
            continue
        name, value = pair.strip().split("=", 1)
        if name and not _CTRL.search(name + value) and "\t" not in name + value:
            lines.append("\t".join([host, "FALSE", "/", secure, "0", name, value]))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return path


def ytdlp_args(job, cookie_file=None):
    """Extra yt-dlp argv items for a job. Returns a list; never join into a string."""
    args = []
    h = job.get("headers", {})
    if h.get("Referer") or job.get("page_url"):
        args += ["--referer", h.get("Referer") or job["page_url"]]
    if h.get("User-Agent"):
        args += ["--user-agent", h["User-Agent"]]
    if cookie_file:
        args += ["--cookies", cookie_file]
    return args
