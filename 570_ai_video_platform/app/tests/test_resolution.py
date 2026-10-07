"""Orientation, output resolution and upscaler (ffmpeg / SeedVR2): real workflow + real ffmpeg, fake ComfyUI."""

import asyncio
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from fakes import requires_ffmpeg
from test_pipeline import make_services, settings  # noqa: F401 (fixture)
from video_platform import media
from video_platform.comfyui import load_workflow
from video_platform.config import Settings
from video_platform.jobs import JobManager
from video_platform.narration import fingerprint
from video_platform.operations import OpKind, OpStatus
from video_platform.schemas import JobState, JobStatus, VideoRequest
from video_platform.video_models import UPSCALE_WORKFLOW, VIDEO_MODELS, output_size
from video_platform.workflow import naturalistic_manifest, new_video_job

TINY = {"720p": (320, 180), "1080p": (480, 270), "4k": (960, 540)}  # same as the settings fixture


def is_upscale(workflow: dict) -> bool:
    return any(n["class_type"] == "SeedVR2Preprocess" for n in workflow.values())


def test_request_defaults_and_validation():
    request = VideoRequest(prompt="a lighthouse")
    assert (request.orientation, request.resolution, request.upscaler) == ("horizontal", "720p", "ffmpeg")
    # 720p is native: SeedVR2 is skipped rather than rejected.
    assert VideoRequest(prompt="a lighthouse", upscaler="seedvr2").upscaler == "ffmpeg"
    assert VideoRequest(prompt="a lighthouse", resolution="4k", upscaler="seedvr2").upscaler == "seedvr2"
    for field, value in (("orientation", "square"), ("resolution", "8k"), ("upscaler", "esrgan")):
        with pytest.raises(ValidationError):
            VideoRequest(prompt="a lighthouse", **{field: value})


def test_output_and_render_sizes():
    assert output_size("horizontal", "720p") == (1280, 720)
    assert output_size("vertical", "720p") == (720, 1280)
    assert output_size("horizontal", "1080p") == (1920, 1080)
    assert output_size("vertical", "1080p") == (1080, 1920)
    assert output_size("horizontal", "4k") == (3840, 2160)
    assert output_size("vertical", "4k") == (2160, 3840)
    for model in VIDEO_MODELS.values():
        w, h = model.render_size("horizontal")
        assert model.render_size("vertical") == (h, w) and w > h
    # The models' size constraints hold in both orientations (LTX-2.5 also renders a half-size first stage).
    assert all(v % 64 == 0 for v in VIDEO_MODELS["ltx2"].render_size("vertical"))
    assert all(v % 32 == 0 and (v // 2) % 32 == 0 for v in VIDEO_MODELS["ltx25"].render_size("vertical"))
    assert media.fit_scale(1280, 720, 1920, 1080) == 1.5 and media.fit_scale(720, 1280, 2160, 3840) == 3
    assert media.fit_scale(704, 1280, 1080, 1920) == 1.5  # keeps the aspect ratio: 1056x1920, padded to 1080


def test_old_jobs_load_with_previous_behavior():
    old = {"id": "abc", "status": "completed", "request": {"prompt": "a lighthouse", "duration_minutes": 0.25,
                                                           "video_model": "wan22", "naturalistic": True}}
    state = JobState.model_validate(old)
    assert (state.request.orientation, state.request.resolution, state.request.upscaler) == (
        "horizontal", "720p", "ffmpeg")


def test_naturalistic_fingerprint_of_existing_jobs_is_unchanged():
    s = Settings()
    request = VideoRequest(prompt="a lighthouse", video_model="wan22", naturalistic=True, seed=1)
    job = new_video_job("abc", request, s)
    # The manifest as it was computed before the output format became selectable.
    legacy = {
        "version": 1,
        "request": {k: v for k, v in request.model_dump(exclude={"music"}).items()
                    if k not in ("orientation", "resolution", "upscaler")},
        "model": vars(job.model), "voice": s.tts_voice, "output": [1280, 720, 24],
        "ambient_volume": s.ambient_audio_volume,
    }
    assert fingerprint(naturalistic_manifest(job, s)) == fingerprint(legacy)
    vertical = new_video_job("abc", request.model_copy(update={"orientation": "vertical"}), s)
    assert fingerprint(naturalistic_manifest(vertical, s)) != fingerprint(legacy)


async def run_job(settings, tmp_path, monkeypatch, model_key="wan22", orientation="horizontal",
                  narration_seconds=9.0, **request):
    clip_size = (176, 320) if orientation == "vertical" else (320, 176)
    store, factory, close, comfy, team, narrator = make_services(settings, tmp_path, monkeypatch, model_key,
                                                                 narration_seconds=narration_seconds,
                                                                 clip_size=clip_size,
                                                                 fail_upscale=request.pop("fail_upscale", False))
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse keeper", duration_minutes=0.25,
                                              video_model=model_key, orientation=orientation, **request))
    await asyncio.wait_for(manager.wait(state.id), 180)
    return manager, store, close, comfy, team, await manager.get(state.id)


