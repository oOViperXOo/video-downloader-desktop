"""Capture Settings/menu evidence using an isolated store and no receiver."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
import app

app.DEFAULTS['receiver']=False
screenshots=Path(__file__).resolve().parents[1]/'docs'/'screenshots';screenshots.mkdir(parents=True,exist_ok=True)
qt=QApplication([]); qt.setStyle('Fusion'); QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
store=app.Store(Path('test-temp/settings-review'));store.data['settings']['theme']='Dark'
window=app.Window(store)
window.show(); window.open_preferences(); qt.processEvents()
print('Menu:',[a.text() for a in window.app_more.menu().actions()])
print('Categories:',[window.settings_nav.item(i).text() for i in range(window.settings_nav.count())])
print('Dialog title:',window.advanced.windowTitle())
window.advanced.grab().save(str(screenshots/'settings-review-dark.png'))
window.theme.setCurrentText('Light'); window.save_settings(); qt.processEvents(); window.advanced.grab().save(str(screenshots/'settings-review-light.png'))
window.advanced.reject(); window.show_main_page(0)
window.app_more.menu().actions()[1].trigger(); qt.processEvents()
print('Diagnostics separate:',window.diagnostics.isVisible() and not window.advanced.isVisible())
window.diagnostics.close(); window.close()
