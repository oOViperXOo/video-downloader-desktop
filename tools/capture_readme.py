"""Capture the real compact window with isolated illustrative queue data."""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer,QEventLoop
import app

root=Path(__file__).resolve().parents[1]
qt=QApplication([]);qt.setStyle('Fusion');qt.setFont(QFont('Segoe UI',10))
app.DEFAULTS.update(receiver=False,clipboard=False)
store=app.Store(root/'test-temp'/'readme-screenshot')
store.data['settings'].update(theme='Dark',receiver=False,clipboard=False)
window=app.Window(store)
for timer in window.findChildren(QTimer):timer.stop()
window.start_next=lambda:None
window.jobs.clear()
samples=[
    ('01 - A guide to better photography','downloading',64,85.2,4.6,'1080'),
    ('02 - Understanding light and composition','downloading',31,62.8,2.3,'1080'),
    ('03 - Simple editing techniques','ready',0,0,0,'720'),
    ('A weekend in the mountains','paused',42,128.4,0,'1080'),
    ('Creative workspace tour','done',100,74.6,0,'1080'),
]
for i,(title,status,percent,total,rate,quality) in enumerate(samples):
    cfg=dict(app.DEFAULTS,quality=quality)
    window.jobs.append(dict(id=str(i),title=title,url=f'https://example.com/video/{i}',status=status,
        percent=percent,total=total*1024*1024,downloaded=total*percent/100*1024*1024,
        speed=f'{rate:.1f} MiB/s' if rate else '-',speed_bytes=rate*1024*1024,
        eta='7 s' if i==0 else '19 s',config=cfg,error=''))
window.workers={j['id']:SimpleNamespace(job=j) for j in window.jobs[:2]}
window.active=window.jobs[0]
window.refresh_queue();window.resize(1040,520);window.show()
loop=QEventLoop();QTimer.singleShot(500,loop.quit);loop.exec()
window.queue.fit_columns();window.queue.doItemsLayout();qt.processEvents()
output=root/'docs'/'screenshots'/'orvanta-downloads.png'
assert window.grab().save(str(output))
print(output)
window.workers.clear();window.active=None;window.jobs.clear();window.close()
