"""Real-process tests: resume of partial downloads, multi-connection downloads, aria2c fallback.

They run the real yt-dlp against a local HTTP server that supports Range requests (tests/rangeserver.py).
Engine validate_url() is deliberately not involved: it blocks 127.0.0.1, and these tests drive Downloader directly.
aria2c tests are skipped when aria2c is not installed.
"""
import hashlib
import os
import re
import signal
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

import engine
from rangeserver import start_server

ROOT = Path(__file__).resolve().parents[1]
SIZE = 6_000_000
needs_ytdlp = pytest.mark.skipif(subprocess.run([sys.executable, "-m", "yt_dlp", "--version"], capture_output=True).returncode != 0,
                                 reason="yt-dlp not installed")
needs_posix_groups = pytest.mark.skipif(os.name != "posix", reason="requires POSIX killpg/signals; Windows pause acceptance is separate")
needs_aria2 = pytest.mark.skipif(engine.find_aria2c() is None, reason="aria2c not installed")

RUNNER = textwrap.dedent("""
    import sys, json
    sys.path.insert(0, %r)
    import engine
    cfg = json.loads(sys.argv[1])
    engine.Downloader(cfg, lambda e: print(json.dumps(e), flush=True)).run(sys.argv[2])
""") % str(ROOT)


def cfg(out, **kw):
    base = dict(output_dir=str(out), skip_existing=False, retries=2)
    base.update(kw)
    return base


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def part_size(out):
    parts = [p for p in Path(out).glob("*.part")]
    return parts[0].stat().st_size if parts else 0


@needs_ytdlp
@needs_posix_groups
def test_real_resume_after_hard_kill(tmp_path):
    """Kill the whole engine process (simulated crash) mid-download, restart, and check it continues from the .part."""
    data = os.urandom(SIZE)
    srv, log, url = start_server(data, delay=0.02)
    try:
        import json
        cmd = [sys.executable, "-c", RUNNER, json.dumps(cfg(tmp_path, connections=1)), url]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        deadline = time.time() + 40
        while time.time() < deadline and part_size(tmp_path) < SIZE * 0.25:
            time.sleep(0.05)
        killed_at = part_size(tmp_path)
        assert killed_at >= SIZE * 0.25, "download never got going"
        os.killpg(p.pid, signal.SIGKILL)      # hard crash: no cleanup chance
        p.wait()
        time.sleep(0.3)
        kept = part_size(tmp_path)
        assert 0 < kept < SIZE, "partial file must be kept after a crash"
        assert not list(tmp_path.glob("*.mp4"))
        log.clear()
        srv.RequestHandlerClass.delay = 0
        events = []
        res = engine.Downloader(cfg(tmp_path, connections=1), events.append).run(url)
        assert res["returncode"] == 0 and not res["errors"]
        out = res["path"]
        assert sha(out) == hashlib.sha256(data).hexdigest()
        ranged = [l for l in log if l[0] == "GET" and l[1]]
        assert ranged, "resume must use an HTTP Range request"
        start = int(re.match(r"bytes=(\d+)-", ranged[-1][1]).group(1))
        assert start >= kept * 0.9 and start > 0
        assert sum(l[2] for l in log if l[0] == "GET" and l[1]) <= SIZE - start + 1
        st = [e for e in events if e["type"] == "status"]
        assert any(e["status"] == "partials_found" for e in st)
        assert any(e["status"] == "resuming" and e["offset"] > 0 for e in st)
        assert not list(tmp_path.glob("*.part"))
    finally:
        srv.shutdown()


