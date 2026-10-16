import json
import sys

from PySide6.QtCore import QCoreApplication, QEvent
from app import Window, Store, DEFAULTS, engine_config
from test_process import app, spin_until


def test_two_workers_have_independent_configs_and_pause(tmp_path):
    fake=tmp_path/'worker.py'
    fake.write_text('import json,time\nprint(json.dumps(dict(type="progress",percent=35,total=100,downloaded=35)),flush=True)\ntime.sleep(1)\nprint(json.dumps(dict(type="done",path="result.webm",errors=[],returncode=0)),flush=True)\n',encoding='utf-8')
    window=Window(Store(tmp_path/'state'))
    window.command=lambda p,args:p.start(sys.executable,[str(fake)])
    for i in range(3):
        window.jobs.append(dict(id=str(i),video_id=str(i+1),title='Video '+str(i),url='https://vimeo.com/'+str(i+1),status='queued',percent=0,config=dict(DEFAULTS),error=''))
    window.start_next()
    assert len(window.workers)==2
    configs=[w.config_path for w in window.workers.values()]
    assert len(set(configs))==2 and all(p.is_file() for p in configs)
    assert all(json.loads(p.read_text())['external_downloader']=='off' for p in configs)
    spin_until(lambda:all(j.get('percent')==35 for j in window.jobs[:2]))
    window.row_action(window.jobs[0],'pause')
    spin_until(lambda:window.jobs[0]['status']=='paused')
    assert window.jobs[1]['status'] in ('downloading','done')
    spin_until(lambda:not window.workers and window.jobs[2]['status']=='done')
    assert window.jobs[0]['status']=='paused'
    assert window.jobs[1]['status']=='done'
    assert not any(p.exists() for p in configs)
    window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_connection_modes_and_per_item_overrides(tmp_path):
    window=Window(Store(tmp_path))
    config=dict(DEFAULTS,connection_mode='single',connections=8)
    single=engine_config(config)
    assert single['connections']==1 and single['external_downloader']=='off'
    job=dict(id='a',title='item',url='https://vimeo.com/1',status='ready',config=config,percent=0,error='')
    window.jobs.append(job)
    window.set_job_connection(job,'multiple')
    multi=engine_config(job['config'])
    assert multi['connections']==8 and multi['external_downloader']=='auto'
    assert Store(tmp_path).data['queue'][0]['config']['connection_mode']=='multiple'
    window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_excluded_queued_item_does_not_start(tmp_path):
    window=Window(Store(tmp_path))
    window.command=lambda *args: (_ for _ in ()).throw(AssertionError('Excluded item started'))
    window.jobs.append(dict(id='x',title='Excluded',url='https://vimeo.com/1',status='queued',included=False,config=dict(DEFAULTS),percent=0,error=''))
    window.start_next()
    assert not window.workers
    window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_playlist_cookie_file_survives_first_completed_job(tmp_path):
    window=Window(Store(tmp_path/'state'))
    folder=tmp_path/'cookies';folder.mkdir();cookie=folder/'shared.txt';cookie.write_text('test',encoding='utf-8')
    jobs=[dict(id=str(i),title='item',url='https://vimeo.com/1',status=status,config=dict(DEFAULTS,cookies_file=str(cookie)),percent=0,error='') for i,status in enumerate(['done','queued'])]
    window.jobs.extend(jobs)
    window.drop_cookie_file(jobs[0]);assert cookie.is_file()
    jobs[1]['status']='done'
    window.drop_cookie_file(jobs[1]);assert not cookie.exists()
    window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_switching_sparse_partial_to_single_keeps_backup(tmp_path):
    window=Window(Store(tmp_path/'state'))
    destination=tmp_path/'video.mp4'
    partial=tmp_path/'video.mp4.part';partial.write_bytes(b'partial')
    control=tmp_path/'video.mp4.part.aria2';control.write_bytes(b'range-state')
    job=dict(id='a',title='item',url='https://vimeo.com/1',status='paused',config=dict(DEFAULTS,outdir=str(tmp_path),connection_mode='multiple'),percent=50,transfer_files=[str(destination)],error='')
    window.jobs.append(job);window.set_job_connection(job,'single')
    assert not partial.exists() and not control.exists()
    assert next(tmp_path.glob('video.mp4.part.multi-backup-*')).read_bytes()==b'partial'
    assert next(tmp_path.glob('video.mp4.part.aria2.multi-backup-*')).read_bytes()==b'range-state'
    assert job['percent']==0
    window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_bulk_defaults_preserve_partial_in_old_directory(tmp_path,monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.Yes)
    window=Window(Store(tmp_path/'state'))
    old=tmp_path/'old';old.mkdir()
    partial=old/'video.mp4.part';partial.write_bytes(b'sparse-data')
    control=old/'video.mp4.part.aria2';control.write_bytes(b'ranges')
    job=dict(id='bulk',title='Video',url='https://vimeo.com/1',status='paused',percent=50,
             config=dict(DEFAULTS,outdir=str(old),connection_mode='multiple'),
             transfer_files=[str(old/'video.mp4')],error='')
    window.jobs.append(job)
    defaults=dict(DEFAULTS,outdir=str(tmp_path/'new'),connection_mode='single')
    window.config=lambda:defaults
    window.apply_defaults_to_waiting()
    assert job['config']['outdir']==defaults['outdir'] and job['config']['connection_mode']=='single'
    assert not partial.exists() and not control.exists()
    assert next(old.glob('*.part.multi-backup-*')).read_bytes()==b'sparse-data'
    assert next(old.glob('*.aria2.multi-backup-*')).read_bytes()==b'ranges'
    window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_scheduler_serializes_colliding_custom_template(tmp_path):
    from types import SimpleNamespace
    window=Window(Store(tmp_path/'state'))
    config=dict(DEFAULTS,outdir=str(tmp_path),template='video.%(ext)s')
    running=dict(id='first',video_id='1',title='First',url='https://vimeo.com/1',status='downloading',config=dict(config))
    queued=dict(id='second',video_id='2',title='Second',url='https://vimeo.com/2',status='queued',config=dict(config))
    window.jobs.extend([running,queued]);window.workers={'first':SimpleNamespace(job=running)}
    window.command=lambda *args: (_ for _ in ()).throw(AssertionError('Colliding item started'))
    window.start_next()
    assert queued['status']=='queued' and len(window.workers)==1
    window.workers.clear();window.jobs.clear()
    window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
