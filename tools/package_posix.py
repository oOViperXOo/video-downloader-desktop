"""Package native builds without changing already-signed macOS app contents."""
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from release_updates import APP_VERSION

def main():
    if sys.platform not in ('linux','darwin'):raise SystemExit('Run on Linux or macOS.')
    system='linux-x64' if sys.platform=='linux' else 'macos-arm64'
    assert platform.machine().lower()==('x86_64' if sys.platform=='linux' else 'arm64')
    output=ROOT/'dist/release-output';output.mkdir(exist_ok=True)
    prefix=f'OrvantaVideoDownloader-{APP_VERSION}-{system}'
    if sys.platform=='linux':
        bundle=ROOT/'dist/OrvantaVideoDownloader'
        (bundle/'orvanta-video-downloader.desktop').write_text(
            '[Desktop Entry]\nType=Application\nName=Orvanta Video Downloader\n'
            'Exec=OrvantaVideoDownloader\nIcon=orvanta-video-downloader\nTerminal=false\nCategories=AudioVideo;Network;\n',encoding='utf-8')
        shutil.copy2(ROOT/'assets/app-icon.png',bundle/'orvanta-video-downloader.png')
        (bundle/'README.txt').write_text(
            'Extract this entire folder and run ./OrvantaVideoDownloader. Keep _internal beside the executable.\n'
            'Requires a Linux x64 graphical desktop, glibc 2.35+ and Qt X11/OpenGL system libraries; built/tested on Ubuntu 22.04.\n'
            'The desktop entry is a template: add the extracted folder to PATH and install the icon before using it.\n',encoding='utf-8')
        artifact=output/(prefix+'.tar.gz')
        with tarfile.open(artifact,'w:gz') as archive:archive.add(bundle,arcname=bundle.name)
    else:
        bundle=ROOT/'dist/Orvanta Video Downloader.app'
        subprocess.run(['codesign','--verify','--deep','--strict',str(bundle)],check=True)
        artifact=output/(prefix+'.dmg')
        with tempfile.TemporaryDirectory(prefix='orvanta-dmg-') as directory:
            directory=Path(directory)
            subprocess.run(['ditto',str(bundle),str(directory/bundle.name)],check=True)
            (directory/'Applications').symlink_to('/Applications')
            subprocess.run(['hdiutil','create','-volname','Orvanta Video Downloader','-srcfolder',str(directory),
                '-format','UDZO','-ov',str(artifact)],check=True)
    info=dict(version=APP_VERSION,platform=system,commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        python=sys.version,os=platform.platform(),mac_signing='ad-hoc; not Developer ID signed or notarized' if sys.platform=='darwin' else None,
        packages={name:version(name) for name in ('PySide6','yt-dlp','yt-dlp-ejs','pyinstaller','psutil')},tools={})
    for name,args in (('ffmpeg',['-version']),('ffprobe',['-version']),('aria2c',['--version'])):
        executable=shutil.which(name);assert executable
        info['tools'][name]=dict(sha256=hashlib.sha256(Path(executable).read_bytes()).hexdigest(),
            version_output=subprocess.check_output([executable,*args],text=True,stderr=subprocess.STDOUT))
    info['quickjs_commit']='6d46d07d04041b40f4f49eaa7fdebe44c314c699'
    report=output/(prefix+'-build-info.json');report.write_text(json.dumps(info,indent=2)+'\n',encoding='utf-8')
    (output/(prefix+'-SHA256SUMS.txt')).write_text(''.join(
        hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in (artifact,report)),encoding='utf-8')
    print('Created',artifact)

if __name__=='__main__':main()
