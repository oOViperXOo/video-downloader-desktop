import sys, os, json, threading, time
sys.path.insert(0,'/tmp/out/receiver-patch')
import receiver as R
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
jobs=[]
def on_job(j): jobs.append(j); open('/tmp/e2e/jobs.json','w').write(json.dumps(jobs))
r=R.Receiver(on_job,'/tmp/e2e/state.json',port=17653,allow_private=True); r.start()
open('/tmp/e2e/code.txt','w').write(r.new_pairing_code())
PAGE=b'<html><head><title>Demo clip page</title></head><body><h1>Demo</h1><video id=v controls src="/clip.mp4"></video><script>fetch("/live/master.m3u8").then(r=>r.text());fetch("/seg0.ts");fetch("/tiny.mp4")</script></body></html>'
class H(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        p=self.path.split('?')[0]
        if p=='/': b,ct=PAGE,'text/html'
        elif p=='/clip.mp4': b,ct=os.urandom(400000),'video/mp4'
        elif p=='/tiny.mp4': b,ct=os.urandom(500),'video/mp4'
        elif p=='/live/master.m3u8': b,ct=b'#EXTM3U\n',"application/vnd.apple.mpegurl"
        elif p=='/seg0.ts': b,ct=os.urandom(2000),'video/mp2t'
        else: self.send_response(404); self.end_headers(); return
        self.send_response(200); self.send_header('Content-Type',ct); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b)
ThreadingHTTPServer(('127.0.0.1',8099),H).serve_forever()
