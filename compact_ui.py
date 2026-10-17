"""Compact download row: progress first, editing controls on demand."""
from urllib.parse import urlparse

from PySide6.QtCore import Qt, QSize, QTimer, QPoint, QEvent, Signal
from PySide6.QtGui import QPainter, QPolygon, QPalette, QMouseEvent
from PySide6.QtWidgets import (QWidget, QFrame, QLabel, QPushButton, QToolButton, QMenu,
                               QVBoxLayout, QHBoxLayout, QFormLayout, QProgressBar, QCheckBox,
                               QStackedWidget, QTreeWidget, QHeaderView, QDialog, QLineEdit, QApplication,
                               QStyledItemDelegate, QStyleOptionViewItem, QComboBox)


class ResponsiveDownloadTable(QTreeWidget):
    removeRequested = Signal()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete and event.modifiers() == Qt.NoModifier:
            self.removeRequested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def __init__(self,parent=None):
        super().__init__(parent)
        self.itemSelectionChanged.connect(self.paint_selection)
        self.setHeaderLabels(['File','Status / progress','Speed / ETA','Quality','Actions'])
        self.setRootIsDecorated(False);self.setIndentation(0);self.setUniformRowHeights(True)
        self._weights=[.49,.25,.14,.12];self._fitting=False
        header=self.header();header.setStretchLastSection(False);header.setMinimumSectionSize(80)
        for column in range(4):header.setSectionResizeMode(column,QHeaderView.Interactive)
        header.setSectionResizeMode(4,QHeaderView.Fixed);header.resizeSection(4,140)
        self._fit_timer=QTimer(self);self._fit_timer.setSingleShot(True);self._fit_timer.timeout.connect(self.fit_columns)
        header.sectionResized.connect(self.remember_widths);self.viewport().installEventFilter(self)
        self._fit_timer.start(0)

    def remember_widths(self,column,old,new):
        if not self._fitting and column<4:
            self._weights=[max(1,self.columnWidth(i)) for i in range(4)]

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'_fit_timer'):self._fit_timer.start(0)

    def eventFilter(self,watched,event):
        if watched.property('downloadCell'):
            if event.type() in (QEvent.MouseButtonPress, QEvent.MouseButtonRelease, QEvent.MouseButtonDblClick):
                position=watched.mapTo(self.viewport(),event.position().toPoint())
                self.setFocus(Qt.MouseFocusReason)
                forwarded=QMouseEvent(event.type(),position,event.globalPosition(),event.button(),event.buttons(),event.modifiers())
                QApplication.sendEvent(self.viewport(),forwarded)
                return True
        if watched is self.viewport() and event.type()==QEvent.Resize and event.size().width()!=event.oldSize().width():
            self._fit_timer.start(0)
        return super().eventFilter(watched,event)

    def register_cells(self,item):
        for column in range(self.columnCount()):
            cell=self.itemWidget(item,column)
            if cell is None:continue
            # Do not filter combo popup frames or button descendants: they must
            # receive their own mouse events rather than selecting table rows.
            for widget in [cell,*cell.findChildren(QLabel),*cell.findChildren(QProgressBar)]:
                widget.setProperty('downloadCell',True)
                widget.installEventFilter(self)

    def paint_selection(self):
        for i in range(self.topLevelItemCount()):
            item=self.topLevelItem(i)
            for column in range(self.columnCount()):
                cell=self.itemWidget(item,column)
                if cell is None or cell.property('downloadSelected') is item.isSelected():continue
                for widget in [cell,*cell.findChildren(QLabel)]:
                    widget.setProperty('downloadSelected',item.isSelected())
                    widget.style().unpolish(widget);widget.style().polish(widget);widget.update()

    def fit_columns(self):
        available=self.viewport().width()-140
        if available<505:return
        total=sum(self._weights)
        widths=[0]+[max(low,min(high,round(available*self._weights[i]/total))) for i,low,high in ((1,135,300),(2,100,190),(3,90,140))]
        widths[0]=available-sum(widths[1:])
        if widths[0]<180:
            for i,minimum in ((1,135),(2,100),(3,90)):
                reduction=min(180-widths[0],widths[i]-minimum);widths[i]-=reduction;widths[0]+=reduction
        self._fitting=True
        try:
            for i,width in enumerate(widths+[140]):self.header().resizeSection(i,width)
        finally:self._fitting=False


