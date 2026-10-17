"""Read-only release discovery. No binaries are downloaded or executed."""
import ipaddress
import json
import re
from time import monotonic
from queue import Queue, Empty
from threading import BoundedSemaphore, Thread
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler

APP_VERSION = '1.0.4'
MAX_MANIFEST_BYTES = 65536

class UpdateCheckError(ValueError):
    pass

def validate_https_url(url):
    if not isinstance(url, str) or not url or len(url) > 4096 or any(c.isspace() or ord(c) < 32 for c in url) or '\\' in url:
        raise UpdateCheckError('A valid HTTPS URL is required.')
    try:
        parts = urlsplit(url)
        port = parts.port
        if parts.scheme != 'https' or not parts.hostname or parts.username is not None or parts.password is not None or parts.fragment:
            raise ValueError()
        hostname = parts.hostname.encode('idna').decode('ascii')
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            if len(hostname) > 253 or not all(re.fullmatch(r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?', label) for label in hostname.rstrip('.').split('.')):
                raise ValueError()
        if re.search(r'%(?![0-9a-fA-F]{2})', url):
            raise ValueError()
        if port is not None and not 1 <= port <= 65535:
            raise ValueError()
    except (ValueError, UnicodeError):
        raise UpdateCheckError('A valid HTTPS URL without credentials or fragment is required.') from None
    return url

def _version(value):
    if not isinstance(value, str) or len(value) > 64:
        raise UpdateCheckError('Version must use major.minor.patch with optional prerelease.')
    match = re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?', value)
    if not match:
        raise UpdateCheckError('Version must use major.minor.patch with optional prerelease.')
    pre = match[4]
    if pre and any(p.isdigit() and len(p) > 1 and p.startswith('0') for p in pre.split('.')):
        raise UpdateCheckError('Invalid numeric prerelease identifier.')
    return tuple(map(int, match.group(1, 2, 3))), pre

def _newer(candidate, current):
    a, ap = _version(candidate)
    b, bp = _version(current)
    if a != b:
        return a > b
    if ap is None or bp is None:
        return ap is None and bp is not None
    for x, y in zip(ap.split('.'), bp.split('.')):
        if x == y:
            continue
        if x.isdigit() and y.isdigit():
            return int(x) > int(y)
        if x.isdigit() != y.isdigit():
            return not x.isdigit()
        return x > y
    return len(ap.split('.')) > len(bp.split('.'))

def validate_manifest(data, current_version=APP_VERSION):
    _version(current_version)
    if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != 1:
        raise UpdateCheckError('Unsupported update manifest schema.')
    version = data.get('version')
    _version(version)
    url = validate_https_url(data.get('download_url'))
    notes = data.get('notes', '')
    if not isinstance(notes, str) or len(notes) > 16000:
        raise UpdateCheckError('Release notes must be plain text of at most 16000 characters.')
    return dict(available=_newer(version, current_version), version=version, download_url=url, notes=notes)

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise UpdateCheckError('Update manifest redirects are not accepted; configure its final HTTPS URL.')

def _fetch_update(url, current_version=APP_VERSION, *, timeout=8):
    validate_https_url(url)
    _version(current_version)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 30:
        raise UpdateCheckError('Update timeout must be between 1 and 30 seconds.')
    try:
        deadline = monotonic() + timeout
        request = Request(url, headers={'Accept': 'application/json', 'User-Agent': 'VideoDownloader/' + APP_VERSION})
        with build_opener(_NoRedirect()).open(request, timeout=timeout) as response:
            # read1 performs at most one socket read, so a trickling peer cannot
            # hide indefinitely inside HTTPResponse.read(size). Each read still
            # has the socket timeout; deadline checks bound the body phase to
            # the deadline plus at most one outstanding socket read.
            read_chunk = getattr(response, 'read1', None)
            if read_chunk is None:  # Small in-memory response adapters in tests.
                if monotonic() >= deadline:
                    raise UpdateCheckError('Update check exceeded its total deadline.')
                raw = response.read(MAX_MANIFEST_BYTES + 1)
            else:
                chunks = []
                size = 0
                while True:
                    if monotonic() >= deadline:
                        raise UpdateCheckError('Update check exceeded its total deadline.')
                    chunk = read_chunk(min(4096, MAX_MANIFEST_BYTES + 1 - size))
                    if monotonic() >= deadline:
                        raise UpdateCheckError('Update check exceeded its total deadline.')
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    if size > MAX_MANIFEST_BYTES:
                        raise UpdateCheckError('Update manifest is too large.')
                raw = b''.join(chunks)
            if monotonic() >= deadline:
                raise UpdateCheckError('Update check exceeded its total deadline.')
        if len(raw) > MAX_MANIFEST_BYTES:
            raise UpdateCheckError('Update manifest is too large.')
        return validate_manifest(json.loads(raw.decode('utf-8')), current_version)
    except UpdateCheckError:
        raise
    except Exception as exc:
        raise UpdateCheckError('Could not read the update manifest: ' + str(exc)) from exc

# At most one abandoned network operation can remain alive. It owns no Qt
# objects and is daemonized, so slow DNS/TLS/headers cannot prevent app exit.
_FETCH_SLOT = BoundedSemaphore(1)

def check_for_update(url, current_version=APP_VERSION, *, timeout=8):
    validate_https_url(url)
    _version(current_version)
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 1 <= timeout <= 30:
        raise UpdateCheckError('Update timeout must be between 1 and 30 seconds.')
    fetch_slot = _FETCH_SLOT
    if not fetch_slot.acquire(blocking=False):
        raise UpdateCheckError('An earlier update request is still finishing; try again later.')
    result = Queue(maxsize=1)
    def fetch():
        try:
            result.put((True, _fetch_update(url, current_version, timeout=timeout)))
        except Exception as exc:
            result.put((False, exc))
        finally:
            fetch_slot.release()
    try:
        Thread(target=fetch, name='release-metadata-fetch', daemon=True).start()
    except Exception:
        fetch_slot.release()
        raise
    try:
        success, value = result.get(timeout=timeout * 2)
    except Empty:
        raise UpdateCheckError('Update check exceeded its total deadline.') from None
    if not success:
        raise value
    return value
