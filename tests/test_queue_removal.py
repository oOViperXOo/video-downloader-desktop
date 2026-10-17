from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from app import Window, Store
from test_process import app
from test_ui_performance import job, finish


def test_ctrl_shift_selection_and_delete_keep_files(tmp_path):
    w=Window(Store(tmp_path));w.show()
    w.jobs.extend(job(i) for i in range(4));w.refresh_queue();app.processEvents()
    rows=[w.row_widgets[str(i)] for i in range(4)]
    QTest.mouseClick(rows[0],Qt.LeftButton)
    QTest.mouseClick(rows[2],Qt.LeftButton,Qt.ControlModifier)
    assert {j['id'] for j in w.selected_jobs()}=={'0','2'}
    QTest.mouseClick(rows[3],Qt.LeftButton,Qt.ShiftModifier)
    assert {'2','3'} <= {j['id'] for j in w.selected_jobs()}
    w.queue.clearSelection()
    w._queue_items['0'].setSelected(True);w._queue_items['2'].setSelected(True)
    downloaded=tmp_path/'download.mp4';downloaded.write_bytes(b'keep')
    w.jobs[0]['path']=str(downloaded)
    w.queue.setFocus();QTest.keyClick(w.queue,Qt.Key_Delete);app.processEvents()
    assert [j['id'] for j in w.jobs]==['1','3']
    assert downloaded.read_bytes()==b'keep'
    finish(w)


def test_remove_mixed_history_and_queue(tmp_path):
    w=Window(Store(tmp_path));w.jobs.extend(job(i) for i in range(2))
    record=dict(title='Old download',status='done',path=str(tmp_path/'old.mp4'))
    w.history.append(record);w.refresh_queue()
    w._queue_items['0'].setSelected(True)
    w._queue_items['history:'+str(id(record))].setSelected(True)
    menu=w.create_row_menu(w.queue.visualItemRect(w._queue_items['0']).center())
    next(action for action in menu.actions() if action.text()=='Remove from list').trigger();app.processEvents()
    assert [j['id'] for j in w.jobs]==['1'] and not w.history
    finish(w)


def test_click_visible_labels_then_delete_without_forcing_focus(tmp_path):
    w=Window(Store(tmp_path));w.show();w.jobs.extend(job(i) for i in range(4));w.refresh_queue();app.processEvents()
    w.url.setFocus()
    QTest.mouseClick(w.row_widgets['0'].title,Qt.LeftButton)
    QTest.mouseClick(w.row_widgets['2'].detail,Qt.LeftButton,Qt.ControlModifier)
    assert {j['id'] for j in w.selected_jobs()}=={'0','2'}
    assert w.queue.hasFocus()
    assert w.row_widgets['0'].property('downloadSelected') is True
    assert w.row_widgets['2'].cells[0].property('downloadSelected') is True
    QTest.keyClick(app.focusWidget(),Qt.Key_Delete);app.processEvents()
    assert [j['id'] for j in w.jobs]==['1','3']
    finish(w)


def test_inline_quality_popup_keeps_its_mouse_events(tmp_path):
    w=Window(Store(tmp_path));w.show();w.jobs.append(dict(job(0),formats=[{'height':1080,'vcodec':'avc1'},{'height':720,'vcodec':'avc1'}]));w.refresh_queue();app.processEvents()
    combo=w.row_widgets['0'].quality
    w.activateWindow();QTest.qWait(100);combo.setFocus();combo.showPopup();QTest.qWait(100)
    index=combo.model().index(combo.findData('720'),0)
    QTest.mouseClick(combo.view().viewport(),Qt.LeftButton,pos=combo.view().visualRect(index).center())
    app.processEvents()
    assert w.jobs[0]['config']['quality']=='720'
    finish(w)


def test_removing_active_row_waits_for_worker_stop(tmp_path):
    from unittest.mock import Mock
    w=Window(Store(tmp_path));record=job(0);record['status']='downloading'
    w.jobs.append(record);worker=Mock();w.workers['0']=worker;w.refresh_queue()
    w._queue_items['0'].setSelected(True);w.remove_selected_rows()
    worker.stop.assert_called_once_with('cancelled')
    assert record['remove_after_stop'] and record in w.jobs
    w.workers.clear();record['status']='cancelled';finish(w)
