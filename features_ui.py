"""Compact, optional download controls and policy integration."""
import json
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from PySide6.QtCore import Qt, QTimer, QUrl, QThread, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QFormLayout,QLabel,QPlainTextEdit,
    QPushButton,QComboBox,QCheckBox,QLineEdit,QMessageBox,QSystemTrayIcon,QWidget,QScrollArea,QMenu)


def record_matches(w, record, kind):
    controls=getattr(w,kind+'_search',None)
    if not controls: return True
    text,site,status,date=controls
    hay=' '.join(str(record.get(k,'')) for k in ('title','url','path')).lower()
    return (text.text().lower() in hay and site.text().lower() in urlparse(record.get('url','')).netloc.lower()
        and (status.currentText()=='Any status' or status.currentText()==record.get('status'))
        and (not date.text() or str(record.get('time',record.get('added_at',''))).startswith(date.text())))


def filter_queue(w):
    visible=0
    jobs_by_id={job['id']:job for job in w.jobs}
    for i in range(w.queue.topLevelItemCount()):
        row=w.queue.topLevelItem(i); job=jobs_by_id.get(row.data(0,Qt.UserRole),{})
        row.setHidden(row.isHidden() or not record_matches(w,job,'queue')); visible+=not row.isHidden()
    return visible


def add_filters(w,kind,layout,index):
    bar=QHBoxLayout(); text=QLineEdit(); text.setPlaceholderText('Search titles or URLs')
    site=QLineEdit(); site.setPlaceholderText('Site domain'); status=w.combo(['Any status','ready','queued','downloading','processing','paused','done','skipped','error','cancelled'],'Any status')
    date=QLineEdit(); date.setPlaceholderText('Date: YYYY-MM-DD'); date.setMaximumWidth(155)
    setattr(w,kind+'_search',(text,site,status,date))
    callback=w.apply_queue_filter if kind=='queue' else w.refresh_history
    for c in (text,site,date): c.textChanged.connect(callback); bar.addWidget(c)
    status.currentTextChanged.connect(callback); bar.addWidget(status); layout.insertLayout(index,bar)


def install_features(w):
    w.batch_links=[]; w.stop_after_current=False; w.feature_settings={}
    w.setAcceptDrops(True)
    w.feature_timer=QTimer(w); w.feature_timer.timeout.connect(lambda:tick_queue(w)); w.feature_timer.start(1000)
    add_filters(w,'history',w.main_stack.widget(1).layout(),2)
    menu=w.queue_more.menu()
    menu.addAction('Add several links…',lambda:batch_dialog(w))
    w.app_more.menu().addAction('Check for updates…',lambda:check_updates(w))
    # Settings use the existing snapshot / Apply / Cancel mechanism.
    from preferences_ui import SettingsForm
    page=QWidget(); page_layout=QVBoxLayout(page); form=SettingsForm(); page_layout.addLayout(form); page_layout.addStretch()
    for key,label in [('start_at','Start queue at (local date and time)'),('quiet_start','Quiet hours from (HH:mm)'),('quiet_end','Quiet hours until (HH:mm)'),('update_manifest_url','Update manifest HTTPS URL'),('max_retries','Automatic retries (0 disables, maximum 3)')]:
        control=QLineEdit(str(w.store.data['settings'].get(key,''))); form.addRow(label,control); w.feature_settings[key]=control
        if key=='start_at': control.setPlaceholderText('YYYY-MM-DD HH:mm — leave blank to start now')
    note=QLabel('Schedules apply while this app is open. Quiet hours and stop-after-current allow active downloads to finish. Updates need a publisher HTTPS manifest; no automatic installation.'); note.setWordWrap(True); form.addRow(note)
    scroll=QScrollArea(); scroll.setFrameShape(QScrollArea.NoFrame); scroll.setWidgetResizable(True); scroll.setWidget(page); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); w.tabs.addWidget(scroll)
    w.settings_nav.addItem('Schedule and updates')
    w.completion_bar=QWidgetCompletion(w); w.download_layout.addWidget(w.completion_bar); w.completion_bar.hide()
    w.tray=QSystemTrayIcon(w.windowIcon(),w)
    w.tray.setToolTip('Orvanta Video Downloader — click to restore')
    tray_menu=QMenu(w)
    tray_menu.addAction('Show window',w.restore_from_tray)
    tray_menu.addAction('Open download folder',w.open_output_folder)
    tray_menu.addAction('Pause all downloads',w.pause_all)
    tray_menu.addSeparator();tray_menu.addAction('Quit',w.quit_from_tray)
    w.tray.setContextMenu(tray_menu)
    w.tray.activated.connect(lambda reason:w.restore_from_tray() if reason in (QSystemTrayIcon.Trigger,QSystemTrayIcon.DoubleClick) else None)
    w.tray.messageClicked.connect(lambda:w.restore_from_tray() if getattr(w,'_tray_message_action','')=='restore' else open_completed(w,False))
    if QSystemTrayIcon.isSystemTrayAvailable(): w.tray.show()


