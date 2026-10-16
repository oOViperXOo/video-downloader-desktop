"""Multi-site URL validation (SSRF / safety) tests."""
import pytest
import engine

GOOD = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "https://youtu.be/dQw4w9WgXcQ", "https://music.youtube.com/watch?v=x",
    "https://vimeo.com/76979871", "https://player.vimeo.com/video/76979871",
    "https://www.facebook.com/watch/?v=1", "https://fb.watch/abc/",
    "https://www.instagram.com/reel/Cabc123/", "https://www.tiktok.com/@u/video/1", "https://vm.tiktok.com/ZM1/",
    "https://twitter.com/u/status/1", "https://x.com/u/status/1",
    "https://www.dailymotion.com/video/x8abc", "https://www.twitch.tv/videos/123", "https://clips.twitch.tv/Abc",
    "https://www.reddit.com/r/videos/comments/abc/t/", "https://soundcloud.com/a/b",
    "https://example.com/some/page.mp4", "http://example.org/v", "https://8.8.8.8/x.mp4",
]
BAD = [
    "", "   ", "not a url", "youtube.com/watch?v=x", "ftp://example.com/a.mp4", "file:///etc/passwd", "javascript:alert(1)",
    "data:text/html,hi", "https://user:pass@vimeo.com/1", "https://example.com:notaport/",
    "http://localhost/", "http://LOCALHOST:8080/x", "http://foo.localhost/", "http://127.0.0.1/", "http://127.1/",
    "http://2130706433/", "http://0x7f000001/", "http://017700000001/", "http://0.0.0.0/", "http://10.1.2.3/",
    "http://172.16.0.1/", "http://192.168.1.1/", "http://169.254.169.254/latest/meta-data/", "http://100.64.0.1/",
    "http://[::1]/", "http://[::ffff:127.0.0.1]/", "http://[fe80::1]/", "http://[fc00::1]/", "http://224.0.0.1/",
    "http://printer.local/", "http://nas.lan/", "http://router.home/", "http://intranet/", "https://vimeo.com/a b",
    "https://vimeo.com/1\nhttps://evil", None, 123,
]


@pytest.mark.parametrize("url", GOOD)
def test_accepts_public_sites(url):
    assert engine.validate_url(url) == url


@pytest.mark.parametrize("url", BAD)
def test_blocks_unsafe(url):
    with pytest.raises(ValueError):
        engine.validate_url(url)


def test_resolve_blocks_private_dns(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, p, *a, **k: [(2, 1, 6, "", ("10.0.0.7", 0))])
    with pytest.raises(ValueError):
        engine.validate_url("https://evil.example.com/v", resolve=True)
    engine.validate_url("https://evil.example.com/v")  # not resolved by default
    monkeypatch.setattr(socket, "getaddrinfo", lambda h, p, *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))])
    engine.validate_url("https://example.com/v", resolve=True)


def test_site_names():
    assert engine.site_name("https://m.youtube.com/watch?v=1") == "YouTube"
    assert engine.site_name("https://vm.tiktok.com/x") == "TikTok"
    assert engine.site_name("https://x.com/a") == "X / Twitter"
    assert engine.site_name("https://notyoutube.com/a") is None
    assert engine.site_name("https://youtube.com.evil.com/a") is None


def test_no_shell_in_engine():
    import inspect
    src = inspect.getsource(engine)
    assert "shell=True" not in src and "os.system" not in src


def test_cli_rejects_private(capsys):
    assert engine.main(["--inspect", "http://127.0.0.1/x"]) == 2
    assert engine.main(["--inspect", "file:///etc/passwd"]) == 2
