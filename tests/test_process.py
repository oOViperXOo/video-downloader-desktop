import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QElapsedTimer, QCoreApplication, QEvent
from app import Window, Store
app=QApplication.instance() or QApplication([])

def spin_until(predicate, timeout=5000):
    timer=QElapsedTimer(); timer.start()
    while not predicate() and timer.elapsed()<timeout:
        app.processEvents()
    assert predicate()

def test_process_queue_protocol(tmp_path):
    fake=tmp_path/'fake.py'
    fake.write_text('import json\nprint(json.dumps(dict(type="progress",percent=50,speed=1048576,eta=2)),flush=True)\nprint(json.dumps(dict(type="done",path="/tmp/demo.mp4")),flush=True)\n')
    s=Store(tmp_path/'state'); w=Window(s)
    import sys
    w.command=lambda p,args:p.start(sys.executable,[str(fake)])
    for i in range(2):
        w.jobs.append(dict(id=str(i),title='Example '+str(i),url='https://youtu.be/test',status='queued',percent=0,config=dict(s.data['settings']),error=''))
    w.start_next()
    spin_until(lambda:len(w.history)==2 and w.active is None)
    assert all(j['status']=='done' for j in w.jobs)
    assert w.jobs[0]['speed']=='1.00 MiB/s'
    assert w.jobs[0]['eta']=='2 s'
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

def test_stop_resume_state(tmp_path):
    fake=tmp_path/'slow.py'; fake.write_text('import time\ntime.sleep(20)\n')
    s=Store(tmp_path/'state'); w=Window(s)
    import sys
    w.command=lambda p,args:p.start(sys.executable,[str(fake)])
    w.jobs.append(dict(id='1',title='Paused example',url='https://youtu.be/test',status='queued',percent=0,config=dict(s.data['settings']),error=''))
    w.start_next(); w.queue.topLevelItem(0).setSelected(True); w.stop_selected('paused')
    spin_until(lambda:w.active is None)
    assert w.jobs[0]['status']=='paused'
    assert not w.history
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

def test_error_summary_is_not_done(tmp_path):
    w=Window(Store(tmp_path)); w.active=dict(status='downloading',percent=20,error='')
    w.handle_engine_event(dict(type='done',path=None,errors=[dict(message='Unavailable')],returncode=0,skipped=0))
    assert w.active['status']=='error' and w.active['error']=='Unavailable'
    w.active=None; w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

def test_failed_start_advances_queue(tmp_path):
    w=Window(Store(tmp_path)); w.command=lambda p,args:p.start('/nonexistent/python',[])
    w.jobs.append(dict(id='1',title='Bad command',url='https://youtu.be/test',status='queued',percent=0,config=dict(w.store.data['settings']),error=''))
    w.start_next(); spin_until(lambda:w.active is None)
    assert w.jobs[0]['status']=='error'
    assert len(w.history)==1
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

def test_stop_cleans_child_tree(tmp_path):
    from PySide6.QtCore import QProcess
    from app import stop_process_tree
    import sys, psutil, time
    marker=tmp_path/'child.pid'; fake=tmp_path/'parent.py'
    fake.write_text('import subprocess,sys,time\np=subprocess.Popen([sys.executable,"-c","import time;time.sleep(20)"])\nopen(sys.argv[1],"w").write(str(p.pid))\ntime.sleep(20)\n')
    p=QProcess(); p.start(sys.executable,[str(fake),str(marker)])
    spin_until(lambda: marker.exists() and bool(marker.read_text()))
    pid=int(marker.read_text()); stop_process_tree(p,force=True); assert p.waitForFinished(3000)
    timer=QElapsedTimer();timer.start()
    while psutil.pid_exists(pid) and timer.elapsed()<3000:
        try:
            if psutil.Process(pid).status()==psutil.STATUS_ZOMBIE: break
        except psutil.NoSuchProcess: break
        app.processEvents(); time.sleep(.01)
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status()==psutil.STATUS_ZOMBIE
    p.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

def test_bad_config_does_not_deadlock(tmp_path):
    w=Window(Store(tmp_path));w.jobs.append(dict(id='1',title='Bad',url='https://youtu.be/x',status='queued',percent=0,config={'template':'a/b'},error=''))
    w.start_next();assert w.active is None and w.jobs[0]['status']=='error'
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

def test_archive_skip_distinct_state(tmp_path):
    w=Window(Store(tmp_path));w.active=dict(status='downloading',percent=0,error='')
    w.handle_engine_event(dict(type='done',path=None,errors=[],returncode=0,skipped=1))
    assert w.active['status']=='skipped' and '.completed-' in w.active['error']
    w.active=None;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)

def test_utf8_split_chunks(tmp_path):
    import codecs, json
    w=Window(Store(tmp_path));w.active=dict(status='downloading',percent=0,error='');w.output='';w.download_decoder=codecs.getincrementaldecoder('utf-8')('replace')
    class Fake:
        def __init__(self,data):self.data=data
        def readAllStandardOutput(self):return self.data
    data=json.dumps(dict(type='error',message='عربي'),ensure_ascii=False).encode()+b'\n'
    offset=data.index('ع'.encode())+1
    w.read_download(Fake(data[:offset]));w.read_download(Fake(data[offset:]))
    assert w.active['error']=='عربي'
    w.active=None;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