@needs_ytdlp
@needs_posix_groups
def test_resume_after_graceful_stop_keeps_partial(tmp_path):
    """SIGTERM (what Pause / Cancel / closing the app send) keeps the .part file; second run completes it."""
    import json
    data = os.urandom(SIZE)
    srv, log, url = start_server(data, delay=0.02)
    try:
        cmd = [sys.executable, "-c", RUNNER, json.dumps(cfg(tmp_path, connections=1)), url]
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        deadline = time.time() + 40
        while time.time() < deadline and part_size(tmp_path) < SIZE * 0.2:
            time.sleep(0.05)
        os.killpg(p.pid, signal.SIGTERM)
        p.wait(timeout=20)
        assert 0 < part_size(tmp_path) < SIZE
        srv.RequestHandlerClass.delay = 0
        res = engine.Downloader(cfg(tmp_path, connections=1)).run(url)
        assert res["returncode"] == 0 and sha(res["path"]) == hashlib.sha256(data).hexdigest()
    finally:
        srv.shutdown()


@needs_ytdlp
def test_server_without_range_restarts_cleanly(tmp_path):
    """If the server cannot resume, the download restarts and still produces a correct file (no corruption)."""
    data = os.urandom(1_000_000)
    srv, log, url = start_server(data, support_ranges=False)
    try:
        (tmp_path / "clip [clip].mp4.part").write_bytes(data[:300_000])
        res = engine.Downloader(cfg(tmp_path, connections=1)).run(url)
        assert res["returncode"] == 0 and sha(res["path"]) == hashlib.sha256(data).hexdigest()
    finally:
        srv.shutdown()


@needs_ytdlp
@needs_aria2
def test_multi_connection_aria2c_uses_parallel_ranges(tmp_path):
    data = os.urandom(SIZE)
    srv, log, url = start_server(data, delay=0.005)
    try:
        c = cfg(tmp_path, connections=6, external_downloader="aria2c")
        assert "--downloader" in engine.build_command(c, url)
        res = engine.Downloader(c).run(url)
        assert res["returncode"] == 0 and not res["errors"]
        assert sha(res["path"]) == hashlib.sha256(data).hexdigest()
        ranged = {l[1] for l in log if l[0] == "GET" and l[1]}
        assert len(ranged) >= 3, "aria2c should split the file into several ranged requests, saw %r" % ranged
    finally:
        srv.shutdown()


def _covered(entries):
    """Unique bytes delivered by ranged GETs (aria2c re-splits pieces, so raw byte sums double count)."""
    spans = []
    for method, rng, sent in entries:
        if method == "GET" and rng and sent:
            m = re.match(r"bytes=(\d+)-", rng)
            spans.append((int(m.group(1)), int(m.group(1)) + sent))
    spans.sort()
    total, end = 0, -1
    for s, e in spans:
        s = max(s, end)
        if e > s:
            total += e - s
            end = e
    return total


