import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace

spec = importlib.util.spec_from_file_location('release_manifest', Path(__file__).resolve().parents[1] / 'tools/release_manifest.py')
manifest = importlib.util.module_from_spec(spec)
spec.loader.exec_module(manifest)


def test_manifest_records_exact_artifact_and_source_changes(tmp_path, monkeypatch):
    artifact = tmp_path / 'Custom.exe'
    artifact.write_bytes(b'new artifact')
    source = tmp_path / 'app.py'
    source.write_text('original')
    (tmp_path / 'tools/media').mkdir(parents=True)
    tool = tmp_path / 'tools/media/ffmpeg.exe'
    tool.write_bytes(b'tool')
    for env in ('VD_FFMPEG', 'VD_FFPROBE', 'VD_JSBIN', 'VD_ARIA'):
        monkeypatch.delenv(env, raising=False)
    monkeypatch.setattr(manifest.subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout='ffmpeg version test', stderr='', returncode=0))
    monkeypatch.setattr(manifest.platform,'platform',lambda:'test-platform')
    first = manifest.create_manifest(artifact, tmp_path)
    assert first['artifact']['path'] == str(artifact.resolve())
    assert first['artifact']['sha256'] == hashlib.sha256(b'new artifact').hexdigest()
    assert first['tools']['ffmpeg']['sha256'] == hashlib.sha256(b'tool').hexdigest()
    assert first['tools']['ffmpeg']['version_output'] == 'ffmpeg version test'
    assert first['tools']['aria2c']['missing']
    assert first['installed_dependencies']
    source.write_text('changed')
    assert manifest.create_manifest(artifact, tmp_path)['source_sha256']['app.py'] != first['source_sha256']['app.py']


def test_named_build_verifies_and_reports_same_artifact():
    build = (Path(__file__).resolve().parents[1] / 'build.bat').read_text()
    assert 'set "VD_ARTIFACT=dist\\%VD_APP_NAME%.exe"' in build
    assert 'tools\\verify_build.py "%VD_ARTIFACT%"' in build
    assert 'tools\\release_manifest.py "%VD_ARTIFACT%"' in build
    assert 'echo Built %VD_ARTIFACT%' in build
