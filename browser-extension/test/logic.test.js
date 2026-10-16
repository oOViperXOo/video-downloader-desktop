const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const D = require("../lib/detect.js");
const C = require("../lib/client.js");
const h = (o) => Object.entries(o).map(([name, value]) => ({ name, value }));

test("classify: HLS/DASH by extension and content type", () => {
  assert.equal(D.classify("https://a.com/x/master.m3u8?t=1", "", []).kind, "hls");
  assert.equal(D.classify("https://a.com/x", "application/vnd.apple.mpegurl; charset=utf-8", []).kind, "hls");
  assert.equal(D.classify("https://a.com/x", "application/x-mpegURL", []).kind, "hls");
  assert.equal(D.classify("https://a.com/m.mpd", "", []).kind, "dash");
  assert.equal(D.classify("https://a.com/m", "application/dash+xml", []).kind, "dash");
});
test("classify: progressive video/audio and size floor", () => {
  assert.equal(D.classify("https://a.com/v.mp4", "video/mp4", h({ "content-length": "5000000" })).kind, "video");
  assert.equal(D.classify("https://a.com/v.mp4", "video/mp4", h({ "content-length": "5000000" })).size, 5000000);
  assert.equal(D.classify("https://a.com/v.mp4", "video/mp4", h({ "content-length": "1000" })), null);
  assert.equal(D.classify("https://a.com/v.webm", "application/octet-stream", []).kind, "video");
  assert.equal(D.classify("https://a.com/s.mp3", "audio/mpeg", h({ "content-length": "4000000" })).kind, "audio");
});
test("classify: 206 uses Content-Range total, not partial length", () => {
  const r = D.classify("https://a.com/v.mp4", "video/mp4", h({ "content-length": "1000", "content-range": "bytes 0-999/9000000" }));
  assert.equal(r.size, 9000000);
});
test("classify: ignores segments, subtitles, googlevideo, non-http", () => {
  for (const [u, ct] of [["https://a.com/seg1.ts", "video/mp2t"], ["https://a.com/x", "video/mp2t"], ["https://a.com/i.m4s", ""],
    ["https://a.com/s.vtt", "text/vtt"], ["https://r1.googlevideo.com/videoplayback?x=1", "video/mp4"],
    ["blob:https://a.com/abc", "video/mp4"], ["data:video/mp4;base64,AA", ""], ["ftp://a.com/v.mp4", ""], ["https://a.com/page.html", "text/html"], ["notaurl", ""]])
    assert.equal(D.classify(u, ct, []), null, u);
});
test("addItem dedupes by URL ignoring hash, newest first, capped", () => {
  let l = [];
  l = D.addItem(l, { url: "https://a.com/1.m3u8#x", kind: "hls" });
  l = D.addItem(l, { url: "https://a.com/2.mp4", kind: "video" });
  l = D.addItem(l, { url: "https://a.com/1.m3u8#y", kind: "hls" });
  assert.deepEqual(l.map((x) => x.url), ["https://a.com/1.m3u8#y", "https://a.com/2.mp4"]);
  for (let i = 0; i < 80; i++) l = D.addItem(l, { url: "https://a.com/v" + i + ".mp4", kind: "video" });
  assert.equal(l.length, D.MAX_ITEMS);
  assert.equal(l[0].url, "https://a.com/v79.mp4");
});
test("pageItems drops blob/data, keeps http(s)", () => {
  const r = D.pageItems([{ src: "blob:https://a.com/1", kind: "video" }, { src: "https://a.com/v.mp4", kind: "video" }, { src: "data:x", kind: "video" }, null]);
  assert.equal(r.length, 1); assert.equal(r[0].url, "https://a.com/v.mp4");
});
test("nameOf", () => {
  assert.equal(D.nameOf("https://a.com/path/My%20Video.mp4?x=1"), "My Video.mp4");
  assert.equal(D.nameOf("https://a.com/"), "a.com");
});
test("buildPayload: headers, cookie opt-in, scheme check", () => {
  const p = C.buildPayload({ url: "https://a.com/v.m3u8", pageUrl: "https://a.com/w", title: "T", kind: "hls", userAgent: "UA" });
  assert.deepEqual(p.headers, { Referer: "https://a.com/w", "User-Agent": "UA" });
  assert.equal(p.v, 1); assert.ok(!("Cookie" in p.headers));
  assert.equal(C.buildPayload({ url: "https://a.com/v", cookie: "a=b" }).headers.Cookie, "a=b");
  assert.equal(C.buildPayload({ url: "https://a.com/v", pageUrl: "file:///x" }).page_url, "");
  assert.throws(() => C.buildPayload({ url: "file:///etc/passwd" }), /scheme_not_allowed/);
  assert.throws(() => C.buildPayload({ url: "javascript:alert(1)" }), /scheme_not_allowed/);
  assert.equal(C.buildPayload({ url: "https://a.com/v", title: "x".repeat(999) }).title.length, 300);
});
test("cookieHeader", () => assert.equal(C.cookieHeader([{ name: "a", value: "1" }, { name: "b", value: "2" }, null]), "a=1; b=2"));
test("send: no token -> not_paired without network", async () => {
  let called = false;
  const r = await C.send(async () => { called = true; }, 17653, "", {});
  assert.deepEqual(r, { ok: false, error: "not_paired" }); assert.equal(called, false);
});
test("send/pair/ping: request shape and error mapping", async () => {
  const seen = [];
  const f = (status, body) => async (url, opts) => { seen.push({ url, opts }); return { ok: status < 300, status, json: async () => body }; };
  let r = await C.send(f(202, { ok: true, id: "x" }), 17653, "tok", { url: "u" });
  assert.equal(r.ok, true);
  assert.equal(seen[0].url, "http://127.0.0.1:17653/v1/download");
  assert.equal(seen[0].opts.headers.Authorization, "Bearer tok");
  assert.equal(seen[0].opts.credentials, "omit"); assert.equal(seen[0].opts.redirect, "error");
  r = await C.send(f(422, { error: "private_address" }), 1, "tok", {}); assert.equal(r.error, "private_address");
  assert.match(C.friendly(r.error), /private/);
  r = await C.pair(f(403, { error: "bad_pairing_code" }), 17653, " 1234-5678 ");
  assert.equal(r.error, "bad_pairing_code"); assert.equal(JSON.parse(seen.at(-1).opts.body).code, "1234-5678");
  r = await C.ping(async () => { throw new TypeError("fail"); }, 17653, "");
  assert.equal(r.error, "app_unreachable");
});
test("client only ever targets 127.0.0.1", async () => {
  const urls = [];
  const f = async (u) => { urls.push(u); return { ok: true, status: 200, json: async () => ({}) }; };
  await C.ping(f, "17653; evil", ""); await C.send(f, undefined, "t", {});
  urls.forEach((u) => assert.match(u, /^http:\/\/127\.0\.0\.1:/));
});