@requires_ffmpeg
@pytest.mark.parametrize("orientation", ["horizontal", "vertical"])
@pytest.mark.parametrize("resolution,upscaler", [
    ("720p", "ffmpeg"), ("1080p", "ffmpeg"), ("1080p", "seedvr2"), ("4k", "ffmpeg"), ("4k", "seedvr2"),
])
async def test_exact_output_sizes(settings, tmp_path, monkeypatch, orientation, resolution, upscaler):
    manager, store, close, comfy, team, final = await run_job(
        settings, tmp_path, monkeypatch, orientation=orientation, resolution=resolution, upscaler=upscaler)
    assert final.status == JobStatus.completed, final.error
    w, h = TINY[resolution] if orientation == "horizontal" else TINY[resolution][::-1]
    assert output_size(orientation, resolution) == (w, h)
    video = store.path(final.id, "final.mp4")
    assert await media.video_size(video) == (w, h)
    duration, has_audio = await media.probe(video)
    assert has_audio and 19.5 < duration < 20.8, duration

    # Clips are rendered natively in the requested orientation; the generated shots are kept unchanged.
    render = VIDEO_MODELS["wan22"].render_size(orientation)
    clip_wfs = [wf for wf in comfy.submitted if not is_upscale(wf)]
    sizes = {(n["inputs"]["width"], n["inputs"]["height"]) for wf in clip_wfs for n in wf.values()
             if n["class_type"] == "EmptyHunyuanLatentVideo"}
    assert len(clip_wfs) == 6 and sizes == {render}
    assert all(store.path(final.id, f"clips/shot_{i:03d}.mp4").read_bytes() == comfy.clip_bytes for i in range(6))
    assert [await media.video_size(store.path(final.id, f"processed/shot_{i:03d}.mp4")) for i in range(6)] == [
        (w, h)] * 6
    for i in range(2):
        assert await media.video_size(store.path(final.id, f"scenes/scene_{i:03d}.mp4")) == (w, h)
        assert store.path(final.id, f"scenes/scene_{i:03d}_voice.mp4").exists()
    assert any(c.endswith("-vertical") for c in team.calls) == (orientation == "vertical")

    upscale_wfs = [wf for wf in comfy.submitted if is_upscale(wf)]
    ops = await manager.operations(final.id)
    step = next(o for o in ops if o.attrs.get("step") == "process_shots")
    assert step.status == OpStatus.succeeded and step.attrs["resolution"] == f"{w}x{h}"
    assert step.progress_done == step.progress_total == 6
    shots = [o for o in ops if o.parent_id == step.id]
    if upscaler == "seedvr2":
        assert step.attrs["upscaler"] == "SeedVR2 7B"
        assert len(upscale_wfs) == 6 and comfy.submitted[6:] == upscale_wfs, "upscaled after all clips"
        scales = {n["inputs"]["resize_type.multiplier"] for wf in upscale_wfs for n in wf.values()
                  if n["class_type"] == "ResizeImageMaskNode"}
        assert scales == {1.5 if resolution == "1080p" else 3.0}
        loads = sorted(n["inputs"]["file"] for wf in upscale_wfs for n in wf.values() if n["class_type"] == "LoadVideo")
        assert loads == [f"aivideo/{final.id}/shot_{i:03d}.mp4" for i in range(6)]
        assert all(store.path(final.id, f"upscaled/shot_{i:03d}.mp4").exists() for i in range(6))
        # SeedVR2's own output is already upscaled (not the input preview that ComfyUI also reports).
        factor = 1.5 if resolution == "1080p" else 3
        clip_w, clip_h = (176, 320) if orientation == "vertical" else (320, 176)
        assert await media.video_size(store.path(final.id, "upscaled/shot_000.mp4")) == (
            int(clip_w * factor), int(clip_h * factor))
        assert len(shots) == 6 and all(o.kind == OpKind.upscale and o.attrs["prompt_id"] for o in shots)
    else:
        assert step.attrs["upscaler"] == "ffmpeg" and not upscale_wfs
        assert not store.path(final.id, "upscaled").exists()
        assert len(shots) == 6 and all(o.kind == OpKind.ffmpeg for o in shots)
    assert sorted(o.attrs["artifact"] for o in shots) == [f"processed/shot_{i:03d}.mp4" for i in range(6)]
    await close()


