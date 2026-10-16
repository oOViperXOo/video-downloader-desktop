"""Product workflow regression checks without network or media processes."""
import time
from types import SimpleNamespace
from datetime import datetime
from PySide6.QtCore import QEvent, QCoreApplication, Qt
from PySide6.QtWidgets import QApplication, QDialog, QComboBox, QCheckBox
from app import Window, Store, DEFAULTS
from test_process import app
from features_ui import (tick_queue, record_matches, move_jobs, prioritize,
    validate_feature_settings, choose_formats, finish_feature_job)


def finish(w):
    w.close(); w.deleteLater(); QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def job(identifier,status='ready'):
    return dict(id=identifier,title='Video '+identifier,url='https://vimeo.com/'+identifier,
        config=dict(DEFAULTS),status=status,percent=0,error='',path='')


def test_schedule_settings_apply_cancel_and_restart(tmp_path):
    w=Window(Store(tmp_path)); w.open_preferences(); w.feature_settings['quiet_start'].setText('22:00'); w.feature_settings['quiet_end'].setText('07:00')
    w.cancel_preferences(); assert w.config()['quiet_start']==''
    w.feature_settings['quiet_start'].setText('22:00');w.feature_settings['quiet_end'].setText('07:00');w.feature_settings['max_retries'].setText('0')
    assert w.save_settings(); assert Store(tmp_path).data['settings']['max_retries']=='0'; finish(w)


def test_invalid_settings_and_idle_timer(tmp_path,monkeypatch):
    import pytest
    with pytest.raises(ValueError): validate_feature_settings(dict(DEFAULTS,quiet_start='99:10'))
    with pytest.raises(ValueError): validate_feature_settings(dict(DEFAULTS,update_manifest_url='http://example.com/update.json'))
    w=Window(Store(tmp_path));calls=[];monkeypatch.setattr(w,'start_next',lambda:calls.append(True)); tick_queue(w);assert not calls
    j=job('1','queued');w.jobs.append(j);j['retry_at']=time.time()+100;tick_queue(w);assert not calls
    j['status']='paused';j['retry_at']=0;tick_queue(w);assert not calls
    j['status']='queued';tick_queue(w);assert calls==[True];w.stop_after_current=True;tick_queue(w);assert len(calls)==1;finish(w)


def test_filters_priority_and_reorder_do_not_delete(tmp_path):
    w=Window(Store(tmp_path)); a,b,c=job('1'),job('2'),job('3');w.jobs.extend([a,b,c]);w.refresh_queue()
    w.queue.topLevelItem(1).setSelected(True);move_jobs(w,-1);assert w.jobs==[b,a,c]
    w.queue.topLevelItem(0).setSelected(True);prioritize(w);assert b['priority']>0
    assert not hasattr(w,'queue_search') and len(w.jobs)==3
    w.history.extend([dict(title='Video '+str(i),status='done',path=str(tmp_path),url='https://vimeo.com/'+str(i)) for i in (1,3)])
    w.refresh_history();w.history_search[0].setText('Video 3')
    assert w.main_history.topLevelItemCount()==1 and len(w.history)==2
    assert not record_matches(w,a,'history');finish(w)


def test_format_selection_records_exact_stream_and_optional_copy(tmp_path,monkeypatch):
    from PySide6.QtWidgets import QTreeWidgetItem
    w=Window(Store(tmp_path));w.items=[dict(title='Test',formats=[dict(format_id='22',selector='22',vcodec='h264',acodec='aac',estimated_size=1000000,label='720p MP4')])]
    row=QTreeWidgetItem(['Test','1:00']);row.setCheckState(0,Qt.Checked);w.pick.addTopLevelItem(row)
    def accept(dialog):
        for combo in dialog.findChildren(QComboBox):
            if combo.count()>1 and isinstance(combo.itemData(1),dict): combo.setCurrentIndex(1)
        for check in dialog.findChildren(QCheckBox): check.setChecked(True)
        return QDialog.Accepted
    monkeypatch.setattr(QDialog,'exec',accept);assert choose_formats(w)
    assert w.items[0]['_selection']['format_id']=='22';assert w.items[0]['_selection']['convert_mp4'];assert w.items[0]['estimated_bytes']==1000000
    j=job('1');j['config'].update(w.items[0]['_selection']);w.update_job_choice(j,'mode','audio');assert j['config']['format_id']=='';finish(w)


def test_retry_backoff_and_conversion_abort_preserves_original(tmp_path):
    w=Window(Store(tmp_path));j=job('1','error');j['error']='Connection timed out';w.jobs.append(j)
    config=tmp_path/'active.json';config.write_text('{}');worker=SimpleNamespace(job=j,reason=None,config_path=config,deleteLater=lambda:None)
    w.workers[j['id']]=worker
    assert finish_feature_job(w,worker,1);assert j['status']=='queued' and j['retry_count']==1 and j['retry_at']>time.time();assert not config.exists()
    j.update(_converting=True,_original_path=str(tmp_path/'original.webm'),path=str(tmp_path/'copy.mp4'),kind='conversion');worker.reason='cancelled'
    assert not finish_feature_job(w,worker,1);assert j['path'].endswith('original.webm');assert not j.get('_converting');assert not w.completion_bar.isVisible()
    config.write_text('{}');w.workers[j['id']]=worker;j.update(_converting=True,_original_path=j['path'],kind='conversion');worker.reason='cancelled';w.worker_finished(worker,1)
    assert j['status']=='done' and j['conversion_status']=='cancelled';assert j['path'].endswith('original.webm');finish(w)

def test_existing_copy_starts_conversion_without_download(tmp_path,monkeypatch):
    from features_ui import convert_existing
    from download_worker import DownloadWorker
    w=Window(Store(tmp_path));j=job('10','done');source=tmp_path/'source.webm';source.write_bytes(b'original');j['path']=str(source);w.jobs.append(j);w.refresh_queue();w.queue.topLevelItem(0).setSelected(True)
    started=[];monkeypatch.setattr(DownloadWorker,'start',lambda worker:started.append(worker.job.get('_converting')));monkeypatch.setattr(QDialog,'exec',lambda dialog:QDialog.Accepted)
    convert_existing(w);assert started==[True] and j['kind']=='conversion';worker=w.workers[j['id']];worker.reason='paused';w.worker_finished(worker,1)
    assert j['status']=='done' and j['conversion_status']=='paused' and source.read_bytes()==b'original';finish(w)
