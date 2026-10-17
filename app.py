#!/usr/bin/env python3
"""Native desktop entry point. Engine mode is safe for PyInstaller onefile."""
import sys
if any(flag in sys.argv for flag in ('--engine', '--ytdlp', '--smoke-test')):
    from windows_stdio import restore_worker_streams
    restore_worker_streams()
if '--ytdlp' in sys.argv:
    sys.argv.remove('--ytdlp')
    import yt_dlp
    yt_dlp.main()
    raise SystemExit
if '--engine' in sys.argv:
    sys.argv.remove('--engine')
    import engine
    raise SystemExit(engine.main())
import json
import os
import uuid
import codecs
import receiver
from download_safety import apply_waiting_defaults, set_connection_mode, destinations_conflict
from pathlib import Path
from PySide6.QtCore import Qt, QObject, Signal, QSize, QProcess, QTimer, QUrl, QStandardPaths, QEvent, QSignalBlocker
from PySide6.QtGui import QDesktopServices, QFont, QGuiApplication, QIcon, QPalette, QColor
from PySide6.QtWidgets import (QApplication, QSizePolicy, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QLineEdit, QComboBox, QCheckBox, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QFileDialog, QMessageBox, QFormLayout,
    QGroupBox, QProgressBar, QTextEdit, QAbstractItemView, QScrollArea, QDialog, QStyledItemDelegate, QMenu, QToolButton)

APP_NAME = 'Orvanta Video Downloader'
DEVELOPER = 'oOViperXOo'
DEVELOPER_URL = 'https://github.com/oOViperXOo'
REPOSITORY_URL = 'https://github.com/oOViperXOo/video-downloader-desktop'

def asset_path(name):
    return Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent)) / name
DEFAULTS = dict(theme='Dark', minimize_to_tray=True, outdir=str(Path.home() / 'Downloads' / 'Video Downloader'),
    parallel_downloads=2, connection_mode='single',
    mode='video', container='original', quality='1080', audio_format='mp3', bitrate='192',
    subtitles=False, embed_subtitles=False, subtitle_languages='en.*,ar.*',
    auto_subtitles=False, thumbnail=False, metadata=True, rate_limit='',
    template='%(title).150B [%(id)s].%(ext)s', playlist_folders=False, playlist_folder_name='{playlist}', playlist_numbering=False, playlist_digits=2, clipboard=True, skip_existing=True,
    connections=4, aria2='off', resume=True, proxy='', cookies_browser='none',
    receiver=True, referer='', user_agent='', cookies_file='', format_id='',
    max_retries='3', convert_mp4=False, conversion_quality='balanced', start_at='', quiet_start='', quiet_end='', update_manifest_url='')

SITE_NOTE = ('Works with most sites yt-dlp supports (YouTube, Vimeo, Facebook, Instagram, TikTok, X/Twitter, Dailymotion, Twitch, Reddit, SoundCloud and more). '
    'Private, age-restricted or members-only videos may need you to be logged in: pick your browser under Settings > Login and network. '
    'DRM-protected streams (e.g. Netflix, Disney+, most paid streaming) are not supported and never bypassed. '
    'Only download content you own or have the right to download.')

SITE_HINTS = {'Instagram': 'Instagram often needs a logged-in browser (Settings > Login and network).',
    'Facebook': 'Facebook private or group videos need a logged-in browser (Settings > Login and network).',
    'X / Twitter': 'X/Twitter may need a logged-in browser for some posts.',
    'TikTok': 'TikTok can rate-limit; if a link fails, retry later or log in via browser cookies.',
    'Twitch': 'Twitch: VODs and clips work; live streams and subscriber-only VODs may not.'}

def supported_cookie_browser(value):
    browser = str(value or 'none').strip()
    if sys.platform != 'darwin' and browser.lower().split(':',1)[0].split('+',1)[0] == 'safari': return 'none'
    return browser

def friendly_error(text):
    """Turn raw yt-dlp output into a short, readable message (no tracebacks)."""
    t = (text or '').strip()
    low = t.lower()
    if 'watch later' in low or 'liked videos' in low:return t[:400]
    if 'playlist' in low and any(word in low for word in ('does not exist','not found','resolve url')):
        return 'YouTube could not open this playlist. It may be private, deleted, or account-only. For Watch Later or a private list, choose your logged-in browser in Settings > Login and network, Apply, then Add again.'
    if 'unsupported platform' in low and ('win32' in low or 'safari' in low): return 'Safari login cookies are unavailable on this platform. Choose Chrome, Edge or Firefox in Settings > Login and network, then retry.'
    if 'drm' in low: return 'This video is DRM-protected and cannot be downloaded.'
    if 'unsupported url' in low: return 'This site or page is not supported by yt-dlp.'
    if any(k in low for k in ('login required','log in','logged-in','logged in','sign in','private video','members-only','cookies')): return 'This video needs a login. Choose your browser in Settings > Login and network, then retry. ('+t[:160]+')'
    if 'traceback' in low: return 'Unexpected error. Details are in the download messages.'
    return t[:400]

def engine_config(cfg):
    import hashlib
    from pathlib import PureWindowsPath
    template=cfg['template']
    if not cfg['outdir']: raise ValueError('Choose an output folder.')
    if cfg.get('playlist_folders'):
        from playlist_paths import playlist_directory
        playlist_directory(cfg['outdir'],cfg.get('playlist_folder_name','{playlist}'),'Playlist')
    import re
    if not template or '/' in template or '\\' in template or PureWindowsPath(template).drive or re.match(r'^[A-Za-z]+:',template) or template in ('.','..'):
        raise ValueError('Use a filename template without folders or absolute paths.')
    if '%(ext)s' not in template: raise ValueError('Include %(ext)s in the filename template.')
    import shutil
    if not getattr(sys,'frozen',False) and (not shutil.which('ffmpeg') or not shutil.which('ffprobe')):
        raise ValueError('FFmpeg and ffprobe are required. Install them, add them to PATH and reopen the app.')
    quality=cfg['quality']
    options=dict(output_dir=str(Path(cfg['outdir']).expanduser()),output_template=template,mode=cfg['mode'],
        max_height=int(quality) if quality.isdigit() else None,prefer_worst=quality=='worst',
        merge_format='mp4' if cfg.get('container')=='mp4' else 'native',audio_format=cfg['audio_format'],audio_bitrate=cfg['bitrate'],
        subtitles=cfg['subtitles'],sub_langs=[s.strip() for s in cfg['subtitle_languages'].split(',') if s.strip()],
        auto_subs=cfg['auto_subtitles'],embed_subs=cfg['embed_subtitles'],embed_thumbnail=cfg['thumbnail'],
        embed_metadata=cfg['metadata'],rate_limit=cfg['rate_limit'] or None,no_playlist=True,skip_existing=True,
        referer=cfg.get('referer') or None,user_agent=cfg.get('user_agent') or None,
        cookies_file=cfg['cookies_file'] if cfg.get('cookies_file') and Path(cfg['cookies_file']).is_file() else None,
        proxy=cfg['proxy'].strip() or None,cookies_from_browser=None if supported_cookie_browser(cfg['cookies_browser'])=='none' else supported_cookie_browser(cfg['cookies_browser']))
    if cfg.get('format_id'): options['format_id']=cfg['format_id']
    per_job={k:options.pop(k) for k in ('referer','user_agent','cookies_file')}   # browser context must not change the archive token
    if cfg['skip_existing']:
        token=hashlib.sha256(json.dumps(options,sort_keys=True).encode()).hexdigest()[:16]
        options['archive_file']=str(Path(options['output_dir'])/('.completed-'+token+'.txt'))
    # Download-speed settings are added after the archive token so changing them never invalidates 'already completed' records.
    multi=cfg.get('connection_mode','single')=='multiple'
    options.update({k:v for k,v in per_job.items() if v},connections=max(2,int(cfg['connections'])) if multi else 1,
                   external_downloader='auto' if multi else 'off',resume=bool(cfg['resume']))
    return options

def stop_process_tree(process, force=False):
    import psutil
    pid=process.processId()
    if not pid: return
    try:
        root=psutil.Process(pid); children=root.children(recursive=True)
        for child in reversed(children):
            try: child.kill() if force or sys.platform=='win32' else child.terminate()
            except psutil.Error: pass
        if force or sys.platform=='win32': process.kill()
        else: process.terminate()
    except psutil.Error:
        process.kill() if force else process.terminate()

def default_state_directory():
    """A setup-created marker opts the frozen app into folder-local data."""
    if getattr(sys, 'frozen', False):
        folder = Path(sys.executable).resolve().parent
        if (folder / 'portable.ini').is_file():
            return folder / 'Data'
    return Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))