class VisibleComboBox(QComboBox):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.setMaxVisibleItems(8);self.view().setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon);self.setMinimumContentsLength(12)
        self.view().setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff);self.view().setTextElideMode(Qt.ElideRight)
    def wheelEvent(self,event):
        if self.view().isVisible():super().wheelEvent(event)
        else:event.ignore()
    def showPopup(self):
        screen=self.screen().availableGeometry()
        maximum=min(700,max(120,screen.width()-24))
        self.view().setMinimumWidth(min(self.width(),maximum));self.view().setMaximumWidth(maximum)
        super().showPopup()
        popup=self.view().window()
        row_height=max(20,self.view().sizeHintForRow(0))
        popup.resize(min(popup.width(),maximum+4),min(popup.height(),row_height*self.maxVisibleItems()+8,screen.height()-24))
        popup.move(max(screen.left()+4,min(popup.x(),screen.right()-popup.width()-4)),max(screen.top()+4,min(popup.y(),screen.bottom()-popup.height()-4)))
    def paintEvent(self, event):
        super().paintEvent(event)
        painter=QPainter(self); painter.setPen(Qt.NoPen); painter.setBrush(self.palette().color(QPalette.Active if self.isEnabled() else QPalette.Disabled,QPalette.Text))
        x=self.width()-14; y=self.height()//2
        painter.drawPolygon(QPolygon([QPoint(x-4,y-2),QPoint(x+4,y-2),QPoint(x,y+3)]))


class CompactItemDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super().initStyleOption(option,index)
        option.features &= ~QStyleOptionViewItem.HasCheckIndicator
        if not index.data(Qt.UserRole+2):option.text=''


