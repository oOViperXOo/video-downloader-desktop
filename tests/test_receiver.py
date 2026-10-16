import http.client, json, os, stat, tempfile, unittest
import receiver as R

ORIGIN = "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
FAKE_DNS = {"example.com": ["93.184.216.34"], "rebind.test": ["127.0.0.1"],
            "mixed.test": ["93.184.216.34", "10.0.0.5"], "v6.test": ["::ffff:192.168.1.1"]}

def resolver(host):
    if host in FAKE_DNS:
        return FAKE_DNS[host]
    raise OSError("nxdomain")

class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.jobs = []
        self.now = [0.0]
        self.r = R.Receiver(self.jobs.append, os.path.join(self.tmp.name, "r.json"), port=0,
                            resolver=resolver, clock=lambda: self.now[0])
        self.port = self.r.start()
    def tearDown(self):
        self.r.stop(); self.tmp.cleanup()
    def req(self, method, path, body=None, headers=None, host=None, origin=ORIGIN, raw=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = {"Host": host or "127.0.0.1:%d" % self.port}
        if origin: h["Origin"] = origin
        if body is not None or raw is not None:
            h["Content-Type"] = "application/json"
        h.update(headers or {})
        data = raw if raw is not None else (json.dumps(body) if body is not None else None)
        c.request(method, path, body=data, headers=h)
        resp = c.getresponse(); txt = resp.read().decode()
        out = (resp.status, json.loads(txt) if txt else {}, dict(resp.getheaders()))
        c.close(); return out
    def pair(self):
        code = self.r.new_pairing_code()
        st, body, _ = self.req("POST", "/v1/pair", {"code": code})
        self.assertEqual(st, 200); return body["token"]
    def dl(self, token, payload, **kw):
        return self.req("POST", "/v1/download", payload, {"Authorization": "Bearer " + token}, **kw)

class TestServer(Base):
    def test_binds_loopback_only(self):
        self.assertEqual(self.r._httpd.server_address[0], "127.0.0.1")
    def test_ping_unpaired_then_paired(self):
        st, b, h = self.req("POST", "/v1/ping")
        self.assertEqual((st, b["paired"]), (200, False))
        self.assertEqual(h["Access-Control-Allow-Origin"], ORIGIN)
        t = self.pair()
        st, b, _ = self.req("POST", "/v1/ping", headers={"Authorization": "Bearer " + t})
        self.assertTrue(b["paired"])
    def test_web_page_origin_rejected(self):
        for o in ("https://evil.example", "http://127.0.0.1:%d" % self.port, "null", "file://", "chrome-extension://x"):
            st, b, h = self.req("POST", "/v1/ping", origin=o)
            self.assertEqual((st, b["error"]), (403, "bad_origin"), o)
            self.assertNotIn("Access-Control-Allow-Origin", h)
    def test_get_not_supported(self):
        self.assertEqual(self.req("GET", "/v1/ping")[0], 405)
        self.assertEqual(self.req("GET", "/v1/ping", origin="https://evil.example")[0], 403)
    def test_missing_origin_rejected(self):
        self.assertEqual(self.req("POST", "/v1/ping", origin=None)[0], 403)
    def test_dns_rebinding_host_rejected(self):
        st, b, _ = self.req("POST", "/v1/ping", host="evil.example:%d" % self.port)
        self.assertEqual((st, b["error"]), (403, "bad_host"))
        self.assertEqual(self.req("POST", "/v1/ping", host="localhost:%d" % self.port)[0], 200)
    def test_preflight(self):
        st, _, h = self.req("OPTIONS", "/v1/download", headers={"Access-Control-Request-Method": "POST"})
        self.assertEqual(st, 204)
        self.assertEqual(h["Access-Control-Allow-Origin"], ORIGIN)
        self.assertEqual(h["Access-Control-Allow-Private-Network"], "true")
        self.assertEqual(self.req("OPTIONS", "/v1/download", origin="https://evil.example")[0], 403)
    def test_download_requires_token(self):
        self.assertEqual(self.req("POST", "/v1/download", {"url": "https://example.com/a.mp4"})[0], 401)
        self.assertEqual(self.dl("wrong", {"url": "https://example.com/a.mp4"})[0], 401)
        self.assertEqual(self.jobs, [])
    def test_token_bound_to_origin(self):
        t = self.pair()
        other = "moz-extension://11111111-2222-3333-4444-555555555555"
        self.assertEqual(self.dl(t, {"url": "https://example.com/a.mp4"}, origin=other)[0], 401)
    def test_happy_path_and_header_allowlist(self):
        t = self.pair()
        st, b, _ = self.dl(t, {"v": 1, "url": "https://example.com/v/index.m3u8", "page_url": "https://example.com/watch",
                               "title": "Hi\nthere", "kind": "hls",
                               "headers": {"referer": "https://example.com/watch", "Cookie": "a=b", "X-Evil": "1", "Host": "x"}})
        self.assertEqual((st, b["ok"]), (202, True))
        j = self.jobs[0]
        self.assertEqual(j["headers"], {"Referer": "https://example.com/watch", "Cookie": "a=b"})
        self.assertEqual(j["title"], "Hi there"); self.assertEqual(j["kind"], "hls"); self.assertEqual(j["origin"], ORIGIN)
    def test_bad_urls_rejected(self):
        t = self.pair()
        bad = ["file:///etc/passwd", "ftp://example.com/a", "javascript:alert(1)", "data:text/plain,hi",
               "http://localhost/a", "http://127.0.0.1/a", "http://[::1]/a", "http://10.1.2.3/a",
               "http://192.168.0.1/a", "http://169.254.169.254/latest", "http://2130706433/a", "http://0x7f.1/a",
               "http://rebind.test/a", "http://mixed.test/a", "http://v6.test/a", "http://nxdomain.test/a",
               "http://100.64.0.1/a", "http://printer.local/a", "https://user:pw@example.com/a",
               "https://example.com/a b", "http://example.com:99999/a", "", None, 5, "https://example.com/" + "a" * 9000]
        for u in bad:
            self.now[0] += 10
            st, b, _ = self.dl(t, {"url": u})
            self.assertEqual(st, 422, u)
        self.assertEqual(self.jobs, [])
    def test_bad_requests(self):
        t = self.pair()
        self.assertEqual(self.dl(t, [1])[0], 422)
        self.assertEqual(self.dl(t, {"v": 2, "url": "https://example.com/a"})[0], 422)
        self.assertEqual(self.dl(t, {"url": "https://example.com/a", "headers": {"Cookie": "a\r\nX: y"}})[0], 422)
        self.assertEqual(self.dl(t, {"url": "https://example.com/a", "page_url": "file:///x"})[0], 422)
        self.assertEqual(self.req("POST", "/v1/download", raw="{nope", headers={"Authorization": "Bearer " + t})[0], 400)
        self.assertEqual(self.req("POST", "/v1/download", raw="x" * 70000, headers={"Authorization": "Bearer " + t})[0], 413)
        st, _, _ = self.req("POST", "/v1/download", raw="{}", headers={"Authorization": "Bearer " + t, "Content-Type": "text/plain"})
        self.assertEqual(st, 415)
        self.assertEqual(self.req("POST", "/v1/nope")[0], 404)
    def test_rate_limit_downloads(self):
        t = self.pair(); codes = []
        for _ in range(14):
            codes.append(self.dl(t, {"url": "https://example.com/a.mp4"})[0])
        self.assertEqual(codes.count(202), 10); self.assertIn(429, codes)
        self.now[0] += 5
        self.assertEqual(self.dl(t, {"url": "https://example.com/a.mp4"})[0], 202)

class TestPairing(Base):
    def test_wrong_code_and_lockout(self):
        code = self.r.new_pairing_code()
        for _ in range(R.PAIR_MAX_FAILS):
            self.assertEqual(self.req("POST", "/v1/pair", {"code": "0000-0000" if code != "0000-0000" else "1111-1111"})[0], 403)
        self.now[0] += 120  # let the pair rate limit refill; code is already burned
        self.assertEqual(self.req("POST", "/v1/pair", {"code": code})[0], 403)
    def test_pair_rate_limit(self):
        self.r.new_pairing_code(); sts = [self.req("POST", "/v1/pair", {"code": "x"})[0] for _ in range(8)]
        self.assertIn(429, sts)
    def test_code_single_use_and_expiry(self):
        code = self.r.new_pairing_code()
        self.assertEqual(self.req("POST", "/v1/pair", {"code": code})[0], 200)
        self.assertEqual(self.req("POST", "/v1/pair", {"code": code})[0], 403)
        code = self.r.new_pairing_code(); self.now[0] += 121
        self.assertEqual(self.req("POST", "/v1/pair", {"code": code})[0], 403)
    def test_no_code_issued(self):
        self.assertEqual(self.req("POST", "/v1/pair", {"code": "0000-0000"})[0], 403)
    def test_web_origin_cannot_pair(self):
        code = self.r.new_pairing_code()
        self.assertEqual(self.req("POST", "/v1/pair", {"code": code}, origin="https://evil.example")[0], 403)
    def test_state_file_private_and_hashed_and_persistent(self):
        t = self.pair(); p = self.r.state_path
        self.assertNotIn(t, open(p).read())
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
        r2 = R.Receiver(lambda j: None, p, port=0); self.assertTrue(r2._token_ok(ORIGIN, "Bearer " + t))
    def test_revoke(self):
        t = self.pair(); self.r.revoke_all()
        self.assertEqual(self.dl(t, {"url": "https://example.com/a"})[0], 401)

class TestMisc(unittest.TestCase):
    def test_callback_failure_is_500_without_leak(self):
        with tempfile.TemporaryDirectory() as d:
            def boom(j): raise RuntimeError("secret detail")
            r = R.Receiver(boom, os.path.join(d, "s.json"), port=0, resolver=resolver); r.start()
            try:
                code = r.new_pairing_code()
                def call(path, body, tok=None):
                    c = http.client.HTTPConnection("127.0.0.1", r.port)
                    h = {"Host": "127.0.0.1:%d" % r.port, "Origin": ORIGIN, "Content-Type": "application/json"}
                    if tok: h["Authorization"] = "Bearer " + tok
                    c.request("POST", path, json.dumps(body), h); x = c.getresponse(); return x.status, x.read().decode()
                st, txt = call("/v1/pair", {"code": code}); tok = json.loads(txt)["token"]
                st, txt = call("/v1/download", {"url": "https://example.com/a"}, tok)
                self.assertEqual(st, 500); self.assertNotIn("secret", txt)
            finally: r.stop()
    def test_cookie_file_and_args(self):
        with tempfile.TemporaryDirectory() as d:
            p = R.cookie_header_to_netscape("a=b; c=d", "https://example.com/x", os.path.join(d, "c.txt"))
            txt = open(p).read()
            self.assertIn("example.com\tFALSE\t/\tTRUE\t0\ta\tb", txt)
            if os.name == "posix": self.assertEqual(stat.S_IMODE(os.stat(p).st_mode), 0o600)
        a = R.ytdlp_args({"headers": {"Referer": "https://r/", "User-Agent": "UA", "Cookie": "a=b"}}, "/tmp/c")
        self.assertEqual(a, ["--referer", "https://r/", "--user-agent", "UA", "--cookies", "/tmp/c"])
        self.assertNotIn("a=b", a)
    def test_no_shell_use(self):
        src = open(R.__file__).read()
        for bad in ("subprocess", "os.system", "os.popen", "shell=True", "eval(", "exec("):
            self.assertNotIn(bad, src)

if __name__ == "__main__":
    unittest.main()
