import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for the UI behavior test")
def test_document_controls_upload_validation_and_submission():
    script = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {File} = require("node:buffer");
const html = fs.readFileSync(process.argv[1], "utf8");
assert.match(html, /option value="document">PowerPoint \/ PDF to narrated video/);
assert.match(html, /id="documentInput"[^>]*accept="\.pptx,\.pdf"[^>]*required/);
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
for (const match of html.matchAll(/\bid="([^"]+)"/g)) {
  const attrs = html.slice(html.lastIndexOf("<", match.index), html.indexOf(">", match.index));
  const classes = new Set();
  elements.set(match[1], {
    value: attrs.match(/\bvalue="([^"]*)"/)?.[1] || "", checked: /\bchecked\b/.test(attrs),
    disabled: /\bdisabled\b/.test(attrs), hidden: /\bhidden\b/.test(attrs), style: {}, options: [], files: [],
    title: "", innerHTML: "", textContent: "",
    classList: {add(c) {classes.add(c)}, remove(c) {classes.delete(c)},
      toggle(c, on) {on ? classes.add(c) : classes.delete(c)}},
    addEventListener() {}, focus() {}, querySelectorAll() {return []}, querySelector() {return {}},
  });
}
const el = id => {assert(elements.has(id), `Missing ${id}`); return elements.get(id)};
el("useCase").value = "cinematic"; el("resolution").value = "720p"; el("orientation").value = "vertical";
el("upscaler").value = "seedvr2"; el("naturalistic").checked = true; el("music").checked = true;
el("narration").checked = false;
const posts = [], alerts = [];
const config = {max_image_mb: 50, document: {max_document_mb: 1, max_pages: 60,
  powerpoint_configured: false, pdf_configured: true, narration_configured: true}};
