import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for the UI behavior test")
def test_model_and_tool_badges_are_visible_without_expanding_steps():
    script = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[1], "utf8");
const source = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const context = {
  URL, console, researchSourceUrls() {return []}, time() {return "now"}, fmtDur() {return "1s"},
  esc: s => String(s ?? "").replace(/[&<>"']/g, c =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]),
  document: {getElementById() {return {}}},
};
vm.createContext(context);
vm.runInContext('let cur = {job: {request: {use_case: "cinematic", video_model: "wan22"}}, ops: new Map()}; const toggled = new Map();\n' +
  source.slice(source.indexOf("    const STEPS"), source.indexOf("    function fmtDur")) +
  source.slice(source.indexOf("    function isOpen"), source.indexOf("    function formatText")), context);
function op(kind, attrs = {}, status = "succeeded", id = "op") {
  return {id, kind, title: "Test step", attrs, status, logs: []};
}
function render(operation, children = new Map()) {
  context.operation = operation; context.children = children;
  return vm.runInContext("toggled.set(operation.id, false); renderOp(operation, children)", context);
}
for (const status of ["queued", "running", "succeeded", "failed", "reused", "skipped", "cancelled"]) {
  const result = render(op("step", {step: "enhance_prompt", tool: "Microsoft Foundry", model: "text-deployment"}, status));
  assert.match(result, /class="tool"[^>]*>Microsoft Foundry · text-deployment<\/span>/);
  assert.doesNotMatch(result, /class="op-body"/, "Badges must not depend on expansion");
}
for (const [kind, attrs, expected] of [
  ["agent", {model: "gpt-custom"}, /Microsoft Foundry · gpt-custom/],
  ["clip", {model: "Wan 2.2"}, /ComfyUI · Wan 2.2/],
  ["upscale", {model: "SeedVR2 7B"}, /ComfyUI · SeedVR2 7B/],
  ["music", {model: "MiniMax-Music3"}, /ComfyUI · MiniMax-Music3/],
  ["narration", {tool: "Azure AI Speech", voice: "en-US-Voice"}, /Azure AI Speech · en-US-Voice/],
  ["narration", {tool: "Voice-clone service", model: "Chatterbox"}, /Voice-clone service · Chatterbox/],
  ["ffmpeg", {}, />ffmpeg<\/span>/],
  ["upload", {}, />Artifact storage<\/span>/],
  ["keyframe", {tool: "Microsoft Foundry", model: "image-deployment"}, /Microsoft Foundry · image-deployment/],
  ["keyframe", {tool: "draw.io MCP + exporter"}, /draw\.io MCP \+ exporter/],
]) assert.match(render(op(kind, attrs)), expected);
const children = new Map([["parent", [
  op("agent", {model: "text-deployment"}, "succeeded", "child-ai"),
  op("ffmpeg", {}, "succeeded", "child-ffmpeg"),
  op("upload", {}, "succeeded", "child-upload"),
]]]);
const parent = render(op("step", {}, "succeeded", "parent"), children);
assert.match(parent, /Microsoft Foundry · text-deployment/);
assert.match(parent, />ffmpeg<\/span>/);
assert.match(parent, />Artifact storage<\/span>/);
assert.doesNotMatch(parent, /op-children|op-body/, "Collapsed parents must summarize descendant tools");
const pending = vm.runInContext("renderRun([], new Map(), STEPS)", context);
for (const tool of ["Microsoft Foundry", "ComfyUI", "Azure AI Speech", "ffmpeg"])
  assert(pending.includes(tool), `Pending steps must identify ${tool}`);
assert.match(render(op("step", {step: "document_extract"})), /PDFium/);
vm.runInContext('cur.job.request = {use_case:"document", document:{filename:"slides.pptx"}}', context);
assert.match(render(op("step", {step:"document_extract"})), /LibreOffice/);
assert.match(render(op("step", {step:"document_plan"})), /model not recorded/);
vm.runInContext('cur.job.request = {use_case:"document", voice_clone:{model:"qwen3-tts"}}', context);
assert.match(render(op("narration")), /Voice-clone service · qwen3-tts/);
vm.runInContext('cur.job.request = {use_case:"educational", education:{image_provider:"foundry", motion_provider:"foundry"}}', context);
assert.doesNotMatch(render(op("keyframe")), /ComfyUI/, "Do not mislabel legacy Foundry/diagram assets as ComfyUI");
assert.match(render(op("clip")), /Microsoft Foundry/);
assert.match(render(op("step", {step:"unknown"})), /Tool not recorded/);
const escaped = render(op("step", {tool:'Tool <unsafe>', model:'model"><script>alert(1)</script>'}));
assert.doesNotMatch(escaped, /<script>|Tool <unsafe>/);
assert.match(escaped, /&lt;script&gt;/);
const css = html.match(/<style>([\s\S]*?)<\/style>/)[1];
assert.match(css, /\.op-row\s*\{[^}]*flex-wrap:\s*wrap/);
assert.match(css, /\.op-heading\s*\{[^}]*flex:\s*1 1 180px/);
assert.match(css, /\.op-tools\s*\{[^}]*flex-wrap:\s*wrap/);
assert.match(css, /\.tool\s*\{[^}]*overflow-wrap:\s*anywhere/);
assert.doesNotMatch(css, /\.op-tools[^{}]*\{[^}]*display:\s*none/);
"""
    page = Path(__file__).parents[1] / "video_platform" / "static" / "index.html"
    result = subprocess.run(["node", "-e", script, str(page)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