class CompactDownloadRow(QFrame):
    _option_names={'mode','container','connections','format','include','options','hint','convert_copy','conversion_preset','advanced_toggle','remove_button','cancel_button'}

    def __getattr__(self,name):
        if name in self._option_names:
            self.ensure_options()
            return self.__dict__[name]
        raise AttributeError(name)

    def __init__(self,window,job,item):
        super().__init__()
        self.window,self.job,self.item=window,job,item
        self.settings_dialog=None;self._options_built=False
        self.setObjectName('downloadRow');self.setAttribute(Qt.WA_StyledBackground,True);self.setFixedHeight(44)
        layout=QHBoxLayout(self);layout.setContentsMargins(8,3,8,3)
        self.title=QLabel(job['title']);self.title.setTextFormat(Qt.PlainText);self.title.setObjectName('fileTitle');self.title.setMinimumWidth(0)
        self.title.setToolTip(job['title']+'\n'+job['url']);layout.addWidget(self.title)
        cfg=job['config'];audio=cfg.get('mode')=='audio'
        from engine import available_video_qualities
        values=available_video_qualities(job.get('formats',[]))
        self.quality=window.combo(['64 kbps','96 kbps','128 kbps','160 kbps','192 kbps','256 kbps','320 kbps'] if audio else values,str(cfg.get('bitrate','192'))+' kbps' if audio else str(cfg.get('quality','1080')))
        if not audio:
            window.label_quality(self.quality)
            if values==['best']:
                self.quality.setItemText(0,'Best available')
                self.quality.setToolTip('Video resolutions could not be detected. The best available format will be used.')
        self.quality.setMinimumHeight(36);self.quality.setEnabled(not self.locked())
        self.quality.currentIndexChanged.connect(lambda _:window.update_job_choice(job,'quality',self.quality.currentText() if audio else self.quality.currentData()))
        quality=QWidget();box=QHBoxLayout(quality);box.setContentsMargins(5,3,5,3);box.addWidget(self.quality)
        self.progress=QProgressBar();self.progress.setTextVisible(False);self.progress.setFixedHeight(5);self.progress.setFixedWidth(55)
        self.detail=QLabel();self.detail.setObjectName('transferDetail');self.detail.setTextFormat(Qt.PlainText);self.detail.setMaximumWidth(180)
        status=QWidget();box=QHBoxLayout(status);box.setContentsMargins(8,3,8,3);box.setSpacing(6);box.addWidget(self.detail,1);box.addWidget(self.progress)
        self.timing=QLabel();self.timing.setObjectName('muted');self.timing.setAlignment(Qt.AlignRight|Qt.AlignVCenter)
        timing=QWidget();box=QHBoxLayout(timing);box.setContentsMargins(8,3,8,3);box.addWidget(self.timing)
        self.actions=QWidget();box=QHBoxLayout(self.actions);box.setContentsMargins(0,0,0,0);box.setSpacing(4)
        text,action=('Open folder','open') if job['status'] in ('done','skipped') else (('Pause','pause') if window.is_running(job) else (('Retry','start') if job['status']=='error' else (('Resume','start') if job['status']=='paused' else ('Start','start'))))
        self.primary=QPushButton(text);self.primary.setObjectName('rowAction');self.primary.clicked.connect(lambda:window.row_action(job,action));box.addWidget(self.primary)
        self.more=QToolButton();self.more.setText('···');self.more.setObjectName('rowMore');self.more.setToolTip('Download options');self.more.clicked.connect(lambda:window.toggle_job_details(job));box.addWidget(self.more)
        self.cells=[status,timing,quality,self.actions];self.update_state()

    def locked(self):
        return self.window.is_running(self.job) or self.job['status'] in ('done','skipped','processing','downloading')

    def ensure_options(self):
        if self._options_built:return
        self._options_built=True
        window,job,item=self.window,self.job,self.item;cfg=job['config'];locked=self.locked();audio=cfg.get('mode')=='audio'
        self.mode=window.combo(['Video','Audio'],'Audio' if audio else 'Video');self.mode.setEnabled(not locked)
        self.container=window.combo(['MP3','M4A'] if audio else ['Original format','MP4 (remux only)'],cfg.get('audio_format','mp3').upper() if audio else ('MP4 (remux only)' if cfg.get('container')=='mp4' else 'Original format'));self.container.setEnabled(not locked)
        self.connections=window.combo(['Single connection','Multiple connections'],'Multiple connections' if cfg.get('connection_mode')=='multiple' else 'Single connection');self.connections.setEnabled(not locked)
        for control in (self.mode,self.container,self.connections):control.setMinimumHeight(36)
        self.format=window.combo([],'');self.format.addItem('Automatic — use resolution in the table','')
        for choice in job.get('formats',[]):
            if audio!=(choice.get('vcodec') in (None,'none')):continue
            size=choice.get('estimated_size');label=choice.get('label') or choice.get('selector','Format')
            self.format.addItem(label+(f' · ~{size/1048576:.1f} MiB' if size else ''),choice.get('selector',''))
        self.format.setCurrentIndex(max(0,self.format.findData(cfg.get('format_id',''))));self.format.setEnabled(not locked)
        self.convert_copy=QCheckBox('Create a separate MP4 copy');self.convert_copy.setChecked(cfg.get('convert_mp4',False));self.convert_copy.setEnabled(not locked and not audio)
        self.conversion_preset=window.combo(['balanced','small','high'],cfg.get('conversion_quality','balanced'));self.conversion_preset.setEnabled(not locked and not audio)
        self.include=QCheckBox('Include in Start all');self.include.setChecked(job.get('included',True));self.include.setEnabled(not locked)
        self.remove_button=QPushButton('Remove');self.remove_button.setObjectName('quietButton');self.remove_button.clicked.connect(lambda:window.remove_job(job))
        self.cancel_button=None
        if job['status'] not in ('done','skipped','cancelled'):
            self.cancel_button=QPushButton('Cancel download');self.cancel_button.setObjectName('quietButton');self.cancel_button.clicked.connect(lambda:window.row_action(job,'cancel'))
        self.hint=QLabel();self.hint.setObjectName('muted');self.hint.setWordWrap(True)
        self.settings_dialog=QDialog(self);self.settings_dialog.setWindowTitle('Download options');self.settings_dialog.setMinimumWidth(460);self.settings_dialog.resize(510,360)
        self.format.setParent(self.settings_dialog)
        if self.cancel_button:self.cancel_button.setParent(self.settings_dialog);self.cancel_button.hide()
        dialog_layout=QVBoxLayout(self.settings_dialog);dialog_layout.setContentsMargins(20,18,20,18);dialog_layout.setSpacing(12)
        title=QLabel(self.job['title']);title.setTextFormat(Qt.PlainText);title.setWordWrap(True);title.setMaximumHeight(48);dialog_layout.addWidget(title)
        path=QLineEdit(self.job.get('path') or self.job['config']['outdir']);path.setReadOnly(True);path.setToolTip(path.text());dialog_layout.addWidget(path)
        complete=self.job['status'] in ('done','skipped');editable=self.mode.isEnabled()
        basic=QWidget();form=QFormLayout(basic);form.setContentsMargins(0,0,0,0);form.setSpacing(10);form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        for label,control in [('Media',self.mode),('Save as',self.container),('Connections',self.connections)]:form.addRow(label,control)
        dialog_layout.addWidget(basic);basic.setVisible(not complete)
        self.hint.setText('Pause this download to change its settings.');self.hint.setVisible(not editable and not complete);dialog_layout.addWidget(self.hint)
        advanced=QWidget();advanced_form=QFormLayout(advanced);advanced_form.setContentsMargins(0,0,0,0);advanced_form.setSpacing(10)
        if self.format.count()>1:advanced_form.addRow('Exact format',self.format)
        else:self.format.hide()
        advanced_form.addRow(self.include)
        advanced_form.addRow(self.convert_copy)
        advanced_form.addRow('MP4 quality',self.conversion_preset)
        def conversion_changed(checked):
            self.conversion_preset.setVisible(checked);advanced_form.labelForField(self.conversion_preset).setVisible(checked)
        self.convert_copy.toggled.connect(conversion_changed);conversion_changed(self.convert_copy.isChecked())
        self.options=advanced
        self.advanced_toggle=QToolButton();self.advanced_toggle.setText('More options');self.advanced_toggle.setCheckable(True);self.advanced_toggle.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        def toggle_advanced(checked):
            advanced.setVisible(checked);self.advanced_toggle.setArrowType(Qt.DownArrow if checked else Qt.RightArrow)
            if checked:self.window.expanded_jobs.add(self.job['id'])
            else:self.window.expanded_jobs.discard(self.job['id'])
            QTimer.singleShot(0,self.settings_dialog,self.settings_dialog.adjustSize)
        self.advanced_toggle.toggled.connect(toggle_advanced);dialog_layout.addWidget(self.advanced_toggle);dialog_layout.addWidget(advanced)
        self.advanced_toggle.setVisible(editable);toggle_advanced(self.job['id'] in self.window.expanded_jobs and editable);self.advanced_toggle.setChecked(self.job['id'] in self.window.expanded_jobs and editable)
        footer=QHBoxLayout();self.remove_button.setText('Remove');footer.addWidget(self.remove_button)
        if self.cancel_button and self.job['status'] not in ('ready','queued'):footer.addWidget(self.cancel_button)
        footer.addStretch();close=QPushButton('Close');close.setObjectName('primaryButton');close.clicked.connect(self.settings_dialog.hide);footer.addWidget(close);dialog_layout.addLayout(footer)
        self.mode.currentTextChanged.connect(lambda value:window.update_job_choice(job,'mode','audio' if value=='Audio' else 'video'))
        if audio:self.container.currentTextChanged.connect(lambda value:window.update_job_choice(job,'audio_format',value.lower()))
        else:self.container.currentIndexChanged.connect(lambda index:window.update_job_choice(job,'container','mp4' if index else 'original'))
        self.connections.currentIndexChanged.connect(lambda index:QTimer.singleShot(0,self,lambda:window.set_job_connection(job,'multiple' if index else 'single')))
        self.format.currentIndexChanged.connect(lambda index:window.set_job_format(job,self.format.itemData(index)))
        self.convert_copy.toggled.connect(lambda value:window.update_job_choice(job,'convert_mp4',value))
        self.conversion_preset.currentTextChanged.connect(lambda value:window.update_job_choice(job,'conversion_quality',value))
        self.include.toggled.connect(lambda value:item.setCheckState(0,Qt.Checked if value else Qt.Unchecked))

    def open_options(self):
        self.ensure_options();self.settings_dialog.show();self.settings_dialog.raise_();self.settings_dialog.activateWindow()

    def update_state(self):
        job=self.job; cfg=job['config']; state=job['status']
        display=(state,cfg.get('mode'),cfg.get('quality'),cfg.get('bitrate'),cfg.get('container'),cfg.get('audio_format'),job.get('percent'),job.get('downloaded'),job.get('total'),job.get('speed'),job.get('eta'),job.get('error'),job.get('_converting'),job.get('retry_at'),int(__import__('time').time()) if job.get('retry_at') else None)
        if self.__dict__.get('_display_state')==display:return
        self._display_state=display
        quality=str(cfg.get('bitrate','192'))+' kbps' if cfg.get('mode')=='audio' else str(cfg.get('quality','1080'))
        if quality.isdigit(): quality+='p'
        container=cfg.get('audio_format','mp3').upper() if cfg.get('mode')=='audio' else ('MP4' if cfg.get('container')=='mp4' else 'Original')
        self.window.set_job_progress(self.progress,job)
        percent=job.get('percent',0)
        downloaded=(job.get('downloaded') or 0)/1024/1024
        total=(job.get('total') or 0)/1024/1024
        if state=='downloading':
            self.detail.setText(f'{percent:.0f}% · {downloaded:.1f} of {total:.1f} MiB' if total else f'{downloaded:.1f} MiB downloaded · total size unknown')
            self.timing.setText(' · '.join(str(x) for x in (job.get('speed'),job.get('eta')) if x and x!='-'))
        elif state=='processing':
            self.detail.setText(f'Creating {job.get("_conversion_format","mp4").upper()} copy - {percent:.0f}%' if job.get('_converting') else 'Preparing the file...'); self.timing.setText('Original preserved' if job.get('_converting') else 'Merging / metadata')
        elif state in ('done','skipped'): self.detail.setText((job.get('error') or 'Completed') if state=='done' else 'Already downloaded'); self.timing.setText(('Requested: '+quality) if cfg.get('mode')=='video' else container)
        elif state=='error': self.detail.setText(job.get('error') or 'Download failed. Open options for details.'); self.timing.setText('Needs attention')
        elif state=='paused': self.detail.setText(f'Paused · {percent:.0f}% saved'); self.timing.setText('Resume when ready')
        elif state=='queued':
            self.detail.setText(job.get('error') or 'Queued'); self.timing.setText(('Retry '+str(job.get('retry_count',0))+' in '+str(max(0,int(job['retry_at']-__import__('time').time())))+' s') if job.get('retry_at') else 'Waiting for a slot')
        else: self.detail.setText('Cancelled' if state=='cancelled' else 'Ready to download'); self.timing.setText('')
        failed=state=='error'
        if self.detail.property('failed')!=failed:
            self.detail.setProperty('failed',failed);self.detail.style().unpolish(self.detail);self.detail.style().polish(self.detail)
        self.progress.setVisible(state not in ('done','skipped','ready','cancelled','error'))

    def mousePressEvent(self,event):
        viewport = self.window.queue.viewport()
        position = self.mapTo(viewport, event.position().toPoint())
        forwarded = QMouseEvent(event.type(), position, event.globalPosition(),
                                event.button(), event.buttons(), event.modifiers())
        QApplication.sendEvent(viewport, forwarded)
        event.accept()

    def sizeHint(self):
        return QSize(180,44)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.title.setText(self.title.fontMetrics().elidedText(self.job['title'],Qt.ElideRight,max(20,self.width()-18)))
        # Item widgets inherit the themed stylesheet only after attachment to the
        # tree. Recalculate then, and on width changes, using polished controls.
        hint=self.sizeHint()
        if self.item.sizeHint(0)!=hint: self.item.setSizeHint(0,hint)


