from PySide6.QtCore import QCoreApplication,QEvent
from PySide6.QtTest import QTest
from app import Window,Store,DEFAULTS
from test_process import app


def job(i):
    return dict(id=str(i),title='Video '+str(i),url='https://example.com/'+str(i),status='ready',percent=0,error='',config=dict(DEFAULTS))


def finish(w):
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_dialogs_lazy_and_unchanged_rows_survive_refresh(tmp_path):
    w=Window(Store(tmp_path));w.show();w.jobs.extend(job(i) for i in range(20));w.refresh_queue();app.processEvents()
    original=dict(w.row_widgets)
    assert all(row.settings_dialog is None for row in original.values())
    w.refresh_queue();app.processEvents()
    assert all(w.row_widgets[key] is row for key,row in original.items())
    w.jobs[0]['config']['mode']='audio';w.refresh_queue();app.processEvents()
    assert w.row_widgets['0'] is not original['0']
    assert all(w.row_widgets[key] is row for key,row in original.items() if key!='0')
    w.row_widgets['1'].open_options();app.processEvents()
    assert sum(row.settings_dialog is not None for row in w.row_widgets.values())==1
    w.jobs.pop(0);w.refresh_queue();app.processEvents()
    assert w.row_widgets['1'] is original['1'] and w.queue.itemWidget(w.queue.topLevelItem(0),0) is original['1']
    finish(w)


def test_removing_opened_row_releases_its_unused_controls(tmp_path):
    from shiboken6 import isValid
    w=Window(Store(tmp_path));record=job(0);w.jobs.append(record);w.refresh_queue()
    row=w.row_widgets['0'];row.open_options();hidden_format=row.format;hidden_cancel=row.cancel_button
    w.remove_job(record);app.processEvents();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
    assert not isValid(hidden_format) and not isValid(hidden_cancel)
    finish(w)


def test_progress_is_coalesced_and_done_cannot_be_overwritten(tmp_path):
    w=Window(Store(tmp_path));w.jobs.extend([job(0),job(1)]);w.refresh_queue()
    calls=[]
    for key,row in w.row_widgets.items():
        original=row.update_state
        row.update_state=lambda key=key,original=original:(calls.append(key),original())
    for i in range(100):
        for record in w.jobs:w.handle_engine_event(dict(type='progress',percent=i,total=100,downloaded=i,speed=1,eta=1),record)
    assert all(record['percent']==99 for record in w.jobs) and calls==[]
    QTest.qWait(130);assert sorted(calls)==['0','1']
    record=w.jobs[0];w.handle_engine_event(dict(type='progress',percent=80,total=100,downloaded=80),record)
    w.handle_engine_event(dict(type='done',path='file.mp4',errors=[],returncode=0),record)
    QTest.qWait(130)
    assert record['status']=='done' and record['percent']==100 and w.row_widgets['0'].detail.text()=='Completed'
    finish(w)
