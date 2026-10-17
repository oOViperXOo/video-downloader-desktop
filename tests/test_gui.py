import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app import Store, Window, DEFAULTS
app = QApplication.instance() or QApplication([])

def test_persistence_and_restart(tmp_path):
    s=Store(tmp_path)
    s.data['settings']['theme']='Light'
    s.data['queue']=[dict(id='1',title='Video',url='https://youtu.be/test',status='downloading',config=dict(s.data['settings']))]
    s.save()
    again=Store(tmp_path)
    assert again.data['settings']['theme']=='Light'
    assert again.data['queue'][0]['status']=='paused'

def test_settings_and_theme(tmp_path):
    w=Window(Store(tmp_path))
    assert w.config()['quality']=='1080'
    w.theme.setCurrentText('Light')
    assert w.config()['theme']=='Light'
    w.show(); app.processEvents()
    assert w.tabs.count()==9 and w.tabs.parent() is not w.centralWidget()
    assert w.settings_nav.findItems('Playlists',Qt.MatchExactly)
    w.close(); w.deleteLater(); app.sendPostedEvents(None, 0); app.processEvents()

def test_selection_and_queue_restore(tmp_path):
    s=Store(tmp_path)
    s.data['queue']=[dict(id='1',title='Demo video',status='paused',percent=30,config=dict(s.data['settings']),url='https://www.youtube.com/watch?v=test',error='')]
    w=Window(s)
    w.queue.topLevelItem(0).setSelected(True)
    assert w.selected_jobs()[0]['id']=='1'
    w.stop_selected('cancelled')
    assert w.jobs[0]['status']=='cancelled'
    w.clear_finished()
    assert not w.jobs
    w.close(); w.deleteLater(); app.sendPostedEvents(None, 0); app.processEvents()

def test_enqueue_video_id_and_none_title(tmp_path):
    from PySide6.QtWidgets import QTreeWidgetItem
    from PySide6.QtCore import Qt
    w=Window(Store(tmp_path)); w.start_next=lambda:None
    w.items=[dict(id='abc123',title=None,url='https://youtu.be/abc123',index=1,duration=5)]
    row=QTreeWidgetItem(['abc123','0:05']);row.setCheckState(0,Qt.Checked);w.pick.addTopLevelItem(row)
    w.enqueue()
    assert len(w.jobs)==1
    assert w.jobs[0]['video_id']=='abc123' and w.jobs[0]['id']!='abc123'
    assert w.jobs[0]['title']=='abc123'
    w.close(); w.deleteLater(); app.processEvents()

def test_corrupt_state_recovers(tmp_path):
    (tmp_path/'state.json').write_text('[1,2]')
    s=Store(tmp_path)
    assert s.data['queue']==[] and (tmp_path/'state.json.bad').exists()

def test_malformed_entries_filtered(tmp_path):
    import json
    (tmp_path/'state.json').write_text(json.dumps(dict(settings={'quality':None},queue=[None,dict(status='queued')],history=[None])))
    s=Store(tmp_path)
    assert not s.data['queue'] and not s.data['history']
    assert s.data['settings']['quality']=='1080'


def test_generic_branding_and_settings_roundtrip(tmp_path):
    import app as appmod
    w=Window(Store(tmp_path))
    assert appmod.APP_NAME=='Orvanta Video Downloader' and w.windowTitle()==appmod.APP_NAME
    assert w.tray.toolTip()=='Orvanta Video Downloader — click to restore'
    assert appmod.DEVELOPER=='oOViperXOo'
    c=w.config()
    assert c['connections']==4 and c['aria2']=='off' and c['resume'] is True and c['cookies_browser']=='none'
    w.connections.setCurrentText('8'); w.aria2.setCurrentText('off'); w.cookies_browser.setCurrentText('firefox'); w.proxy.setText('socks5://10.0.0.5:1080')
    w.save_settings()
    again=Store(tmp_path)
    assert again.data['settings']['connections']==8 and again.data['settings']['aria2']=='off'
    ec=appmod.engine_config(w.config())
    assert ec['connections']==1 and ec['external_downloader']=='off' and ec['cookies_from_browser']=='firefox' and ec['proxy']=='socks5://10.0.0.5:1080'
    import engine; engine.build_options(ec)
    w.close(); w.deleteLater(); app.processEvents()

def test_about_uses_public_github_identity(tmp_path,monkeypatch):
    import app as appmod
    calls=[]
    monkeypatch.setattr(appmod.QMessageBox,'about',lambda parent,title,text:calls.append((title,text)))
    w=Window(Store(tmp_path));w.show_about()
    title,text=calls[0]
    assert title=='About Orvanta Video Downloader'
    assert '>oOViperXOo</a>' in text
    assert 'href="https://github.com/oOViperXOo"' in text
    assert 'href="https://github.com/oOViperXOo/video-downloader-desktop"' in text
    assert 'Ahmed Eladwy' not in text and 'gmail.com' not in text and 'mailto:' not in text
    w.close();w.deleteLater();app.processEvents()


