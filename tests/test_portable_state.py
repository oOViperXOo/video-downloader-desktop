import sys

import app


def test_portable_state_stays_beside_frozen_executable(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'Downloader.exe'))
    (tmp_path / 'portable.ini').write_text('[Application]\nMode=portable\n')
    store = app.Store()
    assert store.root == tmp_path / 'Data'
    store.data['history'] = [{'title': 'Portable history', 'status': 'done', 'path': 'video.mp4'}]
    store.save()
    assert store.path.is_file()
    assert app.Store().data['history'] == store.data['history']


def test_installed_or_source_state_uses_appdata(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'Downloader.exe'))
    expected = app.Path(app.QStandardPaths.writableLocation(app.QStandardPaths.AppDataLocation))
    assert app.default_state_directory() == expected
    (tmp_path / 'portable.ini').touch()
    monkeypatch.setattr(sys, 'frozen', False)
    assert app.default_state_directory() == expected


def test_explicit_state_root_overrides_portable_marker(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(sys, 'executable', str(tmp_path / 'Downloader.exe'))
    (tmp_path / 'portable.ini').touch()
    assert app.Store(tmp_path / 'isolated').root == tmp_path / 'isolated'
