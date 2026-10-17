#!/usr/bin/env python3
"""engine.py - GUI-agnostic video download engine for YouTube and the many other sites yt-dlp supports.

Drives the yt-dlp CLI through subprocess. No GUI code, no DRM circumvention
(DRM-protected streams are reported as per-item errors, never bypassed).

Public API
----------
inspect_url(url)                 -> {"title", "items": [...], "heights": [...], "is_playlist"}
build_options(config)            -> dict of yt-dlp CLI options  {"--flag": value}
options_to_args(opts)            -> list[str] for subprocess
build_command(config, url)       -> full argv list
Downloader(config, callback)     -> .run(url) / .cancel() / .pause() / .resume()
run_download(config, url, emit)  -> emit defaults to NDJSON on stdout
main()                           -> CLI: --inspect URL | --download CONFIG_JSON URL

Events (dicts passed to callback / written as one JSON object per line):
  {"type":"progress","percent","speed","eta","filename","downloaded","total","item"}
  {"type":"status","status":"starting|item_start|skipped|processing|paused|resumed|cancelled|finished", ...}
  {"type":"item_done","path","item"}
  {"type":"error","message","item"}     item = {"index","id","title"} or None
  {"type":"done","path","paths","errors","skipped","returncode"}

The desktop GUI uses process-tree stop-and-resume on both operating systems.
Downloader.pause()/resume() are optional low-level POSIX-only controls for
programmatic callers; the GUI does not use those methods. Partials are kept.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
from urllib.parse import urlsplit,parse_qs,urlencode
from html import unescape
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Callable, Dict, List, Optional

Event = Dict[str, Any]
Callback = Callable[[Event], None]

YTDLP_CMD = [sys.executable, '--ytdlp'] if getattr(sys, 'frozen', False) else [sys.executable, '-m', 'yt_dlp']


_BLOCKED_HOST_SUFFIXES = (".localhost", ".local", ".internal", ".lan", ".home", ".corp", ".intranet", ".localdomain")
URL_ERROR = "Enter a full http(s) link to a video, audio or playlist page on a public website."

# Well-known sites yt-dlp supports. Used only for friendly clipboard suggestions and labels;
# validate_url() itself accepts any public http(s) URL and yt-dlp decides whether it is supported.
KNOWN_SITES = {
    "YouTube": ("youtube.com", "youtu.be", "youtube-nocookie.com"),
    "Vimeo": ("vimeo.com",),
    "Facebook": ("facebook.com", "fb.watch"),
    "Instagram": ("instagram.com",),
    "TikTok": ("tiktok.com",),
    "X / Twitter": ("twitter.com", "x.com"),
    "Dailymotion": ("dailymotion.com", "dai.ly"),
    "Twitch": ("twitch.tv",),
    "Reddit": ("reddit.com", "redd.it"),
    "SoundCloud": ("soundcloud.com",),
    "Bilibili": ("bilibili.com",),
    "Bandcamp": ("bandcamp.com",),
    "Streamable": ("streamable.com",),
    "Rumble": ("rumble.com",),
    "Odysee": ("odysee.com",),
    "Vevo": ("vevo.com",),
    "Mixcloud": ("mixcloud.com",),
    "Tumblr": ("tumblr.com",),
    "VK": ("vk.com",),
    "Archive.org": ("archive.org",),
}


def _host_matches(host, domain):
    return host == domain or host.endswith("." + domain)


def site_name(url):
    """Friendly name of a well-known site for this URL, or None."""
    from urllib.parse import urlparse
    try:
        host = (urlparse(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return None
    for name, domains in KNOWN_SITES.items():
        if any(_host_matches(host, d) for d in domains):
            return name
    return None


def _ip_from_host(host):
    """Parse a host as an IP, including the legacy shorthand forms (2130706433, 0x7f.1, 017700000001)."""
    import ipaddress
    import socket
    try:
        return ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        pass
    if re.fullmatch(r"[0-9a-fx.]+", host, re.I):
        try:
            return ipaddress.ip_address(socket.inet_ntoa(socket.inet_aton(host)))
        except (OSError, ValueError):
            return None
    return None


def _ip_is_public(ip):
    mapped = getattr(ip, "ipv4_mapped", None)
    if mapped is not None:
        ip = mapped
    return ip.is_global and not ip.is_multicast


def validate_url(url, resolve=False):
    """Accept only http(s) URLs that point at a public host. Returns the URL or raises ValueError.

    Blocks: non-http(s) schemes (file:, ftp:, javascript: ...), embedded credentials, localhost and
    internal-looking names, and literal or (with resolve=True) DNS-resolved private, loopback,
    link-local, reserved and multicast addresses. Hosts that fail to resolve are left to yt-dlp.
    """
    from urllib.parse import urlparse
    if not isinstance(url, str) or not url.strip() or url != url.strip() or any(c in url for c in "\r\n\t \x00"):
        raise ValueError(URL_ERROR)
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().rstrip(".")
        parsed.port  # raises ValueError on a bad port
    except ValueError:
        raise ValueError(URL_ERROR)
    if parsed.scheme not in ("http", "https") or not host or parsed.username or parsed.password:
        raise ValueError(URL_ERROR)
    blocked = ValueError("This address points to a local or private network and is blocked.")
    if host == "localhost" or host.endswith(_BLOCKED_HOST_SUFFIXES) or "." not in host and _ip_from_host(host) is None:
        raise blocked
    ip = _ip_from_host(host)
    if ip is not None:
        if not _ip_is_public(ip):
            raise blocked
    elif resolve:
        import socket
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError:
            infos = []
        import ipaddress
        for info in infos:
            try:
                addr = ipaddress.ip_address(info[4][0].split("%")[0])
            except ValueError:
                continue
            if not _ip_is_public(addr):
                raise blocked
    return url


PROG_MARK = "YTDLPENG_PROG "
ITEM_MARK = "YTDLPENG_ITEM "
FILE_MARK = "YTDLPENG_FILE "

MAX_CONNECTIONS = 16                 # aria2c accepts at most 16 connections per server
DEFAULT_CONNECTIONS = 4
BROWSERS = ("chrome", "firefox", "edge", "brave", "chromium", "opera", "vivaldi", "safari", "whale")
AUDIO_FORMATS = ("mp3", "m4a", "opus")
SUB_FORMATS = ("srt", "vtt", "ass", "best")


class EngineError(Exception):
    pass


@dataclass
class DownloadConfig:
    # --- output ---
    output_dir: str = "."
    output_template: str = "%(title)s [%(id)s].%(ext)s"
    # --- video ---
    mode: str = "video"                 # "video" | "audio"
    max_height: Optional[int] = None    # quality ladder cap: 2160/1440/1080/720/480/360/240/144; None = best
    min_height: Optional[int] = None    # optional floor; ignored if nothing qualifies (falls back to best)
    format_id: Optional[str] = None     # exact inspected format selector, no fallback
    prefer_worst: bool = False
    merge_format: str = "native"        # native preserves source containers; optional mp4/mkv/webm remux
    prefer_mp4_codecs: bool = False     # prefer h264/aac so mp4 needs no re-encode
    # --- audio only ---
    audio_format: str = "mp3"           # mp3 | m4a | opus
    audio_bitrate: Optional[str] = "192"  # kbps ("128","192","320") ; None = best (VBR 0)
    # --- subtitles ---
    subtitles: bool = False
    sub_langs: List[str] = field(default_factory=lambda: ["en"])
    auto_subs: bool = False
    embed_subs: bool = False
    sub_format: str = "srt"
    # --- embedding ---
    embed_thumbnail: bool = False
    embed_metadata: bool = False
    write_thumbnail: bool = False
    # --- throttling / retries ---
    rate_limit: Optional[str] = None    # "500K", "2M"
    retries: int = 10
    # --- playlist handling ---
    no_playlist: bool = False
    playlist_items: Optional[str] = None  # "1-3,7"
    # --- archive / skip ---
    archive_file: Optional[str] = None  # --download-archive
    skip_existing: bool = True          # --no-overwrites
    # --- resume / connections ---
    resume: bool = True                 # continue partial .part files (yt-dlp --continue); partials are always kept
    connections: int = 4                # parallel connections/fragments (1 = single connection)
    external_downloader: str = "off"    # native gives continuous progress and sequential writes
    aria2c_path: Optional[str] = None   # explicit aria2c location; None = auto-detect
    # --- misc ---
    referer: Optional[str] = None       # set by the browser extension for sites that check the Referer
    user_agent: Optional[str] = None
    proxy: Optional[str] = None         # http://host:port | https:// | socks5://host:port
    cookies_file: Optional[str] = None
    cookies_from_browser: Optional[str] = None  # chrome|firefox|edge|brave|... (optional login for private/age-gated content)
    extra_args: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DownloadConfig":
        known = {f.name for f in fields(cls)}
        unknown = set(d) - known
        if unknown:
            raise EngineError("unknown config keys: %s" % ", ".join(sorted(unknown)))
        return cls(**d)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _as_config(config: Any) -> DownloadConfig:
    if isinstance(config, DownloadConfig):
        return config
    if isinstance(config, dict):
        return DownloadConfig.from_dict(config)
    raise EngineError("config must be DownloadConfig or dict")


# ---------------------------------------------------------------- options

def format_selector(c: DownloadConfig) -> str:
    """Quality ladder -> yt-dlp -f expression with graceful fallbacks."""
    if c.format_id:
        return c.format_id
    if c.mode == "audio":
        return "bestaudio/best"
    h = c.max_height
    if c.prefer_worst:
        return "worstvideo+worstaudio/worst"
    hf = "[height<=%d]" % h if h else ""
    if c.min_height:
        hf += "[height>=%d]" % c.min_height
    pref = ""
    if c.prefer_mp4_codecs and (h is not None and h <= 1080):
        pref = "bv*%s[vcodec^=avc1]+ba[ext=m4a]/" % hf
    # All alternatives preserve the chosen resolution ceiling.
    # trailing "/ba" lets audio-only sites (SoundCloud, Bandcamp, Mixcloud) work in video mode
    return "%sbv*%s+ba/b%s/ba" % (pref, hf, hf)


def _validate(c: DownloadConfig) -> None:
    if c.format_id is not None and (not isinstance(c.format_id, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:\+[A-Za-z0-9_.-]+)?", c.format_id)):
        raise EngineError("format_id must be an inspected format ID or video+audio pair")
    if c.mode not in ("video", "audio"):
        raise EngineError("mode must be 'video' or 'audio'")
    if c.audio_format not in AUDIO_FORMATS:
        raise EngineError("audio_format must be one of %s" % (AUDIO_FORMATS,))
    if c.sub_format not in SUB_FORMATS:
        raise EngineError("sub_format must be one of %s" % (SUB_FORMATS,))
    if c.merge_format not in ("native", "mp4", "mkv", "webm"):
        raise EngineError("merge_format must be native, mp4, mkv or webm")
    if c.audio_bitrate is not None and not re.fullmatch(r"\d{2,3}", str(c.audio_bitrate).rstrip("kK")):
        raise EngineError("audio_bitrate must look like '192' (kbps)")
    if c.rate_limit is not None and not re.fullmatch(r"\d+(\.\d+)?[KkMmGg]?", c.rate_limit):
        raise EngineError("rate_limit must look like '500K' or '2M'")
    if c.max_height is not None and c.max_height <= 0:
        raise EngineError("max_height must be positive")
    if not isinstance(c.connections, int) or isinstance(c.connections, bool) or not 1 <= c.connections <= MAX_CONNECTIONS:
        raise EngineError("connections must be a whole number from 1 to %d" % MAX_CONNECTIONS)
    for name in ("referer", "user_agent"):
        v = getattr(c, name)
        if v is not None and (not isinstance(v, str) or len(v) > 1000 or re.search(r"[\x00-\x1f\x7f]", v)):
            raise EngineError("%s contains invalid characters" % name)
    if c.proxy is not None and not re.fullmatch(r"(https?|socks4a?|socks5h?)://[^\s/]+(:\d{1,5})?/?", c.proxy):
        raise EngineError("proxy must look like http://host:port or socks5://host:port")
    if c.external_downloader not in ("auto", "aria2c", "off"):
        raise EngineError("external_downloader must be auto, aria2c or off")
    if c.cookies_from_browser is not None and c.cookies_from_browser.split(":")[0].lower() not in BROWSERS:
        raise EngineError("cookies_from_browser must be one of %s" % ", ".join(BROWSERS))
    if c.cookies_from_browser is not None and not re.fullmatch(r"[A-Za-z0-9_\-]+(:[^\s:+]{1,200})?", c.cookies_from_browser):
        raise EngineError("cookies_from_browser must be just a browser name (optionally name:profile)")


def find_aria2c(hint: Optional[str] = None) -> Optional[str]:
    """Locate aria2c: explicit hint, a copy bundled with the app, then PATH. None if missing."""
    cands = []
    if hint:
        cands.append(hint)
    exe = "aria2c.exe" if os.name == "nt" else "aria2c"
    bases = []
    if getattr(sys, "frozen", False):
        bases += [getattr(sys, "_MEIPASS", ""), os.path.dirname(sys.executable)]
    bases += [os.path.dirname(os.path.abspath(__file__))]
    for b in bases:
        if b:
            cands += [os.path.join(b, exe), os.path.join(b, "bin", exe)]
    for p in cands:
        if os.path.isfile(p) and os.access(p, os.X_OK):
            return p
    return shutil.which("aria2c")


def js_runtime_args() -> List[str]:
    """Select a bundled or locally installed runtime for YouTube challenges."""
    if getattr(sys, "frozen", False):
        bases = [getattr(sys, "_MEIPASS", os.path.dirname(sys.executable)), os.path.dirname(sys.executable)]
    else:
        bases = [os.path.dirname(sys.executable), os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools")]
    for name, exe in (("deno", "deno"), ("quickjs", "qjs"), ("quickjs", "quickjs")):
        for base in bases:
            p = os.path.join(base, exe + (".exe" if os.name == "nt" else ""))
            if os.path.isfile(p):
                return ["--js-runtimes", name + ":" + p]
    return []


def plan_downloader(c: DownloadConfig) -> Dict[str, Any]:
    """Decide how multi-connection downloading will run: {"aria2c": path|None, "connections": n, "notice": str|None}."""
    n = c.connections
    if n <= 1:
        return {"aria2c": None, "connections": 1, "notice": None}
    if c.external_downloader == "off":
        return {"aria2c": None, "connections": n, "notice": None}
    path = find_aria2c(c.aria2c_path)
    if path:
        return {"aria2c": path, "connections": n, "notice": None}
    return {"aria2c": None, "connections": n, "notice": None}   # silent fallback: parallel fragments


def build_options(config: Any) -> Dict[str, Any]:
    """Return an ordered dict {"--flag": value}; True = bare flag, list = repeated."""
    c = _as_config(config)
    _validate(c)
    o: Dict[str, Any] = {}
    if getattr(sys,'frozen',False):
        o['--ffmpeg-location']=getattr(sys,'_MEIPASS',os.path.dirname(sys.executable))
    _jr = js_runtime_args()
    if _jr: o[_jr[0]] = _jr[1]
    o['--ignore-config']=True
    o['--encoding']='utf-8'  # output is decoded as UTF-8, including Arabic filenames
    o["--newline"] = True
    o["--no-colors"] = True
    o["--no-quiet"] = True                # --print implies --quiet otherwise; we need progress/skip/error lines
    o["--ignore-errors"] = True           # one bad playlist item must not stop the rest
    o["--continue" if c.resume else "--no-continue"] = True   # partial .part files are always kept, never deleted
    o["--retries"] = str(c.retries)
    o["--no-simulate"] = True
    o["--progress-template"] = "download:" + PROG_MARK + "%(progress)j"
    o["--print"] = [
        "before_dl:" + ITEM_MARK + "%(.{id,title,playlist_index,playlist_count})j",
        "after_move:" + FILE_MARK + "%(filepath)s",
    ]
    o["-P"] = c.output_dir
    o["-o"] = c.output_template
    o["-f"] = format_selector(c)
    o["-S"] = "res,vcodec:av01,acodec:opus" if not c.prefer_mp4_codecs else "res,vcodec:h264,acodec:aac"
    if c.mode == "audio":
        o["-x"] = True
        o["--audio-format"] = c.audio_format
        o["--audio-quality"] = (str(c.audio_bitrate).rstrip("kK") + "K") if c.audio_bitrate else "0"
    elif c.merge_format != 'native':
        o["--merge-output-format"] = c.merge_format
        o["--remux-video"] = c.merge_format
    if c.subtitles or c.embed_subs:
        o["--write-subs"] = True
        if c.auto_subs:
            o["--write-auto-subs"] = True
        o["--sub-langs"] = ",".join(c.sub_langs) or "en"
        if c.sub_format != "best":
            o["--sub-format"] = c.sub_format + "/best"
            o["--convert-subs"] = c.sub_format if c.sub_format in ("srt", "vtt", "ass") else None
            if o["--convert-subs"] is None:
                del o["--convert-subs"]
        if c.embed_subs and c.mode == "video":
            o["--embed-subs"] = True
    if c.embed_thumbnail:
        o["--embed-thumbnail"] = True
        # mp3/m4a/mp4 accept cover art; webm/opus embedding needs yt-dlp's mutagen path
    if c.write_thumbnail:
        o["--write-thumbnail"] = True
    if c.embed_metadata:
        o["--embed-metadata"] = True
    if c.rate_limit:
        o["--limit-rate"] = c.rate_limit
    if c.no_playlist:
        o["--no-playlist"] = True
    if c.playlist_items:
        o["--playlist-items"] = c.playlist_items
    if c.archive_file:
        o["--download-archive"] = c.archive_file
    if c.skip_existing:
        o["--no-overwrites"] = True
    if c.cookies_file:
        o["--cookies"] = c.cookies_file
    if c.referer:
        o["--referer"] = c.referer
    if c.user_agent:
        o["--user-agent"] = c.user_agent
    if c.proxy:
        o["--proxy"] = c.proxy
    if c.cookies_from_browser and not (c.cookies_from_browser.split(":")[0].lower() == "safari" and sys.platform != "darwin"):
        # Safari cookies exist only on macOS; passing it elsewhere made yt-dlp print "unsupported platform: win32"
        o["--cookies-from-browser"] = c.cookies_from_browser
    plan = plan_downloader(c)
    if plan["connections"] > 1:
        o["--concurrent-fragments"] = str(plan["connections"])
    if plan["aria2c"]:
        n = plan["connections"]
        o["--downloader"] = plan["aria2c"]
        o["--downloader-args"] = "aria2c:-x %d -s %d -k 1M --file-allocation=none --auto-save-interval=5 --summary-interval=1 --show-console-readout=true --enable-color=false --human-readable=false --console-log-level=warn" % (n, n)
    return o


def options_to_args(opts: Dict[str, Any]) -> List[str]:
    args: List[str] = []
    for k, v in opts.items():
        if v is True:
            args.append(k)
        elif v is False or v is None:
            continue
        elif isinstance(v, (list, tuple)):
            for x in v:
                args += [k, str(x)]
        else:
            args += [k, str(v)]
    return args


def build_command(config: Any, url: str) -> List[str]:
    c = _as_config(config)
    return YTDLP_CMD + options_to_args(build_options(c)) + list(c.extra_args) + ["--", url]


# ---------------------------------------------------------------- inspect

def _run_json_lines(args: List[str], timeout: int = 120) -> List[dict]:
    args = js_runtime_args() + ['--encoding', 'utf-8'] + args
    p = subprocess.run(YTDLP_CMD + args, capture_output=True, text=True, timeout=timeout,
                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    rows = []
    for line in p.stdout.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    if not rows:
        err = [l for l in p.stderr.splitlines() if l.startswith("ERROR")]
        raise EngineError(err[-1] if err else "yt-dlp returned no data (exit %s)" % p.returncode)
    return rows


def _heights(info: dict) -> List[int]:
    hs = {f["height"] for f in info.get("formats") or [] if f.get("height") and f.get("vcodec") != "none"}
    return sorted(hs, reverse=True)


def inspection_target(url):
    """Normalize copied YouTube playlist links without losing account/mix identity."""
    url=unescape(url.strip().strip('<>"\''))
    parts=urlsplit(url);host=(parts.hostname or '').lower();query=parse_qs(parts.query)
    youtube=host in ('youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','youtu.be','www.youtu.be')
    playlist=query.get('list',[''])[0] if youtube else ''
    if not playlist:return url,''
    if not re.fullmatch(r'[A-Za-z0-9_-]+',playlist):raise EngineError('The YouTube playlist ID is invalid. Copy the full playlist link again.')
    if playlist.startswith('RD'):
        video=query.get('v',[''])[0] or (parts.path.strip('/') if host.endswith('youtu.be') else '')
        if video:return 'https://www.youtube.com/watch?'+urlencode({'v':video,'list':playlist}),playlist
        return url,playlist
    return 'https://www.youtube.com/playlist?'+urlencode({'list':playlist}),playlist


def inspect_url(url: str, probe_first_for_heights: bool = True, timeout: int = 120,
                extra_args: Optional[List[str]] = None) -> Dict[str, Any]:
    """Inspect a video or playlist without downloading.

    Returns {"title", "is_playlist", "items":[{index,title,url,duration,id}], "heights":[...]}.
    Playlist entries are probed individually for their own available formats.
    """
    extra = list(extra_args or [])
    url,playlist_id=inspection_target(url)
    if playlist_id in ('WL','LL') and not any(flag in extra for flag in ('--cookies','--cookies-from-browser')):
        raise EngineError('Watch Later / Liked Videos needs your YouTube login. Choose the logged-in browser in Settings > Login and network, Apply, then Add again.')
    rows = _run_json_lines(["--ignore-config", "--flat-playlist", "--dump-json", "--no-warnings"] + (["--yes-playlist"] if playlist_id else []) + extra + ["--", url], timeout)
    single = len(rows) == 1 and "formats" in rows[0] and rows[0].get("_type", "video") == "video" \
        and not rows[0].get("playlist_index") and not playlist_id
    if single:
        r = rows[0]
        return {"title": r.get("title"), "is_playlist": False, "heights": _heights(r),
                "items": [_item(1, r, url)]}
    items = [_item(i, r, url) for i, r in enumerate(rows, 1)]
    title = rows[0].get("playlist_title") or rows[0].get("playlist") or url
    heights: List[int] = []
    if probe_first_for_heights and items:
        from concurrent.futures import ThreadPoolExecutor
        def probe(item):
            if item.get('formats') or not item.get('url'):
                return [int(v) for v in available_video_qualities(item.get('formats',[])) if v.isdigit()]
            try:
                rows = _run_json_lines(["--ignore-config", "--dump-json", "--no-playlist", "--no-warnings"] + extra + ["--", item["url"]], timeout)
                if rows:
                    item['formats']=normalized_formats(rows[0])
                    return _heights(rows[0])
            except (EngineError, subprocess.TimeoutExpired):
                pass
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(probe,items))
        heights=results[0] or []
    return {"title": title, "is_playlist": True, "heights": heights, "items": items}


def available_video_qualities(formats):
    """Actual downloadable video heights, with an automatic fallback if unknown."""
    heights={int(f['height']) for f in formats if isinstance(f.get('height'),(int,float))
             and f['height']>0 and f.get('vcodec') not in (None,'none')}
    return [str(h) for h in sorted(heights,reverse=True)] or ['best']


def selected_video_quality(formats, requested):
    values=available_video_qualities(formats)
    requested=str(requested)
    if requested in values:return requested
    candidates=[v for v in values if v.isdigit() and requested.isdigit() and int(v)<=int(requested)]
    if candidates:return candidates[0]
    return values[-1] if requested=='worst' or requested.isdigit() else values[0]


def normalized_formats(info: dict) -> List[dict]:
    """Public format choices, pairing video-only streams with the best audio."""
    formats = [f for f in info.get("formats", []) or [] if f.get("format_id") and not f.get("has_drm")
               and (f.get("vcodec") not in (None, "none") or f.get("acodec") not in (None, "none"))]
    audios = [f for f in formats if f.get("vcodec") == "none" and f.get("acodec") not in (None, "none")]
    audio = max(audios, key=lambda f: f.get("abr") or f.get("tbr") or 0, default=None)
    duration = info.get("duration") or 0
    def size(f):
        if f.get("filesize"):
            return int(f["filesize"]), False
        if f.get("filesize_approx"):
            return int(f["filesize_approx"]), True
        if duration and f.get("tbr"):
            return int(duration * f["tbr"] * 1000 / 8), True
        return None, True
    result = []
    for f in formats:
        fid = str(f["format_id"])
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", fid):
            continue
        pair = audio if f.get("vcodec") not in (None, "none") and f.get("acodec") == "none" else None
        if f.get("acodec") == "none" and pair is None:
            continue
        n, approximate = size(f)
        if pair:
            a, a_estimate = size(pair)
            n = n + a if n is not None and a is not None else None
            approximate = approximate or a_estimate
        selector = fid + ("+" + str(pair["format_id"]) if pair else "")
        ext = f.get("ext") or "unknown"
        height = f.get("height")
        label = (str(height) + "p" if height else "Audio") + " · " + ext + " · " + selector
        result.append({"format_id": fid, "selector": selector, "ext": ext, "height": height,
                       "fps": f.get("fps"), "vcodec": f.get("vcodec"),
                       "acodec": pair.get("acodec") if pair else f.get("acodec"),
                       "estimated_size": n, "size_is_estimate": approximate, "label": label})
    return sorted(result, key=lambda f: (f["height"] or 0, f["fps"] or 0, f["estimated_size"] or 0), reverse=True)


def _item(index: int, r: dict, fallback_url: str) -> Dict[str, Any]:
    item_url=r.get('webpage_url') or r.get('url') or fallback_url
    host=(urlsplit(fallback_url).hostname or '').lower()
    if host in ('youtube.com','www.youtube.com','m.youtube.com','music.youtube.com','youtu.be','www.youtu.be') and r.get('id') and re.fullmatch(r'[A-Za-z0-9_-]{11}',str(r['id'])):
        item_url='https://www.youtube.com/watch?'+urlencode({'v':r['id']})
    return {"index": r.get("playlist_index") or index, "id": r.get("id"), "title": r.get("title"),
            "url": item_url, "duration": r.get("duration"),
            "formats": normalized_formats(r)}


# ---------------------------------------------------------------- parsing

_ERR_RE = re.compile(r"^ERROR:\s*(?:\[[^\]]+\]\s*)?(?:(?P<id>[\w\-]{3,})\s*:\s*)?(?P<msg>.*)$")


_RESUME_RE = re.compile(r"^\[download\] Resuming download at byte (\d+)")
PARTIAL_SUFFIXES = (".part", ".ytdl", ".aria2")


def partial_files(output_dir: str) -> List[Dict[str, Any]]:
    """List resumable partial files (.part, .ytdl, .aria2, fragment parts) in output_dir with sizes."""
    out = []
    try:
        names = os.listdir(output_dir)
    except OSError:
        return out
    for n in sorted(names):
        if n.endswith(PARTIAL_SUFFIXES) or ".part-Frag" in n:
            try:
                out.append({"name": n, "size": os.path.getsize(os.path.join(output_dir, n))})
            except OSError:
                pass
    return out


def parse_progress(line: str) -> Optional[Event]:
    """Parse a progress-template line into a progress event (or None)."""
    if not line.startswith(PROG_MARK):
        return None
    try:
        d = json.loads(line[len(PROG_MARK):])
    except ValueError:
        return None
    status = d.get("status")
    total = d.get("total_bytes") or d.get("total_bytes_estimate")
    done = d.get("downloaded_bytes") or 0
    if status == "finished":
        pct = 100.0
    elif total:
        pct = round(done * 100.0 / total, 1)
    elif d.get("fragment_count") and d.get("fragment_index"):
        pct = round(d["fragment_index"] * 100.0 / d["fragment_count"], 1)
    else:
        pct = 0.0
    return {"type": "progress", "percent": min(pct, 100.0), "speed": d.get("speed"), "eta": d.get("eta"),
            "filename": d.get("filename"), "downloaded": done, "total": total, "state": status}


def parse_line(line: str) -> Optional[Event]:
    """Classify one output line into an event dict (before item attribution)."""
    line = line.rstrip("\r\n")
    ev = parse_progress(line)
    if ev:
        return ev
    # External aria2 does not emit yt-dlp's intermediate progress hooks.
    # Read its actual transfer counters instead of the sparse file's length.
    aria = re.search(r'\[#[0-9a-f]+\s+(\d+)B/(\d+)B\((\d+)%\).*?DL:(\d+)B(?:\s+ETA:([^\]]+))?', line, re.I)
    if aria:
        done, total, percent, speed = map(int, aria.group(1, 2, 3, 4))
        return {'type': 'progress', 'percent': percent, 'downloaded': done, 'total': total,
                'speed': speed, 'eta': (aria.group(5) or '').strip() or None, 'state': 'downloading'}
    if line.startswith(ITEM_MARK):
        try:
            d = json.loads(line[len(ITEM_MARK):])
        except ValueError:
            return None
        return {"type": "status", "status": "item_start",
                "item": {"index": d.get("playlist_index") or 1, "id": d.get("id"), "title": d.get("title"),
                         "count": d.get("playlist_count")}}
    if line.startswith(FILE_MARK):
        return {"type": "item_done", "path": line[len(FILE_MARK):]}
    if line.startswith('[download] Destination: '):
        return {'type':'status','status':'destination','filename':line[len('[download] Destination: '):]}
    m = _RESUME_RE.search(line)
    if m:
        return {"type": "status", "status": "resuming", "offset": int(m.group(1)), "message": line}
    if "has already been recorded in the archive" in line:
        return {"type": "status", "status": "skipped", "message": line, "reason": "archive"}
    if "has already been downloaded" in line:
        return {"type": "status", "status": "skipped", "message": line, "reason": "exists"}
    if line.startswith("ERROR:"):
        m = _ERR_RE.match(line)
        return {"type": "error", "message": (m.group("msg") if m else line[6:]).strip(),
                "video_id": m.group("id") if m else None, "raw": line}
    if line.startswith("[Merger]") or line.startswith("[ExtractAudio]") or line.startswith("[EmbedThumbnail]") \
            or line.startswith("[Metadata]") or line.startswith("[EmbedSubtitle]") or line.startswith("[FixupM3u8]"):
        return {"type": "status", "status": "processing", "message": line}
    return None


# ---------------------------------------------------------------- runner

class Downloader:
    """One download job. Thread-safe cancel()/pause()/resume() from any thread."""

    def __init__(self, config: Any, callback: Optional[Callback] = None,
                 popen: Callable[..., Any] = subprocess.Popen):
        self.config = _as_config(config)
        self.callback = callback or (lambda e: None)
        self._popen = popen
        self._proc: Any = None
        self._lock = threading.Lock()
        self._cancelled = False
        self._paused = False
        self.current_item: Optional[dict] = None
        self.paths: List[str] = []
        self.errors: List[Event] = []
        self.skipped: List[Event] = []

    def _emit(self, ev: Event) -> None:
        try:
            self.callback(ev)
        except Exception as exc:
            print("Event callback failed: "+str(exc),file=sys.stderr)

    def run(self, url: str) -> Dict[str, Any]:
        cmd = build_command(self.config, url)
        self._emit({"type": "status", "status": "starting", "command": cmd})
        os.makedirs(self.config.output_dir, exist_ok=True)
        plan = plan_downloader(self.config)
        if plan["notice"]:
            self._emit({"type": "status", "status": "notice", "message": plan["notice"]})
        if self.config.resume:
            parts = [p for p in partial_files(self.config.output_dir) if p["name"].endswith(".part") or p["name"].endswith(".aria2")]
            if parts:
                self._emit({"type": "status", "status": "partials_found", "count": len(parts),
                            "bytes": sum(p["size"] for p in parts),
                            "message": "Found %d partial file(s) from an earlier run; resuming where possible." % len(parts)})
        with self._lock:
            if self._cancelled:
                return self._finish(-15)
            try:
                self._proc = self._popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                         encoding="utf-8", errors="replace", bufsize=1,
                                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            except OSError as e:
                err = {"type": "error", "message": "cannot start yt-dlp: %s" % e, "item": None}
                self.errors.append(err)
                self._emit(err)
                return self._finish(-1)
        for line in self._proc.stdout:
            self._handle(line)
        rc = self._proc.wait()
        return self._finish(rc)

    def _handle(self, line: str) -> None:
        ev = parse_line(line)
        if ev is None:
            return
        t = ev["type"]
        if t == "status" and ev["status"] == "item_start":
            self.current_item = ev["item"]
        if t in ("progress", "error", "item_done") or (t == "status" and ev["status"] == "skipped"):
            ev["item"] = self._item_for(ev)
        if t == "item_done":
            self.paths.append(ev["path"])
        elif t == "error":
            self.errors.append(ev)
        elif t == "status" and ev["status"] == "skipped":
            self.skipped.append(ev)
        self._emit(ev)

    def _item_for(self, ev: Event) -> Optional[dict]:
        vid = ev.get("video_id")
        if vid and (not self.current_item or self.current_item.get("id") != vid):
            return {"index": None, "id": vid, "title": None}   # error for an item that never started (e.g. unavailable)
        return self.current_item

    def _finish(self, rc: int) -> Dict[str, Any]:
        if self._cancelled:
            self._emit({"type": "status", "status": "cancelled"})
        else:
            self._emit({"type": "status", "status": "finished"})
        result = {"type": "done", "path": self.paths[-1] if self.paths else None, "paths": list(self.paths),
                  "errors": [{"item": e.get("item"), "message": e["message"]} for e in self.errors],
                  "skipped": len(self.skipped), "returncode": rc, "cancelled": self._cancelled}
        self._emit(result)
        return result

    # --- control (child process only; partial files are kept for resume) ---
    def cancel(self, grace: float = 5.0) -> None:
        with self._lock:
            self._cancelled = True
            p = self._proc
        if p is None or p.poll() is not None:
            return
        if self._paused:
            self.resume()
        p.terminate()
        try:
            p.wait(timeout=grace)
        except subprocess.TimeoutExpired:
            p.kill()

    def pause(self) -> bool:
        """SIGSTOP the child (POSIX only). Returns False where unsupported."""
        if self._proc is None or self._proc.poll() is not None or not hasattr(signal, "SIGSTOP"):
            return False
        self._proc.send_signal(signal.SIGSTOP)
        self._paused = True
        self._emit({"type": "status", "status": "paused"})
        return True

    def resume(self) -> bool:
        if self._proc is None or not self._paused or not hasattr(signal, "SIGCONT"):
            return False
        self._proc.send_signal(signal.SIGCONT)
        self._paused = False
        self._emit({"type": "status", "status": "resumed"})
        return True


def ndjson_emitter(stream=None) -> Callback:
    stream = stream or sys.stdout
    lock = threading.Lock()

    def emit(ev: Event) -> None:
        if ev.get("type") == "status":
            ev = {k: v for k, v in ev.items() if k != "command"}
        with lock:
            stream.write(json.dumps(ev, ensure_ascii=True) + "\n")
            stream.flush()
    return emit


def run_download(config: Any, url: str, emit: Optional[Callback] = None) -> Dict[str, Any]:
    """Blocking download; events go to emit (default: NDJSON on stdout).

    Stream summary: progress, status, done{path}, plus error events. If nothing
    was downloaded and errors exist, a final {"type":"error"} summarises it.
    """
    emit = emit or ndjson_emitter()
    d = Downloader(config, emit)
    res = d.run(url)
    return res


# ---------------------------------------------------------------- CLI

def main(argv: Optional[List[str]] = None) -> int:
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    ap = argparse.ArgumentParser(description="yt-dlp download engine")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--inspect", metavar="URL")
    g.add_argument("--download", nargs=2, metavar=("CONFIG_JSON", "URL"))
    g.add_argument("--convert", nargs=2, metavar=("CONFIG_JSON", "SOURCE"))
    ap.add_argument("--referer"); ap.add_argument("--user-agent"); ap.add_argument("--cookies")
    ap.add_argument("--proxy")
    ap.add_argument('--cookies-from-browser')
    a = ap.parse_args(argv)
    emit = ndjson_emitter()
    try:
        if a.inspect:
            validate_url(a.inspect)
            extra = []
            if a.cookies_from_browser:
                build_options({'cookies_from_browser':a.cookies_from_browser})
                extra+=['--cookies-from-browser',a.cookies_from_browser]
            for flag, val in (("--referer", a.referer), ("--user-agent", a.user_agent), ("--cookies", a.cookies), ("--proxy", a.proxy)):
                if val:
                    if re.search(r"[\x00-\x1f\x7f]", val):
                        raise EngineError("invalid characters in " + flag)
                    extra += [flag, val]
            print(json.dumps(inspect_url(a.inspect, extra_args=extra), ensure_ascii=True))
            return 0
        if a.convert:
            from media_conversion import Converter
            cfg_path, source = a.convert
            with open(cfg_path, encoding="utf-8") as f:
                converter = Converter(json.load(f), emit)
            signal.signal(signal.SIGTERM, lambda *_: converter.cancel())
            signal.signal(signal.SIGINT, lambda *_: converter.cancel())
            result = converter.run(source)
            return 130 if result["cancelled"] else (0 if result["paths"] else 1)
        cfg_path, url = a.download
        validate_url(url)
        with open(cfg_path, encoding="utf-8") as f:
            cfg = DownloadConfig.from_dict(json.load(f))
        d = Downloader(cfg, emit)
        signal.signal(signal.SIGTERM, lambda *_: d.cancel())
        signal.signal(signal.SIGINT, lambda *_: d.cancel())
        res = d.run(url)
        if not res["paths"] and not res["skipped"]:
            emit({"type": "error", "message": res["errors"][-1]["message"] if res["errors"]
                  else "no files downloaded (exit %s)" % res["returncode"]})
            return 1
        return 0 if not res["cancelled"] else 130
    except (EngineError, OSError, ValueError, subprocess.TimeoutExpired) as e:
        emit({"type": "error", "message": str(e)})
        return 2


if __name__ == "__main__":
    sys.exit(main())