class Store:
    def __init__(self, root=None):
        self.root = Path(root) if root is not None else default_state_directory()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'state.json'
        self.data = {'settings': dict(DEFAULTS), 'queue': [], 'history': []}
        try:
            old = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(old,dict): raise ValueError('Invalid state root')
            settings=old.get('settings',{})
            if not isinstance(settings,dict): raise ValueError('Invalid settings')
            for key,default in DEFAULTS.items():
                value=settings.get(key,default)
                if isinstance(value,type(default)): self.data['settings'][key]=value
            if self.data['settings']['aria2']=='auto': self.data['settings']['aria2']='off'
            queue=old.get('queue',[]); history=old.get('history',[])
            if not isinstance(queue,list) or not isinstance(history,list): raise ValueError('Invalid state lists')
            for j in queue:
                if not isinstance(j,dict) or not all(isinstance(j.get(k),str) for k in ('id','title','url','status')) or not isinstance(j.get('config'),dict): continue
                config=dict(self.data['settings']); config.update({k:v for k,v in j['config'].items() if k in DEFAULTS and isinstance(v,type(DEFAULTS[k]))})
                config['container']=j['config'].get('container','original')
                if config['aria2']=='auto': config['aria2']='off'
                j['config']=config
                try: j['percent']=float(j.get('percent',0))
                except (ValueError,TypeError): j['percent']=0
                self.data['queue'].append(j)
            if self.data['settings']['cookies_browser']=='safari': self.data['settings']['cookies_browser']='none'
            for job in self.data['queue']:
                if job['config']['cookies_browser']=='safari': job['config']['cookies_browser']='none'
            self.data['settings']['cookies_browser']=supported_cookie_browser(self.data['settings']['cookies_browser'])
            for job in self.data['queue']:
                job['config']['cookies_browser']=supported_cookie_browser(job['config']['cookies_browser'])
            self.data['history']=[h for h in history if isinstance(h,dict) and all(isinstance(h.get(k),str) for k in ('title','status','path'))]
        except FileNotFoundError: pass
        except (OSError,ValueError,TypeError):
            try: self.path.replace(self.root/'state.json.bad')
            except OSError: pass
        for job in self.data['queue']:
            if job.get('status') in ('downloading', 'processing', 'queued'):
                job['status'] = 'paused'
                job['error'] = 'Restored after restart. Start / resume continues from the partial file.'
    def save(self):
        tmp = self.path.with_suffix('.tmp')
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding='utf-8')
        tmp.replace(self.path)

class BrowserBridge(QObject):
    job = Signal(dict)   # emitted from the receiver's server thread; Qt queues it to the GUI thread

class DownloadRowDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        hint=super().sizeHint(option,index); hint.setHeight(54); return hint

