import subprocess
from pathlib import Path
import pytest
import engine
from media_conversion import Converter, find_ffmpeg, estimate_conversion_size

def test_exact_formats_and_sizes():
    info = {'duration': 10, 'formats': [
        {'format_id':'v1','height':720,'vcodec':'vp9','acodec':'none','ext':'webm','filesize':100},
        {'format_id':'a1','vcodec':'none','acodec':'opus','ext':'webm','filesize':20},
        {'format_id':'drm','vcodec':'avc1','has_drm':True}]}
    choice = engine.normalized_formats(info)[0]
    assert choice['selector'] == 'v1+a1'
    assert choice['estimated_size'] == 120
    assert choice['size_is_estimate'] is False
    assert engine.build_options({'format_id':'v1+a1'})['-f'] == 'v1+a1'
    with pytest.raises(engine.EngineError):
        engine.build_options({'format_id':'best/evil'})

def test_conversion_failure_cleanup(tmp_path):
    original = tmp_path / 'bad.webm'
    original.write_bytes(b'not media')
    events = []
    result = Converter(callback=events.append).run(original)
    assert result['errors'] and not result['paths']
    assert list(tmp_path.iterdir()) == [original]
    assert events[-1]['type'] == 'done'

def test_cancel_before_start(tmp_path):
    original = tmp_path / 'bad.webm'
    original.write_bytes(b'not media')
    converter = Converter()
    converter.cancel()
    assert converter.run(original)['cancelled']
    assert list(tmp_path.iterdir()) == [original]

def test_local_conversion_preserves_original_and_existing(tmp_path):
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        pytest.skip('local ffmpeg unavailable')
    original = tmp_path / 'tiny.mkv'
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'color=c=blue:s=64x64:d=0.2', '-c:v', 'ffv1', str(original)], check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name == 'nt' else 0)
    before = original.read_bytes()
    existing = tmp_path / 'tiny (converted).mp4'
    existing.write_bytes(b'keep')
    result = Converter({'quality':'small'}).run(original)
    assert result['returncode'] == 0, result
    assert Path(result['path']).name == 'tiny (converted) 2.mp4'
    assert original.read_bytes() == before and existing.read_bytes() == b'keep'
    assert Path(result['path']).stat().st_size > 0
    assert estimate_conversion_size(10) > 0

def test_audio_only_conversion_fails_without_artifacts(tmp_path):
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        pytest.skip('local ffmpeg unavailable')
    original = tmp_path / 'audio.wav'
    subprocess.run([ffmpeg, '-hide_banner', '-loglevel', 'error', '-f', 'lavfi', '-i',
                    'sine=frequency=440:duration=0.1', str(original)], check=True,
                   creationflags=subprocess.CREATE_NO_WINDOW if __import__('os').name == 'nt' else 0)
    result = Converter().run(original)
    assert result['errors'] and not result['paths']
    assert list(tmp_path.iterdir()) == [original]

def test_conversion_output_error_and_bad_quality(tmp_path):
    original = tmp_path / 'original.mp4'
    original.write_bytes(b'original')
    blocker = tmp_path / 'not_directory'
    blocker.write_bytes(b'keep')
    assert Converter({'output_dir':str(blocker)}).run(original)['errors']
    assert original.read_bytes() == b'original'
    with pytest.raises(ValueError):
        Converter({'quality':'invalid'})
