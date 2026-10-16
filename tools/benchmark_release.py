"""Compare repeatable launch-and-close smoke times for frozen builds."""
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

results=[]
for argument in sys.argv[1:]:
    executable=Path(argument).resolve();samples=[]
    for _ in range(3):
        start=time.perf_counter()
        process=subprocess.run([str(executable),'--smoke-test'],capture_output=True,text=True,encoding='utf-8',errors='replace',creationflags=subprocess.CREATE_NO_WINDOW,env=dict(os.environ,QT_QPA_PLATFORM='windows'),timeout=90)
        assert process.returncode==0 and 'GUI_READY' in process.stdout,process.stdout+process.stderr
        samples.append(round((time.perf_counter()-start)*1000,1))
    results.append(dict(executable=str(executable),samplesMs=samples,medianMs=statistics.median(samples)))
print(json.dumps(dict(note='Each native Windows launch-and-close sample includes the same 750 ms smoke-test timer; not a cold-boot benchmark.',results=results),indent=2))
