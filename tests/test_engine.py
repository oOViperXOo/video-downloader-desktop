"""pytest tests for engine.py. Mocked-subprocess tests always run; the
real-run test is skipped unless yt-dlp and ffmpeg are installed."""
import io
import json
import os
import shutil
import subprocess
import sys
import threading
import http.server
import functools

import pytest

import engine
from engine import DownloadConfig, Downloader, PROG_MARK, ITEM_MARK, FILE_MARK


def prog(**kw):
    d = {"status": "downloading", "downloaded_bytes": 50, "total_bytes": 200, "speed": 1000.0, "eta": 3,
         "filename": "/o/a.mp4"}
    d.update(kw)
    return PROG_MARK + json.dumps(d)


class FakeProc:
    def __init__(self, lines, rc=0, block=None):
        self.stdout = self._gen(lines, block)
        self.rc = rc
        self.terminated = False
        self.killed = False
        self._done = False

    def _gen(self, lines, block):
        for l in lines:
            yield l + "\n"
            if block and not self.terminated:
                block.wait(2)
        self._done = True

    def wait(self, timeout=None):
        return -15 if self.terminated else self.rc

    def poll(self):
        return None if not self._done and not self.terminated else self.rc

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True


def fake_popen(lines, rc=0, block=None, store=None):
    def _p(cmd, **kw):
        p = FakeProc(lines, rc, block)
        if store is not None:
            store.append((cmd, kw, p))
        return p
    return _p


# ---------------- options ----------------

def args_for(**kw):
    return engine.options_to_args(engine.build_options(DownloadConfig(**kw)))


def test_quality_ladder_and_mp4_merge():
    a = args_for(max_height=720, merge_format='mp4')
    f = a[a.index("-f") + 1]
    assert "height<=720" in f and all("height<=720" in option for option in f.split("/") if option != "ba")  # "ba" = audio-only fallback
    assert a[a.index("--merge-output-format") + 1] == "mp4"


def test_best_has_no_height_filter():
    a = args_for()
    assert "height" not in a[a.index("-f") + 1]


def test_audio_options():
    a = args_for(mode="audio", audio_format="opus", audio_bitrate="160")
    assert "-x" in a and a[a.index("--audio-format") + 1] == "opus"
    assert a[a.index("--audio-quality") + 1] == "160K"
    assert "--merge-output-format" not in a
    a = args_for(mode="audio", audio_bitrate=None)
    assert a[a.index("--audio-quality") + 1] == "0"


def test_subs_thumb_meta_rate_template_archive():
    a = args_for(subtitles=True, sub_langs=["en", "ar"], auto_subs=True, embed_subs=True, embed_thumbnail=True,
                 embed_metadata=True, rate_limit="2M", output_template="%(uploader)s/%(title)s.%(ext)s",
                 output_dir="/x", archive_file="/x/a.txt", playlist_items="1-3", no_playlist=False)
    assert a[a.index("--sub-langs") + 1] == "en,ar"
    for flag in ("--write-subs", "--write-auto-subs", "--embed-subs", "--embed-thumbnail", "--embed-metadata",
                 "--no-overwrites"):
        assert flag in a
    assert a[a.index("--limit-rate") + 1] == "2M"
    assert a[a.index("-o") + 1] == "%(uploader)s/%(title)s.%(ext)s"
    assert a[a.index("-P") + 1] == "/x"
    assert a[a.index("--download-archive") + 1] == "/x/a.txt"
    assert a[a.index("--playlist-items") + 1] == "1-3"


def test_skip_existing_off():
    assert "--no-overwrites" not in args_for(skip_existing=False)


@pytest.mark.parametrize("kw", [dict(mode="x"), dict(audio_format="flac"), dict(rate_limit="fast"),
                                dict(audio_bitrate="abc"), dict(merge_format="avi"), dict(max_height=0)])
def test_validation(kw):
    with pytest.raises(engine.EngineError):
        engine.build_options(DownloadConfig(**kw))


def test_config_from_dict_rejects_unknown():
    with pytest.raises(engine.EngineError):
        DownloadConfig.from_dict({"nope": 1})


def test_url_after_double_dash():
    cmd = engine.build_command(DownloadConfig(), "-evil")
    assert cmd[-2:] == ["--", "-evil"]


# ---------------- parsing ----------------

def test_parse_progress():
    ev = engine.parse_progress(prog())
    assert ev["percent"] == 25.0 and ev["speed"] == 1000.0 and ev["eta"] == 3 and ev["filename"] == "/o/a.mp4"