def test_archive_token_independent_of_speed_settings(tmp_path):
    import app as appmod
    w=Window(Store(tmp_path)); a=appmod.engine_config(w.config())['archive_file']
    w.connections.setCurrentText('16'); b=appmod.engine_config(w.config())['archive_file']
    assert a==b
    w.close(); w.deleteLater(); app.processEvents()

def test_events_notice_resume_and_friendly_errors(tmp_path):
    import app as appmod
    w=Window(Store(tmp_path)); j=dict(id='1',title='t',status='downloading',percent=0,config=dict(w.store.data['settings']),url='https://vimeo.com/1',error='')
    w.jobs.append(j); w.active=j
    w.handle_engine_event({'type':'status','status':'resuming','offset':5*1024*1024})
    w.handle_engine_event({'type':'status','status':'notice','message':'aria2c was not found'})
    assert j['resumed'] is True and 'aria2c was not found' in w.log.toPlainText() and 'Continuing from 5.0 MiB' in w.log.toPlainText()
    w.handle_engine_event({'type':'error','message':'ERROR: [vimeo] 1: Video is DRM protected'})
    assert 'DRM' in j['error'] and 'Traceback' not in j['error']
    assert 'login' in appmod.friendly_error('ERROR: Sign in to confirm').lower()
    w.active=None; w.close(); w.deleteLater(); app.processEvents()

def test_clipboard_and_site_hint_for_multiple_sites(tmp_path):
    w=Window(Store(tmp_path)); w.show()
    for url,name in [('https://vimeo.com/76979871','Vimeo'),('https://www.tiktok.com/@a/video/1','TikTok'),('https://x.com/a/status/2','X / Twitter')]:
        w.url.clear(); w.clip_last=''
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(url); w.check_clipboard()
        assert name in w.clip_notice.text() and w.url.text()==url
    QApplication.clipboard().setText('http://127.0.0.1/x'); w.url.clear(); w.clip_last=''; w.check_clipboard()
    assert w.url.text()==''
    w.show_site_hint('https://www.instagram.com/reel/abc/'); assert 'logged-in browser' in w.site_note.text() and 'DRM' in w.site_note.text()
    w.close(); w.deleteLater(); app.processEvents()

def test_pause_all_marks_queued(tmp_path):
    w=Window(Store(tmp_path)); cfg=dict(w.store.data['settings'])
    w.jobs.append(dict(id='1',title='a',status='queued',url='https://vimeo.com/1',config=cfg)); w.pause_all()
    assert w.jobs[0]['status']=='paused'
    w.close(); w.deleteLater(); app.processEvents()


def test_browser_extension_pairing_and_job_flow(tmp_path, monkeypatch):
    import app as appmod, http.client, json, time
    from pathlib import Path
    appmod.DEFAULTS['receiver']=True
    try:
        w=Window(Store(tmp_path))
    finally:
        appmod.DEFAULTS['receiver']=False
    assert w.receiver and w.receiver.port
    w.inspect=lambda: setattr(w,'inspected',True)      # do not spawn yt-dlp here
    origin='chrome-extension://abcdefghijklmnopabcdefghijklmnop'
    def call(path, body, token=None, host=None):
        c=http.client.HTTPConnection('127.0.0.1',w.receiver.port,timeout=5)
        h={'Host':host or f'127.0.0.1:{w.receiver.port}','Origin':origin,'Content-Type':'application/json'}
        if token: h['Authorization']='Bearer '+token
        c.request('POST',path,json.dumps(body),h); r=c.getresponse(); return r.status, json.loads(r.read() or b'{}')
    st,_=call('/v1/download',{'v':1,'url':'https://vimeo.com/1'}); assert st==401       # unpaired
    code=w.receiver.new_pairing_code(); st,b=call('/v1/pair',{'code':code}); assert st==200
    tok=b['token']
    st,_=call('/v1/download',{'v':1,'url':'http://127.0.0.1/x'},tok); assert st==422     # private target rejected
    st,_=call('/v1/download',{'v':1,'url':'https://vimeo.com/1'},tok,host='evil.com'); assert st==403
    st,_=call('/v1/download',{'v':1,'url':'https://vimeo.com/76979871','page_url':'https://vimeo.com/x','headers':{'User-Agent':'UA/1','Cookie':'a=b; c=d'}},tok); assert st==202
    for _ in range(100):
        app.processEvents()
        if w.url.text(): break
        time.sleep(0.02)
    assert w.url.text()=='https://vimeo.com/76979871' and getattr(w,'inspected',False)
    ctx=w.ctx_for(w.url.text()); assert ctx['user_agent']=='UA/1' and ctx['referer']=='https://vimeo.com/x'
    cf=Path(ctx['cookies_file']); assert cf.is_file() and 'a\tb' in cf.read_text()
    import os
    if os.name=='posix': assert (cf.stat().st_mode & 0o777)==0o600
    assert not w.jobs                                           # never auto-queued
    w.items=[dict(id='1',title='t',url=w.url.text(),index=1,duration=1)]
    from PySide6.QtWidgets import QTreeWidgetItem
    from PySide6.QtCore import Qt
    row=QTreeWidgetItem(['t','0:01']); row.setCheckState(0,Qt.Checked); w.pick.addTopLevelItem(row); w.start_next=lambda:None
    w.enqueue()
    cfgj=w.jobs[0]['config']; assert cfgj['cookies_file']==str(cf) and cfgj['referer']
    ec=appmod.engine_config(cfgj); import engine; cmd=engine.build_command(ec,w.jobs[0]['url'])
    assert '--cookies' in cmd and '--referer' in cmd and 'a=b' not in ' '.join(cmd)       # cookie values never on the command line
    assert appmod.engine_config(dict(w.config(),quality=cfgj['quality']))['archive_file']==appmod.engine_config(cfgj)['archive_file']
    assert w.store.data['settings'].get('cookies_file','')==''  # browser context is not saved as a global setting
    w.jobs[0]['status']='done'; w.clear_finished(); assert not cf.exists()
    w.close(); w.deleteLater(); app.processEvents()
    assert w.receiver is None

