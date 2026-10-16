/* Receiver client logic. Pure except for the injected fetch, so it can be unit-tested. */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.Client = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var DEFAULT_PORT = 17653;
  var ERRORS = {
    not_paired: "Not paired. Open the extension options and enter the pairing code shown in the app.",
    app_unreachable: "Could not reach the app. Is it running with the browser receiver enabled?",
    bad_pairing_code: "Pairing code wrong or expired. Generate a new one in the app.",
    private_address: "The app refuses local/private network addresses.",
    scheme_not_allowed: "Only http and https links can be sent.",
    rate_limited: "Too many requests. Wait a few seconds.",
    bad_url: "The app did not accept that URL.",
    unresolvable_host: "The app could not resolve that host name.",
    credentials_not_allowed: "URLs with a username/password are refused.",
    app_error: "The app failed to queue the download."
  };
  function friendly(code) { return ERRORS[code] || ("The app rejected the request (" + code + ")."); }

  function isHttp(u) { return /^https?:\/\//i.test(String(u || "")); }

  function cookieHeader(cookies) {
    return (cookies || []).filter(function (c) { return c && c.name; })
      .map(function (c) { return c.name + "=" + c.value; }).join("; ");
  }

  /** Build the wire payload. Cookie is included only when the caller passes one. */
  function buildPayload(o) {
    if (!isHttp(o.url)) throw new Error("scheme_not_allowed");
    var headers = {};
    if (isHttp(o.pageUrl)) headers.Referer = o.pageUrl;
    if (o.userAgent) headers["User-Agent"] = o.userAgent;
    if (o.cookie) headers.Cookie = o.cookie;
    return { v: 1, url: o.url, page_url: isHttp(o.pageUrl) ? o.pageUrl : "", title: String(o.title || "").slice(0, 300),
             kind: o.kind || "link", headers: headers };
  }

  function base(port) { return "http://127.0.0.1:" + (port || DEFAULT_PORT); }

  async function call(fetchImpl, port, path, method, body, token) {
    var h = {};
    if (body) h["Content-Type"] = "application/json";
    if (token) h.Authorization = "Bearer " + token;
    var res;
    try {
      res = await fetchImpl(base(port) + path, { method: method, headers: h, body: body ? JSON.stringify(body) : undefined,
                                                  credentials: "omit", cache: "no-store", redirect: "error" });
    } catch (e) { return { ok: false, error: "app_unreachable" }; }
    var data = {};
    try { data = await res.json(); } catch (e) { /* ignore */ }
    if (res.ok) return { ok: true, data: data };
    return { ok: false, status: res.status, error: data.error || ("http_" + res.status) };
  }

  return {
    DEFAULT_PORT: DEFAULT_PORT, friendly: friendly, buildPayload: buildPayload, cookieHeader: cookieHeader, isHttp: isHttp,
    ping: function (f, port, token) { return call(f, port, "/v1/ping", "POST", {}, token); },
    pair: function (f, port, code) { return call(f, port, "/v1/pair", "POST", { code: String(code || "").trim() }); },
    send: function (f, port, token, payload) {
      if (!token) return Promise.resolve({ ok: false, error: "not_paired" });
      return call(f, port, "/v1/download", "POST", payload, token);
    }
  };
});