def build_chrome(window, outer):
    window.downloads_nav=QPushButton(window);window.downloads_nav.hide();window.downloads_nav.setCheckable(True);window.downloads_nav.clicked.connect(lambda:window.show_main_page(0))
    window.history_nav=QPushButton(window);window.history_nav.hide();window.history_nav.setCheckable(True);window.history_nav.clicked.connect(lambda:window.show_main_page(1))
    window.app_more=QToolButton();window.app_more.setText('···');window.app_more.setToolTip('Settings and app actions');window.app_more.setObjectName('rowMore')
    window.main_stack=QStackedWidget(); outer.addWidget(window.main_stack,1)
    downloads=QWidget(); layout=QVBoxLayout(downloads); layout.setContentsMargins(12,12,12,12); layout.setSpacing(8); window.download_layout=layout; window.main_stack.addWidget(downloads)
    window.queue_caption=QLabel(window);window.queue_caption.hide()
    history=QWidget(); history_layout=QVBoxLayout(history); history_layout.setContentsMargins(28,24,28,18); history_title=QLabel('History'); history_title.setObjectName('viewTitle'); history_layout.addWidget(history_title)
    history_note=QLabel('Completed downloads and recent results.'); history_note.setObjectName('muted'); history_layout.addWidget(history_note)
    window.main_history=QTreeWidget(); window.main_history.setHeaderLabels(['File','Result','Saved location']); window.main_history.header().setSectionResizeMode(0,QHeaderView.Stretch); window.main_history.setColumnWidth(2,300); history_layout.addWidget(window.main_history,1)
    window.hist=window.main_history
    actions=QHBoxLayout(); window.button('Open selected folder',window.open_history,actions).setObjectName('quietButton')
    window.remove_history_btn=window.button('Remove selected record',window.remove_history_record,actions); window.remove_history_btn.setObjectName('quietButton'); window.remove_history_btn.setEnabled(False)
    window.main_history.itemSelectionChanged.connect(lambda:window.remove_history_btn.setEnabled(bool(window.main_history.selectedItems())))
    actions.addStretch(); history_layout.addLayout(actions); window.main_stack.addWidget(history)


