"""Pure queue decisions shared by UI workflows; no network requests."""
from datetime import datetime,time
from pathlib import Path
import math
import shutil
from urllib.parse import urlsplit,urlunsplit,parse_qs


def canonical_url(url):
    from engine import validate_url
    url=str(url).strip();validate_url(url)
    parts=urlsplit(url);host=(parts.hostname or '').lower();query=parse_qs(parts.query)
    if host in ('youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','youtu.be','www.youtu.be'):
        if query.get('list'): return 'youtube:playlist:'+query['list'][0]
        identity=None;segments=parts.path.strip('/').split('/')
        if host.endswith('youtu.be'): identity=segments[0]
        elif parts.path=='/watch': identity=query.get('v',[None])[0]
        elif len(segments)==2 and segments[0] in ('shorts','embed','live'): identity=segments[1]
        if identity:return 'youtube:video:'+identity
    port=parts.port
    authority=('['+host+']') if ':' in host else host
    if port and not ((parts.scheme=='https' and port==443) or (parts.scheme=='http' and port==80)): authority+=':'+str(port)
    return urlunsplit((parts.scheme.lower(),authority,parts.path or '/',parts.query,''))


def unique_links(text,existing_urls=()):
    """Keep original valid URL spelling; canonical identities only deduplicate."""
    known=set();accepted=[];invalid=[];duplicates=0
    for url in existing_urls:
        try:known.add(canonical_url(url))
        except (ValueError,TypeError):pass
    for token in str(text).split():
        url=token.strip('<>"\'')
        try:key=canonical_url(url)
        except (ValueError,TypeError):invalid.append(token);continue
        if key in known:duplicates+=1;continue
        known.add(key);accepted.append(url)
    return accepted,duplicates,invalid


def retry_delay(job,now=None,max_retries=3):
    """Only transient failures retry; count describes attempts already retried."""
    if job.get('status') in ('cancelled','paused','done','skipped') or job.get('user_stopped'):return None
    try:count=max(0,int(job.get('retry_count',0)))
    except (ValueError,TypeError):return None
    if count>=max_retries:return None
    message=str(job.get('error') or '').lower()
    permanent=('drm','unsupported','login','log in','sign in','private video','members-only','not found','404','403','permission denied','disk','space','no format','not available in your country','file exists')
    if any(word in message for word in permanent):return None
    transient=('timed out','timeout','temporar','connection','network','429','500','502','503','504','reset','rate limit','service unavailable','remote end closed','try again later')
    if not any(word in message for word in transient):return None
    return min(120,5*3**count)


def schedule_allows(now,start_at='',quiet_start='',quiet_end=''):
    """Local wall-clock schedule. Quiet windows hold new jobs, never active jobs."""
    try:
        if start_at:
            start=datetime.fromisoformat(start_at)
            compare=now
            if start.tzinfo is not None and now.tzinfo is None:compare=now.astimezone()
            elif start.tzinfo is None and now.tzinfo is not None:compare=now.replace(tzinfo=None)
            if compare<start:return False
        if quiet_start or quiet_end:
            if not quiet_start or not quiet_end:return False
            start=time.fromisoformat(quiet_start);end=time.fromisoformat(quiet_end);current=now.time().replace(tzinfo=None)
            if start==end:return True
            if (start<end and start<=current<end) or (start>end and (current>=start or current<end)):return False
        return True
    except (TypeError,ValueError):return False


def _estimated_size(job):
    selection=job.get('selected_format') or {}
    if not isinstance(selection,dict):selection={}
    candidates=[job.get('estimated_bytes'),job.get('estimated_size'),job.get('total'),selection.get('estimated_bytes'),selection.get('estimated_size'),selection.get('filesize'),selection.get('filesize_approx')]
    for value in candidates:
        try:
            value=float(value)
            if math.isfinite(value) and value>0:return int(value)
        except (TypeError,ValueError,OverflowError):pass
    return 0


def disk_space_required(job):
    """Allow temporary streams/remux/conversion; unknown sizes get a small floor.

    This is a preflight estimate, never a promise that an unknown-size file fits.
    """
    estimate=_estimated_size(job)
    downloaded=max(0,int(job.get('downloaded') or 0))
    factor=2.5 if job.get('kind')=='conversion' or job.get('_converting') or job.get('convert_to_mp4') or job.get('config',{}).get('convert_mp4') else 2.0
    return max(64*1024*1024,int(estimate*factor)-min(downloaded,estimate)+32*1024*1024)


def check_disk_space(job,free_bytes=None):
    destination=Path(job.get('config',{}).get('outdir') or '.').expanduser().resolve()
    while not destination.exists() and destination!=destination.parent:destination=destination.parent
    available=shutil.disk_usage(destination).free if free_bytes is None else int(free_bytes)
    required=disk_space_required(job)
    return available>=required,required,available