@requires_ffmpeg
async def test_seedvr2_keeps_ambient_audio_padding_and_naturalistic_timing(settings, tmp_path, monkeypatch):
    # LTX-2.5 renders 704x1280 with audio: SeedVR2 output keeps the aspect ratio (padded) and the exact duration.
    manager, store, close, comfy, _, final = await run_job(
        settings, tmp_path, monkeypatch, "ltx25", orientation="vertical", resolution="1080p", upscaler="seedvr2",
        naturalistic=True, narration_seconds=3.0)
    assert final.status == JobStatus.completed, final.error
    video = store.path(final.id, "final.mp4")
    assert await media.video_size(video) == (270, 480)
    assert abs(await media.video_duration(video) - 15) <= 1 / settings.output_fps
    upscaled = store.path(final.id, "upscaled/shot_000.mp4")
    assert await media.video_size(upscaled) == (264, 480)  # 176x320 * 1.5, padded to 270x480 afterwards
    assert (await media.probe(upscaled))[1], "SeedVR2 output keeps the clip's audio"
    clip_wfs = [wf for wf in comfy.submitted if not is_upscale(wf)]
    sizes = {(n["inputs"]["width"], n["inputs"]["height"]) for wf in clip_wfs for n in wf.values()
             if n["class_type"] == "EmptyImage"}
    assert sizes == {(704, 1280)}
    await close()


@requires_ffmpeg
async def test_seedvr2_resume_reuses_and_reattaches(settings, tmp_path, monkeypatch):
    manager, store, close, comfy, _, final = await run_job(
        settings, tmp_path, monkeypatch, resolution="1080p", upscaler="seedvr2")
    assert final.status == JobStatus.completed, final.error
    upscale_ids = [f"p{i + 1}" for i, wf in enumerate(comfy.submitted) if is_upscale(wf)]

    # Crash before ProcessShots finished: shot 0's SeedVR2 render was submitted but never downloaded,
    # shot 1 was upscaled but not processed yet.
    await manager.progress(final.id, JobStatus.processing)
    shot0 = next(p for p in upscale_ids if comfy.upscale_prompts[p][0].endswith("/shot_000.mp4"))
    for name in ("processed/shot_000.mp4", "upscaled/shot_000.mp4", "processed/shot_001.mp4", "final.mp4"):
        store.path(final.id, name).unlink()
    store.path(final.id, "upscaled/shot_000.pending.json").write_text(
        f'{{"server": "http://comfy0:8188", "prompt_id": "{shot0}"}}')
    submitted = len(comfy.submitted)
    manager2 = JobManager(settings, store, manager._workflow_factory)
    await manager2.resume_unfinished()
    await manager2.wait(final.id)
    resumed = await manager2.get(final.id)
    assert resumed.status == JobStatus.completed, resumed.error
    assert len(comfy.submitted) == submitted, "SeedVR2 work is reattached or reused, never redone"
    assert await media.video_size(store.path(final.id, "processed/shot_000.mp4")) == (480, 270)
    run2 = [o for o in await manager2.operations(final.id) if o.run == 2]
    step = next(o for o in run2 if o.attrs.get("step") == "process_shots")
    shots = {o.attrs["shot"]: o for o in run2 if o.parent_id == step.id}
    assert shots[0].status == OpStatus.succeeded and any("Reattaching" in line.message for line in shots[0].logs)
    assert shots[1].status == OpStatus.succeeded and any("Reusing" in line.message for line in shots[1].logs)
    assert all(shots[i].status == OpStatus.reused for i in range(2, 6))
    await close()


@requires_ffmpeg
async def test_seedvr2_failure_is_explicit_without_ffmpeg_fallback(settings, tmp_path, monkeypatch):
    manager, store, close, comfy, _, final = await run_job(
        settings, tmp_path, monkeypatch, resolution="4k", upscaler="seedvr2", fail_upscale=True)
    assert final.status == JobStatus.failed
    assert "SeedVR2 upscaling of shot" in final.error and "failed" in final.error
    assert not store.path(final.id, "processed").exists(), "no ffmpeg output instead of SeedVR2"
    assert not store.path(final.id, "final.mp4").exists()
    ops = await manager.operations(final.id)
    step = next(o for o in ops if o.attrs.get("step") == "process_shots")
    assert step.status == OpStatus.failed and "SeedVR2" in step.error
    assert not any(o.attrs.get("step") == "assemble" for o in ops)

    # Retry: the clips are reused, only the upscales are submitted again.
    comfy.fail_upscale = False
    clips = sum(not is_upscale(wf) for wf in comfy.submitted)
    await manager.retry(final.id)
    await manager.wait(final.id)
    retried = await manager.get(final.id)
    assert retried.status == JobStatus.completed, retried.error
    assert sum(not is_upscale(wf) for wf in comfy.submitted) == clips
    assert await media.video_size(store.path(final.id, "final.mp4")) == (960, 540)
    await close()