class QWidgetCompletion(QDialog):
    def __init__(self,w):
        # A regular widget is needed in the layout; clear the dialog window flag.
        super().__init__(w); self.setWindowFlags(Qt.Widget)
        bar=QHBoxLayout(self); self.label=QLabel(); self.label.setTextFormat(Qt.PlainText); bar.addWidget(self.label,1)
        for label,folder in [('Open file',False),('Open folder',True)]:
            b=QPushButton(label); b.clicked.connect(lambda checked=False,f=folder:open_completed(w,f)); bar.addWidget(b)
        dismiss=QPushButton('Dismiss'); dismiss.clicked.connect(self.hide); bar.addWidget(dismiss)


def open_completed(w,folder):
    path=Path(getattr(w,'completed_path',''))
    if str(path)=='.': return
    if folder or not path.is_file(): path=path if path.is_dir() else path.parent
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))


def notify_completed(w,job):
    w.completed_path=job.get('converted_path') or job.get('path') or job['config']['outdir']
    copy_format=Path(job.get('converted_path') or '').suffix.lstrip('.').upper() or 'MP4'
    w.completion_bar.label.setText((copy_format+' copy ready: ' if job.get('converted_path') else 'Completed: ')+job['title']); w.completion_bar.show()
    if w.tray.isVisible() and QSystemTrayIcon.supportsMessages():
        w._tray_message_action='open_completed'
        w.tray.showMessage('Download complete',job['title']+'\nClick to open the saved file.',QSystemTrayIcon.Information,6000)


def choose_formats(w):
    if not any(item.get('formats') for item in w.items): return True
    dialog=QDialog(w); dialog.setWindowTitle('Choose format and estimated size'); dialog.resize(620,350)
    layout=QVBoxLayout(dialog); note=QLabel('Sizes are estimates. Original downloads are kept when a separate MP4 copy is enabled.'); note.setWordWrap(True); layout.addWidget(note)
    scroll=QScrollArea(); scroll.setWidgetResizable(True); content=QWidget(); form=QFormLayout(content); scroll.setWidget(content); layout.addWidget(scroll); selections=[]
    for index,item in enumerate(w.items):
        if w.pick.topLevelItem(index).checkState(0)!=Qt.Checked: continue
        combo=w.combo([],''); combo.addItem('Use quality defaults · size unknown',None)
        for fmt in item.get('formats',[]):
            if w.mode.currentText()=='Audio' and fmt.get('acodec') in ('none',None): continue
            if w.mode.currentText()!='Audio' and fmt.get('vcodec')=='none': continue
            size=fmt.get('estimated_size'); label=(fmt.get('label') or fmt.get('format_id','Format'))+' / '+str(fmt.get('vcodec',''))+' / '+str(fmt.get('acodec',''))
            combo.addItem(label+(f' · ~{size/1048576:.1f} MiB' if size else ' · size unknown'),fmt)
        form.addRow(item.get('title','Video')[:75],combo); selections.append((item,combo))
    convert=QCheckBox('Also create a separate MP4 copy (re-encodes video)'); layout.addWidget(convert); convert.setVisible(w.mode.currentText()!='Audio')
    quality=w.combo(['balanced','small','high'],'balanced'); form.addRow('MP4 quality / size preset',quality); quality.setVisible(w.mode.currentText()!='Audio'); form.labelForField(quality).setVisible(w.mode.currentText()!='Audio')
    estimate=QLabel(); estimate.setWordWrap(True); layout.addWidget(estimate)
    def update_estimate():
        from media_conversion import estimate_conversion_size
        sizes=[estimate_conversion_size(item.get('duration'),quality.currentText()) for item,combo in selections]
        value=sum(size or 0 for size in sizes)
        estimate.setText(('MP4 copy: approximately '+str(round(value/1048576,1))+' MiB total' if value else 'MP4 copy size unknown')+'; rough estimate, actual varies.'+(' Some durations are unknown.' if any(size is None for size in sizes) else ''))
        estimate.setVisible(w.mode.currentText()!='Audio')
    quality.currentTextChanged.connect(update_estimate); update_estimate()
    buttons=QHBoxLayout(); cancel=QPushButton('Cancel'); cancel.clicked.connect(dialog.reject); buttons.addWidget(cancel)
    add=QPushButton('Add selected'); add.clicked.connect(dialog.accept); buttons.addWidget(add); layout.addLayout(buttons)
    if dialog.exec()!=QDialog.Accepted:
        w.batch_links=[]; w.statusBar().showMessage('Selection cancelled. Batch stopped.'); return False
    for item,combo in selections:
        fmt=combo.currentData() or {}; item['estimated_bytes']=fmt.get('estimated_size'); item['selected_format']=fmt
        item['_selection']={'format_id':fmt.get('selector',''),'convert_mp4':convert.isChecked() and w.mode.currentText()!='Audio','conversion_quality':quality.currentText()}
    return True


