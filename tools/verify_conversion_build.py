"""Verify the exact frozen conversion worker against an isolated tiny local clip."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    executable=Path(sys.argv[1]).resolve()
    root=ROOT/'test-temp';root.mkdir(exist_ok=True)
    hidden=getattr(subprocess,'CREATE_NO_WINDOW',0)
    with tempfile.TemporaryDirectory(prefix='packaged-conversion-',dir=root) as directory:
        directory=Path(directory);source=directory/'source.mkv'
        subprocess.run([str(ROOT/'tools/media/ffmpeg.exe'),'-hide_banner','-loglevel','error',
            '-f','lavfi','-i','testsrc2=size=160x90:rate=10','-t','2','-c:v','ffv1',str(source)],
            check=True,capture_output=True,creationflags=hidden,timeout=30)
        original=hashlib.sha256(source.read_bytes()).hexdigest()
        config=directory/'convert.json';config.write_text(json.dumps({'quality':'small'}),encoding='utf-8')
        result=subprocess.run([str(executable),'--engine','--convert',str(config),str(source)],
            capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=hidden,timeout=120)
        if result.returncode:raise RuntimeError(result.stdout+result.stderr)
        events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        done=next(event for event in reversed(events) if event.get('type')=='done')
        target=Path(done.get('path') or '')
        assert not done.get('errors') and target.is_file() and target!=source and target.suffix=='.mp4'
        assert original==hashlib.sha256(source.read_bytes()).hexdigest()
        measured=subprocess.run([str(ROOT/'tools/media/ffprobe.exe'),'-v','error','-select_streams','v:0',
            '-show_entries','stream=codec_name','-of','default=noprint_wrappers=1:nokey=1',str(target)],
            capture_output=True,text=True,check=True,creationflags=hidden,timeout=30)
        assert measured.stdout.strip()=='h264'
        print('Packaged MP4 conversion passed: H.264 copy, original intact, hidden worker, clean exit.')


if __name__=='__main__':main()
