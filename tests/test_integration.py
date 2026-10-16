from app import DEFAULTS, engine_config
import engine
import pytest

def test_gui_settings_map(tmp_path):
    cfg=dict(DEFAULTS,outdir=str(tmp_path),quality='720',embed_subtitles=True,thumbnail=True,rate_limit='2M')
    mapped=engine_config(cfg); opts=engine.build_options(mapped)
    assert mapped['max_height']==720 and mapped['no_playlist']
    assert opts['--embed-subs'] and opts['--embed-thumbnail']
    assert opts['--limit-rate']=='2M'
    assert '--remux-video' not in opts
    assert '--ignore-config' in opts

@pytest.mark.parametrize('value',['../x.%(ext)s','/tmp/x.%(ext)s','C:\\x.%(ext)s','test.mp4'])
def test_filename_template_validation(value):
    with pytest.raises(ValueError): engine_config(dict(DEFAULTS,template=value))

@pytest.mark.parametrize('url',['file:///tmp/a','https://name:pass@youtube.com/','http://localhost:8000/','http://169.254.169.254/'])
def test_url_validation(url):
    with pytest.raises(ValueError): engine.validate_url(url)

def test_archive_differs_by_quality(tmp_path):
    a=engine_config(dict(DEFAULTS,outdir=str(tmp_path),quality='720'))
    b=engine_config(dict(DEFAULTS,outdir=str(tmp_path),quality='1080'))
    assert a['archive_file']!=b['archive_file']

@pytest.mark.parametrize('value',['C:test.%(ext)s','http:test.%(ext)s'])
def test_drive_prefix_rejected(value):
    with pytest.raises(ValueError): engine_config(dict(DEFAULTS,template=value))

def test_4k_format_not_h264_capped():
    opts=engine.build_options(dict(max_height=2160))
    assert 'avc1' not in opts['-f']
    assert opts['-S'].startswith('res,')
