const api = globalThis.browser || globalThis.chrome;
const $ = (id) => document.getElementById(id);
const HOSTS = ["http://*/*", "https://*/*"];
function msg(t, ok) { $("msg").textContent = t; $("msg").className = ok ? "ok" : "err"; }

async function refresh() {
  const s = await api.storage.local.get({ port: Client.DEFAULT_PORT, token: "", sendCookies: false });
  $("port").value = s.port; $("cookies").checked = s.sendCookies;
  const p = await Client.ping(fetch, s.port, s.token);
  $("state").textContent = !p.ok ? "App not reachable on port " + s.port + "." : p.data.paired ? "Paired and connected." : "App found, not paired yet.";
  const d = await api.permissions.contains({ origins: HOSTS });
  $("detect-state").textContent = d ? "On" : "Off";
}
$("port").addEventListener("change", async () => {
  const v = parseInt($("port").value, 10);
  if (v >= 1024 && v <= 65535) await api.storage.local.set({ port: v, token: "" }); // new port = new app instance, re-pair
  refresh();
});
$("pair").addEventListener("click", async () => {
  const s = await api.storage.local.get({ port: Client.DEFAULT_PORT });
  const r = await Client.pair(fetch, s.port, $("code").value);
  if (r.ok) { await api.storage.local.set({ token: r.data.token }); $("code").value = ""; msg("Paired.", true); }
  else msg(Client.friendly(r.error), false);
  refresh();
});
$("forget").addEventListener("click", async () => { await api.storage.local.set({ token: "" }); msg("Pairing removed from this browser. Also revoke it in the app.", true); refresh(); });
$("detect").addEventListener("click", async () => { const ok = await api.permissions.request({ origins: HOSTS }); msg(ok ? "Detection enabled." : "Permission not granted.", ok); refresh(); });
$("detect-off").addEventListener("click", async () => { await api.permissions.remove({ origins: HOSTS }); msg("Detection disabled.", true); refresh(); });
$("cookies").addEventListener("change", async (e) => {
  if (e.target.checked && !(await api.permissions.request({ permissions: ["cookies"], origins: HOSTS }))) e.target.checked = false;
  await api.storage.local.set({ sendCookies: e.target.checked });
});
refresh();
