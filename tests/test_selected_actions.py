from pathlib import Path
import errno
import subprocess
import pytest
from PySide6.QtCore import Qt,QUrl
from PySide6.QtWidgets import QMessageBox,QInputDialog,QFileDialog,QDialog
from PySide6.QtTest import QTest
from app import Window,Store
import row_actions as actions
from test_process import app
from test_ui_performance import job,finish


def completed(w,tmp_path,suffix='.mkv'):
    record=job(0);source=tmp_path/('video'+suffix);source.write_bytes(b'original')
    record.update(path=str(source),status='done');w.jobs.append(record)
    w.history.append(dict(title=record['title'],path=str(source),status='done',url=record['url']))
    w.refresh_queue();w._queue_items['0'].setSelected(True)
    return record,source


def test_double_click_actual_title_and_missing_file(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));record,source=completed(w,tmp_path);w.show();app.processEvents()
    opened=[];messages=[]
    monkeypatch.setattr(actions.QDesktopServices,'openUrl',lambda url:opened.append(url.toLocalFile()) or True)
    monkeypatch.setattr(QMessageBox,'information',lambda *args:messages.append(args[2]))
    QTest.mouseClick(w.row_widgets['0'].title,Qt.LeftButton)
    QTest.mouseDClick(w.row_widgets['0'].title,Qt.LeftButton);app.processEvents()
    assert [Path(path) for path in opened]==[source]
    source.unlink();w.open_downloaded_item(w._queue_items['0'])
    assert len(opened)==1 and 'no longer available' in messages[-1]
    record['status']='paused';w.open_downloaded_item(w._queue_items['0']);assert len(messages)==1
    finish(w)


def test_open_failure_is_graceful(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));record,source=completed(w,tmp_path);messages=[]
    monkeypatch.setattr(actions.QDesktopServices,'openUrl',lambda url:False)
    monkeypatch.setattr(QMessageBox,'information',lambda *args:messages.append(args[2]))
    actions.open_record(w,record);assert 'could not open' in messages[0].lower()
    finish(w)


def test_selected_menu_and_copy_link(tmp_path):
    w=Window(Store(tmp_path));record,source=completed(w,tmp_path)
    menu=w.create_row_menu(w.queue.visualItemRect(w._queue_items['0']).center())
    texts={a.text() for a in menu.actions() if not a.isSeparator()}
    assert texts=={'Open','Show in folder','Copy link','Open download page','Rename file','Move to…','Delete file','make MP4 copy','Make MP3 copy','Remove from list'}
    next(a for a in menu.actions() if a.text()=='Copy link').trigger()
    assert app.clipboard().text()==record['url']
    finish(w)


def test_show_folder_and_download_page(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));record,source=completed(w,tmp_path);calls=[]
    monkeypatch.setattr(actions.subprocess,'Popen',lambda command,**kwargs:calls.append(command))
    opened=[];monkeypatch.setattr(actions.QDesktopServices,'openUrl',lambda url:opened.append(url.toString()) or True)
    actions.show_in_folder(w,record)
    if actions.os.name=='nt':assert calls[0][-1]==str(source)
    else:assert opened==[QUrl.fromLocalFile(str(source.absolute().parent)).toString()]
    opened.clear()
    menu=w.create_row_menu(w.queue.visualItemRect(w._queue_items['0']).center())
    next(a for a in menu.actions() if a.text()=='Open download page').trigger()
    assert opened==[record['url']]
    finish(w)


def test_invalid_url_leaves_job_unchanged(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));record=job(0);record['status']='error';w.jobs.append(record)
    previous=dict(record);messages=[]
    monkeypatch.setattr(QInputDialog,'getText',lambda *args,**kwargs:('file:///C:/wrong',True))
    monkeypatch.setattr(QMessageBox,'information',lambda *args:messages.append(args[2]))
    actions.change_url(w,record);assert record==previous and messages
    finish(w)


def test_rename_updates_history_and_preserves_collision(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));record,source=completed(w,tmp_path)
    monkeypatch.setattr(QInputDialog,'getText',lambda *args,**kwargs:('renamed.mkv',True))
    actions.rename_file(w,record);destination=tmp_path/'renamed.mkv'
    assert destination.read_bytes()==b'original' and not source.exists()
    assert record['path']==w.history[0]['path']==str(destination)
    assert record['title']==w.history[0]['title']=='renamed.mkv'
    assert Store(tmp_path).data['history'][0]['path']==str(destination)
    source.write_bytes(b'keep');messages=[]
    monkeypatch.setattr(QInputDialog,'getText',lambda *args,**kwargs:(source.name,True))
    monkeypatch.setattr(QMessageBox,'information',lambda *args:messages.append(args[2]))
    actions.rename_file(w,record)
    assert destination.exists() and source.read_bytes()==b'keep' and messages
    finish(w)


def test_background_move_updates_all_records(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));record,source=completed(w,tmp_path);target=tmp_path/'moved';target.mkdir()
    monkeypatch.setattr(QFileDialog,'getExistingDirectory',lambda *args:str(target))
    actions.move_files(w,[record]);assert w.file_task.wait(5000);app.processEvents()
    assert not source.exists() and (target/source.name).read_bytes()==b'original'
    assert record['path']==w.history[0]['path']==str(target/source.name)
    finish(w)


