"""One GUI per user, with a local activation signal for repeat launches."""
import hashlib
from pathlib import Path
from PySide6.QtCore import QObject,QLockFile,QTimer
from PySide6.QtNetwork import QLocalServer,QLocalSocket


class SingleInstance(QObject):
    def __init__(self,directory,parent=None):
        super().__init__(parent)
        directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
        self.lock=QLockFile(str(directory/'app-instance.lock'));self.lock.setStaleLockTime(0)
        self.name='orvanta-video-'+hashlib.sha256(str(directory.resolve()).lower().encode()).hexdigest()[:24]
        self.server=None;self.callback=None;self.pending=False

    def acquire(self):
        if not self.lock.tryLock(0):
            if self.lock.error()!=QLockFile.LockFailedError:raise OSError('Cannot access the application instance lock.')
            import sys
            if sys.platform=='win32':
                import ctypes
                pid,_,_=self.lock.getLockInfo()
                if pid>0:ctypes.windll.user32.AllowSetForegroundWindow(int(pid))
            socket=QLocalSocket();socket.connectToServer(self.name)
            if socket.waitForConnected(1500):socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.name)
        self.server=QLocalServer(self);self.server.setSocketOptions(QLocalServer.UserAccessOption)
        self.server.newConnection.connect(self.activate)
        if not self.server.listen(self.name):
            self.lock.unlock();raise OSError('Cannot create the application activation channel.')
        return True

    def activate(self):
        while self.server.hasPendingConnections():
            socket=self.server.nextPendingConnection();socket.close();socket.deleteLater()
        if self.callback:self.callback()
        else:self.pending=True

    def set_window(self,window):
        self.callback=window.restore_from_tray
        if self.pending:QTimer.singleShot(0,self.callback)

    def close(self):
        if self.server:self.server.close()
        self.lock.unlock()
