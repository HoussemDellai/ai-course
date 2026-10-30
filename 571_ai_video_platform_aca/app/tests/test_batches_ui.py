import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for the UI behavior test")
def test_batch_pair_selection_uploads_and_submit_preserve_unblurred_voice():
    script = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const {File} = require("node:buffer");
const html = fs.readFileSync(process.argv[1], "utf8");
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
for (const match of html.matchAll(/\bid="([^"]+)"/g)) {
  const attrs = html.slice(html.lastIndexOf("<", match.index), html.indexOf(">", match.index));
  elements.set(match[1], {
    value: attrs.match(/\bvalue="([^"]*)"/)?.[1] || "", checked: /\bchecked\b/.test(attrs),
    disabled: /\bdisabled\b/.test(attrs), hidden: /\bhidden\b/.test(attrs), style: {}, options: [], files: [],
    title: "", innerHTML: "", textContent: "",
    classList: {add() {}, remove() {}, toggle() {}},
    addEventListener() {}, focus() {}, querySelectorAll() {return []}, querySelector() {return {}},
  });
}
const el = id => {assert(elements.has(id), `Missing ${id}`); return elements.get(id)};
el("useCase").value = "cinematic"; el("resolution").value = "720p";
el("orientation").value = "horizontal"; el("upscaler").value = "ffmpeg";
el("duration").value = "0.25"; el("narration").checked = true;
const posts = [], alerts = [];
const config = {max_image_mb: 50, batch: {parallel_capacity: 2},
  voice_clone: {configured: true, max_sample_mb: 25,
    models: [{key: "chatterbox", name: "Chatterbox", license: "MIT"},
             {key: "qwen3-tts", name: "Qwen3", license: "Apache"}]},
  document: {max_document_mb: 100, max_pages: 60, powerpoint_configured: true, narration_configured: true},
  education: {text_models: [], search_configured: true, narration_configured: true,
    images: {comfyui: true}, motion: {comfyui: true}}};
const context = {
  document: {getElementById: el, addEventListener() {}, hidden: true},
  window: {addEventListener() {}}, localStorage: {getItem() {return ""}},
  location: {hash: ""}, console, URL, FormData,
  setInterval() {}, clearInterval() {}, setTimeout() {}, clearTimeout() {},
  alert(message) {alerts.push(message)},
  async fetch(url, options) {
    if (options.method === "POST") {
      const multipart = options.body instanceof FormData;
      const payload = JSON.parse(multipart ? options.body.get("request") : options.body);
      posts.push({url, payload, multipart, sample: multipart ? options.body.get("voice_sample") : null});
      if (!payload.variants) return {ok: true, status: 202, json: async () => ({id: `single${posts.length}`, request: payload})};
      return {ok: true, status: 202, json: async () => ({id: "batch", concurrency: 1,
        jobs: payload.variants.map((v, i) => ({id: `job${posts.length}-${i}`,
          request: {...payload.request, ...v}}))})};
    }
    if (url === "/api/config") return {ok: true, json: async () => config};
    if (url === "/api/models") return {ok: true, json: async () => [
      {key: "wan22", name: "Wan", license: "Apache"}, {key: "ltx25", name: "LTX", license: "license"}]};
    return {ok: true, json: async () => []};
  },
};
vm.createContext(context);
vm.runInContext(source, context);
const change = (index, field, value) =>
  el("variants").onchange({target: {dataset: {index: String(index), field}, value}});
const typeVoice = (index, value) =>
  el("variants").oninput({target: {dataset: {index: String(index), field: "voice"}, value}});