def show_settings(window):
    window.open_preferences()


def make_composer(window):
    # Retain default controls for config/persistence; all per-file editing is in the queue.
    window.add_dialog=QDialog(window)
    for control in (window.mode,window.quality): control.setParent(window.add_dialog)
    window.new_container=window.combo(['Original format','MP4 (remux only)'],'MP4 (remux only)' if window.container.currentIndex() else 'Original format')
    window.new_connection=window.combo(['Single connection','Multiple connections'],window.connection_mode.currentText())
    window.new_audio=window.combo(['mp3','m4a'],window.audio.currentText())
    window.new_bitrate=window.combo(['64','96','128','160','192','256','320'],window.bitrate.currentText())
    for control in (window.new_container,window.new_connection,window.new_audio,window.new_bitrate): control.setParent(window.add_dialog)
    window.new_audio.currentTextChanged.connect(window.audio.setCurrentText); window.audio.currentTextChanged.connect(window.new_audio.setCurrentText)
    window.new_bitrate.currentTextChanged.connect(window.bitrate.setCurrentText); window.bitrate.currentTextChanged.connect(window.new_bitrate.setCurrentText)
    row=QWidget(); row.setObjectName('linkEntry'); layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.setSpacing(8)
    window.link_entry_layout=layout
    window.url=QLineEdit();window.url.setPlaceholderText('Copy or paste a video / playlist link here');window.url.setClearButtonEnabled(True);layout.addWidget(window.url,1)
    window.url.textEdited.connect(window.link_edited)
    def paste_links(): window.capture_copied_links(force=True)
    window.paste_btn=window.button('Paste',paste_links,layout);window.paste_btn.setObjectName('quietButton')
    window.inspect_btn=window.button('Add',window.begin_compact_inspection,layout);window.inspect_btn.setObjectName('primaryButton');window.add_link_btn=window.inspect_btn
    window.inspect_cancel=window.button('Stop',window.cancel_inspection,layout);window.inspect_cancel.hide()
    window.url.returnPressed.connect(window.begin_compact_inspection);window.download_layout.addWidget(row)
    window.play_title=QLabel();window.play_title.setWordWrap(True);window.play_title.setTextFormat(Qt.PlainText);window.play_title.setObjectName('muted');window.download_layout.addWidget(window.play_title);window.play_title.hide()
    window.site_note=QLabel(window);window.site_note.hide()
    window.clip_notice=window.play_title
    window.pick=QTreeWidget(window.add_dialog);window.pick.setHeaderLabels(['Choose videos','Duration']);window.pick.hide()