def batch_dialog(w,text=''):
    dialog=QDialog(w); dialog.setWindowTitle('Add several links'); layout=QVBoxLayout(dialog)
    label=QLabel('One video or playlist URL per line. Duplicate links are skipped.'); layout.addWidget(label)
    links=QPlainTextEdit(text); links.setMinimumSize(520,220); layout.addWidget(links)
    add=QPushButton('Inspect links'); layout.addWidget(add)
    def accept():
        from queue_policy import unique_links
        accepted,duplicates,invalid=unique_links(links.toPlainText(),[j['url'] for j in w.jobs])
        if not accepted: label.setText(f'No new links. {duplicates} duplicate(s), {len(invalid)} invalid line(s).'); return
        w.batch_links=accepted; dialog.accept(); w.statusBar().showMessage(f'{duplicates} duplicate(s) skipped; {len(invalid)} invalid line(s).'); continue_batch(w)
    add.clicked.connect(accept); dialog.exec()


def continue_batch(w):
    if w.batch_links and not w.inspector and not w.closing:
        w.url.setText(w.batch_links.pop(0)); w.open_add_dialog(); QTimer.singleShot(0,w.begin_compact_inspection)


def move_jobs(w,direction):
    selected=w.selected_jobs(); indexes=range(len(w.jobs)) if direction<0 else reversed(range(len(w.jobs)))
    ids={j['id'] for j in selected}
    for i in indexes:
        target=i+direction
        if w.jobs[i]['id'] in ids and 0<=target<len(w.jobs) and w.jobs[target]['id'] not in ids:
            w.jobs[i],w.jobs[target]=w.jobs[target],w.jobs[i]
    w.store.save(); w.refresh_queue()


def prioritize(w):
    for j in w.selected_jobs(): j['priority']=max((x.get('priority',0) for x in w.jobs),default=0)+1
    w.store.save(); w.refresh_queue()


def queue_allowed(w):
    from queue_policy import schedule_allows
    cfg=w.effective_config()
    try: allowed=schedule_allows(datetime.now(),cfg.get('start_at',''),cfg.get('quiet_start',''),cfg.get('quiet_end',''))
    except ValueError:
        w.statusBar().showMessage('Invalid schedule. Set a local ISO date/time and HH:mm quiet hours in Settings.'); return False
    return allowed and not w.stop_after_current


def job_allowed(w,job):
    from queue_policy import check_disk_space,disk_space_required
    if job.get('retry_at',0)>time.time(): return False
    try:
        ok,required,free=check_disk_space(job)
        other=sum(disk_space_required(x.job) for x in w.workers.values() if Path(x.job['config']['outdir']).resolve().anchor.casefold()==Path(job['config']['outdir']).resolve().anchor.casefold())
        if not ok or required+other>free:
            job.update(status='paused',error=f'Low disk space: approximately {(required+other)/1048576:.0f} MiB needed including active downloads; {free/1048576:.0f} MiB available. Free space and resume.'); return False
    except OSError as exc:
        job.update(status='paused',error='Cannot check output disk space: '+str(exc)); return False
    if not job.get('estimated_bytes'): w.statusBar().showMessage('Download size is unknown; available disk space cannot guarantee completion.')
    return True


