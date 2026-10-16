/* Service worker (Chrome/Edge) / event page (Firefox). */
if (typeof importScripts === "function") importScripts("lib/detect.js", "lib/client.js");

const api = globalThis.browser || globalThis.chrome;
const ALL_HOSTS = { origins: ["http://*/*", "https://*/*"] };
const MENU_ID = "vd-send";

/* ---------- settings ---------- */
async function getSettings() {
  const s = await api.storage.local.get({ port: Client.DEFAULT_PORT, token: "", sendCookies: false });
  return s;
}

/* ---------- per-tab media list (session storage so it survives worker restarts) ---------- */
let chain = Promise.resolve();
function serial(fn) { chain = chain.then(fn, fn); return chain; }
const mkey = (tabId) => "media:" + tabId;

async function getMedia(tabId) {
  const r = await api.storage.session.get(mkey(tabId));
  return r[mkey(tabId)] || [];
}
async function setMedia(tabId, list) {
  await api.storage.session.set({ [mkey(tabId)]: list });
  const n = list.length;
  try {
    await api.action.setBadgeBackgroundColor({ tabId, color: "#0f766e" });
    await api.action.setBadgeText({ tabId, text: n ? String(n) : "" });
  } catch (e) { /* tab may be gone */ }
}

function onHeaders(d) {
  if (d.tabId < 0) return;
  if (d.type === "main_frame") { serial(() => setMedia(d.tabId, [])); return; }
  if (d.statusCode !== 200 && d.statusCode !== 206) return;
  const ct = Detect.header(d.responseHeaders, "content-type");
  const c = Detect.classify(d.url, ct, d.responseHeaders);
  if (!c) return;
  serial(async () => {
    const list = await getMedia(d.tabId);
    await setMedia(d.tabId, Detect.addItem(list, { url: d.url, kind: c.kind, size: c.size, source: "network", ts: Date.now() }));
  });
}

let listening = false;
async function syncListener() {
  const has = await api.permissions.contains(ALL_HOSTS);
  if (has && !listening) {
    api.webRequest.onHeadersReceived.addListener(onHeaders,
      { urls: ["http://*/*", "https://*/*"], types: ["main_frame", "media", "xmlhttprequest", "other", "sub_frame"] },
      ["responseHeaders"]);
    listening = true;
  } else if (!has && listening) {
    api.webRequest.onHeadersReceived.removeListener(onHeaders);
    listening = false;
  }
  return has;
}
api.permissions.onAdded.addListener(syncListener);
api.permissions.onRemoved.addListener(syncListener);
syncListener();
api.tabs.onRemoved.addListener((tabId) => api.storage.session.remove(mkey(tabId)));

/* ---------- sending ---------- */
async function collectCookie(url, settings) {
  if (!settings.sendCookies) return { cookie: "" };
  const ok = await api.permissions.contains({ permissions: ["cookies"], origins: ALL_HOSTS.origins });
  if (!ok) return { cookie: "", warn: "Cookie access not granted; sent without cookies." };
  try {
    return { cookie: Client.cookieHeader(await api.cookies.getAll({ url })) };
  } catch (e) { return { cookie: "", warn: "Could not read cookies; sent without them." }; }
}

async function sendItem({ url, pageUrl, title, kind }) {
  const s = await getSettings();
  const { cookie, warn } = await collectCookie(url, s);
  let payload;
  try {
    payload = Client.buildPayload({ url, pageUrl, title, kind, userAgent: navigator.userAgent, cookie });
  } catch (e) { return { ok: false, error: e.message, message: Client.friendly(e.message) }; }
  const r = await Client.send(fetch, s.port, s.token, payload);
  if (r.ok) return { ok: true, warn };
  return { ok: false, error: r.error, message: Client.friendly(r.error) };
}

async function flash(tabId, ok) {
  if (tabId == null || tabId < 0) return;
  try {
    await api.action.setBadgeBackgroundColor({ tabId, color: ok ? "#15803d" : "#b91c1c" });
    await api.action.setBadgeText({ tabId, text: ok ? "OK" : "!" });
    setTimeout(async () => {
      const list = await getMedia(tabId);
      api.action.setBadgeBackgroundColor({ tabId, color: "#0f766e" });
      api.action.setBadgeText({ tabId, text: list.length ? String(list.length) : "" });
    }, 2500);
  } catch (e) { /* ignore */ }
}

/* ---------- context menu ---------- */
api.runtime.onInstalled.addListener(() => {
  api.contextMenus.removeAll(() => {
    api.contextMenus.create({ id: MENU_ID, title: "Download with app", contexts: ["link", "video", "audio", "page"] });
  });
});
api.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== MENU_ID) return;
  const target = info.linkUrl || info.srcUrl || info.pageUrl;
  const pageUrl = info.pageUrl || (tab && tab.url) || "";
  const kind = info.linkUrl ? "link" : info.srcUrl ? "video" : "page";
  const r = await sendItem({ url: target, pageUrl, title: (tab && tab.title) || "", kind });
  await flash(tab && tab.id, r.ok);
  if (!r.ok) await api.storage.session.set({ lastError: r.message });
});

/* ---------- messages from popup/options ---------- */
api.runtime.onMessage.addListener((msg, sender, reply) => {
  (async () => {
    if (msg.type === "getMedia") return { items: await getMedia(msg.tabId), detecting: await syncListener() };
    if (msg.type === "send") return await sendItem(msg.item);
    return { ok: false, error: "unknown" };
  })().then(reply, (e) => reply({ ok: false, error: "internal", message: String(e) }));
  return true;
});