const submit = async () => {el("prompt").value = "Explain a lighthouse"; await el("form").onsubmit({preventDefault() {}})};
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  el("model").value = "wan22"; el("batchEnabled").checked = true;
  el("batchEnabled").onchange();
  assert.equal(el("batchControls").hidden, false);
  assert.match(el("variants").innerHTML, /Variant 2/);
  change(1, "video_model", "ltx25");
  const originalRows = el("variants").innerHTML;
  typeVoice(0, "voice-one"); typeVoice(1, "voice-two");
  assert.equal(el("variants").innerHTML, originalRows, "Typing must not replace focused inputs");
  await submit();
  assert.equal(alerts.length, 0, alerts.join("\n"));
  assert.equal(posts[0].url, "/api/video-batches");
  assert.equal(posts[0].multipart, false);
  assert.equal(posts[0].payload.execution, "sequential");
  assert.deepEqual(posts[0].payload.variants.map(v => [v.video_model, v.voice]),
    [["wan22", "voice-one"], ["ltx25", "voice-two"]]);
  change(1, "engine", "chatterbox");
  assert.equal(el("cloneFields").hidden, false);
  el("cloneModel").value = "qwen3-tts";
  el("cloneSample").files = [new File(["sample"], "sample.wav")];
  await submit();
  assert.match(alerts.at(-1), /right to clone/);
  assert.equal(posts.length, 1, "Missing consent must not submit");
  el("cloneConsent").checked = true;
  el("batchExecution").value = "auto";
  await submit();
  const mixed = posts[1];
  assert(mixed.multipart && mixed.sample.name === "sample.wav");
  assert.equal(mixed.payload.variants[0].voice_clone, null);
  assert.equal(mixed.payload.variants[1].voice_clone.model, "chatterbox");
  assert.equal(mixed.payload.variants[1].voice_clone.consent, true);
  assert.equal(mixed.payload.variants[1].voice, null);
  assert.equal(mixed.payload.execution, "auto");
  el("useCase").value = "document"; el("useCase").onchange();
  el("documentResolution").value = "4k"; el("documentResolution").onchange();
  assert.match(el("variants").innerHTML, /data-field="video_model" disabled/);
  el("documentLanguage").value = "en-US"; el("pronunciations").value = "";
  el("documentInput").files = [new File(["%PDF"], "slides.pdf")];
  el("cloneSample").files = [new File(["sample"], "sample.wav")];
  el("cloneConsent").checked = true; await submit();
  assert.equal(posts[2].url, "/api/video-batches/document");
  assert.equal(posts[2].payload.request.use_case, "document");
  assert.equal(posts[2].payload.request.resolution, "4k");
  el("useCase").value = "educational"; el("useCase").onchange();
  el("publicTopic").value = "Public lighthouse optics"; el("educationStyle").value = "presentation";
  el("imageProvider").value = "comfyui"; el("motionProvider").value = "comfyui";
  el("audience").value = "Beginners"; el("musicMode").value = "off";
  el("cloneSample").files = [new File(["sample"], "sample.wav")];
  el("cloneConsent").checked = true; await submit();
  assert.equal(posts[3].url, "/api/video-batches");
  assert.equal(posts[3].payload.request.use_case, "educational");
  assert.equal(posts[3].payload.request.education.public_topic, "Public lighthouse optics");
  el("batchEnabled").checked = false; el("batchEnabled").onchange();
  assert.equal(el("batchControls").hidden, true);
  el("cloneModel").value = "chatterbox"; el("cloneModel").onchange();
  assert.equal(el("cloneFields").hidden, false, "Models are selectable without a sample");
  assert.equal(el("cloneModel").disabled, false);
  el("cloneSample").files = []; el("cloneConsent").checked = false; await submit();
  assert.equal(alerts.length, 1, "Built-in voice needs no sample or consent: " + alerts.at(-1));
  assert.equal(posts[4].url, "/api/videos");
  assert.equal(posts[4].multipart, false);
  assert.deepEqual(posts[4].payload.voice_clone, {model: "chatterbox", builtin_voice: true});
  assert.equal(posts[4].payload.voice, null);
  el("cloneModel").value = "azure"; el("cloneModel").onchange();
  assert.equal(el("cloneFields").hidden, true);
  await submit();
  assert.equal(posts[5].payload.voice_clone, undefined);
  assert.equal(el("send").disabled, false);
})().catch(error => {console.error(error); process.exitCode = 1});
"""
    html = Path(__file__).parents[1] / "video_platform" / "static" / "index.html"
    result = subprocess.run(["node", "-e", script, str(html)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
