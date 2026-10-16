# Linux/macOS folder bundles; Windows retains VideoDownloaderDesktop.spec.
import os
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

root=Path(SPECPATH)
sys.path.insert(0,str(root))
from release_updates import APP_VERSION

assert sys.platform in ('linux','darwin')
tools={name:os.environ['VD_'+name.upper()] for name in ('ffmpeg','ffprobe','aria','jsbin')}
datas=[('assets/app-icon.ico','assets'),('assets/app-icon.png','assets'),('build/posix/licenses','licenses')]
binaries=[(path,'.') for path in tools.values()]
imports=['engine']
for module in ('yt_dlp','yt_dlp_ejs'):
    data,binary,hidden=collect_all(module);datas+=data;binaries+=binary;imports+=hidden
excludes=['tkinter','unittest','pydoc','test','curl_cffi',
    'PySide6.QtWebEngineCore','PySide6.QtWebEngineWidgets','PySide6.QtQml','PySide6.QtQuick',
    'PySide6.QtQuickWidgets','PySide6.Qt3DCore','PySide6.QtMultimedia','PySide6.QtMultimediaWidgets',
    'PySide6.QtPdf','PySide6.QtCharts','PySide6.QtDataVisualization','PySide6.QtSql','PySide6.QtTest']
a=Analysis(['app.py'],pathex=[str(root)],binaries=binaries,datas=datas,hiddenimports=imports,
    hookspath=[],hooksconfig={},runtime_hooks=[],excludes=excludes,noarchive=False,optimize=0)
pyz=PYZ(a.pure)
exe=EXE(pyz,a.scripts,[],exclude_binaries=True,name='OrvantaVideoDownloader',
    debug=False,strip=False,upx=False,console=False,
    target_arch='arm64' if sys.platform=='darwin' else None,codesign_identity=None)
bundle=COLLECT(exe,a.binaries,a.datas,strip=False,upx=False,name='OrvantaVideoDownloader')
if sys.platform=='darwin':
    app=BUNDLE(bundle,name='Orvanta Video Downloader.app',icon='build/posix/app-icon.icns',
        bundle_identifier='com.orvanta.video-downloader',version=APP_VERSION,
        info_plist={'CFBundleDisplayName':'Orvanta Video Downloader','CFBundleShortVersionString':APP_VERSION,
                    'LSMinimumSystemVersion':'15.0','NSHighResolutionCapable':True})
