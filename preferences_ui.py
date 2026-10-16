"""Categorized preferences with a fixed Apply/Cancel footer."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QFormLayout,
    QCheckBox,QLineEdit,QScrollArea,QListWidget,QStackedWidget,QSizePolicy)


class SettingsForm(QVBoxLayout):
    def addRow(self, *parts):
        for part in parts:
            if isinstance(part,str):
                label=QLabel(part);label.setWordWrap(True);self.addWidget(label)
            elif isinstance(part,QWidget): self.addWidget(part)
            else: self.addLayout(part)


def build_preferences(w, outer):
    cfg=w.store.data['settings']; body=QHBoxLayout(); outer.addLayout(body,1)
    w.settings_nav=QListWidget(); w.settings_nav.setObjectName('settingsNav'); w.settings_nav.setFixedWidth(180); body.addWidget(w.settings_nav)
    w.tabs=QStackedWidget(); body.addWidget(w.tabs,1)
    def page(name, explanation):
        w.settings_nav.addItem(name); content=QWidget(); content.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); layout=QVBoxLayout(content)
        heading=QLabel(name); heading.setObjectName('viewTitle'); layout.addWidget(heading)
        note=QLabel(explanation); note.setWordWrap(True); note.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); note.setObjectName('muted'); layout.addWidget(note)
        form=SettingsForm(); form.setSpacing(10); layout.addLayout(form); layout.addStretch()
        scroll=QScrollArea(); scroll.setFrameShape(QScrollArea.NoFrame); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); scroll.setWidget(content); w.tabs.addWidget(scroll)
        return form
    def text(form,label,key):
        control=QLineEdit(cfg[key]); form.addRow(label,control); return control
    def check(form,key,label):
        control=QCheckBox(label); control.setChecked(bool(cfg[key])); control.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); form.addRow(control); w.checks[key]=control; return control
    w.checks={}
    form=page('General','Changes take effect when you choose Apply. Existing download choices are kept.')
    row=QHBoxLayout(); w.folder=QLineEdit(cfg['outdir']); row.addWidget(w.folder); w.button('Browse…',w.choose_folder,row); form.addRow('Download folder',row)
    w.theme=w.combo(['Dark','Light'],cfg['theme']); form.addRow('Appearance',w.theme)
    check(form,'clipboard','Suggest links from clipboard')
    check(form,'minimize_to_tray','Minimize to the system tray (downloads keep running)')
    form=page('Download defaults','Defaults for newly added items. Each queued item keeps its own format and quality.')
    w.mode=w.combo(['Video','Audio'],'Audio' if cfg['mode']=='audio' else 'Video')
    w.quality=w.combo(['best','2160','1440','1080','720','480','360','240','144','worst'],cfg['quality']); w.label_quality(w.quality)
    w.default_mode=w.combo(['Video','Audio'],w.mode.currentText()); form.addRow('Media',w.default_mode)
    w.default_quality=w.combo(['best','2160','1440','1080','720','480','360','240','144','worst'],cfg['quality']); w.label_quality(w.default_quality); form.addRow('Maximum video resolution',w.default_quality)
    w.container=w.combo(['Original (recommended)','MP4 (remux)'],'MP4 (remux)' if cfg['container']=='mp4' else 'Original (recommended)'); form.addRow('Video container',w.container)
    w.audio=w.combo(['mp3','m4a'],cfg['audio_format']); form.addRow('Audio format',w.audio)
    w.bitrate=w.combo(['64','96','128','160','192','256','320'],cfg['bitrate']); form.addRow('Audio bitrate (kbps)',w.bitrate)
    def media_changed():
        audio=w.default_mode.currentText()=='Audio'
        for control in (w.default_quality,w.container): control.setEnabled(not audio)
        for control in (w.audio,w.bitrate): control.setEnabled(audio)
    w.default_mode.currentIndexChanged.connect(media_changed); media_changed()
    check(form,'skip_existing','Skip completed items with matching settings')
    form=page('Connections and speed','File concurrency and connections per file are separate. Some websites require a single connection.')
    w.parallel_downloads=w.combo(['1','2','3','4'],str(cfg['parallel_downloads'])); form.addRow('Files downloading at once',w.parallel_downloads)
    w.connection_mode=w.combo(['Single connection','Multiple connections'],'Multiple connections' if cfg['connection_mode']=='multiple' else 'Single connection'); form.addRow('Connections for new items',w.connection_mode)
    w.connections=w.combo(['2','4','8','12','16'],str(max(2,cfg['connections']))); form.addRow('Maximum connections per file',w.connections)
    w.aria2=w.combo(['auto','aria2c','off'],cfg['aria2']); w.aria2.hide()
    w.aria2_status=QLabel(); w.aria2_status.setWordWrap(True); w.aria2_status.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); form.addRow(w.aria2_status)
    w.rate=text(form,'Speed limit (bytes/second)','rate_limit'); w.rate.setPlaceholderText('Unlimited, or 2M / 500K')
    w.resume=QCheckBox('Resume partial downloads'); w.resume.setChecked(cfg['resume']); form.addRow(w.resume)
    w.connections.currentTextChanged.connect(w.update_aria2_status); w.connection_mode.currentIndexChanged.connect(w.update_aria2_status); w.update_aria2_status()
    form=page('Subtitles and metadata','Embedding depends on the downloaded container and available subtitle format. Original video codecs are preserved.')
    check(form,'subtitles','Save subtitle files'); check(form,'embed_subtitles','Embed compatible subtitles in video')
    check(form,'auto_subtitles','Include automatically generated subtitles')
    w.lang=text(form,'Subtitle languages (comma-separated)','subtitle_languages')
    check(form,'thumbnail','Embed thumbnail where supported'); check(form,'metadata','Embed title and metadata')
    def subtitles_changed():
        enabled=w.checks['subtitles'].isChecked() or w.checks['embed_subtitles'].isChecked()
        w.checks['auto_subtitles'].setEnabled(enabled); w.lang.setEnabled(enabled)
    for key in ('subtitles','embed_subtitles'): w.checks[key].toggled.connect(subtitles_changed)
    subtitles_changed()
    form=page('Login and network','Use your browser login for videos you can already watch. Browser cookie access may require closing the browser.')
    from browser_login import browser_choices
    w.cookies_browser=w.combo(['none',*browser_choices()],cfg['cookies_browser']); form.addRow('Browser login (optional)',w.cookies_browser)
    from browser_login import SITES,open_sign_in
    w.login_site=w.combo(list(SITES),'YouTube');form.addRow('Account website',w.login_site)
    login_actions=QHBoxLayout()
    w.login_status=QLabel('Sign in on the website in your selected browser, then Apply. The app uses that browser session; it does not store passwords.');w.login_status.setWordWrap(True)
    def sign_in():
        try:
            open_sign_in(w.cookies_browser.currentText(),w.login_site.currentText())
            w.login_status.setText('Browser opened. Complete sign-in there, then Apply here. Session access is checked when you add or download a link; you may need to close the browser first.')
        except (ValueError,OSError) as exc:w.login_status.setText(str(exc))
    w.login_button=w.button('Sign in with browser',sign_in,login_actions)
    w.button('Stop using browser login',lambda:w.cookies_browser.setCurrentText('none'),login_actions);form.addRow(login_actions);form.addRow(w.login_status)
    w.cookies_browser.currentTextChanged.connect(lambda value:w.login_button.setEnabled(value!='none'));w.login_button.setEnabled(cfg['cookies_browser']!='none')
    w.proxy=text(form,'Proxy (optional)','proxy'); w.proxy.setPlaceholderText('http://host:port or socks5://host:port')
    form=page('Browser extension','Receive links from paired browsers on this computer. Apply receiver changes before pairing.')
    w.receiver_check=QCheckBox('Enable browser extension'); w.receiver_check.setChecked(cfg['receiver']); form.addRow(w.receiver_check)
    w.receiver_status=QLabel(); w.receiver_status.setWordWrap(True); w.receiver_status.setSizePolicy(QSizePolicy.Ignored,QSizePolicy.Preferred); form.addRow(w.receiver_status)
    actions=QHBoxLayout(); w.pair_btn=w.button('Pair browser',w.pair_browser,actions); w.forget_btn=w.button('Forget paired browsers',w.forget_browsers,actions); actions.addStretch(); form.addRow(actions)
    w.receiver_check.toggled.connect(w.update_receiver_controls)
    form=page('Playlists','Defaults for new playlists. Numbering adds a filename prefix automatically when you add a playlist. Existing queue items keep their filenames.')
    from playlist_ui import NumberingControls
    w.numbering_controls=NumberingControls(w,cfg['playlist_numbering'],cfg['playlist_digits'])
    form.addRow(w.numbering_controls)
    w.checks['playlist_numbering']=w.numbering_controls.enabled;w.playlist_digits=w.numbering_controls.style
    check(form,'playlist_folders','Create a separate folder for each playlist')
    w.playlist_folder_name=text(form,'Playlist folder name — {playlist} uses the playlist title','playlist_folder_name')
    form=page('Advanced naming','Use filename placeholders such as %(title)s, %(id)s and %(ext)s. Keep the full item ID to support safe parallel downloads.')
    w.template=text(form,'Filename template','template')
    w.settings_nav.currentRowChanged.connect(w.tabs.setCurrentIndex); w.settings_nav.setCurrentRow(0)
    footer=QHBoxLayout(); w.settings_feedback=QLabel(''); w.settings_feedback.setWordWrap(True); footer.addWidget(w.settings_feedback,1)
    w.button('Cancel',w.advanced.reject,footer); w.apply_settings_btn=w.button('Apply',w.save_settings,footer); w.apply_settings_btn.setObjectName('primaryButton'); outer.addLayout(footer)


def restore_controls(w,cfg):
    for key,control in getattr(w,'feature_settings',{}).items(): control.setText(cfg.get(key,''))
    combo_values={'theme':cfg['theme'],'mode':'Audio' if cfg['mode']=='audio' else 'Video',
        'default_mode':'Audio' if cfg['mode']=='audio' else 'Video','container':'MP4 (remux)' if cfg['container']=='mp4' else 'Original (recommended)',
        'audio':cfg['audio_format'],'bitrate':cfg['bitrate'],'parallel_downloads':str(cfg['parallel_downloads']),
        'connection_mode':'Multiple connections' if cfg['connection_mode']=='multiple' else 'Single connection',
        'connections':str(max(2,cfg['connections'])),'aria2':cfg['aria2'],'cookies_browser':cfg['cookies_browser']}
    for name,value in combo_values.items(): getattr(w,name).setCurrentText(value)
    for name in ('quality','default_quality'):
        control=getattr(w,name)
        for i in range(control.count()):
            if control.itemData(i)==cfg['quality']: control.setCurrentIndex(i); break
    for name,key in [('folder','outdir'),('template','template'),('playlist_folder_name','playlist_folder_name'),('lang','subtitle_languages'),('rate','rate_limit'),('proxy','proxy')]: getattr(w,name).setText(cfg[key])
    for key,control in w.checks.items(): control.setChecked(cfg[key])
    w.playlist_digits.setCurrentIndex(0 if cfg['playlist_digits']==2 else 1)
    w.resume.setChecked(cfg['resume']); w.receiver_check.setChecked(cfg['receiver'])
