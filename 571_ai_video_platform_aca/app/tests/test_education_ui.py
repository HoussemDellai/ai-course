import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for the UI behavior test")
def test_public_source_urls_in_research_step_across_job_states():
    script = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[1], "utf8");
const pageScript = html.match(/<script>([\s\S]*?)<\/script>/)[1];
new vm.Script(pageScript);
const elements = new Map();
const el = id => {
  if (!elements.has(id)) elements.set(id, {
    innerHTML: "", textContent: "", dataset: {}, hidden: false,
    querySelectorAll() {return []},
  });
  return elements.get(id);
};
const draft = {
  revision: 1,
  research: {
    summary: "Verified <public> facts",
    sources: [
      {id: "s1", title: "Pods & containers", url: "https://kubernetes.io/docs/?a=1&b=2"},
      {id: "s2", title: "<unsafe>", url: "javascript:alert(1)"},
    ],
  },
  brief: {title: "Pods", description: "Containers", audience: "Developers",
    objectives: ["Understand Pods"], language: "en-US", visual_theme: "Clean"},
  scenes: [],
};
const calls = [];
let fail = false, pending = null;
const researchOp = {id: "research", kind: "step", title: "Research public sources",
  run: 1, status: "succeeded", created_at: "2026-10-11T10:00:00Z", attrs: {step: "research"}, logs: []};
