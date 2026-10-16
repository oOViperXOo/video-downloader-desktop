"""Filesystem and scheduler safety helpers, independent of the Qt UI."""
from pathlib import Path
import os
import re
import uuid
from urllib.parse import parse_qs, urlsplit


WAITING_DEFAULT_KEYS = ('mode', 'container', 'quality', 'audio_format', 'bitrate',
                        'outdir', 'connection_mode', 'connections')


def set_connection_mode(job, mode):
    """Preserve aria2 sparse state in its OLD directory before changing mode.

    Return the number of control files preserved. Errors propagate so callers
    must not apply defaults or start the job after a failed preservation.
    """
    saved = 0
    if mode == 'single' and job['config'].get('connection_mode') == 'multiple':
        root = Path(job['config']['outdir']).expanduser().resolve()
        for filename in job.get('transfer_files', []):
            partial = Path(str(filename) + '.part')
            control = Path(str(partial) + '.aria2')
            if not partial.resolve().is_relative_to(root) or not control.resolve().is_relative_to(root):
                continue
            if not control.is_file():
                continue
            suffix = '.multi-backup-' + uuid.uuid4().hex
            backup = Path(str(partial) + suffix)
            moved = False
            if partial.is_file():
                partial.rename(backup)
                moved = True
            try:
                control.rename(str(control) + suffix)
            except OSError:
                if moved:
                    backup.rename(partial)
                raise
            saved += 1
            job.update(percent=0, downloaded=0, total=None)
    job['config']['connection_mode'] = mode
    job['config']['connections'] = max(2, int(job['config'].get('connections', 4)))
    return saved


def apply_waiting_defaults(job, defaults):
    """Caller checks waiting/not-running status; preserve before replacing outdir."""
    saved = set_connection_mode(job, defaults['connection_mode'])
    job['config'].update({key: defaults[key] for key in WAITING_DEFAULT_KEYS})
    return saved


def _youtube_id(url):
    """Only identify aliases whose extractor item identity is well understood."""
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or '').lower()
        parts = parsed.path.strip('/').split('/')
        if host in ('youtu.be', 'www.youtu.be'):
            return parts[0] or None
        if host in ('youtube.com', 'www.youtube.com', 'm.youtube.com', 'music.youtube.com'):
            if parsed.path == '/watch':
                return parse_qs(parsed.query).get('v', [None])[0]
            if len(parts) == 2 and parts[0] in ('shorts', 'embed', 'live'):
                return parts[1] or None
    except ValueError:
        pass
    return None


def destinations_conflict(left, right):
    """Conservatively exclude possible concurrent final/partial destination writers.

    Arbitrary templates and unknown extractor identities serialize per directory.
    Only the same template with an unmodified id token and known distinct inspected
    item IDs can establish separate names without inspecting rendered metadata.
    """
    def directory(job):
        return os.path.normcase(str(Path(job['config']['outdir']).expanduser().resolve()))
    if directory(left) != directory(right):
        return False
    template = left['config'].get('template', '')
    if template != right['config'].get('template', '') or '%(id)s' not in template.replace('%%', ''):
        return True
    def identity(job):
        value = str(job.get('video_id') or _youtube_id(job['url']) or '')
        # Restrict inspected IDs to characters whose Windows filename mapping is
        # unambiguous. Other IDs fall back to conservative directory exclusion.
        return value if re.fullmatch(r'[A-Za-z0-9_-]+', value) else None
    left_id, right_id = identity(left), identity(right)
    return not (left_id and right_id and left_id.casefold() != right_id.casefold())