def test_parse_progress_unknown_total_and_finished_and_fragments():
    assert engine.parse_progress(prog(total_bytes=None))["percent"] == 0.0
    assert engine.parse_progress(prog(total_bytes=None, fragment_index=3, fragment_count=4))["percent"] == 75.0
    assert engine.parse_progress(prog(status="finished"))["percent"] == 100.0
    assert engine.parse_progress(PROG_MARK + "{bad") is None


def test_parse_error_line():
    ev = engine.parse_line("ERROR: [youtube] abc123XYZ_-: Video unavailable")
    assert ev["type"] == "error" and ev["video_id"] == "abc123XYZ_-" and ev["message"] == "Video unavailable"


def test_parse_skip_lines():
    assert engine.parse_line("[download] x: has already been recorded in the archive")["reason"] == "archive"
    assert engine.parse_line("[download] /a.mp4 has already been downloaded")["reason"] == "exists"


# ---------------- runner (mocked subprocess) ----------------

def test_run_playlist_with_item_error_and_events():
    lines = [
        ITEM_MARK + json.dumps({"id": "v1", "title": "One", "playlist_index": 1, "playlist_count": 3}),
        prog(), prog(downloaded_bytes=200),
        "[Merger] Merging formats into \"/o/a.mp4\"",
        FILE_MARK + "/o/a.mp4",
        "ERROR: [youtube] vid2xxxxxxx: Video unavailable. This video is private",
        ITEM_MARK + json.dumps({"id": "v3", "title": "Three", "playlist_index": 3, "playlist_count": 3}),
        FILE_MARK + "/o/c.mp4",
    ]
    ev = []
    store = []
    d = Downloader(DownloadConfig(output_dir="/tmp/_eng_t"), ev.append, popen=fake_popen(lines, 0, store=store))
    res = d.run("http://u")
    types = [e["type"] for e in ev]
    assert types[0] == "status" and types[-1] == "done"
    assert res["paths"] == ["/o/a.mp4", "/o/c.mp4"] and res["path"] == "/o/c.mp4"
    assert len(res["errors"]) == 1 and res["errors"][0]["item"]["id"] == "vid2xxxxxxx"
    assert "private" in res["errors"][0]["message"]
    progs = [e for e in ev if e["type"] == "progress"]
    assert [p["percent"] for p in progs] == [25.0, 100.0] and progs[0]["item"]["id"] == "v1"
    assert any(e.get("status") == "processing" for e in ev)
    assert store[0][0][-2:] == ["--", "http://u"]


def test_error_for_current_item_gets_item_attached():
    ev = []
    lines = [ITEM_MARK + json.dumps({"id": "abcdefg", "title": "T", "playlist_index": 2}),
             "ERROR: [youtube] abcdefg: Unable to download"]
    Downloader(DownloadConfig(output_dir="/tmp/_eng_t"), ev.append, popen=fake_popen(lines, 1)).run("u")
    err = [e for e in ev if e["type"] == "error"][0]
    assert err["item"]["index"] == 2 and err["item"]["title"] == "T"


def test_skipped_counts():
    ev = []
    r = Downloader(DownloadConfig(output_dir="/tmp/_eng_t"), ev.append,
                   popen=fake_popen(["[download] x: x has already been recorded in the archive"], 0)).run("u")
    assert r["skipped"] == 1 and not r["paths"]


def test_cancel_terminates_and_reports():
    block = threading.Event()
    ev = []
    store = []
    lines = [prog(), prog(), prog()]
    d = Downloader(DownloadConfig(output_dir="/tmp/_eng_t"), ev.append, popen=fake_popen(lines, 0, block, store))

    def on_event(e):
        ev.append(e)
        if e["type"] == "progress":
            d.cancel(grace=0.1)
    d.callback = on_event
    res = d.run("u")
    assert store[0][2].terminated and res["cancelled"] is True
    assert any(e.get("status") == "cancelled" for e in ev)


def test_cancel_before_start():
    d = Downloader(DownloadConfig(output_dir="/tmp/_eng_t"), popen=fake_popen([], 0))
    d.cancel()
    assert d.run("u")["cancelled"] is True


def test_spawn_failure_is_reported():
    def boom(*a, **k):
        raise FileNotFoundError("yt-dlp")
    ev = []
    r = Downloader(DownloadConfig(output_dir="/tmp/_eng_t"), ev.append, popen=boom).run("u")
    assert r["errors"] and "cannot start" in r["errors"][0]["message"]


