"""Repeatable source UI benchmark; no network or user state is used."""
from pathlib import Path
import argparse
import json
import os
import sys
import tempfile
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import psutil
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtTest import QTest
from app import Window,Store,DEFAULTS

parser=argparse.ArgumentParser();parser.add_argument('--rows',type=int,default=200);args=parser.parse_args()
qt=QApplication([]);qt.setStyle('Fusion');process=psutil.Process()
benchmark_root=Path(__file__).resolve().parents[1]/'test-temp';benchmark_root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='downloader-benchmark-',dir=benchmark_root) as directory:
    assert Path(directory).resolve().is_relative_to(benchmark_root.resolve())
    store=Store(directory);store.data['settings'].update(receiver=False,clipboard=False)
    started=time.perf_counter();window=Window(store);window.show();QTest.qWait(20)
    startup=time.perf_counter()-started
    before=process.memory_info().rss
    for i in range(args.rows):
        window.jobs.append(dict(id=str(i),title='Benchmark video '+str(i),url='https://example.com/'+str(i),status='ready',percent=0,config=dict(DEFAULTS),error=''))
    started=time.perf_counter();window.refresh_queue();qt.processEvents();build=time.perf_counter()-started
    dialogs=sum(isinstance(row.__dict__.get('settings_dialog'),QDialog) for row in window.row_widgets.values())
    growth=process.memory_info().rss-before;widgets=len(qt.allWidgets())
    started=time.perf_counter();window.refresh_queue();qt.processEvents();refresh=time.perf_counter()-started
    job=window.jobs[0];job['status']='downloading';started=time.perf_counter()
    for i in range(500):window.handle_engine_event(dict(type='progress',percent=i%100,downloaded=i*1024,total=1024*1024,speed=1024,eta=10),job)
    if hasattr(window,'flush_progress_updates'):window.flush_progress_updates()
    qt.processEvents();progress=time.perf_counter()-started
    print(json.dumps(dict(rows=args.rows,startupMs=round(startup*1000,1),buildMs=round(build*1000,1),unchangedRefreshMs=round(refresh*1000,1),progressBurstMs=round(progress*1000,1),queueMemoryMiB=round(growth/1048576,1),widgets=widgets,optionsDialogs=dialogs)))
    window.close()