def _aria2_interrupted_run(tmp_path, sig, wait):
    import json
    data = os.urandom(SIZE * 2)
    srv, log, url = start_server(data, delay=0.3)
    c = cfg(tmp_path, connections=4, external_downloader="aria2c")
    p = subprocess.Popen([sys.executable, "-c", RUNNER, json.dumps(c), url], stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    time.sleep(wait)
    os.killpg(p.pid, sig)
    p.wait(timeout=30)
    time.sleep(1.5)                      # let the server notice the dropped connections
    assert list(tmp_path.glob("*.part")), "partial must remain"
    first = _covered(log)
    assert first > 0
    srv.RequestHandlerClass.delay = 0
    log.clear()
    res = engine.Downloader(c).run(url)
    assert res["returncode"] == 0 and sha(res["path"]) == hashlib.sha256(data).hexdigest()
    second = _covered(log)
    srv.shutdown()
    return first, second, len(data)


@needs_ytdlp
@needs_aria2
@needs_posix_groups
def test_aria2c_resume_after_graceful_stop(tmp_path):
    """Pause/Cancel/close send SIGTERM to the process tree: aria2c saves its state and the restart only fetches the rest."""
    first, second, total = _aria2_interrupted_run(tmp_path, signal.SIGTERM, 8)
    assert second <= total - 0.7 * first, "second run fetched %d bytes after %d were already done (total %d)" % (second, first, total)


@needs_ytdlp
@needs_aria2
@needs_posix_groups
def test_aria2c_resume_after_hard_kill(tmp_path):
    """After a crash, aria2c resumes from its last auto-save (every 5 s, set by the engine)."""
    first, second, total = _aria2_interrupted_run(tmp_path, signal.SIGKILL, 12)
    assert second <= total - 0.5 * first, "second run fetched %d bytes after %d were already done (total %d)" % (second, first, total)


@needs_ytdlp
def test_concurrent_fragments_flag_and_fallback_without_aria2c(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "find_aria2c", lambda hint=None: None)
    events = []
    data = os.urandom(500_000)
    srv, log, url = start_server(data)
    try:
        c = cfg(tmp_path, connections=8, external_downloader="auto")
        cmd = engine.build_command(c, url)
        assert "--concurrent-fragments" in cmd and cmd[cmd.index("--concurrent-fragments") + 1] == "8"
        assert "--downloader" not in cmd
        res = engine.Downloader(c, events.append).run(url)
        assert res["returncode"] == 0 and sha(res["path"]) == hashlib.sha256(data).hexdigest()
        notices = [e for e in events if e["type"] == "status" and e["status"] == "notice"]
        assert not notices  # optional fallback is silent
    finally:
        srv.shutdown()


def test_options_unit(tmp_path, monkeypatch):
    c = engine.build_options(dict(connections=1))
    assert "--concurrent-fragments" not in c and "--downloader" not in c and c["--continue"] is True
    assert "--no-continue" in engine.build_options(dict(resume=False))
    fake = tmp_path / ("fake_aria2c.exe" if os.name == "nt" else "fake_aria2c")
    fake.write_text("#!/bin/sh\n")
    fake.chmod(0o755)
    # Option rendering is independent of OS executable permission semantics.
    monkeypatch.setattr(engine, "find_aria2c", lambda hint=None: hint)
    try:
        o = engine.build_options(dict(connections=16, aria2c_path=str(fake), external_downloader="auto"))
        assert o["--downloader"] == str(fake) and "-x 16" in o["--downloader-args"] and o["--concurrent-fragments"] == "16"
        o = engine.build_options(dict(connections=8, aria2c_path=str(fake), external_downloader="off"))
        assert "--downloader" not in o and o["--concurrent-fragments"] == "8"
    finally:
        fake.unlink()
    for bad in (0, 17, -1, True, "4"):
        with pytest.raises(engine.EngineError):
            engine.build_options(dict(connections=bad))
    with pytest.raises(engine.EngineError):
        engine.build_options(dict(external_downloader="curl"))
    with pytest.raises(engine.EngineError):
        engine.build_options(dict(cookies_from_browser="chrome; rm -rf /"))
    assert engine.build_options(dict(cookies_from_browser="firefox"))["--cookies-from-browser"] == "firefox"
    with pytest.raises(engine.EngineError):
        engine.build_options(dict(proxy="file:///etc/passwd"))
    assert engine.build_options(dict(proxy="socks5://10.0.0.5:1080"))["--proxy"] == "socks5://10.0.0.5:1080"


def test_parse_resume_line_and_partials(tmp_path):
    ev = engine.parse_line("[download] Resuming download at byte 123456")
    assert ev["status"] == "resuming" and ev["offset"] == 123456
    (tmp_path / "a.mp4.part").write_bytes(b"x" * 10)
    (tmp_path / "a.mp4.ytdl").write_bytes(b"{}")
    (tmp_path / "b.mp4").write_bytes(b"x")
    assert {p["name"] for p in engine.partial_files(str(tmp_path))} == {"a.mp4.part", "a.mp4.ytdl"}


def test_referer_user_agent_options_and_inspect_flags():
    o = engine.build_options(dict(referer="https://site.example/page", user_agent="UA/1"))
    assert o["--referer"] == "https://site.example/page" and o["--user-agent"] == "UA/1"
    with pytest.raises(engine.EngineError):
        engine.build_options(dict(user_agent="bad\nheader"))
    assert engine.main(["--inspect", "https://example.com/x", "--referer", "a\nb"]) == 2


def test_audio_only_sites_get_audio_fallback():
    f = engine.format_selector(engine.DownloadConfig(max_height=720))
    assert f.endswith("/ba") and "height<=720" in f