def test_receiver_off_by_default_in_tests_and_port_busy(tmp_path):
    w=Window(Store(tmp_path)); assert w.receiver is None and 'off' in w.receiver_status.text()
    w.close(); w.deleteLater(); app.processEvents()

def test_inline_choices_persist_and_remove(tmp_path):
    w=Window(Store(tmp_path)); cfg=dict(w.store.data['settings'])
    job=dict(id='a',title='Sample',status='paused',percent=0,url='https://vimeo.com/1',config=cfg,error='')
    w.jobs.append(job);w.refresh_queue(); row=w.queue.topLevelItem(0)
    w.row_widgets[job['id']].mode.setCurrentText('Audio');app.processEvents()
    w.row_widgets[job['id']].quality.setCurrentText('128 kbps')
    assert job['config']['mode']=='audio' and job['config']['bitrate']=='128'
    assert Store(tmp_path).data['queue'][0]['config']['bitrate']=='128'
    w.remove_job(job);app.processEvents();assert not w.jobs and w.queue.topLevelItemCount()==0
    w.close();w.deleteLater();app.processEvents()

def test_safari_settings_migrate(tmp_path,monkeypatch):
    import json
    import app as appmod
    from types import SimpleNamespace
    monkeypatch.setattr(appmod,'sys',SimpleNamespace(**{**vars(appmod.sys),'platform':'win32'}))
    cfg=dict(DEFAULTS,cookies_browser='safari')
    (tmp_path/'state.json').write_text(json.dumps(dict(settings=cfg,queue=[dict(id='a',title='t',url='https://vimeo.com/1',status='paused',config=cfg)],history=[])))
    s=Store(tmp_path);assert s.data['settings']['cookies_browser']=='none' and s.data['queue'][0]['config']['cookies_browser']=='none'

def test_bulk_start_respects_playlist_checks(tmp_path):
    from PySide6.QtCore import Qt
    w=Window(Store(tmp_path));w.start_next=lambda:None
    for i in range(2): w.jobs.append(dict(id=str(i),title='item',url='https://vimeo.com/1',status='ready',config=dict(DEFAULTS),percent=0,error=''))
    w.refresh_queue();w.queue.topLevelItem(1).setCheckState(0,Qt.Unchecked)
    w.start_all();assert w.jobs[0]['status']=='queued' and w.jobs[1]['status']=='ready'
    assert Store(tmp_path).data['queue'][1]['included'] is False
    w.close();w.deleteLater();app.processEvents()

def test_mode_roundtrip_retains_valid_choices(tmp_path):
    w=Window(Store(tmp_path));j=dict(formats=[{'height':1080,'vcodec':'avc1'}],id='a',title='t',url='https://vimeo.com/1',status='ready',config=dict(DEFAULTS),percent=0,error='');w.jobs.append(j);w.refresh_queue()
    for mode in ('Audio','Video','Audio','Video'):
        w.row_widgets[j['id']].mode.setCurrentText(mode);app.processEvents()
        q=w.row_widgets[j['id']].quality
        if mode=='Video': assert q.currentText()=='1080p' and j['config']['quality']=='1080'
        else: assert q.currentText()=='192 kbps' and j['config']['bitrate']=='192'
    w.close();w.deleteLater();app.processEvents()