def test_upscale_workflow_model_files_are_downloaded():
    from test_model_downloads import MODEL_INPUTS, SCRIPT

    files = {v for n in load_workflow(UPSCALE_WORKFLOW).values() for k, v in n["inputs"].items() if k in MODEL_INPUTS}
    assert files == {"seedvr2_7b_fp16.safetensors", "seedvr2_ema_vae_fp16.safetensors"}
    script = SCRIPT.read_text()
    assert all(f"/{name}" in script for name in files)

@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for the UI behavior test")
def test_composer_format_selectors():
    script = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[1], "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
for (const match of html.matchAll(/\bid="([^"]+)"/g)) {
  const attributes = html.slice(html.lastIndexOf("<", match.index), html.indexOf(">", match.index));
  const classes = new Set();
  elements.set(match[1], {
    value: attributes.match(/\bvalue="([^"]*)"/)?.[1] || "", checked: /\bchecked\b/.test(attributes),
    disabled: /\bdisabled\b/.test(attributes), style: {}, classes,
    classList: {add(c) {classes.add(c)}, remove(c) {classes.delete(c)},
                toggle(c, on) {on ? classes.add(c) : classes.delete(c)}},
    addEventListener() {}, focus() {}, querySelectorAll() {return []},
  });
}
const el = id => { assert(elements.has(id), `Missing DOM element ${id}`); return elements.get(id); };
// <select> defaults come from their selected <option>.
el("orientation").value = "horizontal"; el("resolution").value = "720p"; el("upscaler").value = "ffmpeg";
const posts = [];
const context = {
  document: {getElementById: el, addEventListener() {}, querySelectorAll() {return []}, hidden: true},
  window: {addEventListener() {}}, localStorage: {getItem() {return ""}},
  location: {hash: ""}, setInterval() {}, clearInterval() {}, setTimeout() {}, clearTimeout() {},
  alert(message) {throw new Error(message)}, console, URL, FormData,
  async fetch(url, options) {
    if (options.method === "POST") {
      posts.push(JSON.parse(options.body));
      return {ok: true, status: 202, async json() {return {id: "created", request: posts.at(-1)}}};
    }
    if (url === "/api/models") return {ok: true, async json() {return [{key: "ltx25", name: "LTX", clip_seconds: 5,
      resolution: "1280x704", vertical_resolution: "704x1280", native_audio: true, license: "L", default: true}]}};
    return {ok: true, async json() {return []}};
  },
};
vm.createContext(context);
vm.runInContext(script, context);
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  // 720p is native: the upscaler is disabled and never sent as SeedVR2.
  assert.equal(el("upscaler").disabled, true);
  assert(el("upscalerPill").classes.has("off"));
  el("model").value = "ltx25"; el("prompt").value = "A lighthouse";
  el("upscaler").value = "seedvr2";
  await el("form").onsubmit({preventDefault() {}});
  assert.deepEqual([posts[0].orientation, posts[0].resolution, posts[0].upscaler], ["horizontal", "720p", "ffmpeg"]);
  el("orientation").value = "vertical"; el("orientation").onchange();
  el("resolution").value = "4k"; el("resolution").onchange();
  assert.equal(el("upscaler").disabled, false);
  assert(!el("upscalerPill").classes.has("off"));
  assert.match(el("license").textContent, /^704x1280 · upscaled to 2160x3840 with SeedVR2/);
  el("prompt").value = "A lighthouse";
  await el("form").onsubmit({preventDefault() {}});
  assert.deepEqual([posts[1].orientation, posts[1].resolution, posts[1].upscaler], ["vertical", "4k", "seedvr2"]);
  el("resolution").value = "1080p"; el("resolution").onchange();
  el("upscaler").value = "ffmpeg"; el("upscaler").onchange();
  assert.match(el("license").textContent, /^704x1280 · upscaled to 1080x1920 with FFmpeg/);
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    html = Path(__file__).parents[1] / "video_platform" / "static" / "index.html"
    result = subprocess.run(["node", "-e", script, str(html)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
