from PySide6.QtCore import QCoreApplication,QEvent,Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QSystemTrayIcon,QMessageBox
from app import Window,Store
from test_process import app


def finish(w):
    w.inspector=None;w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_minimize_restore_and_background_timers(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));w.show();app.processEvents()
    monkeypatch.setattr(QSystemTrayIcon,'isSystemTrayAvailable',lambda:True)
    monkeypatch.setattr(w.tray,'isVisible',lambda:True)
    notices=[];monkeypatch.setattr(w.tray,'showMessage',lambda *args:notices.append(args))
    w.showMinimized();app.processEvents()
    assert not w.isVisible() and not w.closing and w.feature_timer.isActive() and notices
    w.tray.messageClicked.emit();app.processEvents()
    assert w.isVisible() and not w.isMinimized()
    w.showMaximized();app.processEvents();w.showMinimized();app.processEvents();w.restore_from_tray();app.processEvents()
    assert w.isMaximized() and len(notices)==1
    w.hide();w.tray.activated.emit(QSystemTrayIcon.Trigger);app.processEvents();assert w.isVisible()
    finish(w)


def test_tray_unavailable_and_preference_cancel_apply(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));w.show();app.processEvents()
    monkeypatch.setattr(QSystemTrayIcon,'isSystemTrayAvailable',lambda:False)
    w.showMinimized();app.processEvents();assert w.isVisible()
    w.showNormal();w.open_preferences();w.checks['minimize_to_tray'].setChecked(False);w.advanced.reject()
    assert w.effective_config()['minimize_to_tray'] is True
    w.open_preferences();w.checks['minimize_to_tray'].setChecked(False);assert w.save_settings();w.advanced.reject()
    monkeypatch.setattr(QSystemTrayIcon,'isSystemTrayAvailable',lambda:True)
    monkeypatch.setattr(w.tray,'isVisible',lambda:True)
    w.showMinimized();app.processEvents();assert w.isVisible()
    assert Store(tmp_path).data['settings']['minimize_to_tray'] is False
    finish(w)


def test_tray_menu_and_declined_quit_keeps_running(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));w.show();app.processEvents()
    assert [a.text() for a in w.tray.contextMenu().actions() if not a.isSeparator()]==['Show window','Open download folder','Pause all downloads','Quit']
    w.inspector=object();monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.No)
    w.quit_from_tray();assert w.isVisible() and not w.closing and w.feature_timer.isActive()
    w.inspector=None;finish(w)


def test_quit_from_tray_closes_cleanly(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));w.show();w.hide();exits=[]
    monkeypatch.setattr(app,'quit',lambda:exits.append(True))
    w.quit_from_tray()
    assert exits==[True] and w.closing and not w.feature_timer.isActive() and not w.tray.isVisible()
    finish(w)
