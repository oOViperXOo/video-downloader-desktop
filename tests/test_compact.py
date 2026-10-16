from PySide6.QtCore import Qt, QCoreApplication, QEvent
from app import Window, Store, DEFAULTS
from test_process import app


def finish(window):
    window.close();window.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_compact_navigation_and_inline_add(tmp_path):
    window=Window(Store(tmp_path));window.show();app.processEvents()
    assert window.empty_state.isVisible() and not window.queue.isVisible()
    assert not window.add_dialog.isVisible()
    window.open_add_dialog();app.processEvents()
    assert not window.add_dialog.isVisible() and window.url.isVisible()
    window.container.setCurrentIndex(1);window.connection_mode.setCurrentIndex(1)
    calls=[];window.inspect=lambda:calls.append(window.config())
    window.inspect_btn.click()
    assert calls[0]['container']=='mp4' and calls[0]['connection_mode']=='multiple'
    window.history_nav.click();assert window.main_stack.currentIndex()==1
    window.downloads_nav.click();assert window.main_stack.currentIndex()==0
    finish(window)


def test_compact_filters_and_expanded_options(tmp_path):
    window=Window(Store(tmp_path));window.show()
    for i,status in enumerate(['paused','queued','done']):
        window.jobs.append(dict(id=str(i),title='Video '+str(i),url='https://vimeo.com/'+str(i+1),status=status,percent=25,config=dict(DEFAULTS),error=''))
    window.refresh_queue();app.processEvents()
    window.set_queue_filter('active')
    assert not window.queue.topLevelItem(0).isHidden()
    assert window.queue.topLevelItem(1).isHidden() and window.queue.topLevelItem(2).isHidden()
    window.set_queue_filter('queued')
    assert not window.queue.topLevelItem(1).isHidden() and window.queue.topLevelItem(0).isHidden()
    window.set_queue_filter('all');window.toggle_job_details(window.jobs[0]);app.processEvents()
    row=window.row_widgets['0'];assert row.settings_dialog.isVisible()
    row.container.setCurrentIndex(1);app.processEvents()
    assert window.jobs[0]['config']['container']=='mp4'
    row=window.row_widgets['0'];row.include.setChecked(False)
    assert window.jobs[0]['included'] is False
    window.toggle_job_details(window.jobs[0]);app.processEvents()
    assert not window.row_widgets['0'].settings_dialog.isVisible()
    finish(window)


def test_preferences_refresh_footer_and_visible_history_selection(tmp_path,monkeypatch):
    import app as appmodule
    from pathlib import Path
    window=Window(Store(tmp_path));window.show()
    window.parallel_downloads.setCurrentText('3');window.save_settings()
    assert window.parallel_link.text()=='3 files at once'
    first=tmp_path/'first';second=tmp_path/'second';first.mkdir();second.mkdir()
    window.history.extend([dict(title='First',status='done',path=str(first)),dict(title='Second',status='done',path=str(second))]);window.refresh_history()
    opened=[];monkeypatch.setattr(appmodule.QDesktopServices,'openUrl',lambda url:opened.append(url.toLocalFile()))
    window.show_main_page(1);window.main_history.topLevelItem(0).setSelected(True)
    window.open_history();assert Path(opened[-1])==second
    window.main_history.clearSelection()
    window.hist.topLevelItem(1).setSelected(True)
    window.open_history();assert Path(opened[-1])==first
    finish(window)


def test_audio_choices_are_edited_in_queue(tmp_path):
    window=Window(Store(tmp_path));window.show()
    job=dict(id='audio',title='Audio',url='https://vimeo.com/1',status='ready',config=dict(DEFAULTS,mode='audio'),percent=0,error='')
    window.jobs.append(job);window.refresh_queue();app.processEvents()
    row=window.row_widgets['audio'];assert row.quality.isVisible() and 'kbps' in row.quality.currentText()
    row.quality.setCurrentText('256 kbps');app.processEvents();assert job['config']['bitrate']=='256'
    row=window.row_widgets['audio'];assert row.container.isEnabled()
    row.container.setCurrentText('M4A');app.processEvents();assert job['config']['audio_format']=='m4a'
    finish(window)


