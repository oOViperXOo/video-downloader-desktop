from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
import app

app.DEFAULTS['receiver']=False
screenshots=Path(__file__).resolve().parents[1]/'docs'/'screenshots';screenshots.mkdir(parents=True,exist_ok=True)
qt=QApplication([]);qt.setStyle('Fusion');QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
store=app.Store(Path('test-temp/compact-preview'));store.data['settings']['theme']='Dark'
window=app.Window(store)
window.jobs.clear()
for i,(title,status,percent,total,rate) in enumerate([
    ('Lola El Banat — Official music video','downloading',63,56.5,3.2),
    ('Me at the zoo','downloading',28,4.8,1.7),
    ('Designing a calmer workspace','queued',0,82.4,0),
    ('Weekend highlights','done',100,32.6,0)]):
    window.jobs.append(dict(id=str(i),title=title,url='https://www.youtube.com/watch?v='+str(i),status=status,percent=percent,total=total*1024*1024,downloaded=total*percent/100*1024*1024,speed=f'{rate:.1f} MiB/s',speed_bytes=rate*1024*1024,eta='7 s',config=dict(app.DEFAULTS),error=''))
window.workers={j['id']:SimpleNamespace(job=j) for j in window.jobs[:2]};window.active=window.jobs[0]
window.expanded_jobs.add('2');window.refresh_queue();window.show();qt.processEvents()
window.grab().save(str(screenshots/'compact-preview-dark.png'))
window.theme.setCurrentText('Light');window.apply_theme();qt.processEvents();window.grab().save(str(screenshots/'compact-preview-light.png'))
window.open_add_dialog();qt.processEvents();window.url.parentWidget().grab().save(str(screenshots/'compact-link-entry.png'))
row=window.row_widgets['2'];row.advanced_toggle.setChecked(False);row.open_options();qt.processEvents();row.settings_dialog.grab().save(str(screenshots/'download-options-light.png'))
window.theme.setCurrentText('Dark');window.apply_theme();qt.processEvents();row.settings_dialog.grab().save(str(screenshots/'download-options-dark.png'));row.settings_dialog.hide()
window.workers.clear();window.active=None;window.jobs.clear();window.close()