def finish_feature_job(w,worker,code):
    job=worker.job
    if job.pop('_converting',False):
        conversion_format=job.pop('_conversion_format','mp4')
        job.pop('kind',None)
        job['converted_path']=job.get('path','') if code==0 else ''
        job['path']=job.pop('_original_path',job.get('path',''))
        job['status']='done'; job['_conversion_finished']=True
        reason=worker.reason
        if reason:
            job['conversion_status']=reason; job['error']='Original downloaded successfully. '+conversion_format.upper()+' copy '+reason+'.'; worker.reason=None
        elif code: job['error']='Original downloaded successfully. '+conversion_format.upper()+' conversion failed; see download messages.'
        if not reason: notify_completed(w,job)
        return False
    if code==0 and job.get('status')=='done':
        if job['config'].get('convert_mp4') and job.get('path'):
            from download_worker import DownloadWorker
            job['_original_path']=job['path']; job['_converting']=True; job['kind']='conversion'; job['status']='processing'
            worker.config_path.write_text(json.dumps({'quality':job['config'].get('conversion_quality','balanced')}),encoding='utf-8')
            replacement=DownloadWorker(w,job,worker.config_path); w.workers[job['id']]=replacement; worker.deleteLater(); w.sync_active(); replacement.start(); return True
        notify_completed(w,job)
    elif not worker.reason and code!=0:
        from queue_policy import retry_delay
        job['status']='error'
        delay=retry_delay(job,max_retries=int(w.effective_config().get('max_retries','3')))
        if delay is not None:
            job['retry_count']=job.get('retry_count',0)+1; job['retry_at']=time.time()+delay
            job['status']='queued'; job['error']=f'Retrying in {delay:g}s: '+job.get('error','')
            w.workers.pop(job['id'],None); w.sync_active(); worker.config_path.unlink(missing_ok=True); worker.deleteLater(); w.store.save(); w.refresh_queue(); return True
    return False


class UpdateCheck(QThread):
    result=Signal(object)
    def __init__(self,url,parent): super().__init__(parent); self.url=url
    def run(self):
        from release_updates import check_for_update
        try: self.result.emit(check_for_update(self.url))
        except Exception as exc: self.result.emit(str(exc))


def check_updates(w):
    url=w.effective_config().get('update_manifest_url','')
    if not url:
        QMessageBox.information(w,'Updates not configured','No release manifest URL is configured. Add the publisher HTTPS manifest in Settings > Schedule and updates after release hosting is ready.'); return
    if getattr(w,'update_check',None) and w.update_check.isRunning(): return
    w.update_check=UpdateCheck(url,w)
    def result(value):
        box=QMessageBox(w); box.setWindowTitle('Check for updates'); box.setTextFormat(Qt.PlainText)
        if isinstance(value,str): box.setText('Update check failed: '+value)
        elif value.get('available'):
            box.setText('Version '+value['version']+' is available.\n'+value.get('notes','')); button=box.addButton('Open download page',QMessageBox.AcceptRole)
            box.addButton(QMessageBox.Close); box.exec()
            if box.clickedButton()==button: QDesktopServices.openUrl(QUrl(value['download_url']))
            return
        else: box.setText('You are running the latest published version.')
        box.exec()
    w.update_check.result.connect(result); w.update_check.start()


def tick_queue(w):
    if w.closing or not queue_allowed(w): return
    limit=int(w.effective_config()['parallel_downloads'])
    if len(w.workers)<limit and any(j.get('status')=='queued' and j.get('included',True) and j.get('retry_at',0)<=time.time() and not w.is_running(j) for j in w.jobs):
        w.start_next()


