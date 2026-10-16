import engine


def test_source_runtime_is_used_for_download_and_inspection(monkeypatch, tmp_path):
    runtime = tmp_path / 'tools' / ('qjs.exe' if engine.os.name == 'nt' else 'qjs')
    runtime.parent.mkdir()
    runtime.write_bytes(b'')
    monkeypatch.setattr(engine, '__file__', str(tmp_path / 'engine.py'))
    monkeypatch.setattr(engine.sys, 'executable', str(tmp_path / 'python' / 'python.exe'))
    monkeypatch.setattr(engine.sys, 'frozen', False, raising=False)
    assert engine.js_runtime_args() == ['--js-runtimes', 'quickjs:' + str(runtime)]
    assert engine.build_options({})['--js-runtimes'] == 'quickjs:' + str(runtime)
    assert engine.build_options({})['--encoding'] == 'utf-8'
    calls = []

    class Result:
        stdout = '{"id":"test"}\n'
        stderr = ''
        returncode = 0

    monkeypatch.setattr(engine.subprocess, 'run', lambda args, **kw: calls.append(args) or Result())
    engine._run_json_lines(['--dump-json', 'https://example.com'])
    assert 'quickjs:' + str(runtime) in calls[0]
    assert calls[0][calls[0].index('--encoding') + 1] == 'utf-8'


def test_safari_cookie_profile_is_not_passed_on_windows(monkeypatch):
    monkeypatch.setattr(engine.sys, 'platform', 'win32')
    assert '--cookies-from-browser' not in engine.build_options({'cookies_from_browser': 'Safari:profile'})
