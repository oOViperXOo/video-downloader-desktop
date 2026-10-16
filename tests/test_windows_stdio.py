import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(os.name != 'nt', reason='Windows GUI worker pipe restoration')
def test_windowed_worker_restores_utf8_pipes():
    result = subprocess.run(
        [sys.executable, '-c',
         "import sys;sys.stdout=None;sys.stderr=None;"
         "from windows_stdio import restore_worker_streams;restore_worker_streams();"
         "print('ready \\u0639\\u0631\\u0628\\u064a');print('diagnostic',file=sys.stderr)"],
        cwd=Path(__file__).resolve().parents[1], capture_output=True,
        text=True, encoding='utf-8', creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0
    assert result.stdout.strip() == 'ready عربي'
    assert result.stderr.strip().endswith('diagnostic')
    assert 'Traceback' not in result.stderr
