"""Exercise native tray availability/minimize/restore using isolated app state."""
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication,QSystemTrayIcon
import app

app.DEFAULTS['receiver']=False
qt=QApplication([]);qt.setStyle('Fusion');errors=[]
root=Path(__file__).resolve().parents[1]/'test-temp';root.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='native-tray-',dir=root) as folder:
    window=app.Window(app.Store(folder));window.show()
    available=QSystemTrayIcon.isSystemTrayAvailable()
    def check_restore():
        try:
            assert window.isVisible() and not window.isMinimized()
            assert window.feature_timer.isActive() and not window.closing
        except Exception as exc:errors.append(str(exc) or 'Restore assertion failed')
        window.close();qt.quit()
    def check_minimized():
        try:
            assert window.isMinimized()
            assert window.isVisible()!=available
            assert window.feature_timer.isActive() and not window.closing
            window.restore_from_tray()
            QTimer.singleShot(300,check_restore)
        except Exception as exc:
            errors.append(str(exc) or 'Minimize assertion failed');window.close();qt.quit()
    QTimer.singleShot(300,window.showMinimized)
    QTimer.singleShot(700,check_minimized)
    qt.exec()
if errors:raise RuntimeError('; '.join(errors))
print('Native tray minimize/restore passed.' if available else 'Native tray unavailable; normal taskbar fallback passed.')