class Window(QMainWindow):
    RECEIVER_PORT = receiver.DEFAULT_PORT
    def __init__(self, store=None):
        super().__init__()
        self.store = store or Store()
        self.jobs = self.store.data['queue']; self.history = self.store.data['history']
        self.closing = False; self.active = None; self.stop_reason = None; self.output = ''; self.inspect_output = ''
        self.inspector = None; self.process = None; self.clip_last = ''; self.items = []
        self._link_user_edited=False;self._clipboard_batch_links=[]
        self.workers = {}; self.expanded_jobs=set(); self.row_widgets={}; self.queue_filter="all"
        self._dirty_progress=set();self._progress_timer=QTimer(self);self._progress_timer.setSingleShot(True);self._progress_timer.setInterval(100);self._progress_timer.timeout.connect(self.flush_progress_updates)
        self.setWindowTitle(APP_NAME); self.setWindowIcon(QIcon(str(asset_path('assets/app-icon.ico')))); self.resize(960,520); self.setMinimumSize(760,360)
        host = QWidget(); self.setCentralWidget(host); outer = QVBoxLayout(host)
        outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        self._settings_snapshot=None
        self.advanced = QDialog(self); self.advanced.setWindowTitle('Settings'); self.advanced.resize(820,640); self.advanced.setMinimumSize(700,520); self.advanced.setModal(True)
        self.preferences_layout=QVBoxLayout(self.advanced)
        self.make_settings(); self.advanced.finished.connect(self.cancel_preferences)
        from compact_ui import build_chrome
        build_chrome(self,outer)
        self.make_download(); self.make_queue(); self.make_menu()
        from features_ui import install_features
        install_features(self)
        self.statusBar().hide()
        self.refresh_history(); self.apply_theme()
        self.browser_ctx = {}; self.receiver = None; self.start_receiver(); self.purge_orphan_cookies()
        self.timer = QTimer(self); self.timer.timeout.connect(self.check_clipboard); self.timer.start(1600)
        QApplication.clipboard().dataChanged.connect(self.capture_copied_links)
        QTimer.singleShot(0,self.check_clipboard)
    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() or event.mimeData().hasText(): event.acceptProposedAction()
    def dropEvent(self,event):
        from features_ui import batch_dialog
        mime=event.mimeData(); text='\n'.join(url.toString() for url in mime.urls()) if mime.hasUrls() else mime.text()
        batch_dialog(self,text); event.acceptProposedAction()
    def button(self, text, callback, layout):
        b = QPushButton(text); b.clicked.connect(callback); layout.addWidget(b); return b
    def make_menu(self):
        menu=self.queue_more.menu()
        menu.addSeparator()
        menu.addAction('Settings…',lambda:self.open_preferences())
        menu.addAction('Open output folder', self.open_output_folder)
        menu.addAction('Diagnostics', self.open_diagnostics)
        menu.addSeparator()
        menu.addAction('About', self.show_about)
        self.app_more.setMenu(menu); self.app_more.setPopupMode(QToolButton.InstantPopup)
    def show_about(self):
        from release_updates import APP_VERSION
        QMessageBox.about(self, 'About '+APP_NAME,
            f'<b>{APP_NAME}</b><br>Version {APP_VERSION}'
            f'<p>Developed by <a href="{DEVELOPER_URL}">{DEVELOPER}</a></p>'
            f'<p><a href="{REPOSITORY_URL}">GitHub repository</a></p>'
            '<p>Powered by yt-dlp and FFmpeg.</p>')
    def open_advanced(self):
        if self._settings_snapshot is None:
            self._settings_snapshot=self.config()
            self.default_mode.setCurrentText(self.mode.currentText())
            self.default_quality.setCurrentIndex(self.quality.currentIndex())
        self.settings_feedback.clear()
        self.update_receiver_controls()
        self.advanced.show(); self.advanced.raise_()
    def show_main_page(self,index):
        self.main_stack.setCurrentIndex(index)
        self.downloads_nav.setChecked(index==0); self.history_nav.setChecked(index==1)
    def open_add_dialog(self):
        self.show_main_page(0);self.url.setFocus();self.check_clipboard()
    def begin_compact_inspection(self):
        if self.inspector:return
        if self._clipboard_batch_links:
            self.batch_links=list(self._clipboard_batch_links);self._clipboard_batch_links=[]
        self.inspect()
    def make_download(self):
        from compact_ui import make_composer
        make_composer(self)
    def make_queue(self):
        from compact_ui import CompactItemDelegate,ResponsiveDownloadTable
        lay=self.download_layout
        toolbar=self.link_entry_layout;self.filter_buttons={}
        for key,label in [('all','All files'),('active','Active'),('queued','Queued')]:
            button=QPushButton(label,self); button.hide(); button.setObjectName('filterButton'); button.setCheckable(True); button.setChecked(key=='all'); button.clicked.connect(lambda checked=False,k=key:self.set_queue_filter(k)); self.filter_buttons[key]=button
        self.start_all_btn=self.button('Start all',self.start_all,toolbar); self.start_all_btn.setObjectName('quietButton')
        self.pause_all_btn=self.button('Pause all',self.pause_all,toolbar); self.pause_all_btn.setObjectName('quietButton')
        self.queue_more=self.app_more;toolbar.addWidget(self.queue_more)
        queue_menu=QMenu(self.queue_more)
        self.clear_queue_action=queue_menu.addAction('Clear completed and cancelled items',self.clear_finished)
        self.clear_queue_action.setToolTip('Removes queue entries only. Downloaded files and partial files are kept.')
        queue_menu.aboutToShow.connect(self.update_queue_actions)
        self.queue_more.setMenu(queue_menu); self.queue_more.setPopupMode(QToolButton.InstantPopup)
        self.queue=ResponsiveDownloadTable();self.queue.setObjectName('downloadTable')
        self.queue.setItemDelegate(CompactItemDelegate(self.queue))
        self.queue.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.queue.removeRequested.connect(self.remove_selected_rows)
        self.queue.itemDoubleClicked.connect(self.open_downloaded_item)
        self.queue.setContextMenuPolicy(Qt.CustomContextMenu)
        def show_row_menu(position):
            menu=self.create_row_menu(position)
            menu.exec(self.queue.viewport().mapToGlobal(position))
        self.queue.customContextMenuRequested.connect(show_row_menu)
        self.queue.setSelectionMode(QAbstractItemView.ExtendedSelection); self.queue.itemSelectionChanged.connect(self.show_job_error); self.queue.itemChanged.connect(self.queue_check_changed); lay.addWidget(self.queue,1)
        self.empty_state=QLabel('Your next download starts here.\nAdd a video or playlist link to get started.'); self.empty_state.setObjectName('emptyState'); self.empty_state.setAlignment(Qt.AlignCenter); lay.addWidget(self.empty_state,1)
        self.progress=QProgressBar(); self.progress.hide()
        self.queue_summary=QLabel(); self.queue_summary.setObjectName('muted')
        self.clear_finished_btn=QPushButton(self); self.clear_finished_btn.hide()
        self.job_error=QLabel(); self.job_error.setWordWrap(True); self.job_error.setTextFormat(Qt.PlainText); self.job_error.setTextInteractionFlags(Qt.TextSelectableByMouse); self.job_error.setObjectName('errorMessage'); self.job_error.hide(); lay.addWidget(self.job_error)
        footer=QWidget(); footer.setObjectName('downloadFooter'); row=QHBoxLayout(footer); row.setContentsMargins(0,12,0,0)
        self.folder_link=self.button('Open download folder',self.open_output_folder,row); self.folder_link.setObjectName('quietButton'); row.addStretch()
        row.addWidget(self.queue_summary);row.addStretch()
        self.parallel_link=self.button('',lambda:self.open_preferences(2),row); self.parallel_link.setObjectName('quietButton'); row.addStretch()
        self.total_speed=QLabel('0.00 MiB/s'); self.total_speed.setObjectName('muted'); row.addWidget(self.total_speed);footer.setParent(self);footer.hide()
        self.diagnostics=QDialog(self); self.diagnostics.setWindowTitle('Diagnostics'); self.diagnostics.resize(760,500)
        diagnostics_layout=QVBoxLayout(self.diagnostics)
        diagnostics_layout.addWidget(QLabel('Download messages and technical details for troubleshooting.'))
        self.log=QTextEdit(); self.log.setReadOnly(True); diagnostics_layout.addWidget(self.log)
        self.button('Close',self.diagnostics.close,diagnostics_layout)
    def open_preferences(self, category=None):
        if category is not None: self.settings_nav.setCurrentRow(category)
        self.open_advanced()
    def set_queue_filter(self,value):
        self.queue_filter=value
        for key,button in self.filter_buttons.items(): button.setChecked(key==value)
        self.apply_queue_filter()
    def apply_queue_filter(self):
        visible=0
        jobs_by_id={job['id']:job for job in self.jobs}
        for index in range(self.queue.topLevelItemCount()):
            item=self.queue.topLevelItem(index); job=jobs_by_id.get(item.data(0,Qt.UserRole)) or item.data(0,Qt.UserRole+3)
            show=job is not None and (self.queue_filter=='all' or (self.queue_filter=='active' and job['status'] in ('downloading','processing','paused')) or (self.queue_filter=='queued' and job['status'] in ('queued','ready')))
            item.setHidden(not show); visible+=int(show)
        from features_ui import filter_queue
        visible=filter_queue(self)
        self.queue.setVisible(bool(visible)); self.empty_state.setVisible(not visible)
        self.empty_state.setText('Your next download starts here.\nAdd a video or playlist link to get started.' if not self.jobs else 'No '+('active downloads.' if self.queue_filter=='active' else 'files in this view.'))
    def update_queue_summary(self):
        waiting=sum(j['status'] in ('paused','ready','cancelled','error') and j.get('included',True) and not self.is_running(j) for j in self.jobs)
        queued=sum(j['status']=='queued' and j.get('included',True) for j in self.jobs)
        running=sum(j['status'] in ('downloading','processing') for j in self.jobs)
        failed=sum(j['status']=='error' for j in self.jobs)
        self.queue_caption.setText(f'{running} downloading · {queued} queued' if running or queued else (f'{waiting} ready to start' if waiting else 'Your downloads, in one place.'))
        self.queue_summary.setText(f'{len(self.jobs)} files'+(f' · {failed} need attention' if failed else '') if self.jobs else 'No items yet')
        self.start_all_btn.setEnabled(bool(waiting)); self.start_all_btn.setVisible(bool(waiting))
        self.pause_all_btn.setEnabled(bool(running or queued)); self.pause_all_btn.setVisible(bool(running or queued))
        self.clear_finished_btn.setEnabled(any(j['status'] in ('done','skipped','cancelled') for j in self.jobs))
        cfg=self.effective_config()
        self.folder_link.setText('Save to: '+(Path(cfg['outdir']).name or 'Downloads')); self.folder_link.setToolTip(cfg['outdir'])
        self.parallel_link.setText(str(cfg['parallel_downloads'])+' files at once')
        speed=sum(j.get('speed_bytes',0) for j in self.jobs if j['status']=='downloading')
        self.total_speed.setText(f'{speed/1024/1024:.2f} MiB/s')
    def set_inspection_busy(self, busy):
        self.inspect_btn.setEnabled(not busy); self.inspect_btn.setText('Adding…' if busy else 'Add')
        self.inspect_cancel.setVisible(busy); self.inspect_cancel.setEnabled(busy); self.url.setReadOnly(busy); self.paste_btn.setEnabled(not busy)
    def open_output_folder(self):
        path=Path(self.effective_config()['outdir']).expanduser(); path.mkdir(parents=True,exist_ok=True); QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    def start_all(self):
        for job in self.jobs:
            if job.get('included',True) and not self.is_running(job) and job['status'] in ('paused','ready','cancelled','error'):
                job.update(status='queued',error='')
        self.store.save(); self.refresh_queue(); self.start_next()
    def apply_defaults_to_waiting(self):
        cfg=self.effective_config()
        count=sum(j['status'] in ('paused','ready','queued','error','cancelled') and not self.is_running(j) for j in self.jobs)
        if not count: return
        message=(f'Update {count} waiting item(s), including paused, failed and cancelled items?\n\n'
                 'Changes: media, quality, video/audio format, bitrate, output folder and connection mode/count.\n'
                 'Subtitles, metadata, login/network, speed limit and resume choices stay as they are.\n\n'
                 'Switching multiple connections to single may restart transfer progress. Existing sparse partial files are kept as backups.')
        if QMessageBox.question(self,APP_NAME,message)!=QMessageBox.Yes: return
        for job in self.jobs:
            if job['status'] in ('paused','ready','queued','error','cancelled') and not self.is_running(job):
                try:
                    if apply_waiting_defaults(job,cfg):
                        self.append_log('Saved multi-connection partial data separately before applying single-connection defaults.')
                except OSError as exc:
                    job.update(status='error',error='Could not preserve partial download: '+str(exc))
                    self.append_log(job['error'])
        self.store.data['settings']=cfg; self.store.save(); self.refresh_queue()
    def update_queue_actions(self):
        self.clear_queue_action.setEnabled(any(j['status'] in ('done','skipped','cancelled') for j in self.jobs+self.history))
    def update_job_choice(self, job, key, value):
        if self.is_running(job) or job['status'] in ('done','skipped'): return
        if key in ('mode','quality','container'):
            job['config']['format_id']='';job['estimated_bytes']=None;job['selected_format']={}
        if key=='mode' and value=='audio':job['config']['convert_mp4']=False
        if key=='quality' and job['config']['mode']=='audio':
            job['config']['bitrate']=value.split()[0]
        else: job['config'][key]=value.rstrip('p').lower() if key=='quality' else value
        field={'mode':'mode','quality':'quality','container':'container','audio_format':'container'}.get(key)
        if field:self._pending_row_focus=(job['id'],field)
        self.store.save()
        row=self.row_widgets.get(job['id'])
        if key=='mode':QTimer.singleShot(0,self.refresh_queue)
        elif row:
            if key in ('quality','container') and row._options_built:
                blocker=QSignalBlocker(row.format);row.format.setCurrentIndex(0);del blocker
            row.update_state();self._pending_row_focus=None
    def set_job_format(self,job,selector):
        if self.is_running(job) or job['status'] in ('done','skipped'):return
        job['config']['format_id']=selector or ''
        selected=next((f for f in job.get('formats',[]) if f.get('selector')==selector),{})
        job['selected_format']=selected;job['estimated_bytes']=selected.get('estimated_size')
        if selected.get('height'):job['config']['quality']=str(selected['height'])
        self.store.save()
        row=self.row_widgets.get(job['id'])
        if row:
            blocker=QSignalBlocker(row.quality)
            index=row.quality.findData(job['config']['quality'])
            if index>=0:row.quality.setCurrentIndex(index)
            del blocker
            row.update_state()
    def row_action(self, job, action):
        for i in range(self.queue.topLevelItemCount()):
            row=self.queue.topLevelItem(i); row.setSelected(row.data(0,Qt.UserRole)==job['id'])
        if action=='open': QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(job.get('path') or job['config']['outdir']).parent if job.get('path') else Path(job['config']['outdir']))))
        elif action=='pause': self.stop_selected('paused')
        elif action=='cancel': self.stop_selected('cancelled')
        else: self.resume_selected()
    def combo(self, values, value):
        from compact_ui import VisibleComboBox
        w = VisibleComboBox(); w.addItems(values); w.setCurrentText(str(value)); return w
    def label_quality(self,combo):
        for i in range(combo.count()):
            value=combo.itemText(i); combo.setItemData(i,value); combo.setItemText(i,value+'p' if value.isdigit() else value.capitalize())
    def make_settings(self):
        from preferences_ui import build_preferences
        build_preferences(self,self.preferences_layout)
    def effective_config(self):
        return dict(self._settings_snapshot) if self._settings_snapshot is not None else self.config()
    def cancel_preferences(self, *args):
        if self._settings_snapshot is not None:
            from preferences_ui import restore_controls
            restore_controls(self,self._settings_snapshot)
            self._settings_snapshot=None
            self.apply_theme(); self.update_queue_summary(); self.update_receiver_controls()
    def update_receiver_controls(self, *args):
        active=bool(getattr(self,'receiver',None)) and self.receiver_check.isChecked()
        self.pair_btn.setEnabled(active)
        self.forget_btn.setEnabled(active and bool(self.receiver.paired_origins()))
        if hasattr(self,'receiver') and self.receiver_check.isChecked()!=bool(self.receiver):
            self.receiver_status.setText('Choose Apply to update browser integration.')
        elif active:
            self.receiver_status.setText(f'Ready for paired browsers. {len(self.receiver.paired_origins())} browser(s) paired.')
    def open_diagnostics(self):
        self.diagnostics.show(); self.diagnostics.raise_()
    # ---- browser extension receiver ----
    def start_receiver(self):
        if self.receiver:
            self.receiver.stop(); self.receiver = None
        if not self.effective_config()['receiver']:
            self.receiver_status.setText('Browser integration is off.'); self.update_receiver_controls(); return
        self.bridge = getattr(self, 'bridge', None) or BrowserBridge()
        if not getattr(self, 'bridge_connected', False): self.bridge.job.connect(self.on_browser_job); self.bridge_connected = True
        r = receiver.Receiver(self.bridge.job.emit, str(self.store.root / 'receiver.json'), port=self.RECEIVER_PORT, app_version='3')
        try: r.start()
        except OSError as exc:
            self.receiver_status.setText('Browser integration could not start. Open Diagnostics for details.'); self.append_log(str(exc)); self.update_receiver_controls(); return
        self.receiver = r
        self.receiver_status.setText(f'Ready for paired browsers. {len(r.paired_origins())} browser(s) paired.'); self.update_receiver_controls()
    def pair_browser(self):
        if not self.receiver: self.error('Turn on the browser extension option and save settings first.'); return
        QMessageBox.information(self, APP_NAME, f'Enter this code in the extension Options page (valid 2 minutes, single use):\n\n{self.receiver.new_pairing_code()}')
        self.receiver_status.setText('Ready for browser pairing.'); self.update_receiver_controls()
    def forget_browsers(self):
        if self.receiver and QMessageBox.question(self, APP_NAME, 'Forget all paired browsers? They must pair again.')==QMessageBox.Yes:
            self.receiver.revoke_all(); self.receiver_status.setText('All paired browsers forgotten.'); self.update_receiver_controls()
    def on_browser_job(self, job):
        # Never starts a download by itself: it fills in the link and loads its details; the user still chooses and queues.
        url = job.get('url') or ''
        try:
            from engine import validate_url
            validate_url(url, resolve=True)
        except ValueError as exc:
            self.append_log('Rejected a link from the browser: '+str(exc)); return
        h = job.get('headers') or {}
        ctx = dict(url=url, referer=h.get('Referer') or job.get('page_url') or '', user_agent=h.get('User-Agent') or '', cookies_file='')
        if h.get('Cookie'):
            d = self.store.root / 'cookies'; d.mkdir(exist_ok=True)
            try:
                path = d / (job['id'] + '.txt'); receiver.cookie_header_to_netscape(h['Cookie'], url, str(path)); ctx['cookies_file'] = str(path)
            except OSError: pass
        self.browser_ctx = ctx
        self.url.setText(url); self.statusBar().showMessage('Link received from your browser. Review it and add to the queue.')
        self.activateWindow(); self.raise_()
        if not self.inspector: self.inspect()
    def ctx_for(self, url):
        c = self.browser_ctx
        return c if c and c.get('url') == url else {}
    def purge_orphan_cookies(self):
        d = self.store.root / 'cookies'
        if not d.is_dir(): return
        used = {j['config'].get('cookies_file') for j in self.jobs}
        for f in d.glob('*.txt'):
            if str(f) not in used:
                try: f.unlink()
                except OSError: pass
    def drop_cookie_file(self, job):
        p = job['config'].get('cookies_file') if isinstance(job.get('config'), dict) else ''
        if p and any(other is not job and other['status'] not in ('done','skipped') and other.get('config',{}).get('cookies_file')==p for other in self.jobs): return
        if p and Path(p).parent.name == 'cookies':
            try: Path(p).unlink()
            except OSError: pass
    def update_aria2_status(self, *args):
        import engine
        n=int(self.connections.currentText()); multi=self.connection_mode.currentIndex()==1; path=engine.find_aria2c()
        self.connections.setEnabled(multi)
        if not multi: msg='Single connection per file. Best compatibility with websites.'
        elif path: msg=f'Multiple connections available: up to {n} per file. Website support varies.'
        else: msg=f'Multiple connections unavailable. Segmented streams may use up to {n} parallel fragments; other downloads use one connection.'
        self.aria2_status.setText(msg)
    def config(self):
        mode=self.default_mode if self._settings_snapshot is not None else self.mode
        quality=self.default_quality if self._settings_snapshot is not None else self.quality
        result=dict(parallel_downloads=int(self.parallel_downloads.currentText()), connection_mode='multiple' if self.connection_mode.currentIndex()==1 else 'single', container='mp4' if self.container.currentIndex()==1 else 'original', receiver=self.receiver_check.isChecked(), connections=int(self.connections.currentText()), aria2=self.aria2.currentText(), resume=self.resume.isChecked(), proxy=self.proxy.text().strip(), cookies_browser=self.cookies_browser.currentText(), theme=self.theme.currentText(), outdir=self.folder.text().strip(), mode='video' if mode.currentIndex()==0 else 'audio', quality=quality.currentData() or quality.currentText(), audio_format=self.audio.currentText(), bitrate=self.bitrate.currentText(), subtitle_languages=self.lang.text().strip(), rate_limit=self.rate.text().strip(), template=self.template.text().strip(), **{k:w.isChecked() for k,w in self.checks.items()})
        result.update({k:v.text().strip() for k,v in getattr(self,'feature_settings',{}).items()})
        result['playlist_folder_name']=self.playlist_folder_name.text().strip()
        result['playlist_digits']=self.playlist_digits.currentData()
        return result
    def save_settings(self):
        cfg = self.config()
        try:
            from features_ui import validate_feature_settings
            validate_feature_settings(cfg)
            import engine
            engine.build_options(engine_config(cfg))
            self.mode.setCurrentText('Audio' if cfg['mode']=='audio' else 'Video')
            self.quality.setCurrentIndex(self.default_quality.currentIndex() if self._settings_snapshot is not None else self.quality.currentIndex())
            self.store.data['settings'] = cfg; self.store.save()
            if self._settings_snapshot is not None: self._settings_snapshot=dict(cfg)
            self.apply_theme(); self.settings_feedback.setText('Settings applied.')
            self.statusBar().showMessage('Settings saved.'); self.start_receiver(); self.update_queue_summary(); self.start_next()
            return True
        except Exception as exc: self.error(str(exc))
        return False
    def choose_folder(self):
        p = QFileDialog.getExistingDirectory(self, 'Choose output folder', self.folder.text())
        if p: self.folder.setText(p); self.update_queue_summary()
    def apply_theme(self, *args):
        dark=self.effective_config()['theme']=='Dark'
        bg,panel,ink,muted,line,accent,tint,onaccent=('#11161e','#191f29','#e9edf4','#9aa8bb','#2a3544','#63dbbf','#203b37','#102820') if dark else ('#f7f9fb','#ffffff','#19232f','#5c6979','#dfe6ed','#08796d','#e1f4ed','#ffffff')
        palette=QPalette(self.palette())
        for role,color in ((QPalette.Window,bg),(QPalette.Base,panel),(QPalette.Button,panel),(QPalette.Text,ink),(QPalette.WindowText,ink),(QPalette.ButtonText,ink),(QPalette.Highlight,tint),(QPalette.HighlightedText,ink)):
            palette.setColor(role,QColor(color))
        palette.setColor(QPalette.Disabled,QPalette.Text,QColor(muted));palette.setColor(QPalette.Disabled,QPalette.ButtonText,QColor(muted))
        self.setPalette(palette)
        self.setStyleSheet(f'''QWidget {{background:{bg};color:{ink};font-family:"Segoe UI";font-size:13px;}}
            QLabel {{background:transparent;}} QLabel#viewTitle {{font-size:25px;font-weight:600;}} QLabel#brandName {{font-size:12px;font-weight:600;letter-spacing:1px;}}
            QLabel#muted,QLabel#transferDetail,QLabel#emptyState {{color:{muted};font-size:11px;}} QLabel#fileTitle {{font-size:13px;font-weight:600;}} QLabel#emptyState {{font-size:15px;}}
            QWidget#appChrome {{background:{panel};border-bottom:1px solid {line};}} QWidget#appChrome QLabel {{background:transparent;}}
            QFrame#downloadRow {{background:{bg};border:0;border-bottom:1px solid {line};}}
            QFrame#itemOptions {{background:{panel};border:1px solid {line};border-radius:10px;}} QLabel#fileBadge {{background:{panel};border-radius:9px;color:{muted};font-size:9px;}}
            QPushButton,QToolButton {{background:{panel};border:1px solid {line};border-radius:8px;padding:8px 12px;}} QPushButton:hover,QToolButton:hover {{background:{tint};}}
            QPushButton:disabled,QComboBox:disabled {{color:{muted};}} QPushButton#primaryButton {{background:{accent};color:{onaccent};border:0;font-weight:600;padding:10px 17px;}}
            QPushButton#quietButton,QPushButton#navButton,QPushButton#filterButton,QPushButton#rowAction,QToolButton#rowMore {{border:0;background:transparent;}}
            QPushButton#navButton:checked {{background:{tint};color:{accent};}} QPushButton#filterButton:checked {{background:{panel};}}
            QPushButton#quietButton {{color:{muted};font-size:12px;}} QPushButton#rowAction {{font-size:12px;padding:5px 6px;}} QToolButton#rowMore {{font-size:17px;padding:3px 9px;}}
            QPushButton#quietButton:hover,QPushButton#rowAction:hover,QToolButton#rowMore:hover {{background:{panel};color:{ink};}}
            QLineEdit,QComboBox,QTextEdit {{background:{panel};border:1px solid {line};border-radius:7px;padding:8px;}} QComboBox QAbstractItemView {{background:{panel};color:{ink};}}
            QComboBox {{background-color:{panel};color:{ink};selection-background-color:{tint};selection-color:{ink};}}
            QComboBox QAbstractItemView,QComboBox QAbstractItemView::item {{background-color:{panel};color:{ink};selection-background-color:{tint};selection-color:{ink};}}
            QComboBox QAbstractItemView::item:selected {{background-color:{tint};color:{ink};}}
            QTreeWidget {{border:0;background:{bg};outline:0;}} QTreeWidget::item {{border:0;padding:0;}} QTreeWidget::item:selected {{background:{tint};}}
            QTreeWidget#downloadTable {{border:1px solid {line};}} QTreeWidget#downloadTable::item {{border-right:1px solid {line};border-bottom:1px solid {line};}}
            QTreeWidget#downloadTable QFrame#downloadRow {{border:0;border-right:1px solid {line};border-bottom:1px solid {line};}}
            QTreeWidget#downloadTable QWidget[downloadSelected="true"],QTreeWidget#downloadTable QFrame#downloadRow[downloadSelected="true"] {{background:{tint};}}
            QTreeWidget#downloadTable QComboBox {{padding:4px 6px;min-height:24px;}}
            QScrollBar:vertical {{background:{bg};width:8px;border:0;margin:0;}} QScrollBar::handle:vertical {{background:{line};border-radius:4px;min-height:30px;}} QScrollBar::handle:vertical:hover {{background:{muted};}} QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;border:0;}} QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {{background:transparent;}} QComboBox::drop-down {{border:0;width:22px;}}
            QHeaderView::section {{background:{panel};color:{muted};padding:9px;border:0;}} QProgressBar {{background:{line};border:0;border-radius:2px;min-height:5px;max-height:5px;}} QProgressBar::chunk {{background:{accent};border-radius:2px;}}
            QGroupBox {{border:1px solid {line};border-radius:10px;margin-top:12px;padding:14px;}} QGroupBox::title {{subcontrol-origin:margin;left:12px;}}
            QTabBar::tab {{padding:10px 18px;}} QTabBar::tab:selected {{color:{accent};}} QWidget#downloadFooter {{border-top:1px solid {line};}}
            QListWidget#settingsNav {{background:{panel};border:0;border-radius:8px;outline:0;}}
            QListWidget#settingsNav::item {{padding:9px 7px;margin:2px 3px;border-radius:6px;font-size:12px;}}
            QListWidget#settingsNav::item:selected {{background:{tint};color:{accent};}} QListWidget#settingsNav::item:hover {{background:{tint};}}
            QLabel#errorMessage,QLabel[failed="true"] {{color:{'#ff9e9e' if dark else '#ad2424'};}} QMenu {{background:{panel};border:1px solid {line};padding:5px;}} QMenu::item {{padding:7px 15px;}} QMenu::item:selected {{background:{tint};}}
        ''')
    def error(self, msg):
        QMessageBox.warning(self, APP_NAME, msg)
    def command(self, process, args):
        if getattr(sys,'frozen',False): process.start(sys.executable, ['--engine']+args)
        else: process.start(sys.executable, [str(Path(__file__).resolve()), '--engine']+args)
    def inspect(self):
        if self.inspector: return
        self.inspection_cancelled=False
        from engine import validate_url
        try: validate_url(self.url.text().strip(), resolve=True)
        except ValueError as exc: self.error(str(exc)); return
        self.show_site_hint(self.url.text().strip())
        self.set_inspection_busy(True); self.play_title.show();self.play_title.setText('Reading video / playlist... Large playlists may take a while. You can stop loading.'); self.inspect_output = ''; self.inspect_err = ''; self.inspect_decoder=codecs.getincrementaldecoder('utf-8')('replace')
        self.inspector = QProcess(self); p = self.inspector
        p.readyReadStandardOutput.connect(lambda: self.read_inspection(p))
        p.readyReadStandardError.connect(lambda: setattr(self,'inspect_err',self.inspect_err+bytes(p.readAllStandardError()).decode('utf-8','replace')))
        p.finished.connect(self.inspected); p.errorOccurred.connect(lambda _: self.inspection_failed(p.errorString()))
        args=['--inspect', self.url.text().strip()]; ctx=self.ctx_for(self.url.text().strip())
        if ctx.get('referer'): args+=['--referer',ctx['referer']]
        if ctx.get('user_agent'): args+=['--user-agent',ctx['user_agent']]
        if ctx.get('cookies_file'): args+=['--cookies',ctx['cookies_file']]
        elif self.effective_config()['cookies_browser']!='none':args+=['--cookies-from-browser',supported_cookie_browser(self.effective_config()['cookies_browser'])]
        if self.proxy.text().strip(): args+=['--proxy',self.proxy.text().strip()]
        self.command(p,args)
    def show_site_hint(self, url):
        import engine
        name=engine.site_name(url)
        self.site_note.setText((f'{name}: '+SITE_HINTS[name]+' ' if name in SITE_HINTS else '')+SITE_NOTE)
    def cancel_inspection(self):
        if self.inspector:
            self.batch_links=[]
            self.inspection_cancelled=True; stop_process_tree(self.inspector,force=True)
    def read_inspection(self, p): self.inspect_output += self.inspect_decoder.decode(bytes(p.readAllStandardOutput()))
    def inspection_failed(self, msg):
        self.batch_links=[]
        self.set_inspection_busy(False); self.play_title.setText('Could not load the link. Batch stopped.'); p=self.inspector; self.inspector=None
        if p: p.deleteLater()
        if not self.closing and not getattr(self,'inspection_cancelled',False): self.error(msg)
    def inspected(self, code, *args):
        self.set_inspection_busy(False)
        p = self.inspector
        if not p: return
        self.read_inspection(p); self.inspect_output+=self.inspect_decoder.decode(b'',final=True); self.inspector = None; p.deleteLater()
        if self.inspection_cancelled:
            self.play_title.setText('Loading stopped.'); return
        try:
            data = json.loads(self.inspect_output)
            if self.closing: return
            if code or data.get('type')=='error': raise ValueError(friendly_error(data.get('message') or self.inspect_err or 'Could not read this URL.'))
            self.items = data['items']; self.pick.clear(); self.play_title.setText(f"{data['title']}  |  {len(self.items)} available items")
            self.playlist_title=data.get('title') if data.get('is_playlist') else None
            for item in self.items:
                sec = item.get('duration'); duration = f'{int(sec)//60}:{int(sec)%60:02d}' if sec else '-'
                row = QTreeWidgetItem([item.get('title') or item.get('id') or 'Untitled',duration]); row.setFlags(row.flags() | Qt.ItemIsUserCheckable); row.setCheckState(0, Qt.Checked); self.pick.addTopLevelItem(row)
            self.enqueue()
        except (ValueError, KeyError, TypeError) as exc:
            self.batch_links=[]; self.play_title.setText('Could not load the link. Batch stopped.'); self.error(str(exc))
    def select_all(self, checked):
        for i in range(self.pick.topLevelItemCount()): self.pick.topLevelItem(i).setCheckState(0, Qt.Checked if checked else Qt.Unchecked)
    def confirm_playlist(self, title):
        dialog=QDialog(self); dialog.setWindowTitle('Choose playlist items'); dialog.resize(620,460)
        layout=QVBoxLayout(dialog); count=QLabel(); count.setTextFormat(Qt.PlainText); layout.addWidget(count)
        layout.addWidget(self.pick); self.pick.show()
        def update_count():
            selected=sum(self.pick.topLevelItem(i).checkState(0)==Qt.Checked for i in range(self.pick.topLevelItemCount()))
            count.setText(f'{title}\n{selected} of {len(self.items)} items selected'); add.setEnabled(selected>0)
        actions=QHBoxLayout(); self.button('Select all',lambda:self.select_all(True),actions); self.button('Select none',lambda:self.select_all(False),actions); actions.addStretch()
        self.button('Cancel',dialog.reject,actions); add=self.button('Add selected',dialog.accept,actions); layout.addLayout(actions)
        self.pick.itemChanged.connect(update_count); update_count()
        accepted=dialog.exec()==QDialog.Accepted
        self.pick.itemChanged.disconnect(update_count); self.pick.hide(); self.pick.setParent(self.add_dialog)
        dialog.deleteLater()
        if accepted:
            from features_ui import choose_formats
            if choose_formats(self): self.enqueue()
        else:
            self.batch_links=[]; self.play_title.setText('Playlist not added. Batch stopped.')
    def enqueue(self):
        cfg = self.config()
        try:
            from features_ui import validate_feature_settings
            validate_feature_settings(cfg)
            import engine
            engine.build_options(engine_config(cfg))
            Path(cfg['outdir']).expanduser().mkdir(parents=True, exist_ok=True)
        except Exception as exc: self.error(str(exc)); return
        chosen = [item for i,item in enumerate(self.items) if self.pick.topLevelItem(i).checkState(0)==Qt.Checked]
        if not chosen: self.error('Load a link and select at least one video.'); return
        jobcfg=dict(cfg); jobcfg.update({k:v for k,v in self.ctx_for(self.url.text().strip()).items() if k!='url'})
        playlist_title=getattr(self,'playlist_title',None)
        if playlist_title and cfg.get('playlist_folders'):
            from playlist_paths import playlist_directory
            try:jobcfg['outdir']=playlist_directory(jobcfg['outdir'],cfg['playlist_folder_name'],playlist_title)
            except ValueError as exc:self.error(str(exc));return
        from queue_policy import canonical_url
        existing={canonical_url(j['url']) for j in self.jobs};unique=[]
        for item in chosen:
            identity=canonical_url(item['url'])
            if identity in existing:continue
            existing.add(identity);unique.append(item)
        chosen=unique
        for item in chosen:
            itemcfg=dict(jobcfg); itemcfg.update(item.pop('_selection',{}))
            if playlist_title and cfg.get('playlist_numbering'):
                from playlist_ui import numbered_template
                itemcfg['template']=numbered_template(itemcfg['template'],int(item.get('index') or self.items.index(item)+1),cfg['playlist_digits'])
            job=dict(item); job['added_at']=__import__('datetime').datetime.now().isoformat(); job.update(video_id=item.get('id'),source_id=item.get('id'),source_extractor=item.get('extractor_key') or item.get('extractor'),id=uuid.uuid4().hex,title=item.get('title') or item.get('id') or 'Untitled',config=itemcfg,status='ready',percent=0,speed='',eta='',error='',path=''); self.jobs.append(job)
        self.store.data['settings'] = cfg; self.store.save(); self.refresh_queue(); self.play_title.setText(f'{len(chosen)} item(s) added. Choose resolution / format in each row, then Start or Start all.'); self.url.clear();self._link_user_edited=False; self.statusBar().showMessage(f'{len(chosen)} items ready. Choose a format and click Start.'); self.pick.clear(); self.items=[]; self.show_main_page(0)
        from features_ui import continue_batch
        continue_batch(self)
    def set_job_progress(self, progress, job):
        busy=(job['status']=='processing' and not job.get('_converting')) or (job['status']=='downloading' and not job.get('total'))
        progress.setRange(0,0 if busy else 100); progress.setValue(int(job.get('percent',0)))
        detail=f"{(job.get('downloaded') or 0)/1024/1024:.1f} MiB downloaded"
        progress.setToolTip('Merging or preparing the downloaded file' if job['status']=='processing' else detail+(' (total size unknown)' if busy else ''))
        if busy and job['status']=='downloading': self.statusBar().showMessage(job['title']+': '+detail+'; total size unknown')
    def update_active_row(self, job=None):
        job=job if job is not None else self.active
        if job and job.get('id') in self.row_widgets: self.row_widgets[job['id']].update_state()
        self.update_queue_summary()
    def flush_progress_updates(self):
        self._progress_timer.stop();dirty=self._dirty_progress;self._dirty_progress=set()
        jobs_by_id={job['id']:job for job in self.jobs}
        for key in dirty:
            job=jobs_by_id.get(key);row=self.row_widgets.get(key)
            if job and row:
                self.progress.setValue(int(job.get('percent',0)));row.update_state()
        if dirty:self.update_queue_summary()
    def toggle_job_details(self,job):
        row=self.row_widgets.get(job['id'])
        if row:
            if row.settings_dialog and row.settings_dialog.isVisible():row.settings_dialog.hide()
            else:row.open_options()
    def queue_row_signature(self,job):
        return json.dumps((job['title'],job['url'],job['config'],job['status'],self.is_running(job),job.get('path',''),job.get('formats',[])),sort_keys=True,default=str)

    def refresh_queue(self):
        if self.closing:return
        from compact_ui import CompactDownloadRow
        open_options={key for key,row in self.row_widgets.items() if row.settings_dialog and row.settings_dialog.isVisible()}
        focused=QApplication.focusWidget();focus_key=getattr(self,'_pending_row_focus',None);self._pending_row_focus=None
        if not focus_key:
            for key,row in self.row_widgets.items():
                for field in ('mode','quality','container','connections','format','include','more','primary'):
                    if row.__dict__.get(field) is focused and focused is not None:focus_key=(key,field)
        descriptors=[]
        for job in self.jobs:
            config=dict(DEFAULTS);config.update(job['config']);job['config']=config
            if str(config['quality']) not in ('best','worst') and not str(config['quality']).isdigit():config['quality']='best'
            if config.get('mode')=='video':
                from engine import selected_video_quality
                config['quality']=selected_video_quality(job.get('formats',[]),config['quality'])
            if str(config['bitrate']) not in ('64','96','128','160','192','256','320'):config['bitrate']='192'
            descriptors.append((job['id'],job,False))
        represented={(j.get('url',''),j.get('path') or j['config']['outdir'],j['status']) for j in self.jobs if j['status'] in ('done','skipped','error','cancelled')}
        for record in reversed(self.history):
            if (record.get('url',''),record.get('path',''),record['status']) not in represented:descriptors.append(('history:'+str(id(record)),record,True))
        items=getattr(self,'_queue_items',{});keys=[key for key,_,_ in descriptors];wanted=set(keys)
        order=[self.queue.topLevelItem(i).data(0,Qt.UserRole) for i in range(self.queue.topLevelItemCount())]
        scroll=self.queue.verticalScrollBar().value();selected={item.data(0,Qt.UserRole) for item in self.queue.selectedItems()}
        self.queue.blockSignals(True);self.queue.setUpdatesEnabled(False)
        try:
            if [key for key in order if key in wanted]!=[key for key in keys if key in items]:
                self.queue.clear();items={};self.row_widgets={}
            for key in list(items):
                if key not in wanted:
                    item=items.pop(key);self.queue.takeTopLevelItem(self.queue.indexOfTopLevelItem(item));self.row_widgets.pop(key,None)
            for position,(key,record,archived) in enumerate(descriptors):
                item=items.get(key)
                if archived:
                    if item is not None:
                        item.setText(0,record['title']);item.setToolTip(0,record.get('path',''))
                        item.setSelected(key in selected)
                        continue
                    state={'done':'Completed','skipped':'Already downloaded','error':'Failed','cancelled':'Cancelled'}.get(record['status'],record['status'].title())
                    item=QTreeWidgetItem([record['title'],state,record.get('time','')[:10],'—',''])
                    for column in range(5):item.setData(column,Qt.UserRole+2,True)
                    item.setData(0,Qt.UserRole,key);item.setData(0,Qt.UserRole+3,record);item.setSizeHint(0,QSize(180,44));item.setToolTip(0,record.get('path',''));item.setToolTip(1,record.get('error',''))
                    self.queue.insertTopLevelItem(position,item)
                    actions=QWidget();buttons=QHBoxLayout(actions);buttons.setContentsMargins(3,0,3,0);buttons.setSpacing(2)
                    self.button('Open',lambda checked=False,r=record:self.open_history_record(r),buttons).setObjectName('rowAction')
                    remove=self.button('×',lambda checked=False,r=record:self.remove_archived_record(r),buttons);remove.setToolTip('Remove this history record; keep the file');remove.setObjectName('rowAction')
                    self.queue.setItemWidget(item,4,actions)
                    self.queue.register_cells(item)
                    item.setSelected(key in selected)
                    items[key]=item
                    continue
                job=record;signature=self.queue_row_signature(job);row=self.row_widgets.get(key)
                if item is None:
                    item=QTreeWidgetItem([job['title']]);item.setData(0,Qt.UserRole,key);self.queue.insertTopLevelItem(position,item);items[key]=item
                item.setCheckState(0,Qt.Checked if job.get('included',True) else Qt.Unchecked)
                if row is None or row.render_signature!=signature:
                    if row:
                        for field in ('mode','quality','container','connections','format'):
                            control=row.__dict__.get(field)
                            if isinstance(control,QComboBox) and control.view().isVisible():control.hidePopup()
                    row=CompactDownloadRow(self,job,item);row.render_signature=signature
                    item.setSizeHint(0,row.sizeHint());self.queue.setItemWidget(item,0,row);self.row_widgets[key]=row
                    for column,cell in enumerate(row.cells,1):self.queue.setItemWidget(item,column,cell)
                    self.queue.register_cells(item)
                else:row.update_state()
                item.setSelected(key in selected)
            self._queue_items=items
        finally:
            self.queue.blockSignals(False);self.queue.setUpdatesEnabled(True)
        self.queue.paint_selection()
        self.queue.verticalScrollBar().setValue(scroll);self.apply_queue_filter();self.update_queue_summary();self.show_job_error()
        for key in open_options:
            if key in self.row_widgets:self.row_widgets[key].open_options()
        if focus_key and focus_key[0] in self.row_widgets:getattr(self.row_widgets[focus_key[0]],focus_key[1]).setFocus(Qt.OtherFocusReason)

    def queue_check_changed(self,row,column):
        if column!=0: return
        for job in self.jobs:
            if job['id']==row.data(0,Qt.UserRole): job['included']=row.checkState(0)==Qt.Checked; self.store.save(); self.update_queue_summary(); break
    def set_job_connection(self,job,mode):
        if self.is_running(job): return
        self._pending_row_focus=(job['id'],'connections')
        try:
            if set_connection_mode(job,mode):
                self.append_log('Saved multi-connection partial data separately; single-connection retry starts safely from the beginning.')
        except OSError as exc:
            job.update(status='error',error='Could not preserve partial download: '+str(exc))
            self.append_log(job['error'])
        self.store.save(); self.refresh_queue()
    def remove_job(self, job):
        worker=self.workers.get(job['id'])
        if worker:
            job['remove_after_stop']=True; worker.stop('cancelled'); return
        self.drop_cookie_file(job)
        if job['status'] in ('done','skipped','error','cancelled'):
            for index in reversed(range(len(self.history))):
                record=self.history[index]
                if (record.get('url',''),record.get('path',''),record['status'])==(job.get('url',''),job.get('path') or job['config']['outdir'],job['status']):
                    del self.history[index];break
        self.jobs[:]=[j for j in self.jobs if j is not job]
        self.store.save(); QTimer.singleShot(0,self.refresh_queue)
    def create_row_menu(self,position):
        from row_actions import build_menu
        return build_menu(self,position)

    def open_downloaded_item(self,item,column=0):
        from row_actions import record_for_item,open_record
        open_record(self,record_for_item(self,item))

    def remove_selected_rows(self):
        keys={item.data(0,Qt.UserRole) for item in self.queue.selectedItems()}
        if not keys:return
        for job in list(self.jobs):
            if job['id'] in keys:self.remove_job(job)
        self.history[:]=[record for record in self.history if 'history:'+str(id(record)) not in keys]
        self.store.save()
        self.refresh_history()

    def selected_jobs(self):
        ids = {r.data(0,Qt.UserRole) for r in self.queue.selectedItems()}; return [j for j in self.jobs if j['id'] in ids]
    def show_job_error(self):
        jobs = self.selected_jobs()
        failed = next((j for j in jobs if j.get('error')),None)
        if not jobs: failed = next((j for j in self.jobs if j['status']=='error' and j.get('error')),None)
        error = f"{failed['title']}: {failed['error']}" if failed else ''
        self.job_error.setText(error); self.job_error.setVisible(bool(error))
        if jobs: self.statusBar().showMessage(error or jobs[0]['title'])
    def is_running(self, job):
        return any(w.job is job for w in self.workers.values()) or job is self.active
    def sync_active(self):
        worker=next(iter(self.workers.values()),None)
        self.active=worker.job if worker else None
        self.process=worker.process if worker else None
    def start_next(self):
        if self.closing: return
        if getattr(self,'file_task_pending',False) or (getattr(self,'file_task',None) and self.file_task.isRunning()):return
        from features_ui import queue_allowed
        if not queue_allowed(self): return
        from download_worker import DownloadWorker
        from engine import validate_url
        limit=max(1,min(4,int(self.effective_config()['parallel_downloads'])))
        changed=False
        for job in sorted(self.jobs,key=lambda j:-int(j.get('priority',0))):
            if len(self.workers)>=limit: break
            if job['status']!='queued' or not job.get('included',True) or self.is_running(job): continue
            from features_ui import job_allowed
            if not job_allowed(self,job):
                changed=changed or job['status']!='queued'
                continue
            # Duplicate destinations must not write the same partial simultaneously.
            if any(destinations_conflict(job,w.job) for w in self.workers.values()): continue
            try:
                validate_url(job['url'])
                config_path=self.store.root/('active-'+uuid.uuid4().hex+'.json')
                config_path.write_text(json.dumps(engine_config(job['config'])),encoding='utf-8')
            except Exception as exc:
                job.update(status='error',error=str(exc)); self.append_log(str(exc)); changed=True; continue
            job.update(status='downloading',error='',total=None,downloaded=0)
            changed=True
            worker=DownloadWorker(self,job,config_path)
            self.workers[job['id']]=worker
            self.sync_active()
            worker.start()
        if changed: self.store.save(); self.refresh_queue()
        if not self.workers: self.statusBar().showMessage('Queue idle.')
    def worker_finished(self, worker, code):
        from features_ui import finish_feature_job
        if finish_feature_job(self,worker,code): return
        job=worker.job
        if job.pop('_conversion_finished',False): code=0
        if worker.reason: job['status']=worker.reason
        elif not (code==0 and job['status'] in ('done','skipped')):
            job['status']='error'; job['error']=job.get('error') or f'Engine exited with code {code}. See Download messages.'
        if job['status'] in ('done','skipped','error','cancelled'):
            from datetime import datetime
            self.history.append(dict(title=job['title'],status=job['status'],path=job.get('path') or job['config']['outdir'],url=job['url'],time=datetime.now().isoformat(),error=job.get('error','')))
            del self.history[:-1000]
        if job['status'] in ('done','skipped'): self.drop_cookie_file(job)
        self.workers.pop(job['id'],None); self.sync_active()
        try: worker.config_path.unlink(missing_ok=True)
        except OSError: pass
        worker.deleteLater()
        if job.pop('remove_after_stop',False):
            self.drop_cookie_file(job); self.jobs[:]=[j for j in self.jobs if j is not job]
        self.store.save(); self.refresh_history()
        QTimer.singleShot(0,self.start_next)
    def process_failed(self, process, error):
        self.append_log(process.errorString())
        if error==QProcess.FailedToStart and self.process is process and self.active:
            self.active['error']=process.errorString()
            self.download_finished(-1)
    def append_log(self, text):
        if text.strip():
            self.log.append(text.strip()[:3000])
            try:
                with (self.store.root/'download.log').open('a',encoding='utf-8') as handle: handle.write(text.strip()[:3000]+'\n')
                if (self.store.root/'download.log').stat().st_size>2*1024*1024: (self.store.root/'download.log').replace(self.store.root/'download.previous.log')
            except OSError: pass
        if self.log.document().blockCount()>300: self.log.clear()
    def read_download(self,p):
        self.output += self.download_decoder.decode(bytes(p.readAllStandardOutput()))
        while '\n' in self.output:
            line,self.output = self.output.split('\n',1)
            try: self.handle_engine_event(json.loads(line))
            except (ValueError,TypeError): self.append_log(line)
    def handle_engine_event(self, event, job=None):
        j=job if job is not None else self.active
        if j is None: return
        if event.get('type')=='progress':
            if 'total' in event: j['total']=event.get('total')
            if 'downloaded' in event: j['downloaded']=event.get('downloaded') or 0
            percent = event.get('percent') or 0
            try: j['percent'] = max(0,min(100,float(percent)))
            except (ValueError,TypeError): pass
            speed = event.get('speed'); eta=event.get('eta'); j['speed_bytes']=speed if isinstance(speed,(float,int)) else 0
            j['speed'] = f'{speed/1024/1024:.2f} MiB/s' if isinstance(speed,(float,int)) else str(speed or '-')
            j['eta'] = f'{int(eta)} s' if isinstance(eta,(float,int)) else str(eta or '-')
            self._dirty_progress.add(j['id'])
            if not self._progress_timer.isActive():self._progress_timer.start()
            import time
            if time.monotonic()-getattr(self,'last_save',0)>5: self.last_save=time.monotonic(); self.store.save()   # keep progress across a crash
        elif event.get('type')=='status':
            status=event.get('status')
            if status=='destination':
                files=j.setdefault('transfer_files',[])
                if event.get('filename') and event['filename'] not in files: files.append(event['filename'])
            if status=='processing': j['status']='processing'
            elif status=='skipped': j['skipped']=True
            elif status=='notice': self.append_log(event.get('message',''))
            elif status=='partials_found':
                mb=(event.get('bytes') or 0)/1024/1024; self.append_log(f"Resuming: found {event.get('count')} partial file(s), {mb:.1f} MiB already on disk.")
            elif status=='resuming':
                j['resumed']=True; self.append_log(f"Continuing from {(event.get('offset') or 0)/1024/1024:.1f} MiB (no restart).")
            self.update_active_row(j)
        elif event.get('type')=='item_done': j['path']=event.get('path') or ''
        elif event.get('type')=='done':
            self._dirty_progress.discard(j.get('id'))
            errors=event.get('errors') or []
            success=not errors and not event.get('cancelled') and event.get('returncode',0)==0 and (event.get('path') or event.get('skipped'))
            j.update(status=('skipped' if event.get('skipped') and not event.get('path') else 'done') if success else 'error',percent=100 if success else j.get('percent',0),path=event.get('path') or j.get('path',''))
            if success: j['error']=''
            if j['status']=='skipped': j['error']='Already recorded as completed. If the saved file was deleted, remove the .completed-*.txt archive in the output folder or turn off skip-completed in Settings before adding again.'
            if errors: j['error']='; '.join(friendly_error(e.get('message','Failed')) for e in errors)
            self.update_active_row(j)
        elif event.get('type')=='error': j['error']=friendly_error(event.get('message','Download failed.')); self.append_log(j['error'])
    def stop_selected(self, reason):
        selected=self.selected_jobs()
        if not selected: self.error('Select one or more queue items first.'); return
        for job in selected:
            worker=self.workers.get(job['id'])
            if worker: worker.stop(reason)
            elif job['status'] in ('queued','paused','ready','error'): job['status']=reason
        self.store.save(); self.refresh_queue()
    def pause_all(self):
        for job in self.jobs:
            if job['status']=='queued': job['status']='paused'
        for worker in list(self.workers.values()): worker.stop('paused')
        self.store.save(); self.refresh_queue()
    def resume_selected(self):
        for job in self.selected_jobs():
            if not self.is_running(job) and job['status'] in ('paused','ready','cancelled','error','skipped'):
                job.update(status='queued',error='',included=True,retry_at=0,retry_count=0)
        self.store.save(); self.refresh_queue(); self.start_next()
    def clear_finished(self):
        for j in self.jobs:
            if j['status'] in ('done','skipped','cancelled'): self.drop_cookie_file(j)
        self.jobs[:] = [j for j in self.jobs if j['status'] not in ('done','skipped','cancelled')]
        self.history[:] = [record for record in self.history if record['status'] not in ('done','skipped','cancelled')]
        self.store.save();self.refresh_history()
    def refresh_history(self):
        self.main_history.clear()
        for index in reversed(range(len(self.history))):
            h=self.history[index]
            from features_ui import record_matches
            if not record_matches(self,h,'history'): continue
            row=QTreeWidgetItem([h['title'],h['status'],h['path']]); row.setToolTip(0,h.get('time','')+'\n'+h.get('error','')); row.setData(0,Qt.UserRole,h['path']); row.setData(0,Qt.UserRole+1,index); self.main_history.addTopLevelItem(row)
        self.refresh_queue()
    def open_history_record(self,record):
        path=Path(record.get('path','')).expanduser();path=path.parent if path.is_file() else path
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))
    def remove_archived_record(self,record):
        for index,value in enumerate(self.history):
            if value is record:
                del self.history[index];self.store.save();self.refresh_history();return
    def open_history(self):
        rows=self.main_history.selectedItems()
        if rows:
            p=Path(rows[0].data(0,Qt.UserRole)).expanduser(); p=p.parent if p.is_file() else p
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(p)))
    def remove_history_record(self):
        rows=self.main_history.selectedItems()
        if not rows: return
        index=rows[0].data(0,Qt.UserRole+1)
        if isinstance(index,int) and 0<=index<len(self.history):
            del self.history[index]; self.store.save(); self.refresh_history()
            self.statusBar().showMessage('History record removed. Downloaded files were kept.')
    def clear_history(self):
        if QMessageBox.question(self,APP_NAME,'Clear history? Downloaded files will not be deleted.')==QMessageBox.Yes:
            self.history.clear(); self.store.save(); self.refresh_history()
    def link_edited(self,*args):
        self._link_user_edited=True;self._clipboard_batch_links=[]
    def capture_copied_links(self,force=False):
        if not hasattr(self,'url') or self.closing:return
        if not self.effective_config()['clipboard'] and not force:return
        if self.inspector:return
        text=QApplication.clipboard().text().strip()
        if not force and (text==self.clip_last or (self._link_user_edited and self.url.hasFocus() and self.url.text().strip())):return
        from queue_policy import unique_links
        links,_,_=unique_links(text)
        self.clip_last=text
        if not links:return
        self.url.setText(links[0]);self._link_user_edited=False;self._clipboard_batch_links=links[1:]
        import engine
        self.play_title.setText(f'{engine.site_name(links[0]) or "Video"} link copied. Click Add.' if len(links)==1 else f'{len(links)} copied links ready. Click Add to queue them.');self.play_title.show()
    def check_clipboard(self):
        if self.closing:return
        if self.advanced.isVisible(): self.update_receiver_controls()
        self.capture_copied_links()
    def changeEvent(self,event):
        super().changeEvent(event)
        if event.type()==QEvent.WindowStateChange and self.isMinimized():
            self._tray_was_maximized=bool(event.oldState() & Qt.WindowMaximized)
            QTimer.singleShot(0,self.hide_minimized_to_tray)
    def hide_minimized_to_tray(self):
        from PySide6.QtWidgets import QSystemTrayIcon
        if self.closing or not self.isMinimized() or not hasattr(self,'tray'): return
        if not self.effective_config().get('minimize_to_tray',True): return
        if not QSystemTrayIcon.isSystemTrayAvailable() or not self.tray.isVisible(): return
        self.hide()
        if not getattr(self,'_tray_hint_shown',False):
            self._tray_hint_shown=True
            self._tray_message_action='restore'
            self.tray.showMessage(APP_NAME,'Downloads continue in the background. Click the tray icon to restore the window.')
    def restore_from_tray(self):
        if getattr(self,'_tray_was_maximized',False): self.showMaximized()
        else: self.showNormal()
        self.raise_();self.activateWindow()
    def quit_from_tray(self):
        self.restore_from_tray()
        if self.close() and self.closing: QApplication.instance().quit()
    def closeEvent(self,event):
        if getattr(self,'file_task_pending',False) or (getattr(self,'file_task',None) and self.file_task.isRunning()):
            QMessageBox.information(self,APP_NAME,'A file move is in progress. Please wait for it to finish before closing.');event.ignore();return
        if getattr(self,'update_check',None) and self.update_check.isRunning():
            self.statusBar().showMessage('Finishing update check before closing. Please close again shortly.'); event.ignore(); return
        if self.workers or self.inspector:
            if QMessageBox.question(self,APP_NAME,'Stop current work and close? Partial downloads will be kept.')!=QMessageBox.Yes:
                event.ignore(); return
        if hasattr(self,'feature_timer'): self.feature_timer.stop()
        self._progress_timer.stop()
        self.closing=True
        for worker in list(self.workers.values()):
            worker.stop('paused')
            if not worker.process.waitForFinished(3000):
                stop_process_tree(worker.process,force=True); worker.process.waitForFinished(1500)
        if self.inspector:
            inspector=self.inspector; stop_process_tree(inspector,force=True); inspector.waitForFinished(1000)
        if self.receiver: self.receiver.stop(); self.receiver=None
        if self._settings_snapshot is not None: self.cancel_preferences()
        self.store.data['settings']=self.config(); self.store.save()
        if hasattr(self,'tray'): self.tray.hide()
        event.accept()

