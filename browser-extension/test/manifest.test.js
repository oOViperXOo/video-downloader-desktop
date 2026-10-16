const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const root = path.join(__dirname, "..");
const m = JSON.parse(fs.readFileSync(path.join(root, "manifest.json"), "utf8"));

test("manifest basics", () => {
  assert.equal(m.manifest_version, 3);
  assert.ok(m.version && m.name && m.description.length <= 132);
});
test("permissions are minimal", () => {
  assert.deepEqual([...m.permissions].sort(), ["activeTab", "contextMenus", "scripting", "storage", "webRequest"]);
  assert.deepEqual(m.host_permissions, ["http://127.0.0.1/*"]);
  assert.deepEqual(m.optional_permissions, ["cookies"]);
  for (const bad of ["tabs", "history", "downloads", "nativeMessaging", "webRequestBlocking", "declarativeNetRequest", "<all_urls>"])
    assert.ok(!m.permissions.includes(bad) && !(m.host_permissions || []).includes(bad), bad);
  assert.equal(m.content_scripts, undefined);
});
test("all referenced files exist", () => {
  const files = [m.background.service_worker, ...m.background.scripts, m.action.default_popup, m.options_ui.page,
    ...Object.values(m.icons), ...Object.values(m.action.default_icon)];
  for (const f of files) assert.ok(fs.existsSync(path.join(root, f)), f);
});
test("no remote code / eval / external script URLs", () => {
  for (const f of ["background.js", "popup.js", "options.js", "popup.html", "options.html", "lib/detect.js", "lib/client.js"]) {
    const s = fs.readFileSync(path.join(root, f), "utf8");
    assert.ok(!/\beval\s*\(|new Function\(|<script[^>]+src=["']https?:/i.test(s), f);
    assert.ok(!/(?:src|href)=["']https?:/i.test(s), f);
  }
});
test("popup and options scripts are loaded in dependency order", () => {
  const p = fs.readFileSync(path.join(root, "popup.html"), "utf8");
  assert.ok(p.indexOf("lib/detect.js") < p.indexOf("popup.js") && p.indexOf("lib/client.js") < p.indexOf("popup.js"));
});
