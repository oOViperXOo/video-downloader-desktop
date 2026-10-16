"""Exercise the packaged conversion worker with local audio, without network."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

root=Path(__file__).resolve().parents[1]
flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
with tempfile.TemporaryDirectory(prefix='mp3-worker-',dir=root/'test-temp') as directory:
    folder=Path(directory);source=folder/'audio.wav';config=folder/'copy.json'
    ffmpeg=root/'tools/media/ffmpeg.exe'
    subprocess.run([str(ffmpeg),'-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=440:duration=0.2',str(source)],check=True,creationflags=flags)
    original=source.read_bytes();config.write_text(json.dumps({'format':'mp3'}),encoding='utf-8')
    for executable in sys.argv[1:]:
        result=subprocess.run([str(Path(executable).resolve()),'--engine','--convert',str(config),str(source)],capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=flags,timeout=120)
        events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
        done=next((event for event in reversed(events) if event.get('type')=='done'),None)
        assert result.returncode==0 and done and done.get('returncode')==0,result.stdout+result.stderr
        output=Path(done['path'])
        assert output.suffix=='.mp3' and output.is_file() and output.stat().st_size>0
        assert source.read_bytes()==original
        print(Path(executable).name+': packaged MP3 worker PASS; original preserved')