def main():
    # Stable storage identifiers preserve settings/history and activation with
    # older releases. The visible product name is APP_NAME.
    app=QApplication(sys.argv); app.setApplicationName('VideoDownloaderDesktop'); app.setOrganizationName('VideoDownloaderDesktop'); app.setWindowIcon(QIcon(str(asset_path('assets/app-icon.ico')))); app.setStyle('Fusion')
    app.setApplicationDisplayName(APP_NAME)
    app.setFont(QFont('Segoe UI',10))
    if '--smoke-test' in sys.argv:
        import tempfile
        with tempfile.TemporaryDirectory(prefix='video-downloader-smoke-') as root:
            store=Store(root); store.data['settings']['receiver']=False
            w=Window(store); w.show()
            QTimer.singleShot(750, w.close)
            print('GUI_READY', flush=True)
            print('PRODUCT_NAME=' + app.applicationDisplayName(), flush=True)
            print('STATE_DIRECTORY=' + str(default_state_directory()), flush=True)
            return app.exec()
    from single_instance import SingleInstance
    instance=SingleInstance(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation),app)
    try:
        if not instance.acquire():return 0
    except OSError as exc:
        QMessageBox.warning(None,APP_NAME,str(exc));return 1
    try:
        w=Window();instance.set_window(w);w.show();return app.exec()
    finally:instance.close()
if __name__=='__main__': raise SystemExit(main())
