"""Exercise a distributed POSIX package: native GUI, CLI and MP3 worker."""
from functools import partial
from http.server import SimpleHTTPRequestHandler,ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
from threading import Thread

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from release_updates import APP_VERSION

def check(executable,directory):
    env=dict(os.environ,PATH='/usr/bin:/bin',QT_QPA_PLATFORM='xcb' if sys.platform=='linux' else 'cocoa')
    def run(arguments,timeout=120):
        result=subprocess.run([str(executable),*arguments],env=env,cwd=directory,capture_output=True,text=True,timeout=timeout)
        assert result.returncode==0,result.stdout+result.stderr
        assert 'Traceback' not in result.stderr,result.stderr
        return result.stdout
    assert 'PRODUCT_NAME=Orvanta Video Downloader' in run(['--smoke-test'])
    assert run(['--ytdlp','--version']).strip()
    subprocess.run([shutil.which('ffmpeg'),'-hide_banner','-loglevel','error','-f','lavfi','-i',
        'sine=frequency=440:duration=0.2',str(directory/'source.wav')],check=True,timeout=30)
    source=directory/'source.wav';original=hashlib.sha256(source.read_bytes()).hexdigest()
    config=directory/'config.json';config.write_text(json.dumps({'format':'mp3'}))
    events=[json.loads(line) for line in run(['--engine','--convert',str(config),str(source)]).splitlines() if line.startswith('{')]
    done=next(e for e in reversed(events) if e.get('type')=='done')
    assert done['returncode']==0 and Path(done['path']).suffix=='.mp3' and Path(done['path']).stat().st_size>0
    assert hashlib.sha256(source.read_bytes()).hexdigest()==original
    class Handler(SimpleHTTPRequestHandler):
        def log_message(self,*args):pass
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Handler,directory=str(directory)))
    thread=Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        target=directory/'download.wav'
        run(['--ytdlp','--ignore-config','--no-playlist','--no-cache-dir','--no-progress','-o',str(target),
             f'http://127.0.0.1:{server.server_port}/source.wav'])
        assert hashlib.sha256(target.read_bytes()).hexdigest()==original
    finally:server.shutdown();server.server_close();thread.join()
    print('PASS: native GUI, worker pipes, local download and bundled FFmpeg MP3 conversion; original preserved.')

def main():
    output=ROOT/'dist/release-output'
    with tempfile.TemporaryDirectory(prefix='orvanta-package-check-') as directory:
        directory=Path(directory)
        if sys.platform=='linux':
            artifact=output/f'OrvantaVideoDownloader-{APP_VERSION}-linux-x64.tar.gz'
            with tarfile.open(artifact) as archive:archive.extractall(directory,filter='data')
            check(directory/'OrvantaVideoDownloader/OrvantaVideoDownloader',directory)
        elif sys.platform=='darwin':
            artifact=output/f'OrvantaVideoDownloader-{APP_VERSION}-macos-arm64.dmg'
            mount=directory/'mount';mount.mkdir()
            subprocess.run(['hdiutil','attach','-nobrowse','-readonly','-mountpoint',str(mount),str(artifact)],check=True)
            try:
                bundle=mount/'Orvanta Video Downloader.app'
                subprocess.run(['codesign','--verify','--deep','--strict',str(bundle)],check=True)
                check(bundle/'Contents/MacOS/OrvantaVideoDownloader',directory)
            finally:subprocess.run(['hdiutil','detach',str(mount)],check=True)
        else:raise SystemExit('Run on Linux or macOS.')

if __name__=='__main__':main()
