from pathlib import Path
from PySide6.QtCore import Qt,QCoreApplication,QEvent
from PySide6.QtWidgets import QLineEdit,QComboBox,QMessageBox
from app import Window,Store,DEFAULTS
from test_process import app


def finish(w):
    w.advanced.reject();w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_draft_apply_cancel_and_operational_isolation(tmp_path):
    w=Window(Store(tmp_path));w.show();w.open_preferences();app.processEvents()
    before=w.effective_config();theme=w.styleSheet()
    w.parallel_downloads.setCurrentText('4');w.folder.setText(str(tmp_path/'draft'));w.theme.setCurrentText('Light')
    w.default_mode.setCurrentText('Audio');w.default_quality.setCurrentText('720p')
    assert w.config()['parallel_downloads']==4 and w.effective_config()==before
    w.update_queue_summary();assert w.parallel_link.text()=='2 files at once' and w.styleSheet()==theme
    w.advanced.reject()
    assert w.config()==before and Store(tmp_path).data['settings']==dict(DEFAULTS)
    w.open_preferences();w.parallel_downloads.setCurrentText('3');w.theme.setCurrentText('Light');w.default_quality.setCurrentText('720p')
    assert w.save_settings() is True
    assert w.effective_config()['parallel_downloads']==3 and w.quality.currentData()=='720'
    w.parallel_downloads.setCurrentText('1');w.advanced.reject()
    assert w.config()['parallel_downloads']==3 and Store(tmp_path).data['settings']['parallel_downloads']==3
    assert w.styleSheet()!=theme
    finish(w)


def test_settings_categories_fit_and_footer_stays_visible(tmp_path):
    w=Window(Store(tmp_path));w.show();w.open_preferences()
    for theme in ('Dark','Light'):
        w.theme.setCurrentText(theme);w.save_settings()
        for size in ((820,640),(700,520)):
            w.advanced.resize(*size)
            for category in range(w.tabs.count()):
                w.settings_nav.setCurrentRow(category);app.processEvents()
                scroll=w.tabs.currentWidget();viewport=scroll.viewport()
                assert scroll.horizontalScrollBar().maximum()==0,(theme,size,category,scroll.widget().minimumSizeHint(),viewport.size())
                assert scroll.widget().width()<=viewport.width()
                assert w.apply_settings_btn.isVisible() and w.apply_settings_btn.geometry().height()>=30
                for kind in (QLineEdit,QComboBox):
                    for field in scroll.widget().findChildren(kind):
                        if field.isVisible():
                            assert field.width()>=80
                            assert field.mapTo(scroll.widget(),field.rect().topRight()).x()<=scroll.widget().width()
    finish(w)


def test_history_remove_one_duplicate_record_preserves_file_and_other_rows(tmp_path):
    w=Window(Store(tmp_path));file=tmp_path/'video.mp4';file.write_bytes(b'original')
    w.history.extend([dict(title='Same',status='done',path=str(file),time='first'),dict(title='Same',status='done',path=str(file),time='second'),dict(title='Other',status='done',path=str(file))])
    w.refresh_history();assert not w.remove_history_btn.isEnabled()
    w.main_history.topLevelItem(1).setSelected(True);assert w.remove_history_btn.isEnabled()
    w.remove_history_record()
    assert len(w.history)==2 and w.history[0]['time']=='first' and w.history[1]['title']=='Other'
    assert file.read_bytes()==b'original' and len(Store(tmp_path).data['history'])==2
    w.remove_history_record();assert len(w.history)==2
    finish(w)


def test_menu_queue_scope_and_dependencies(tmp_path,monkeypatch):
    w=Window(Store(tmp_path));texts=[a.text() for a in w.app_more.menu().actions() if not a.isSeparator()]
    assert {'Open output folder','Diagnostics','About','Settings…'}.issubset(texts)
    assert w.app_more is w.queue_more
    assert any(t.startswith('Check for updates') for t in texts)
    w.open_diagnostics();assert w.diagnostics.isVisible() and not w.advanced.isVisible();w.diagnostics.close()
    w.update_queue_actions();assert not w.clear_queue_action.isEnabled()
    assert not w.pair_btn.isEnabled() and not w.forget_btn.isEnabled()
    assert not w.lang.isEnabled() and not w.checks['auto_subtitles'].isEnabled()
    w.checks['subtitles'].setChecked(True);assert w.lang.isEnabled() and w.checks['auto_subtitles'].isEnabled()
    job=dict(id='a',title='Video',url='https://vimeo.com/1',status='paused',config=dict(DEFAULTS),error='')
    w.jobs.append(job);w.container.setCurrentIndex(1);messages=[]
    monkeypatch.setattr(QMessageBox,'question',lambda *args:messages.append(args[2]) or QMessageBox.No)
    w.apply_defaults_to_waiting();assert job['config']['container']=='original'
    assert 'Update 1 waiting item' in messages[0] and 'Subtitles' in messages[0]
    finish(w)


def test_browser_pairing_status_refresh_and_speed_shortcut(tmp_path):
    from types import SimpleNamespace
    w=Window(Store(tmp_path));w.show();paired=[]
    w.receiver=SimpleNamespace(paired_origins=lambda:paired,stop=lambda:None)
    w.receiver_check.setChecked(True)
    w.parallel_link.click();app.processEvents()
    assert w.settings_nav.currentRow()==2 and w.pair_btn.isEnabled() and not w.forget_btn.isEnabled()
    paired.append('chrome-extension://example');w.check_clipboard()
    assert w.forget_btn.isEnabled() and '1 browser(s) paired' in w.receiver_status.text()
    w.advanced.reject();w.receiver=None;w.receiver_check.setChecked(False);finish(w)
