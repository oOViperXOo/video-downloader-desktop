from pathlib import Path
from types import SimpleNamespace
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMessageBox,QDialog
from app import Window,Store,DEFAULTS
from test_process import app


def finish(w):
    w.workers.clear();w.active=None;w.inspector=None;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_colliding_queue_timer_does_not_rewrite_or_rebuild(tmp_path,monkeypatch):
    import features_ui
    w=Window(Store(tmp_path));cfg=dict(DEFAULTS,outdir=str(tmp_path))
    first=dict(id='a',title='A',url='https://vimeo.com/1',status='downloading',config=dict(cfg))
    second=dict(id='b',title='B',url='https://vimeo.com/1',status='queued',config=dict(cfg))
    w.jobs.extend([first,second]);w.workers={'a':SimpleNamespace(job=first)};w.active=first
    calls=[];monkeypatch.setattr(w.store,'save',lambda:calls.append('save'));monkeypatch.setattr(w,'refresh_queue',lambda:calls.append('refresh'))
    monkeypatch.setattr(features_ui,'job_allowed',lambda *args:True)
    w.start_next();assert calls==[] and second['status']=='queued'
    finish(w)


def test_declining_close_keeps_schedule_timer_alive(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));w.inspector=object()
    monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.No)
    event=QCloseEvent();w.closeEvent(event)
    assert not event.isAccepted() and not w.closing and w.feature_timer.isActive()
    finish(w)


def test_conversion_notification_opens_copy_keeps_original(tmp_path,monkeypatch):
    import features_ui
    w=Window(Store(tmp_path));source=tmp_path/'original.webm';source.write_bytes(b'original');copy=tmp_path/'copy.mp4';copy.write_bytes(b'copy')
    item=dict(title='Video',path=str(source),converted_path=str(copy),config=dict(DEFAULTS));opened=[]
    monkeypatch.setattr(features_ui.QDesktopServices,'openUrl',lambda url:opened.append(Path(url.toLocalFile())))
    features_ui.notify_completed(w,item);features_ui.open_completed(w,False)
    assert opened==[copy] and item['path']==str(source) and 'MP4 copy ready' in w.completion_bar.label.text()
    finish(w)


def test_no_space_for_conversion_keeps_completed_original(tmp_path,monkeypatch):
    import features_ui
    w=Window(Store(tmp_path));source=tmp_path/'source.webm';source.write_bytes(b'original')
    item=dict(id='a',title='Video',url='https://vimeo.com/1',status='done',path=str(source),config=dict(DEFAULTS),error='')
    w.jobs.append(item);w.refresh_queue();w.queue.topLevelItem(0).setSelected(True)
    monkeypatch.setattr(QDialog,'exec',lambda *args:QDialog.Accepted)
    def reject(window,job):job.update(status='paused',error='Low disk space');return False
    monkeypatch.setattr(features_ui,'job_allowed',reject)
    features_ui.convert_existing(w)
    assert item['status']=='done' and item['path']==str(source) and source.read_bytes()==b'original' and not w.workers
    finish(w)