def test_cross_volume_failed_copy_keeps_original(tmp_path,monkeypatch):
    source=tmp_path/'a.mkv';source.write_bytes(b'original');destination=tmp_path/'b.mkv'
    monkeypatch.setattr(actions.os,'rename',lambda *args:(_ for _ in ()).throw(OSError(errno.EXDEV,'different volume')))
    monkeypatch.setattr(actions.shutil,'copyfileobj',lambda *args:(_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError):actions.move_without_overwrite(source,destination)
    assert source.read_bytes()==b'original' and not destination.exists()


def test_delete_requires_confirmation_and_removes_persisted_record(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));record,source=completed(w,tmp_path)
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:QMessageBox.No)
    actions.delete_files(w,[record]);assert source.exists() and record in w.jobs and w.history
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:QMessageBox.Yes)
    actions.delete_files(w,[record]);assert not source.exists() and not w.jobs and not w.history
    assert w.queue.topLevelItemCount()==0
    restored=Store(tmp_path);assert not restored.data['queue'] and not restored.data['history']
    finish(w)


def test_delete_partial_failure_keeps_failed_file_and_its_row(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));first,source=completed(w,tmp_path)
    blocked=tmp_path/'blocked.mp4';blocked.write_bytes(b'keep')
    second=job(1);second.update(path=str(blocked),status='done');w.jobs.append(second)
    w.history.append(dict(title=second['title'],path=str(blocked),status='done',url=second['url']))
    w.refresh_queue();messages=[];unlink=Path.unlink
    def remove(path,*args,**kwargs):
        if path==blocked:raise PermissionError('File is locked')
        return unlink(path,*args,**kwargs)
    monkeypatch.setattr(Path,'unlink',remove)
    monkeypatch.setattr(QMessageBox,'warning',lambda *args:QMessageBox.Yes)
    monkeypatch.setattr(actions,'message',lambda parent,text:messages.append(text))
    actions.delete_files(w,[first,second])
    assert not source.exists() and blocked.exists()
    assert w.jobs==[second] and len(w.history)==1 and Path(w.history[0]['path'])==blocked
    assert w.queue.topLevelItemCount()==1 and messages and 'locked' in messages[0]
    finish(w)


def test_change_url_uses_new_destination_preserves_partial(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));record=job(0);record.update(status='paused',video_id='old',source_id='old',duration=100,percent=50,path=str(tmp_path/'old.mkv'))
    partial=tmp_path/'old.mkv.part';partial.write_bytes(b'partial');template=record['config']['template']
    record['config']['format_id']='18';w.jobs.append(record);w.refresh_queue()
    monkeypatch.setattr(QInputDialog,'getText',lambda *args,**kwargs:('https://example.com/new',True))
    actions.change_url(w,record)
    assert record['url'].endswith('/new') and record['status']=='ready' and record['percent']==0
    assert record['config']['template']!=template and record['config']['format_id']==''
    assert 'video_id' not in record and 'source_id' not in record and 'duration' not in record and 'path' not in record and partial.read_bytes()==b'partial'
    finish(w)


def test_make_mp3_copy_uses_worker_and_preserves_original(tmp_path,monkeypatch):
    from features_ui import convert_existing
    from download_worker import DownloadWorker
    import json
    w=Window(Store(tmp_path));record,source=completed(w,tmp_path)
    monkeypatch.setattr(QDialog,'exec',lambda _:QDialog.Accepted)
    monkeypatch.setattr(DownloadWorker,'start',lambda _:None)
    convert_existing(w,record,'mp3');worker=w.workers['0']
    assert json.loads(worker.config_path.read_text())['format']=='mp3'
    assert record['_conversion_format']=='mp3' and source.read_bytes()==b'original'
    worker.reason='paused';w.worker_finished(worker,1);assert record['path']==str(source)
    finish(w)


def test_real_mp3_copy_has_audio_and_preserves_existing_output(tmp_path):
    import os
    from media_conversion import Converter,find_ffmpeg
    ffmpeg=find_ffmpeg()
    if not ffmpeg:pytest.skip('FFmpeg unavailable')
    source=tmp_path/'audio.wav'
    subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-f','lavfi','-i','sine=frequency=440:duration=0.2',str(source)],check=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    original=source.read_bytes();existing=tmp_path/'audio (converted).mp3';existing.write_bytes(b'keep')
    result=Converter({'format':'mp3'}).run(source)
    assert result['returncode']==0,result
    assert Path(result['path']).name=='audio (converted) 2.mp3' and Path(result['path']).stat().st_size>0
    assert source.read_bytes()==original and existing.read_bytes()==b'keep'
    probe=str(Path(ffmpeg).with_name('ffprobe.exe' if os.name=='nt' else 'ffprobe'))
    measured=subprocess.run([probe,'-v','error','-show_entries','stream=codec_name','-of','csv=p=0',result['path']],capture_output=True,text=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    assert measured.stdout.strip()=='mp3'
