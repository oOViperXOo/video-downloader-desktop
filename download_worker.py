"""One isolated GUI download process and its UTF-8 event stream."""
import codecs
import json

from PySide6.QtCore import QObject, QProcess, QTimer


class DownloadWorker(QObject):
    def __init__(self, window, job, config_path):
        super().__init__(window)
        self.window, self.job, self.config_path = window, job, config_path
        self.process = QProcess(self)
        self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.buffer = ''
        self.reason = None
        self.finished = False
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.read_errors)
        self.process.finished.connect(self.finish)
        self.process.errorOccurred.connect(self.failed)

    def start(self):
        args=['--convert',str(self.config_path),self.job['path']] if self.job.get('_converting') else ['--download',str(self.config_path),self.job['url']]
        self.window.command(self.process,args)

    def read(self):
        self.buffer += self.decoder.decode(bytes(self.process.readAllStandardOutput()))
        while '\n' in self.buffer:
            line, self.buffer = self.buffer.split('\n', 1)
            self.handle_line(line)

    def handle_line(self, line):
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                raise ValueError('Invalid worker event')
            self.window.handle_engine_event(event, self.job)
        except (ValueError, TypeError):
            self.window.append_log(line)

    def read_errors(self):
        text = bytes(self.process.readAllStandardError()).decode('utf-8', 'replace')
        if text.strip():
            self.window.append_log(self.job['title'] + ': ' + text)

    def failed(self, error):
        if self.finished:
            return
        self.window.append_log(self.job['title'] + ': ' + self.process.errorString())
        if error == QProcess.FailedToStart:
            self.job['error'] = self.process.errorString()
            self.finish(-1)

    def finish(self, code, *args):
        if self.finished:
            return
        self.finished = True
        self.read()
        self.read_errors()
        self.buffer += self.decoder.decode(b'', final=True)
        if self.buffer.strip():
            self.handle_line(self.buffer)
        self.window.worker_finished(self, code)

    def stop(self, reason):
        from app import stop_process_tree
        self.reason = reason
        stop_process_tree(self.process)
        QTimer.singleShot(2500, self.force_stop)

    def force_stop(self):
        if not self.finished and self.process.state() != QProcess.NotRunning:
            from app import stop_process_tree
            stop_process_tree(self.process, force=True)
