/* Pure detection logic (no browser APIs) so it can be unit-tested in node. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Detect = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  var VIDEO_EXT = ["mp4", "webm", "mkv", "mov", "m4v", "flv", "avi", "ogv", "3gp"];
  var AUDIO_EXT = ["mp3", "m4a", "ogg", "oga", "opus", "flac", "wav"];
  var SEGMENT_EXT = ["ts", "m4s", "aac", "cmfv", "cmfa", "vtt", "srt"];
  var HLS_TYPES = ["application/vnd.apple.mpegurl", "application/x-mpegurl", "audio/mpegurl", "audio/x-mpegurl", "application/mpegurl"];
  var MIN_PROGRESSIVE_BYTES = 150 * 1024; // smaller files are almost always probes/previews/segments
  var MAX_ITEMS = 50;
  // Hosts whose direct URLs are short-lived segment requests; the page URL is the right thing to send.
  var SEGMENT_HOSTS = [/(^|\.)googlevideo\.com$/i];

  function parse(url) {
    try { return new URL(url); } catch (e) { return null; }
  }
  function isHttp(url) {
    var u = parse(url);
    return !!u && (u.protocol === "http:" || u.protocol === "https:");
  }
  function extOf(u) {
    var m = /\.([a-z0-9]{2,5})$/i.exec(u.pathname);
    return m ? m[1].toLowerCase() : "";
  }
  function header(headers, name) {
    name = name.toLowerCase();
    for (var i = 0; headers && i < headers.length; i++) {
      if (String(headers[i].name).toLowerCase() === name) return String(headers[i].value || "");
    }
    return "";
  }
  function totalSize(headers) {
    var cr = /\/(\d+)\s*$/.exec(header(headers, "content-range"));
    if (cr) return parseInt(cr[1], 10);
    var cl = header(headers, "content-length");
    return /^\d+$/.test(cl) ? parseInt(cl, 10) : null;
  }

  /** Returns {kind, size} or null. kind: hls | dash | video | audio */
  function classify(url, contentType, headers) {
    var u = parse(url);
    if (!u || (u.protocol !== "http:" && u.protocol !== "https:")) return null;
    for (var i = 0; i < SEGMENT_HOSTS.length; i++) if (SEGMENT_HOSTS[i].test(u.hostname)) return null;
    var ext = extOf(u);
    var ct = String(contentType || "").split(";")[0].trim().toLowerCase();
    if (SEGMENT_EXT.indexOf(ext) >= 0 || ct === "video/mp2t" || ct === "video/iso.segment" || ct === "text/vtt") return null;
    var size = totalSize(headers);
    if (ext === "m3u8" || HLS_TYPES.indexOf(ct) >= 0) return { kind: "hls", size: null };
    if (ext === "mpd" || ct === "application/dash+xml") return { kind: "dash", size: null };
    var kind = null;
    if (VIDEO_EXT.indexOf(ext) >= 0 || ct.indexOf("video/") === 0) kind = "video";
    else if (AUDIO_EXT.indexOf(ext) >= 0 || ct.indexOf("audio/") === 0) kind = "audio";
    if (!kind) return null;
    if (size !== null && size < MIN_PROGRESSIVE_BYTES) return null;
    return { kind: kind, size: size };
  }

  function keyOf(url) {
    var u = parse(url);
    if (!u) return url;
    u.hash = "";
    return u.toString();
  }
  function nameOf(url) {
    var u = parse(url);
    if (!u) return url;
    var last = decodeSafe(u.pathname.split("/").filter(Boolean).pop() || "");
    return last || u.hostname;
  }
  function decodeSafe(s) { try { return decodeURIComponent(s); } catch (e) { return s; } }

  /** Immutable add: dedupes by URL, newest first, capped. */
  function addItem(list, item) {
    var key = keyOf(item.url);
    var rest = (list || []).filter(function (x) { return keyOf(x.url) !== key; });
    var existing = (list || []).filter(function (x) { return keyOf(x.url) === key; })[0];
    var merged = existing ? Object.assign({}, existing, item) : item;
    return [merged].concat(rest).slice(0, MAX_ITEMS);
  }

  /** Items found in the page DOM: [{src, kind}] -> filtered, http(s) only (blob:/data: dropped). */
  function pageItems(found) {
    var out = [];
    (found || []).forEach(function (f) {
      if (!f || !isHttp(f.src)) return;
      var c = classify(f.src, "", null);
      out.push({ url: f.src, kind: c ? c.kind : (f.kind || "video"), source: "page", size: null });
    });
    return out;
  }

  return { classify: classify, keyOf: keyOf, nameOf: nameOf, addItem: addItem, pageItems: pageItems,
           isHttp: isHttp, header: header, totalSize: totalSize, MAX_ITEMS: MAX_ITEMS };
});
