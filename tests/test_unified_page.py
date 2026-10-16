from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QPushButton
from app import Window,Store,DEFAULTS
from test_process import app


def test_one_toolbar_and_unified_completed_records(tmp_path):
    w=Window(Store(tmp_path));w.show()
    current=dict(id='current',title='Current',url='https://example.com/current',status='done',path=str(tmp_path/'current.mp4'),percent=100,config=dict(DEFAULTS))
    w.jobs.append(current)
    w.history.extend([dict(title='Current',url=current['url'],status='done',path=current['path']),dict(title='Earlier',url='https://example.com/earlier',status='done',path=str(tmp_path/'earlier.mp4'))])
    w.refresh_history();app.processEvents()
    assert w.queue.topLevelItemCount()==2 and w.queue.isVisible()
    assert not w.downloads_nav.isVisible() and not w.history_nav.isVisible()
    assert not w.folder_link.isVisible() and not w.queue_summary.isVisible() and not w.total_speed.isVisible()
    assert w.app_more is w.queue_more and w.app_more.parentWidget() is w.url.parentWidget()
    assert any(action.text()=='Settings…' for action in w.app_more.menu().actions())
    assert [w.queue.headerItem().text(i) for i in range(5)]==['File','Status / progress','Speed / ETA','Quality','Actions']
    old=w.queue.topLevelItem(1);assert old.text(0)=='Earlier' and old.text(1)=='Completed'
    actions=w.queue.itemWidget(old,4)
    next(button for button in actions.findChildren(QPushButton) if button.text()=='×').click();app.processEvents()
    assert len(w.history)==1 and w.queue.topLevelItemCount()==1
    w.clear_finished();app.processEvents()
    assert not w.jobs and not w.history and w.empty_state.isVisible()
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_options_are_compact_and_advanced_choices_are_collapsed(tmp_path):
    w=Window(Store(tmp_path));w.show()
    job=dict(id='ready',title='Choose options',url='https://example.com/video',status='ready',percent=0,config=dict(DEFAULTS))
    w.jobs.append(job);w.refresh_queue();row=w.row_widgets['ready'];row.open_options();app.processEvents()
    assert row.mode.isVisible() and row.container.isVisible() and row.connections.isVisible()
    for theme in ('Light','Dark'):
        w.theme.setCurrentText(theme);w.apply_theme();app.processEvents()
        background=row.settings_dialog.grab().toImage().pixelColor(10,10)
        assert background.alpha()==255
        assert (background.lightness()>200) if theme=='Light' else (background.lightness()<60)
    assert not row.options.isVisible() and not row.convert_copy.isVisible()
    assert row.quality.isVisible() and not row.settings_dialog.isAncestorOf(row.quality)
    row.advanced_toggle.click();app.processEvents();assert row.options.isVisible() and row.convert_copy.isVisible()
    row.advanced_toggle.click();app.processEvents();assert not row.options.isVisible()
    row.settings_dialog.hide();w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_smaller_startup_and_table_fits_window_resize(tmp_path):
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QHeaderView
    w=Window(Store(tmp_path));w.show();app.processEvents()
    assert w.width()==960 and w.height()==520
    for i in range(20):
        w.jobs.append(dict(id=str(i),title='Video '+str(i),url='https://example.com/'+str(i),status='done',percent=100,config=dict(DEFAULTS)))
    w.refresh_queue()
    for width,height in ((760,360),(960,520),(1280,720),(820,400)):
        w.resize(width,height);QTest.qWait(30)
        assert sum(w.queue.columnWidth(i) for i in range(5))==w.queue.viewport().width()
        assert w.queue.horizontalScrollBar().maximum()==0
        assert w.queue.columnWidth(0)>=180
        row=w.row_widgets['0']
        assert row.actions.rect().contains(row.more.geometry())
        assert row.actions.rect().contains(row.primary.geometry())
    assert w.queue.header().sectionResizeMode(0)==QHeaderView.Interactive
    w.queue.setColumnWidth(0,w.queue.columnWidth(0)+40)
    w.resize(1100,600);QTest.qWait(30)
    assert sum(w.queue.columnWidth(i) for i in range(5))==w.queue.viewport().width()
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
