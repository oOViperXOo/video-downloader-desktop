# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all
import os
from pathlib import Path

datas = [('assets/app-icon.ico', 'assets'), ('tools/media/FFmpeg-LICENSE.txt', 'licenses'), ('tools/media/FFmpeg-README.txt', 'licenses')]
binaries = [(os.environ.get('VD_JSBIN','tools/qjs.exe'), '.'), (os.environ.get('VD_FFMPEG','tools/media/ffmpeg.exe'), '.'), (os.environ.get('VD_FFPROBE','tools/media/ffprobe.exe'), '.')]
aria_binary=os.environ.get('VD_ARIA','tools/aria2c.exe')
if Path(aria_binary).is_file(): binaries.append((aria_binary,'.'))
hiddenimports = ['engine']
tmp_ret = collect_all('yt_dlp')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('yt_dlp_ejs')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['tools/qt_windows_runtime.py'],
    excludes=['tkinter', 'unittest', 'pydoc', 'test', 'curl_cffi', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets', 'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.QtQuickWidgets', 'PySide6.Qt3DCore', 'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets', 'PySide6.QtPdf', 'PySide6.QtCharts', 'PySide6.QtDataVisualization', 'PySide6.QtSql', 'PySide6.QtTest'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

# Qt uses the Windows ICU API. A same-name DLL from external tools on the
# builder's PATH has versioned exports and makes QtCore fail before startup.
a.binaries = [entry for entry in a.binaries if entry[0].lower() not in ('icuuc.dll', 'icudt78.dll')]
# The interface uses Qt Widgets, not QML/Quick, PDF rendering, or software OpenGL.
def unused_qt(name):
    name=name.lower().replace('\\','/')
    return (name.startswith(('pyside6/qt6qml','pyside6/qt6quick','pyside6/pyside6qml'))
            or name in ('pyside6/qt6pdf.dll','pyside6/opengl32sw.dll','pyside6/plugins/imageformats/qpdf.dll')
            or name.startswith(('pyside6/plugins/designer/','pyside6/plugins/qmltooling/')))
a.binaries=[entry for entry in a.binaries if not unused_qt(entry[0])]

# Python bundles an older CRT than Qt. Windows loads the root copy first;
# use Qt's newer compatible runtime consistently instead of mixing versions.
from pathlib import Path
import PySide6
qt_root = Path(PySide6.__file__).parent
for index, (target, source, kind) in enumerate(a.binaries):
    if target.lower() in ('vcruntime140.dll', 'vcruntime140_1.dll'):
        a.binaries[index] = (target, str(qt_root / target.lower()), kind)

package_mode=os.environ.get('VD_PACKAGE_MODE','portable')
if package_mode not in ('portable','installed','both'):raise ValueError('VD_PACKAGE_MODE must be portable, installed or both')
app_name=os.environ.get('VD_APP_NAME','OrvantaVideoDownloader')
exe_options=dict(
    icon='assets/app-icon.ico',
    version='assets/version-info.txt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
if package_mode in ('portable','both'):
    portable_name=app_name+'-Portable' if package_mode=='both' else app_name
    portable=EXE(pyz,a.scripts,a.binaries,a.datas,[],name=portable_name,**exe_options)
if package_mode in ('installed','both'):
    installed=EXE(pyz,a.scripts,[],exclude_binaries=True,name=app_name,**exe_options)
    bundle=COLLECT(installed,a.binaries,a.datas,strip=False,upx=True,name=app_name)