def test_queue_feedback_and_loading_controls(tmp_path):
    w=Window(Store(tmp_path)); w.show(); app.processEvents()
    assert not w.start_all_btn.isEnabled() and 'No items' in w.queue_summary.text()
    w.set_inspection_busy(True)
    assert w.url.isReadOnly() and not w.paste_btn.isEnabled() and w.inspect_cancel.isEnabled()
    w.set_inspection_busy(False)
    j=dict(id='a',title='Failed video',url='https://vimeo.com/1',status='error',config=dict(DEFAULTS),percent=0,error='Login required')
    w.jobs.append(j);w.refresh_queue();app.processEvents()
    assert w.start_all_btn.isEnabled() and 'Login required' in w.job_error.text() and w.job_error.isVisible()
    w.queue.topLevelItem(0).setCheckState(0,__import__('PySide6.QtCore',fromlist=['Qt']).Qt.Unchecked)
    assert not w.start_all_btn.isEnabled()
    w.jobs.clear();w.refresh_queue();assert w.job_error.isHidden()
    w.close();w.deleteLater();app.processEvents()

def test_safari_profile_settings_migrate_on_windows(tmp_path, monkeypatch):
    import app as appmod, json
    from types import SimpleNamespace
    monkeypatch.setattr(appmod,'sys',SimpleNamespace(**{**vars(appmod.sys),'platform':'win32'}))
    for browser in ('Safari', ' safari:Default ', 'safari+keychain:profile'):
        cfg=dict(DEFAULTS,cookies_browser=browser)
        (tmp_path/'state.json').write_text(json.dumps(dict(settings=cfg,queue=[dict(id='a',title='t',url='https://vimeo.com/1',status='paused',config=cfg)],history=[])))
        s=Store(tmp_path)
        assert s.data['settings']['cookies_browser']=='none' and s.data['queue'][0]['config']['cookies_browser']=='none'
        assert appmod.engine_config(cfg)['cookies_from_browser'] is None
    assert 'Safari' in appmod.friendly_error('unsupported platform: win32')

def test_original_container_migration_and_remux_choice(tmp_path,monkeypatch):
    import json
    import app as appmod
    legacy=dict(DEFAULTS); legacy.pop('container',None); legacy['aria2']='auto'
    (tmp_path/'state.json').write_text(json.dumps(dict(settings=legacy,queue=[dict(id='old',title='Old',url='https://vimeo.com/1',status='ready',config=legacy)],history=[])),encoding='utf-8')
    store=Store(tmp_path)
    assert store.data['settings']['container']=='original'
    assert store.data['queue'][0]['config']['container']=='original'
    assert store.data['queue'][0]['config']['aria2']=='off'
    assert appmod.engine_config(store.data['settings'])['merge_format']=='native'
    from PySide6.QtWidgets import QMessageBox
    monkeypatch.setattr(QMessageBox,'question',lambda *args:QMessageBox.Yes)
    w=Window(store); w.container.setCurrentIndex(1); w.apply_defaults_to_waiting()
    assert w.jobs[0]['config']['container']=='mp4'
    assert appmod.engine_config(w.config())['merge_format']=='mp4'
    w.close(); w.deleteLater(); app.processEvents()


def test_row_overflow_and_unknown_size_progress(tmp_path):
    from PySide6.QtWidgets import QPushButton, QToolButton
    w=Window(Store(tmp_path))
    job=dict(id='1',title='Stream',url='https://vimeo.com/1',status='downloading',percent=0,config=dict(DEFAULTS))
    w.jobs.append(job); w.active=job; w.refresh_queue()
    actions=w.row_widgets[job['id']].actions
    assert len(actions.findChildren(QPushButton))==1
    overflow=actions.findChild(QToolButton)
    assert not overflow.isCheckable()  # opens options separately; the row never expands
    overflow.click();app.processEvents()
    assert w.row_widgets[job['id']].settings_dialog.isVisible()
    assert not w.row_widgets[job['id']].options.isVisible()
    w.handle_engine_event(dict(type='progress',downloaded=5*1024*1024,total=None,speed=1024,eta=None))
    w.flush_progress_updates()
    progress=w.row_widgets[job['id']].progress
    assert progress.maximum()==0 and '5.0 MiB' in progress.toolTip()
    w.handle_engine_event(dict(type='progress',downloaded=5*1024*1024,total=10*1024*1024,percent=50))
    w.flush_progress_updates()
    assert progress.maximum()==100 and progress.value()==50
    w.active=None; w.close(); w.deleteLater(); app.processEvents()
