from PySide6.QtCore import Qt,QPoint,QPointF,QCoreApplication,QEvent
from PySide6.QtGui import QWheelEvent,QPalette
from PySide6.QtWidgets import QWidget,QVBoxLayout,QAbstractItemView
from PySide6.QtTest import QTest
from compact_ui import VisibleComboBox
from app import Window,Store,DEFAULTS
from test_process import app


def test_popup_scrolls_limits_geometry_and_selects_data():
    host=QWidget();host.resize(500,280);layout=QVBoxLayout(host);combo=VisibleComboBox();layout.addWidget(combo)
    for i in range(70):combo.addItem(f'Format {i} - '+('long codec and metadata '*12),str(i))
    host.show();app.processEvents()
    wheel=QWheelEvent(QPointF(10,10),QPointF(combo.mapToGlobal(QPoint(10,10))),QPoint(),QPoint(0,-120),Qt.NoButton,Qt.NoModifier,Qt.NoScrollPhase,False)
    app.sendEvent(combo,wheel);assert combo.currentData()=='0'
    combo.showPopup();app.processEvents();view=combo.view();popup=view.window()
    assert view.isVisible() and popup.width()<=704 and popup.height()<=max(20,view.sizeHintForRow(0))*8+8
    assert view.verticalScrollBar().maximum()>0
    target=combo.model().index(50,0);view.scrollTo(target,QAbstractItemView.PositionAtCenter);app.processEvents()
    assert view.visualRect(target).intersects(view.viewport().rect())
    QTest.mouseClick(view.viewport(),Qt.LeftButton,pos=view.visualRect(target).center());app.processEvents()
    assert combo.currentData()=='50' and not view.isVisible()
    host.close();host.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_dependent_format_resolution_and_audio_choices_remain_consistent(tmp_path):
    w=Window(Store(tmp_path));w.show()
    job=dict(id='combo',title='Video',url='https://vimeo.com/1',status='ready',percent=0,error='',
             config=dict(DEFAULTS,format_id='18',convert_mp4=True),estimated_bytes=100,selected_format={'estimated_size':100},
             formats=[dict(selector='18',label='360p MP4',height=360,vcodec='h264',acodec='aac',estimated_size=100),dict(selector='22',label='720p MP4',height=720,vcodec='h264',acodec='aac',estimated_size=200)])
    w.jobs.append(job);w.refresh_queue();app.processEvents()
    row=w.row_widgets['combo'];row.open_options();row.advanced_toggle.setChecked(True);w.activateWindow();QTest.qWait(100);row.format.setFocus();row.format.showPopup();QTest.qWait(100)
    index=row.format.model().index(row.format.findData('22'),0)
    QTest.mouseClick(row.format.view().viewport(),Qt.LeftButton,pos=row.format.view().visualRect(index).center());app.processEvents()
    assert job['config']['format_id']=='22' and job['config']['quality']=='720' and job['estimated_bytes']==200
    assert w.row_widgets['combo'].format is row.format
    assert not row.format.view().isVisible()
    row=w.row_widgets['combo'];row.quality.setCurrentText('360p');app.processEvents()
    assert job['config']['format_id']=='' and job['selected_format']=={} and job['estimated_bytes'] is None
    row=w.row_widgets['combo'];row.mode.setCurrentText('Audio');app.processEvents()
    row=w.row_widgets['combo'];assert 'kbps' in row.quality.currentText() and row.container.itemText(0)=='MP3' and not job['config']['convert_mp4']
    row.container.setCurrentText('M4A');app.processEvents();assert job['config']['audio_format']=='m4a'
    row=w.row_widgets['combo'];row.mode.setCurrentText('Video');app.processEvents();assert w.row_widgets['combo'].quality.currentText()=='360p'
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)


def test_popup_palette_tracks_light_and_dark_theme(tmp_path):
    w=Window(Store(tmp_path));w.show()
    for theme,color in [('Light','#ffffff'),('Dark','#191f29'),('Light','#ffffff')]:
        w.theme.setCurrentText(theme);w.apply_theme();app.processEvents()
        combo=w.quality;combo.ensurePolished();combo.view().ensurePolished()
        assert combo.palette().color(QPalette.Base).name()==color
        assert combo.view().palette().color(QPalette.Base).name()==color
    w.close();w.deleteLater();QCoreApplication.sendPostedEvents(None,QEvent.DeferredDelete)
