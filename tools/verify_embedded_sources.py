"""Check that the packaged modules match the current workspace source code."""
from pathlib import Path
import marshal
import sys
from types import CodeType
from PyInstaller.archive.readers import CArchiveReader


def signature(code):
    return (code.co_code,code.co_names,code.co_varnames,code.co_argcount,code.co_kwonlyargcount,
            tuple(signature(value) if isinstance(value,CodeType) else value for value in code.co_consts))


root=Path(__file__).resolve().parents[1]
archive=CArchiveReader(sys.argv[1]);pyz=archive.open_embedded_archive('PYZ.pyz')
for name in ('app','compact_ui','features_ui','row_actions','playlist_ui','media_conversion','preferences_ui','browser_login','playlist_paths','single_instance'):
    actual=marshal.loads(archive.extract(name)) if name=='app' else pyz.extract(name)
    expected=compile((root/(name+'.py')).read_text(encoding='utf-8'),name+'.py','exec',dont_inherit=True,optimize=0)
    assert signature(actual)==signature(expected),f'Packaged {name} differs from current source'
    print(name+': matches source')
