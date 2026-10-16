import os
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
try:
    import app as _app
    _app.DEFAULTS['receiver'] = False      # tests must not bind the real receiver port unless they ask for it
    _app.Window.RECEIVER_PORT = 0
except ImportError:
    pass
