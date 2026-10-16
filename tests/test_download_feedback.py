import engine
import pytest


def test_original_streams_are_default_without_conversion():
    options = engine.build_options({})
    assert '--remux-video' not in options
    assert '--recode-video' not in options
    assert '--merge-output-format' not in options
    assert '--downloader' not in options
    assert 'vcodec:av01' in options['-S']
    assert 'vcodec:h264' not in options['-S']


def test_mp4_is_an_explicit_remux_not_encoding():
    options = engine.build_options({'merge_format': 'mp4'})
    assert options['--remux-video'] == 'mp4'
    assert '--recode-video' not in options


def test_aria2_transfer_progress_uses_download_counters():
    event = engine.parse_line('[#abcdef 1500000B/6000000B(25%) CN:4 DL:500000B ETA:9s]')
    assert event['type'] == 'progress'
    assert event['percent'] == 25
    assert event['downloaded'] == 1500000
    assert event['total'] == 6000000
    assert event['speed'] == 500000
    assert event['eta'] == '9s'


@pytest.mark.parametrize('downloader', ['off', 'aria2c'])
def test_real_intermediate_progress(tmp_path, downloader):
    from pathlib import Path
    import os
    from rangeserver import start_server
    aria = Path(__file__).resolve().parents[1] / 'tools' / 'aria2c.exe'
    if downloader == 'aria2c' and not aria.exists():
        pytest.skip('Bundled aria2 unavailable')
    data = os.urandom(2_000_000)
    server, log, url = start_server(data)
    events = []
    try:
        result = engine.Downloader(dict(output_dir=str(tmp_path), external_downloader=downloader,
                                        aria2c_path=str(aria), rate_limit='500K'), events.append).run(url)
        assert result['returncode'] == 0
        assert Path(result['path']).read_bytes() == data
        assert any(e['type'] == 'progress' and 0 < e['percent'] < 100 for e in events)
    finally:
        server.shutdown()