def validate_feature_settings(cfg):
    from datetime import time as clock_time
    if cfg.get('start_at'): datetime.fromisoformat(cfg['start_at'])
    for key in ('quiet_start','quiet_end'):
        if cfg.get(key):
            clock_time.fromisoformat(cfg[key])
            if len(cfg[key])!=5: raise ValueError('Quiet hours must use HH:mm.')
    if bool(cfg.get('quiet_start'))!=bool(cfg.get('quiet_end')): raise ValueError('Set both quiet-hour times or clear both.')
    retries=int(cfg.get('max_retries','3'))
    if not 0<=retries<=3: raise ValueError('Automatic retries must be between 0 and 3.')
    if cfg.get('update_manifest_url'):
        parsed=urlparse(cfg['update_manifest_url'])
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password: raise ValueError('The update manifest must be an HTTPS URL without credentials.')


def eligible_mp4_source(record):
    path=Path(record.get('path',''))
    return (record.get('status') in ('done','skipped')
            and record.get('config',{}).get('mode')!='audio'
            and path.suffix.lower() in {'.webm','.mkv','.avi','.mov','.m4v','.flv','.wmv','.ts','.m2ts','.mpeg','.mpg','.ogv','.3gp','.vob'}
            and path.is_file())


def mp4_copy_candidate(w):
    rows=w.queue.selectedItems()
    if len(rows)!=1:return None
    key=rows[0].data(0,Qt.UserRole)
    record=next((job for job in w.jobs if job['id']==key),None)
    if record is None:record=rows[0].data(0,Qt.UserRole+3)
    return record if isinstance(record,dict) and eligible_mp4_source(record) else None


def convert_existing(w,record=None,output_format='mp4'):
    if len(w.workers)>=int(w.effective_config()['parallel_downloads']):
        QMessageBox.information(w,'Download slots busy','Wait for an available download slot before making another copy.'); return
    record=record if record is not None else mp4_copy_candidate(w)
    from row_actions import existing_file,in_use,MEDIA
    source=existing_file(record) if record else None
    eligible=eligible_mp4_source(record) if record and output_format=='mp4' else bool(source and source.suffix.lower() in MEDIA-{'.mp3'})
    if output_format not in ('mp4','mp3') or not eligible or in_use(w,source):return
    archived=not any(job is record for job in w.jobs)
    if archived:
        import uuid
        job=dict(record,id=uuid.uuid4().hex,config=dict(w.effective_config(),mode='video',outdir=str(source.parent)),percent=100,error='')
    else:job=record
    dialog=QDialog(w); dialog.setWindowTitle('Make '+output_format.upper()+' copy'); layout=QVBoxLayout(dialog)
    label=QLabel('Extracts audio as MP3. Your original file is preserved.' if output_format=='mp3' else 'Re-encodes video as H.264/AAC. Your original file is preserved.'); label.setWordWrap(True); layout.addWidget(label)
    preset=w.combo(['balanced','small','high'],'balanced'); layout.addWidget(preset); estimate=QLabel(); layout.addWidget(estimate)
    def update():
        from media_conversion import estimate_conversion_size
        size=estimate_conversion_size(job.get('duration'),preset.currentText())
        estimate.setText((f'Approximately {size/1048576:.1f} MiB' if size else 'Size unknown')+'; rough estimate, actual varies.')
    preset.currentTextChanged.connect(update); update()
    if output_format=='mp3':preset.hide();estimate.setText('MP3 audio, 192 kbps')
    actions=QHBoxLayout(); layout.addLayout(actions); cancel=QPushButton('Cancel'); cancel.clicked.connect(dialog.reject); actions.addWidget(cancel); create=QPushButton('Make '+output_format.upper()+' copy'); create.clicked.connect(dialog.accept); actions.addWidget(create)
    if dialog.exec()!=QDialog.Accepted: return
    from download_worker import DownloadWorker
    import uuid
    original_status=job['status']; job['kind']='conversion'
    if not job.get('estimated_bytes'): job['estimated_bytes']=Path(job['path']).stat().st_size
    if not job_allowed(w,job):
        job.pop('kind',None); job['status']=original_status; w.refresh_queue(); return
    path=w.store.root/('active-'+uuid.uuid4().hex+'.json'); path.write_text(json.dumps({'quality':preset.currentText(),'format':output_format}),encoding='utf-8')
    job.update(_converting=True,_conversion_format=output_format,_original_path=job['path'],status='processing',percent=0,error='')
    if archived:w.jobs.append(job)
    worker=DownloadWorker(w,job,path); w.workers[job['id']]=worker; w.sync_active(); w.refresh_queue(); worker.start()