def test_callback_exception_does_not_break_run():
    def bad(e):
        raise RuntimeError("gui bug")
    r = Downloader(DownloadConfig(output_dir="/tmp/_eng_t"), bad,
                   popen=fake_popen([FILE_MARK + "/o/a.mp4"], 0)).run("u")
    assert r["paths"] == ["/o/a.mp4"]


def test_ndjson_emitter_roundtrip():
    buf = io.StringIO()
    em = engine.ndjson_emitter(buf)
    em({"type": "progress", "percent": 1.0})
    em({"type": "status", "status": "starting", "command": ["x"]})
    rows = [json.loads(l) for l in buf.getvalue().splitlines()]
    assert rows[0]["type"] == "progress" and "command" not in rows[1]


def test_inspect_single_and_playlist(monkeypatch):
    single = [{"id": "a", "title": "A", "duration": 5, "webpage_url": "http://a",
               "formats": [{"height": 360, "vcodec": "avc1"}, {"height": 720, "vcodec": "avc1"},
                           {"height": None, "vcodec": "none"}]}]
    monkeypatch.setattr(engine, "_run_json_lines", lambda args, timeout=120: single)
    r = engine.inspect_url("http://a")
    assert r["heights"] == [720, 360] and not r["is_playlist"] and r["items"][0]["duration"] == 5

    flat = [{"id": "a", "title": "A", "url": "http://a", "duration": 1, "playlist_title": "PL", "playlist_index": 1},
            {"id": "b", "title": "B", "url": "http://b", "duration": 2, "playlist_title": "PL", "playlist_index": 2}]

    def fake(args, timeout=120):
        return flat if "--flat-playlist" in args else single
    monkeypatch.setattr(engine, "_run_json_lines", fake)
    r = engine.inspect_url("http://pl")
    assert r["is_playlist"] and r["title"] == "PL" and [i["index"] for i in r["items"]] == [1, 2]
    assert r["heights"] == [720, 360]


def test_main_cli_inspect_and_missing_config(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(engine, "inspect_url", lambda u, **k: {"title": "t", "items": [], "heights": []})
    assert engine.main(["--inspect", "https://youtu.be/example"]) == 0
    assert json.loads(capsys.readouterr().out)["title"] == "t"
    assert engine.main(["--download", str(tmp_path / "none.json"), "https://youtu.be/example"]) == 2
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["type"] == "error"


# ---------------- real run (local HTTP server + generated clip) ----------------

needs_real = pytest.mark.skipif(not (shutil.which("ffmpeg") and (shutil.which("yt-dlp") or
                                    subprocess.run([sys.executable, "-m", "yt_dlp", "--version"],
                                                   capture_output=True).returncode == 0)),
                                reason="yt-dlp/ffmpeg not available")


@pytest.fixture
def local_clip(tmp_path):
    src = tmp_path / "srv"
    src.mkdir()
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=d=2:s=160x120:r=10",
                    "-f", "lavfi", "-i", "sine=d=2", "-c:v", "libx264", "-c:a", "aac", "-pix_fmt", "yuv420p",
                    str(src / "clip.mp4")], check=True)
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(src))
    h.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield "http://127.0.0.1:%d/clip.mp4" % srv.server_address[1]
    srv.shutdown()


@needs_real
def test_real_video_download_archive_and_audio(local_clip, tmp_path):
    out = tmp_path / "dl"
    arch = tmp_path / "arch.txt"
    cfg = DownloadConfig(output_dir=str(out), output_template="%(title)s.%(ext)s", archive_file=str(arch),
                         embed_metadata=True)
    ev = []
    r = Downloader(cfg, ev.append).run(local_clip)
    assert r["returncode"] == 0 and r["path"] and os.path.getsize(r["path"]) > 0
    assert any(e["type"] == "progress" for e in ev)
    # second run is skipped via archive
    ev2 = []
    r2 = Downloader(cfg, ev2.append).run(local_clip)
    assert r2["skipped"] == 1 and not r2["paths"]
    # audio-only mp3
    acfg = DownloadConfig(output_dir=str(out), mode="audio", audio_format="mp3", audio_bitrate="128")
    r3 = Downloader(acfg).run(local_clip)
    assert r3["path"].endswith(".mp3") and os.path.exists(r3["path"])


@needs_real
def test_real_error_captured(local_clip, tmp_path):
    r = Downloader(DownloadConfig(output_dir=str(tmp_path))).run(local_clip.replace("clip.mp4", "missing.mp4"))
    assert r["errors"] and "404" in r["errors"][0]["message"] and not r["paths"]


@needs_real
def test_real_inspect(local_clip):
    r = engine.inspect_url(local_clip)
    assert r["items"][0]["title"] == "clip"