const context = {
  assert, URL, Symbol, console, draft, el, researchOp,
  $: el,
  key: () => "test key",
  esc: value => String(value).replace(/[&<>"']/g, c =>
    ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"})[c]),
  byCreation: (a, b) => new Date(a.created_at) - new Date(b.created_at),
  scheduleRender() {},
  document: {title: ""},
  stopWatching() {}, resetOutputs() {}, renderSidebar() {},
  renderJob() {vm.runInContext("renderEducationReview(cur.job)", context)},
  watch() {vm.runInContext("cur.ops.set(researchOp.id, researchOp)", context)},
  errorText: async () => "Sources unavailable",
  async api(url) {
    calls.push(url);
    if (pending) return await pending;
    return {ok: !fail, json: async () => draft};
  },
};
vm.createContext(context);
vm.runInContext('let cur = null, jobs = [], outcomeKey = "", userMsgKey = ""; const toggled = new Map();\n' +
  pageScript.slice(pageScript.indexOf("    const STEPS"), pageScript.indexOf("    function fmtDur")) +
  pageScript.slice(pageScript.indexOf("    const educationUrl"),
    pageScript.indexOf("    function draftUpdate()")) +
  pageScript.slice(pageScript.indexOf("    function isOpen"),
    pageScript.indexOf("    function formatText")) +
  pageScript.slice(pageScript.indexOf("    function showJob"),
    pageScript.indexOf('    window.addEventListener("hashchange"')), context);
const timeline = () => vm.runInContext("renderOp(researchOp, new Map())", context);
async function render(status, revision = 1, id = "job-1") {
  context.job = {id, status, draft_revision: revision, request: {use_case: "educational"}};
  vm.runInContext("cur = {id: job.id, job, ops: new Map([[researchOp.id, researchOp]])}; renderEducationReview(job);", context);
  await new Promise(resolve => setImmediate(resolve));
}
(async () => {
  const panel = el("educationReview");
  for (const status of ["awaiting_review", "keyframing", "generating", "processing", "completed", "failed"]) {
    await render(status);
    assert.equal(panel.hidden, false);
    const rendered = timeline();
    assert.match(rendered, /<span class="op-title">Research public sources<\/span>/);
    assert.match(rendered, /<ul class="public-sources" aria-label="Public source URLs">/);
    assert.match(rendered, /href="https:\/\/kubernetes.io\/docs\/\?a=1&amp;b=2"[^>]*>https:\/\/kubernetes.io\/docs\/\?a=1&amp;b=2<\/a>/);
    assert.match(rendered, /rel="noopener noreferrer"/);
    assert.doesNotMatch(rendered, /href="javascript:|Pods|containers|unsafe|Verified|<b>s1|Download sources/);
    assert.doesNotMatch(panel.innerHTML, /public-sources|Verified|Pods &amp; containers|&lt;unsafe&gt;/);
    assert.match(panel.innerHTML, /sources\.txt\?key=test%20key/);
    assert.equal(panel.innerHTML.includes('id="draftForm"'), status === "awaiting_review");
  }
  assert.equal(calls.length, 2, "Live updates must not refetch immutable sources");
  assert.equal(calls[0], "/api/videos/job-1/draft");
  vm.runInContext("jobs = [job]; cur = null; showJob(job.id)", context);
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(calls.length, 3, "Reopening the same job must reload cleared draft state");
  assert.match(timeline(), /public-sources/);

  vm.runInContext('toggled.set("research", false)', context);
  assert.doesNotMatch(timeline(), /public-sources/);
  vm.runInContext('toggled.clear()', context);
  assert.match(timeline(), /public-sources/);

  await render("awaiting_review");
  vm.runInContext("review.dirty = true", context);
  panel.innerHTML = "Unsaved edits";
  await render("awaiting_review", 2);
  assert.equal(panel.innerHTML, "Unsaved edits");
  assert.match(el("reviewError").textContent, /edits have been retained/);

  fail = true;
  await render("completed", 2, "failed-load");
  assert.match(el("reviewError").textContent, /Sources unavailable/);
  assert.match(panel.innerHTML, /Reload sources/);
  fail = false;
  await vm.runInContext('loadDraft("failed-load")', context);
  assert.match(timeline(), /public-sources/);

  draft.revision = 3;
  await render("completed", 3, "failed-load");
  assert.equal(vm.runInContext("review.draft.revision", context), 3);

  let resolve;
  pending = new Promise(r => {resolve = r});
  await render("completed", 1, "old-job");
  pending = null;
  await render("completed", 1, "new-job");
  const currentHtml = panel.innerHTML;
  const currentResearch = vm.runInContext("review.draft.research", context);
  resolve({ok: true, json: async () => ({...draft,
    research: {summary: "Stale research", sources: []}})});
  await new Promise(r => setImmediate(r));
  assert.equal(panel.innerHTML, currentHtml, "Late requests must not replace a different job's sources");
  assert.equal(vm.runInContext("review.draft.research", context), currentResearch);

  context.oldOp = {...researchOp, id: "older-research", created_at: "2026-10-10T10:00:00Z"};
  vm.runInContext("cur.ops.set(oldOp.id, oldOp)", context);
  assert.doesNotMatch(vm.runInContext("renderOp(oldOp, new Map())", context), /public-sources/,
    "Do not attach current draft sources to older research operations");
  context.oldOp.attrs = {step: "research", source_urls: ["https://example.com/previous-research"]};
  assert.match(vm.runInContext("renderOp(oldOp, new Map())", context), /example\.com\/previous-research/);
  assert.doesNotMatch(vm.runInContext("renderOp(oldOp, new Map())", context), /kubernetes\.io/);

  context.job = {id: "cinematic", request: {use_case: "cinematic"}};
  vm.runInContext("cur.job = job; renderEducationReview(job)", context);
  assert.equal(panel.hidden, true);
  assert.doesNotMatch(timeline(), /public-sources/);
  context.job = {id: "researching", draft_revision: null, request: {use_case: "educational"}};
  vm.runInContext("cur = {id: job.id, job, ops: new Map([[researchOp.id, researchOp]])}; renderEducationReview(job)", context);
  assert.equal(panel.hidden, true);
  context.researchOp.attrs.source_urls = ["https://example.com/new-research"];
  const recorded = timeline();
  assert.match(recorded, /example\.com\/new-research/);
  assert.doesNotMatch(recorded, /kubernetes\.io|class="chips"|source urls/,
    "Persisted operation URLs must render before a draft exists, without attribute chips");
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    html = Path(__file__).parents[1] / "video_platform" / "static" / "index.html"
    result = subprocess.run(["node", "-e", script, str(html)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
