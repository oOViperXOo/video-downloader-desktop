"""Tiny local HTTP server with Range support, used by the resume / multi-connection tests."""
import hashlib
import http.server
import threading
import time


class RangeHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    data = b""
    delay = 0.0          # seconds to sleep per 32 KiB chunk (slows the transfer)
    support_ranges = True
    log = None           # list of (method, range_header, bytes_sent)
    lock = threading.Lock()

    def log_message(self, *a):
        pass

    def _serve(self, head):
        d = self.data
        rng = self.headers.get("Range")
        start, end, status = 0, len(d) - 1, 200
        if rng and self.support_ranges and rng.startswith("bytes="):
            a, _, b = rng[6:].partition("-")
            start = int(a) if a else 0
            end = int(b) if b else len(d) - 1
            end = min(end, len(d) - 1)
            if start >= len(d):
                self.send_response(416)
                self.send_header("Content-Range", "bytes */%d" % len(d))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            status = 206
        self.send_response(status)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("ETag", '"%s"' % hashlib.md5(d).hexdigest())
        if self.support_ranges:
            self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, len(d)))
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        sent = 0
        if not head:
            try:
                pos = start
                while pos <= end:
                    chunk = d[pos:min(pos + 32768, end + 1)]
                    self.wfile.write(chunk)
                    pos += len(chunk)
                    sent += len(chunk)
                    if self.delay:
                        time.sleep(self.delay)
            except (BrokenPipeError, ConnectionResetError):
                pass
        with self.lock:
            if self.log is not None:
                self.log.append(("HEAD" if head else "GET", rng, sent))

    def do_GET(self):
        self._serve(False)

    def do_HEAD(self):
        self._serve(True)


def start_server(data, delay=0.0, support_ranges=True):
    log = []
    handler = type("H", (RangeHandler,), dict(data=data, delay=delay, support_ranges=support_ranges, log=log,
                                              lock=threading.Lock()))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, log, "http://127.0.0.1:%d/clip.mp4" % srv.server_address[1]
