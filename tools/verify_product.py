"""Opt-in live packaged download verification using the supplied public video."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
EXECUTABLE=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else ROOT/'dist/OrvantaVideoDownloader.exe'


def verify(name, config, url):
    result=subprocess.run([str(EXECUTABLE),'--engine','--download',config,url],
                          cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',
                          creationflags=subprocess.CREATE_NO_WINDOW,timeout=180)
    logs=ROOT/'test-output'/'verification';logs.mkdir(parents=True,exist_ok=True)
    (logs/('verification-'+name+'.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
    events=[json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    done=next((e for e in reversed(events) if e.get('type')=='done'),{})
    path=Path(done.get('path') or '')
    progress=[e for e in events if e.get('type')=='progress' and 0<e.get('percent',0)<100]
    assert result.returncode==0 and not done.get('errors') and path.is_file(), result.stderr+result.stdout[-1500:]
    assert progress, 'No intermediate packaged progress events'
    summary=dict(check=name,exit=result.returncode,intermediate_events=len(progress),bytes=path.stat().st_size,
                 extension=path.suffix,path_exists=True,arabic_path_valid='\ufffd' not in str(path))
    print(json.dumps(summary),flush=True)
    return summary


if __name__=='__main__':
    with ThreadPoolExecutor(max_workers=2) as executor:
        jobs=[executor.submit(verify,'original',str(ROOT/'tools/diagnostics/diagnostic-new-original.json'),'https://www.youtube.com/watch?v=u_G1NCwQZ4E'),
              executor.submit(verify,'mp4',str(ROOT/'tools/diagnostics/diagnostic-new-mp4.json'),'https://www.youtube.com/watch?v=jNQXAC9IVRw')]
        for job in jobs: job.result()