def test_row_focus_resume_and_truthful_completion(tmp_path):
    window=Window(Store(tmp_path)); window.show()
    job=dict(id='focus',title='Video',url='https://example.com/video',status='paused',percent=25,config=dict(DEFAULTS),error='')
    window.jobs.append(job); window.expanded_jobs.add('focus'); window.refresh_queue(); app.processEvents()
    row=window.row_widgets['focus']; assert row.primary.text()=='Resume'
    window.activateWindow(); row.quality.setFocus(); app.processEvents()
    row.quality.setCurrentText('720p'); app.processEvents()
    row=window.row_widgets['focus']; assert row.quality.hasFocus() and job['config']['quality']=='720'
    assert row.sizeHint().height()>=row.layout().minimumSize().height()
    job['status']='done'; window.refresh_queue(); row=window.row_widgets['focus']
    assert row.primary.text()=='Open folder' and row.timing.text()=='Requested: 720p'
    finish(window)


def test_inspection_queues_single_and_multiple_without_prompts(tmp_path,monkeypatch):
    import codecs,json
    class Process:
        def readAllStandardOutput(self): return b''
        def deleteLater(self): pass
    window=Window(Store(tmp_path)); prompted=[]; queued=[]
    monkeypatch.setattr(window,'confirm_playlist',lambda title:prompted.append(title))
    monkeypatch.setattr(window,'enqueue',lambda:queued.append(True))
    for count in (1,3):
        window.inspector=Process(); window.inspection_cancelled=False; window.inspect_decoder=codecs.getincrementaldecoder('utf-8')()
        window.inspect_output=json.dumps(dict(title='Playlist',items=[dict(id=str(i),title=str(i)) for i in range(count)]))
        window.inspected(0)
    assert queued==[True,True] and prompted==[]
    finish(window)


def test_playlist_confirmation_honors_selection_and_cancel(tmp_path,monkeypatch):
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication,QDialog,QPushButton,QTreeWidgetItem,QLabel
    window=Window(Store(tmp_path)); queued=[]; monkeypatch.setattr(window,'enqueue',lambda:queued.append([i for i in range(3) if window.pick.topLevelItem(i).checkState(0)==Qt.Checked]))
    window.items=[dict(id=str(i)) for i in range(3)]
    for i in range(3):
        row=QTreeWidgetItem([str(i)]); row.setCheckState(0,Qt.Checked); window.pick.addTopLevelItem(row)
    def choose():
        dialog=QApplication.activeModalWidget(); assert isinstance(dialog,QDialog)
        window.pick.topLevelItem(1).setCheckState(0,Qt.Unchecked)
        assert any('2 of 3 items selected' in label.text() for label in dialog.findChildren(QLabel))
        next(b for b in dialog.findChildren(QPushButton) if b.text()=='Add selected').click()
    QTimer.singleShot(0,choose); window.confirm_playlist('Playlist'); assert queued==[[0,2]]
    QTimer.singleShot(0,lambda:QApplication.activeModalWidget().reject()); window.confirm_playlist('Playlist'); assert queued==[[0,2]]
    finish(window)


def test_expanded_row_controls_keep_readable_rendered_height(tmp_path):
    window=Window(Store(tmp_path)); window.show()
    window.jobs.append(dict(id='sizing',title='Readable expanded download',url='https://example.com/video',status='queued',percent=0,config=dict(DEFAULTS),error=''))
    window.expanded_jobs.add('sizing'); window.refresh_queue()
    for theme in ('Dark','Light'):
        window.theme.setCurrentText(theme)
        window.apply_theme()
        for width,height in ((1080,780),(820,580)):
            window.resize(width,height)
            for _ in range(3): app.processEvents()
            row=window.row_widgets['sizing']
            assert row.height()>=row.layout().minimumSize().height()
            assert row.height()==44 and window.queue.columnCount()==5 and not window.queue.isHeaderHidden()
            assert row.quality.isVisible() and not row.container.isVisible()
            window.toggle_job_details(window.jobs[0]);app.processEvents()
            assert row.settings_dialog.isVisible() and row.mode.isVisible() and row.connections.isVisible()
            window.toggle_job_details(window.jobs[0]);app.processEvents()
            assert not window.grab().isNull()
    finish(window)
