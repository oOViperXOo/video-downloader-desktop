const api = globalThis.browser || globalThis.chrome;
const $ = (id) => document.getElementById(id);
let tab = null;

function notice(text, cls) {
  const n = $("notice");
  n.textContent = text || ""; n.className = "notice " + (cls || ""); n.hidden = !text;
}
function setStatus(text, cls) { const s = $("status"); s.textContent = text; s.className = "chip " + (cls || ""); }
function fmtSize(n) {
  if (n == null) return "";
  const u = ["B", "KB", "MB", "GB"]; let i = 0;
  while (n >= 1024 && i < 3) { n /= 1024; i++; }
  return n.toFixed(i ? 1 : 0) + " " + u[i];
}
function hostOf(u) { try { return new URL(u).hostname; } catch (e) { return ""; } }

function row(item) {
  const d = document.createElement("div"); d.className = "item";
  const name = document.createElement("div"); name.className = "name"; name.textContent = item.label || Detect.nameOf(item.url);
  name.title = item.url;
  const meta = document.createElement("div"); meta.className = "meta";
  const pill = document.createElement("span"); pill.className = "pill"; pill.textContent = item.kind;
  meta.append(pill, [hostOf(item.url), fmtSize(item.size)].filter(Boolean).join("  "));
  const b = document.createElement("button"); b.textContent = "Send to app"; if (item.kind === "page") b.className = "primary";
  b.addEventListener("click", async () => {
    b.disabled = true; b.textContent = "Sending...";
    const r = await api.runtime.sendMessage({ type: "send", item: { url: item.url, pageUrl: tab.url, title: tab.title, kind: item.kind } });
    b.disabled = false; b.textContent = r.ok ? "Sent" : "Send to app";
    notice(r.ok ? (r.warn || "Sent to the app.") : r.message, r.ok ? (r.warn ? "" : "good") : "err");
  });
  d.append(name, meta, b);
  return d;
}

async function pageVideos() {
  try {
    const [res] = await api.scripting.executeScript({ target: { tabId: tab.id }, func: () => {
      const out = [];
      document.querySelectorAll("video, audio, video source, audio source").forEach((el) => {
        const src = el.currentSrc || el.src; if (src) out.push({ src, kind: el.tagName.toLowerCase().includes("audio") ? "audio" : "video" });
      });
      document.querySelectorAll('meta[property="og:video"],meta[property="og:video:url"],meta[property="og:video:secure_url"],meta[name="twitter:player:stream"]')
        .forEach((m) => m.content && out.push({ src: new URL(m.content, location.href).href, kind: "video" }));
      return out;
    } });
    return Detect.pageItems(res && res.result);
  } catch (e) { return []; }
}

async function init() {
  [tab] = await api.tabs.query({ active: true, currentWindow: true });
  $("options").addEventListener("click", (e) => { e.preventDefault(); api.runtime.openOptionsPage(); });
  const s = await api.storage.local.get({ port: Client.DEFAULT_PORT, token: "", sendCookies: false });
  $("cookies").checked = s.sendCookies;
  $("cookies").addEventListener("change", async (e) => {
    if (e.target.checked) {
      const ok = await api.permissions.request({ permissions: ["cookies"], origins: ["http://*/*", "https://*/*"] });
      if (!ok) { e.target.checked = false; return; }
    }
    await api.storage.local.set({ sendCookies: e.target.checked });
  });

  const ping = await Client.ping(fetch, s.port, s.token);
  if (!ping.ok) setStatus("App not running", "bad");
  else if (!ping.data.paired) { setStatus("Not paired", "warn"); notice("Open Options and enter the pairing code shown in the app.", ""); }
  else setStatus("App connected", "ok");

  const list = $("list");
  if (!tab || !Detect.isHttp(tab.url)) { list.innerHTML = '<div class="empty">Open a web page to find media on it.</div>'; return; }
  const { items, detecting } = await api.runtime.sendMessage({ type: "getMedia", tabId: tab.id });
  $("detect-cta").hidden = detecting;
  $("enable-detect").addEventListener("click", async () => {
    const ok = await api.permissions.request({ origins: ["http://*/*", "https://*/*"] });
    if (ok) { $("detect-cta").hidden = true; notice("Detection is on. Reload the page, then play the video.", "good"); }
  });
  const found = Detect.pageItems ? await pageVideos() : [];
  const seen = new Set();
  const all = [{ url: tab.url, kind: "page", label: "This page (let the app find the video)", size: null }];
  [...items, ...found].forEach((it) => { const k = Detect.keyOf(it.url); if (!seen.has(k)) { seen.add(k); all.push(it); } });
  list.replaceChildren(...all.map(row));
  if (all.length === 1) {
    const e = document.createElement("div"); e.className = "empty";
    e.textContent = detecting ? "No media seen yet. Start playback, then reopen." : "No direct media found on the page.";
    list.append(e);
  }
}
init();
