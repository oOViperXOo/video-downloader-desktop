import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog
from app import Window,Store
from test_process import app
from test_ui_performance import job,finish


def test_main_menu_only_contains_current_actions(tmp_path):
    w=Window(Store(tmp_path))
    texts={a.text() for a in w.app_more.menu().actions() if not a.isSeparator()}
    assert texts=={'Clear completed and cancelled items','Add several links…','Settings…',
                   'Open output folder','Diagnostics','About','Check for updates…'}
    finish(w)


@pytest.mark.parametrize('suffix,status,mode,exists,offered',[
    ('.webm','done','video',True,True),('.MKV','skipped','video',True,True),
    ('.mp4','done','video',True,False),('.MP4','done','video',True,False),
    ('.webm','downloading','video',True,False),('.webm','error','video',True,False),
    ('.webm','ready','video',True,False),('.mp3','done','audio',True,False),
    ('.webm','done','audio',True,False),('.webm','done','video',False,False),
])
def test_mp4_action_only_for_completed_non_mp4_video(tmp_path,suffix,status,mode,exists,offered):
    w=Window(Store(tmp_path));record=job(0);record['status']=status;record['config']['mode']=mode
    source=tmp_path/('video'+suffix)
    if exists:source.write_bytes(b'video')
    record['path']=str(source);w.jobs.append(record);w.refresh_queue()
    item=w._queue_items['0'];item.setSelected(True)
    menu=w.create_row_menu(w.queue.visualItemRect(item).center())
    assert ('make MP4 copy' in [a.text() for a in menu.actions()]) is offered
    finish(w)


def test_multiple_selection_does_not_offer_mp4(tmp_path):
    w=Window(Store(tmp_path));source=tmp_path/'video.mkv';source.touch()
    for i in range(2):
        record=job(i);record.update(status='done',path=str(source));w.jobs.append(record)
    w.refresh_queue()
    for item in w._queue_items.values():item.setSelected(True)
    menu=w.create_row_menu(w.queue.visualItemRect(w._queue_items['0']).center())
    assert 'make MP4 copy' not in [a.text() for a in menu.actions()]
    assert 'Remove from list' in [a.text() for a in menu.actions()]
    finish(w)


def test_archived_video_can_start_copy_from_context_menu(tmp_path,monkeypatch):
    from download_worker import DownloadWorker
    w=Window(Store(tmp_path));source=tmp_path/'saved.webm';source.write_bytes(b'original')
    record=dict(title='Saved',url='https://example.com/1',path=str(source),status='done')
    w.history.append(record);w.refresh_queue();item=w.queue.topLevelItem(0);item.setSelected(True)
    menu=w.create_row_menu(w.queue.visualItemRect(item).center())
    monkeypatch.setattr(QDialog,'exec',lambda _:QDialog.Accepted)
    monkeypatch.setattr(DownloadWorker,'start',lambda _:None)
    next(a for a in menu.actions() if a.text()=='make MP4 copy').trigger()
    assert len(w.workers)==1 and w.jobs[0]['_converting']
    assert record['status']=='done' and source.read_bytes()==b'original'
    worker=next(iter(w.workers.values()));worker.reason='paused';w.worker_finished(worker,1)
    finish(w)