const context = {
  document: {getElementById: el, addEventListener() {}, hidden: true},
  window: {addEventListener() {}}, localStorage: {getItem() {return ""}},
  location: {hash: ""}, console, URL, FormData,
  setInterval() {}, clearInterval() {}, setTimeout() {}, clearTimeout() {},
  alert(message) {alerts.push(message)},
  async fetch(url, options) {
    if (options.method === "POST") {
      assert.equal(url, "/api/videos/document");
      assert(options.body instanceof FormData);
      assert(!options.headers["Content-Type"], "Browser must supply the multipart boundary");
      const request = JSON.parse(options.body.get("request"));
      posts.push({request, file: options.body.get("document")});
      assert.equal(options.body.get("image"), null);
      return {ok: true, status: 202, json: async () => ({id: "created", request})};
    }
    if (url === "/api/config") return {ok: true, json: async () => config};
    if (url === "/api/models") return {ok: true, json: async () => []};
    return {ok: true, json: async () => []};
  },
};
vm.createContext(context);
vm.runInContext(source, context);
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  el("useCase").value = "document"; el("useCase").onchange();
  assert.equal(el("documentControls").hidden, false);
  assert.equal(el("documentControls").disabled, false);
  assert.equal(el("educationControls").hidden, true);
  assert.equal(el("image").disabled, true);
  assert.equal(el("model").disabled, true);
  assert.equal(el("upscaler").disabled, true);
  assert.equal(el("duration").disabled, true);
  assert.match(el("durationPill").title, /each page follows its narration/);
  assert.equal(el("narration").checked, true);
  assert.equal(el("naturalistic").checked, false);
  assert.equal(el("music").checked, false);
  assert.equal(el("resolution").value, "1080p");
  assert.equal(el("documentResolution").value, "1080p");
  assert.equal(el("resolutionPill").hidden, true);
  assert.equal(el("deliveryControls").disabled, false);
  assert.match(el("documentCapabilities").textContent, /requires LibreOffice/);
  assert.match(el("license").textContent, /no GPU/);
  assert.match(el("license").textContent, /without equal scene lengths or target-duration padding/);
  el("prompt").value = "Explain the supplied document";
  el("duration").value = "";
  el("documentLanguage").value = "fr-FR";
  el("pronunciations").value = "";
  el("documentInput").files = [new File(["%PDF"], "Deck.PDF", {type: "application/pdf"})];
  await el("form").onsubmit({preventDefault() {}});
  assert.equal(alerts.length, 0, alerts.join("\n"));
  assert.equal(posts.length, 1);
  assert.equal(posts[0].file.name, "Deck.PDF");
  const request = posts[0].request;
  assert.equal(request.use_case, "document");
  assert.equal(request.duration_minutes, undefined, "Disabled target duration must not affect document requests");
  assert.equal(request.document.language, "fr-FR");
  assert.equal(request.document.cinematic_cutaways, false);
  assert.equal(request.document.animations, false);
  assert.equal(request.video_model, null);
  assert.equal(request.narration, true);
  assert.equal(request.naturalistic, false);
  assert.equal(request.music, false);
  assert.equal(request.upscaler, "ffmpeg");
  assert.equal(request.education, undefined);
  assert.equal(request.resolution, "1080p");
  assert.equal(request.delivery.rate_percent, 0);
  assert.equal(el("send").disabled, false);
  el("documentCinematic").checked = true; el("documentCinematic").onchange();
  assert.equal(el("model").disabled, false);
  assert.equal(el("duration").disabled, true);
  el("model").value = "wan22";
  el("documentInput").files = [new File(["%PDF"], "Deck.PDF", {type: "application/pdf"})];
  await el("form").onsubmit({preventDefault() {}});
  assert.equal(posts[1].request.document.cinematic_cutaways, true);
  assert.equal(posts[1].request.video_model, "wan22");
  el("documentCinematic").checked = false; el("documentCinematic").onchange();
  el("documentAnimations").checked = true; el("documentAnimations").onchange();
  assert.match(el("license").textContent, /animated with a gentle zoom/);
  el("documentInput").files = [new File(["%PDF"], "Deck.PDF", {type: "application/pdf"})];
  await el("form").onsubmit({preventDefault() {}});
  assert.equal(posts[2].request.document.animations, true);
  assert.equal(posts[2].request.document.cinematic_cutaways, false);
  assert.equal(posts[2].request.video_model, null);
  el("documentAnimations").checked = false; el("documentAnimations").onchange();
  for (const [file, error] of [
    [null, /Choose a PowerPoint/], [{name: "old.ppt", size: 10}, /Use a \.pptx or \.pdf/],
    [{name: "large.pdf", size: 2 * 1024 * 1024}, /1 MB or less/],
    [{name: "deck.pptx", size: 10}, /requires LibreOffice/],
  ]) {
    el("documentInput").files = file ? [file] : [];
    await el("form").onsubmit({preventDefault() {}});
    assert.match(alerts.at(-1), error);
    assert.equal(posts.length, 3, "Invalid upload must not create a job");
  }
  el("documentResolution").value = "4k"; el("documentResolution").onchange();
  assert.equal(el("resolution").value, "4k");
  assert.match(el("documentQualityNote").textContent, /4K.*3840 x 2160/);
  assert.match(el("documentQualityNote").textContent, /No GPU upscaler/);
  el("documentInput").files = [new File(["%PDF"], "Deck.PDF", {type: "application/pdf"})];
  await el("form").onsubmit({preventDefault() {}});
  assert.equal(posts[3].request.resolution, "4k");
  assert.equal(posts[3].request.upscaler, "ffmpeg");
  el("orientation").value = "vertical"; el("orientation").onchange();
  assert.match(el("documentQualityNote").textContent, /2160 x 3840/);
  el("documentCinematic").checked = true; el("documentCinematic").onchange();
  assert.equal(el("resolution").value, "4k", "Other options must not reset document quality");
  el("documentAnimations").checked = true;
  el("documentInput").files = [new File(["%PDF"], "Deck.PDF", {type: "application/pdf"})];
  await el("form").onsubmit({preventDefault() {}});
  assert.equal(posts[4].request.resolution, "4k");
  assert.equal(posts[4].request.orientation, "vertical");
  assert.equal(posts[4].request.document.animations, true);
  assert.equal(posts[4].request.document.cinematic_cutaways, true);
  el("useCase").value = "cinematic"; el("useCase").onchange();
  assert.equal(el("documentControls").hidden, true);
  assert.equal(el("documentInput").disabled, true);
  assert.equal(el("model").disabled, false);
  assert.equal(el("duration").disabled, false);
  assert.equal(el("resolution").value, "720p");
  assert.equal(el("resolutionPill").hidden, false);
  assert.equal(el("orientation").value, "vertical");
  assert.equal(el("narration").checked, false);
  assert.equal(el("naturalistic").checked, true);
  assert.equal(el("music").checked, true);
  el("useCase").value = "document"; el("useCase").onchange();
  assert.equal(el("documentResolution").value, "4k");
  assert.equal(el("resolution").value, "4k", "Document quality must survive a scenario round-trip");
  el("documentResolution").value = "720p"; el("documentResolution").onchange();
  el("useCase").value = "educational"; el("useCase").onchange();
  assert.equal(el("resolutionPill").hidden, false);
  assert.equal(el("resolution").value, "1080p", "Educational mode must not inherit unsupported 720p");
})().catch(error => {console.error(error); process.exitCode = 1});
"""
    html = Path(__file__).parents[1] / "video_platform" / "static" / "index.html"
    result = subprocess.run(["node", "-e", script, str(html)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
