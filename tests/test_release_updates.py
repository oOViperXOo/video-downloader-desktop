import io
import json
from unittest.mock import Mock
import pytest
import release_updates as updates
from tools.create_update_manifest import create_manifest

def manifest(version='1.1.0'):
    return dict(schema_version=1, version=version, download_url='https://example.com/app.exe', notes='<b>Untrusted notes</b>')

@pytest.mark.parametrize('new,old,expected', [('1.10.0','1.9.0',True), ('2.0.0','10.0.0',False), ('1.0.0','1.0.0-rc.1',True), ('1.0.0-beta.10','1.0.0-beta.2',True), ('1.0.0-alpha','1.0.0-beta',False), ('1.0.0','1.0.0',False)])
def test_versions(new, old, expected):
    assert updates.validate_manifest(manifest(new), old)['available'] is expected

@pytest.mark.parametrize('url', ['', 'http://example.com/a', 'https://user:pass@example.com/a', 'https://example.com/a#x', 'https://example.com:99999/a', 'https://example.com\\evil/a', 'https://example.com/ a', 'https:///a', 'https://bad!host/a', 'https://example.com/%ZZ'])
def test_bad_urls(url):
    with pytest.raises(updates.UpdateCheckError):
        updates.validate_https_url(url)

@pytest.mark.parametrize('change', [dict(schema_version=True), dict(schema_version=2), dict(version='1.01.0'), dict(version='1.0.0-01'), dict(notes=['bad']), dict(notes='x'*16001)])
def test_invalid_manifest(change):
    with pytest.raises(updates.UpdateCheckError):
        updates.validate_manifest(manifest() | change)

def test_mock_network_preserves_plain_text(monkeypatch):
    response = io.BytesIO(json.dumps(manifest()).encode())
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr(updates, 'build_opener', lambda *_: opener)
    result = updates.check_for_update('https://example.com/update.json')
    assert result['notes'] == '<b>Untrusted notes</b>'
    assert opener.open.call_args.kwargs['timeout'] == 8

@pytest.mark.parametrize('payload', [b'{bad json', b'x'*65537, b'[]'], ids=['json', 'oversized', 'array'])
def test_bad_network_response(monkeypatch, payload):
    opener = Mock()
    opener.open.return_value = io.BytesIO(payload)
    monkeypatch.setattr(updates, 'build_opener', lambda *_: opener)
    with pytest.raises(updates.UpdateCheckError):
        updates.check_for_update('https://example.com/update.json')

def test_network_error(monkeypatch):
    opener = Mock()
    opener.open.side_effect = TimeoutError('timed out')
    monkeypatch.setattr(updates, 'build_opener', lambda *_: opener)
    with pytest.raises(updates.UpdateCheckError, match='timed out'):
        updates.check_for_update('https://example.com/update.json')

@pytest.mark.parametrize('timeout', [0, 31, float('nan'), True])
def test_timeout_bounds(timeout):
    with pytest.raises(updates.UpdateCheckError):
        updates.check_for_update('https://example.com/update.json', timeout=timeout)

def test_redirect_rejected():
    with pytest.raises(updates.UpdateCheckError):
        updates._NoRedirect().redirect_request(None, None, 302, '', {}, 'http://example.com/')

def test_final_artifact_hash(tmp_path):
    artifact = tmp_path / 'app.exe'
    artifact.write_bytes(b'final signed bytes')
    data = create_manifest(artifact, 'https://example.com/app.exe')
    import hashlib
    assert data['sha256'] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert data['size_bytes'] == artifact.stat().st_size

def test_slow_chunk_deadline_closes_response(monkeypatch):
    clock = [0.0]
    class SlowResponse(io.BytesIO):
        calls = 0
        def read1(self, count):
            self.calls += 1
            clock[0] += 3
            return b' '
    response = SlowResponse()
    opener = Mock()
    opener.open.return_value = response
    monkeypatch.setattr(updates, 'build_opener', lambda *_: opener)
    monkeypatch.setattr(updates, 'monotonic', lambda: clock[0])
    with pytest.raises(updates.UpdateCheckError, match='total deadline'):
        updates.check_for_update('https://example.com/update.json', timeout=8)
    assert response.calls == 3
    assert response.closed

def test_connection_consumes_deadline_before_read(monkeypatch):
    clock = [0.0]
    response = io.BytesIO(b'{}')
    def open_response(*args, **kwargs):
        clock[0] = 9
        return response
    opener = Mock()
    opener.open.side_effect = open_response
    monkeypatch.setattr(updates, 'build_opener', lambda *_: opener)
    monkeypatch.setattr(updates, 'monotonic', lambda: clock[0])
    with pytest.raises(updates.UpdateCheckError, match='total deadline'):
        updates.check_for_update('https://example.com/update.json', timeout=8)
    assert response.closed

def test_in_memory_adapter_without_read1(monkeypatch):
    class Adapter:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, count): return json.dumps(manifest()).encode()
    opener = Mock()
    opener.open.return_value = Adapter()
    monkeypatch.setattr(updates, 'build_opener', lambda *_: opener)
    assert updates.check_for_update('https://example.com/update.json')['available']

def test_outer_deadline_bounds_headers_and_limits_outstanding(monkeypatch):
    from threading import Event, BoundedSemaphore
    started, release, finished = Event(), Event(), Event()
    def stalled_fetch(*args, **kwargs):
        started.set()
        try:
            release.wait(5)
            return updates.validate_manifest(manifest())
        finally:
            finished.set()
    monkeypatch.setattr(updates, '_FETCH_SLOT', BoundedSemaphore(1))
    monkeypatch.setattr(updates, '_fetch_update', stalled_fetch)
    real_queue = updates.Queue
    class FastDeadlineQueue(real_queue):
        def get(self, timeout=None):
            assert timeout == 2
            assert started.wait(1)
            return super().get(timeout=0.01)
    monkeypatch.setattr(updates, 'Queue', FastDeadlineQueue)
    try:
        with pytest.raises(updates.UpdateCheckError, match='total deadline'):
            updates.check_for_update('https://example.com/update.json', timeout=1)
        with pytest.raises(updates.UpdateCheckError, match='still finishing'):
            updates.check_for_update('https://example.com/update.json', timeout=1)
    finally:
        release.set()
        assert finished.wait(1)
