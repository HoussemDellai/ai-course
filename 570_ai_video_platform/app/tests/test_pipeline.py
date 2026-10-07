"""End-to-end: real Agent Framework workflow + real ffmpeg, fake ComfyUI / LLM / Speech."""

import asyncio
import json
import re
import subprocess

import pytest
from fastapi.testclient import TestClient

from fakes import FakeComfy, FakeNarrator, FakeTeam, make_clip, make_flac, make_png, requires_ffmpeg, tiny_model
from video_platform import media
from video_platform.api import create_app, job_events
from video_platform.config import Settings
from video_platform.images import sanitize_image
from video_platform.jobs import JobManager
from video_platform.operations import OpKind, OpStatus, load_operations
from video_platform.schemas import JobStatus, VideoRequest
from video_platform.storage import LocalArtifactStore
from video_platform.video_models import RESOLUTIONS, VIDEO_MODELS
from video_platform.workflow import REFERENCE_IMAGE, PipelineDeps, build_video_workflow

pytestmark = requires_ffmpeg


@pytest.fixture
def settings(tmp_path, monkeypatch):
    # Tiny output formats so the tests run fast (each keeps its aspect ratio and the 1.5x / 3x upscale factors).
    for key, size in {"720p": (320, 180), "1080p": (480, 270), "4k": (960, 540)}.items():
        monkeypatch.setitem(RESOLUTIONS, key, size)
    return Settings(local_output_dir=tmp_path / "out", work_dir=tmp_path / "work", output_fps=12, clip_retries=0)


def make_services(settings, tmp_path, monkeypatch, model_key: str, clip_seconds=2.5, narration_seconds=9.0,
                  clip_size=(320, 176), fail_upscale=False):
    base = VIDEO_MODELS[model_key]
    model = tiny_model(base, frames=int(clip_seconds * base.fps), fps=base.fps)
    monkeypatch.setitem(VIDEO_MODELS, model_key, model)
    clip = make_clip(tmp_path / "sample.mp4", clip_seconds, base.fps, *clip_size, audio=model.has_audio)
    fake_comfy = FakeComfy(clip, music=make_flac(tmp_path / "music.flac", 12.0), fail_upscale=fail_upscale)
    team, narrator = FakeTeam(), FakeNarrator(narration_seconds)
    store = LocalArtifactStore(settings.local_output_dir)
    pool = fake_comfy.pool(servers=2)

    def factory(manager):
        return build_video_workflow(PipelineDeps(settings=settings, team=team, comfy=pool, narrator=narrator,
                                                 store=store, progress=manager.progress, ops=manager.recorder))

    async def close():
        await pool.aclose()

    return store, factory, close, fake_comfy, team, narrator


@pytest.mark.parametrize("model_key", ["wan22", "ltx2", "ltx25"])
async def test_full_pipeline(settings, tmp_path, monkeypatch, model_key):
    store, factory, close, fake_comfy, team, narrator = make_services(settings, tmp_path, monkeypatch, model_key)
    manager = JobManager(settings, store, factory)
    # 6 s requested with 1 s clips -> 6 shots, 2 scenes of 3 shots; 3 s narration fits in 0.4 + 3 + 0.6 = 4 s
    state = await manager.create(VideoRequest(prompt="a lighthouse keeper", duration_minutes=0.25,
                                              video_model=model_key))
    await asyncio.wait_for(manager.wait(state.id), 120)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error
    assert final.clips_total == 6 and final.clips_done == 6
    assert final.title == "The Last Lighthouse"
    assert len(fake_comfy.submitted) == 6
    assert narrator.texts == ["The island wakes up.", "The storm comes."]
    video = store.path(state.id, "final.mp4")
    duration, has_audio = await media.probe(video)
    assert has_audio
    assert 19.5 < duration < 20.8, duration
    storyboard = json.loads(store.path(state.id, "storyboard.json").read_text())
    assert len(storyboard["scenes"]) == 2 and storyboard["video_model"] == model_key
    assert [s["narration"] for s in storyboard["scenes"]] == narrator.texts, "speaker labels stripped"

    ops = await manager.operations(state.id)
    steps = [o for o in ops if o.kind == OpKind.step]
    assert [s.attrs["step"] for s in steps] == ["enhance_prompt", "plan_storyboard", "generate_keyframes",
                                                "generate_clips", "process_shots", "narrate", "generate_music",
                                                "assemble"]
    assert all(s.run == 1 for s in steps)
    skipped = {"generate_keyframes", "generate_music"}
    assert {s.attrs["step"]: s.status for s in steps if s.attrs["step"] in skipped} == {
        "generate_keyframes": OpStatus.skipped, "generate_music": OpStatus.skipped}
    assert all(s.status == OpStatus.succeeded for s in steps if s.attrs["step"] not in skipped)
    step_ids = {s.attrs["step"]: s.id for s in steps}
    agents = [o for o in ops if o.kind == OpKind.agent]
    assert [a.title for a in agents][:2] == ["prompt-enhancer", "story-outliner"] and len(agents) == 4
    assert team.images == [None] and not fake_comfy.uploads
    assert not any(o.kind == OpKind.keyframe for o in ops)
    clips = [o for o in ops if o.kind == OpKind.clip]
    assert len(clips) == 6 and all(c.parent_id == step_ids["generate_clips"] for c in clips)
    assert all(c.status == OpStatus.succeeded and c.attrs["server"].startswith("http://comfy")
               and c.attrs["prompt_id"] and "keyframe" not in c.attrs for c in clips)
    assert sum(o.kind == OpKind.narration for o in ops) == 2
    assert any(o.kind == OpKind.upload and o.parent_id == step_ids["assemble"] for o in ops)
    assert steps[3].progress_done == steps[3].progress_total == 6
    assert [o.id for o in await load_operations(store, state.id)] == [o.id for o in ops], "persisted"
    await close()


def max_volume(path, start: float, seconds: float) -> float:
    """Peak level in dB of the audio between start and start + seconds."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-ss", str(start), "-t", str(seconds), "-i", str(path),
                          "-af", "volumedetect", "-f", "null", "-"], capture_output=True, text=True, check=True)
    return float(re.search(r"max_volume: (-?[\d.]+|-inf) dB", out.stderr).group(1).replace("-inf", "-200"))


@pytest.mark.parametrize("model_key", ["wan22", "ltx25"])
async def test_pipeline_with_music(settings, tmp_path, monkeypatch, model_key):
    store, factory, close, fake_comfy, team, _ = make_services(settings, tmp_path, monkeypatch, model_key)
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse keeper", duration_minutes=0.25,
                                              video_model=model_key, music=True))
    await asyncio.wait_for(manager.wait(state.id), 120)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error

    # One music render per scene, after all the clips, so ComfyUI swaps models once.
    is_music = lambda w: any(n["class_type"] == "SaveAudio" for n in w.values())
    music_wfs = [w for w in fake_comfy.submitted if is_music(w)]
    assert len(fake_comfy.submitted) == 8 and len(music_wfs) == 2
    assert all(is_music(w) for w in fake_comfy.submitted[6:])
    # 9 s narration in 7.5 s of clips: the scene is held to 0.4 + 9 + 0.6 = 10 s, the music gets 1 s of margin.
    assert team.music_durations == pytest.approx([10.0, 10.0], abs=0.05)
    encoders = [next(n["inputs"] for n in w.values() if n["class_type"] == "MiniMaxMusic3TextEncode")
                for w in music_wfs]
    assert all(e["max_duration"] == 11.0 and isinstance(e["max_duration"], float) for e in encoders)
    assert all(e["lyrics"] == "[Instrumental]" and "Instrumental only" in e["caption"] for e in encoders)
    assert sorted(e["caption"].splitlines()[0] for e in encoders) == [
        "Global Metadata: ambient score for Dawn.", "Global Metadata: ambient score for Storm."]

    video = store.path(state.id, "final.mp4")
    duration, has_audio = await media.probe(video)
    assert has_audio and 19.5 < duration < 20.8, duration
    # Before the narration's 0.4 s lead-in only the music (fading in) can be heard.
    assert max_volume(video, 0.15, 0.2) > -60
    assert json.loads(store.path(state.id, "music.json").read_text())["theme"]
    assert all(store.path(state.id, f"music/scene_{i:03d}.flac").exists() for i in range(2))

    ops = await manager.operations(state.id)
    step = next(o for o in ops if o.attrs.get("step") == "generate_music")
    assert step.status == OpStatus.succeeded and step.attrs["model"] == "MiniMax-Music3"
    assert step.progress_done == step.progress_total == 2
    cues = [o for o in ops if o.kind == OpKind.music]
    assert len(cues) == 2 and all(c.parent_id == step.id and c.attrs["prompt_id"] for c in cues)
    assert any(o.kind == OpKind.agent and o.title == "music-director" and o.parent_id == step.id for o in ops)
    assert sum(o.kind == OpKind.ffmpeg and o.title.endswith("+ mix music") for o in ops) == 2
    await close()


async def test_music_is_reused_on_resume(settings, tmp_path, monkeypatch):
    store, factory, close, fake_comfy, team, _ = make_services(settings, tmp_path, monkeypatch, "wan22")
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, music=True))
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.completed

    await manager.progress(state.id, JobStatus.assembling)  # crash during assembly
    submitted, calls = len(fake_comfy.submitted), list(team.calls)
    manager2 = JobManager(settings, store, factory)
    await manager2.resume_unfinished()
    await manager2.wait(state.id)
    assert (await manager2.get(state.id)).status == JobStatus.completed
    assert len(fake_comfy.submitted) == submitted and team.calls == calls, "music and its plan are reused"
    run2 = {o.attrs.get("step"): o.status for o in await manager2.operations(state.id)
            if o.run == 2 and o.kind == OpKind.step}
    assert run2["generate_music"] == OpStatus.reused
    await close()


@pytest.mark.parametrize("model_key", ["wan22", "ltx2", "ltx25", "hunyuan15"])
async def test_pipeline_from_reference_photo(settings, tmp_path, monkeypatch, model_key):
    store, factory, close, fake_comfy, team, _ = make_services(settings, tmp_path, monkeypatch, model_key)
    manager = JobManager(settings, store, factory)
    photo = sanitize_image(make_png(800, 600), settings.max_image_bytes)
    # A client can't point the job at an arbitrary file: reference_image is derived from the uploaded image.
    state = await manager.create(VideoRequest(prompt="a lighthouse keeper", duration_minutes=0.25,
                                              video_model=model_key), image=photo)
    assert state.request.reference_image is True
    assert store.path(state.id, REFERENCE_IMAGE).read_bytes() == photo
    await asyncio.wait_for(manager.wait(state.id), 120)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error

    # The prompt-enhancer saw the photo; the shot-writers wrote keyframe prompts.
    assert team.images == [photo]
    assert sorted(c for c in team.calls if c.startswith("shots")) == ["shots-0-keyframes", "shots-1-keyframes"]
    storyboard = json.loads(store.path(state.id, "storyboard.json").read_text())
    shots = [s for scene in storyboard["scenes"] for s in scene["shots"]]
    assert all(s["keyframe_prompt"].startswith("Keep the man from image 1") for s in shots)
    assert json.loads(store.path(state.id, "brief.json").read_text())["reference_notes"]

    # 6 Qwen-Image-Edit keyframes from the photo, then 6 image-to-video clips from the keyframes.
    keyframe_wfs = [w for w in fake_comfy.submitted if any(n["class_type"] == "SaveImage" for n in w.values())]
    clip_wfs = [w for w in fake_comfy.submitted if any(n["class_type"] == "SaveVideo" for n in w.values())]
    assert len(keyframe_wfs) == 6 and len(clip_wfs) == 6
    assert fake_comfy.submitted[:6] == keyframe_wfs, "all keyframes are rendered before any clip"
    load_images = lambda w: [n["inputs"]["image"] for n in w.values() if n["class_type"] == "LoadImage"]
    assert all(load_images(w) == [f"aivideo/{state.id}/reference.png"] for w in keyframe_wfs)
    assert sorted(load_images(w)[0] for w in clip_wfs) == [f"aivideo/{state.id}/shot_{i:03d}.png" for i in range(6)]
    i2v_node = {"wan22": "WanImageToVideo", "ltx2": "LTXVImgToVideoInplace", "ltx25": "LTXVImgToVideoInplace",
                "hunyuan15": "HunyuanVideo15ImageToVideo"}[model_key]
    assert all(any(n["class_type"] == i2v_node for n in w.values()) for w in clip_wfs)
    keyframe_size = {(n["inputs"]["width"], n["inputs"]["height"]) for w in keyframe_wfs for n in w.values()
                     if n["class_type"] == "EmptySD3LatentImage"}
    assert keyframe_size == {(VIDEO_MODELS[model_key].width, VIDEO_MODELS[model_key].height)}
    assert {(sub, name) for _, sub, name in fake_comfy.uploads} >= {(f"aivideo/{state.id}", "reference.png")}
    for i in range(6):
        assert store.path(state.id, f"keyframes/shot_{i:03d}.png").read_bytes() == fake_comfy.image_bytes

    ops = await manager.operations(state.id)
    steps = {o.attrs["step"]: o for o in ops if o.kind == OpKind.step}
    assert steps["generate_keyframes"].status == OpStatus.succeeded
    assert steps["generate_keyframes"].progress_done == 6
    assert steps["generate_clips"].attrs["mode"] == "image-to-video"
    keyframes = [o for o in ops if o.kind == OpKind.keyframe]
    assert len(keyframes) == 6 and all(k.parent_id == steps["generate_keyframes"].id for k in keyframes)
    assert sorted(k.attrs["shot"] for k in keyframes) == list(range(6))
    assert all(k.status == OpStatus.succeeded and k.attrs["prompt_id"] for k in keyframes)
    assert all(c.attrs["keyframe"] for c in ops if c.kind == OpKind.clip)
    assert storyboard["scenes"] and final.title == "The Last Lighthouse"

    # Resume after a crash reuses the keyframes and clips: nothing is sent to ComfyUI again.
    await manager.progress(state.id, JobStatus.generating)
    submitted = len(fake_comfy.submitted)
    manager2 = JobManager(settings, store, factory)
    await manager2.resume_unfinished()
    await manager2.wait(state.id)
    assert (await manager2.get(state.id)).status == JobStatus.completed
    assert len(fake_comfy.submitted) == submitted
    run2 = {o.attrs["step"]: o.status for o in await manager2.operations(state.id)
            if o.run == 2 and o.kind == OpKind.step}
    assert run2["generate_keyframes"] == OpStatus.reused and run2["generate_clips"] == OpStatus.reused
    await close()


async def test_resume_reuses_artifacts(settings, tmp_path, monkeypatch):
    store, factory, close, fake_comfy, team, _ = make_services(settings, tmp_path, monkeypatch, "wan22")
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, video_model="wan22"))
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.completed

    # Simulate a crash during assembly: the job is unfinished but its artifacts exist.
    await manager.progress(state.id, JobStatus.generating)
    submitted, calls = len(fake_comfy.submitted), list(team.calls)
    manager2 = JobManager(settings, store, factory)
    await manager2.resume_unfinished()
    await manager2.wait(state.id)
    assert (await manager2.get(state.id)).status == JobStatus.completed
    assert len(fake_comfy.submitted) == submitted, "clips must not be regenerated"
    assert team.calls == calls, "LLM steps must not be re-run"
    run2 = {o.attrs.get("step"): o.status for o in await manager2.operations(state.id)
            if o.run == 2 and o.kind == OpKind.step}
    assert run2 == {"enhance_prompt": OpStatus.reused, "plan_storyboard": OpStatus.reused,
                    "generate_keyframes": OpStatus.skipped, "generate_clips": OpStatus.reused,
                    "process_shots": OpStatus.reused,
                    "narrate": OpStatus.reused, "generate_music": OpStatus.skipped, "assemble": OpStatus.succeeded}
    await close()


async def test_failed_job_reports_error(settings, tmp_path, monkeypatch):
    store, factory, close, fake_comfy, *_ = make_services(settings, tmp_path, monkeypatch, "hunyuan15")
    fake_comfy.fail_first = 10_000
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, video_model="hunyuan15"))
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.failed
    assert "ComfyUI" in final.error
    ops = await manager.operations(state.id)
    generate = next(o for o in ops if o.attrs.get("step") == "generate_clips")
    assert generate.status == OpStatus.failed and "ComfyUI" in generate.error
    failed_clips = [o for o in ops if o.kind == OpKind.clip and o.status == OpStatus.failed]
    assert failed_clips and any("failed on" in line.message for line in failed_clips[0].logs)
    assert not any(o.attrs.get("step") == "narrate" for o in ops), "later steps never started"

    fake_comfy.fail_first = 0
    await manager.retry(state.id)
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.completed
    ops = await manager.operations(state.id)
    assert {o.run for o in ops} == {1, 2}
    assert all(o.status == OpStatus.succeeded for o in ops if o.run == 2 and o.kind == OpKind.clip)
    await close()


async def collect_events(manager, job_id):
    events = []
    async for chunk in job_events(manager, job_id, poll_seconds=0.05):
        for block in chunk.strip().split("\n\n"):
            lines = dict(line.split(": ", 1) for line in block.splitlines() if not line.startswith(":"))
            if "event" in lines:
                events.append((lines["event"], json.loads(lines["data"])))
    return events


async def test_event_stream_live_and_from_another_replica(settings, tmp_path, monkeypatch):
    store, factory, close, *_ = make_services(settings, tmp_path, monkeypatch, "wan22")
    owner = JobManager(settings, store, factory)
    viewer = JobManager(settings, store, factory)  # another replica: only sees the store
    state = await owner.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, video_model="wan22"))
    live, remote = await asyncio.wait_for(
        asyncio.gather(collect_events(owner, state.id), collect_events(viewer, state.id)), 120)
    final_ops = {o.id: o.model_dump(mode="json") for o in await owner.operations(state.id)}
    for events in (live, remote):
        assert events[0][0] == "state" and events[-1] == ("end", None)
        assert [d for e, d in events if e == "state"][-1]["status"] == "completed"
        last_op = {}
        for event, data in events:
            if event == "op":
                last_op[data["id"]] = data
        assert last_op == final_ops
    assert len([e for e, _ in live if e == "op"]) > len(final_ops), "live stream sends every update"
    await close()


async def test_event_stream_follows_store_while_a_local_task_waits(settings, tmp_path, monkeypatch):
    """A resume task queued on this replica (waiting for a slot) must not freeze the timeline of a job
    that another replica runs."""
    store, factory, close, *_ = make_services(settings, tmp_path, monkeypatch, "wan22")
    owner = JobManager(settings, store, factory)
    viewer = JobManager(settings, store, factory)
    state = await owner.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, video_model="wan22"))
    waiting = asyncio.get_running_loop().create_future()
    viewer._tasks[state.id] = waiting  # queued here, but never got the lease
    stream = asyncio.create_task(collect_events(viewer, state.id))
    await asyncio.wait_for(owner.wait(state.id), 120)
    await asyncio.sleep(0.5)
    assert not stream.done(), "stays open while a local task may still run the job"
    del viewer._tasks[state.id]
    waiting.cancel()
    events = await asyncio.wait_for(stream, 10)
    last_op = {}
    for event, data in events:
        if event == "op":
            last_op[data["id"]] = data
    assert last_op == {o.id: o.model_dump(mode="json") for o in await owner.operations(state.id)}
    assert events[-1] == ("end", None)
    await close()


def test_api(settings, tmp_path, monkeypatch):
    settings = Settings(**{**settings.__dict__, "api_key": "secret"})
    store, factory, close, *_ = make_services(settings, tmp_path, monkeypatch, "wan22")
    app = create_app(settings, services=(store, factory, close))
    with TestClient(app) as client:
        assert client.get("/healthz").status_code == 200
        assert client.get("/api/videos").status_code == 401
        h = {"X-API-Key": "secret"}
        models = client.get("/api/models", headers=h).json()
        assert [m["key"] for m in models] == list(VIDEO_MODELS) and "ltx25" in VIDEO_MODELS
        assert client.post("/api/videos", headers=h, json={"prompt": "a lighthouse", "video_model": "nope"}).status_code == 422
        assert client.post("/api/videos", headers=h, json={"prompt": "a lighthouse", "duration_minutes": 11}).status_code == 422
        r = client.post("/api/videos", headers=h, json={"prompt": "a lighthouse", "duration_minutes": 0.25})
        assert r.status_code == 202
        job_id = r.json()["id"]
        assert r.json()["request"]["video_model"] == "wan22"
        for _ in range(300):
            state = client.get(f"/api/videos/{job_id}", headers=h).json()
            if state["status"] in ("completed", "failed"):
                break
            import time
            time.sleep(0.2)
        assert state["status"] == "completed", state
        assert client.get(f"/api/videos/{job_id}/storyboard", headers=h).status_code == 200
        ops = client.get(f"/api/videos/{job_id}/operations", headers=h).json()
        assert sum(o["kind"] == "step" for o in ops) == 8
        assert all(o["status"] == ("skipped" if o["attrs"].get("step") in ("generate_keyframes", "generate_music")
                                   else "succeeded") for o in ops)
        assert client.get(f"/api/videos/{job_id}/image", headers=h).status_code == 404  # text-only video

        # Every intermediate video recorded in the operations can be previewed, with the key, and seeked.
        artifacts = [o["attrs"][k] for o in ops for k in ("artifact", "voice_artifact", "music_artifact")
                     if k in o["attrs"]]
        assert sorted(a.split("/")[0] for a in artifacts if "/" in a) == ["clips"] * 6 + ["processed"] * 6 + [
            "scenes"] * 4 and "final.mp4" in artifacts
        media_url = f"/api/videos/{job_id}/media"
        for name in artifacts:
            r = client.get(f"{media_url}/{name}?key=secret")
            assert r.status_code == 200 and r.headers["content-type"] == "video/mp4", name
        assert client.get(f"{media_url}/clips/shot_000.mp4").status_code == 401
        assert client.get(f"{media_url}/clips/shot_000.mp4?key=wrong").status_code == 401
        r = client.get(f"{media_url}/processed/shot_000.mp4", headers={**h, "Range": "bytes=0-99"})
        assert r.status_code == 206 and len(r.content) == 100
        for bad in ("state.json", "storyboard.json", "input/reference.png", "clips/shot_000.pending.json",
                    "clips/../state.json", "..%2Fstate.json", "clips/shot_0.mp4", "final.mp4/x"):
            assert client.get(f"{media_url}/{bad}", headers=h).status_code == 404, bad
        assert client.get(f"{media_url}/upscaled/shot_000.mp4", headers=h).status_code == 404  # ffmpeg job
        assert client.get("/api/videos/nope/media/final.mp4", headers=h).status_code == 404
        for field, value in (("orientation", "square"), ("resolution", "8k"), ("upscaler", "magic")):
            assert client.post("/api/videos", headers=h, json={"prompt": "a lighthouse", field: value}).status_code == 422
        request = client.get(f"/api/videos/{job_id}", headers=h).json()["request"]
        assert (request["orientation"], request["resolution"], request["upscaler"]) == ("horizontal", "720p", "ffmpeg")
        assert client.get("/api/videos/nope/operations", headers=h).status_code == 404
        assert client.get(f"/api/videos/{job_id}/events").status_code == 401
        with client.stream("GET", f"/api/videos/{job_id}/events?key=secret") as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            events = [line.removeprefix("event: ") for line in r.iter_lines() if line.startswith("event: ")]
        assert events[0] == "state" and events.count("op") == len(ops) and events[-1] == "end"
        r = client.get(f"/api/videos/{job_id}/download?key=secret")
        assert r.status_code == 200 and r.headers["content-type"] == "video/mp4" and len(r.content) > 1000
        assert client.get("/").status_code == 200


def test_api_reference_photo(settings, tmp_path, monkeypatch):
    settings = Settings(**{**settings.__dict__, "api_key": "secret", "max_image_mb": 1})
    store, factory, close, fake_comfy, team, _ = make_services(settings, tmp_path, monkeypatch, "wan22")
    app = create_app(settings, services=(store, factory, close))
    h = {"X-API-Key": "secret"}
    request = json.dumps({"prompt": "a lighthouse keeper", "duration_minutes": 0.25})
    photo = make_png(640, 480, fmt="JPEG")
    with TestClient(app) as client:
        post = lambda **kw: client.post("/api/videos", headers=h, **kw)
        assert client.get("/api/config", headers=h).json() == {"max_image_mb": 1}
        # JSON clients can't flag a photo that was never uploaded.
        r = post(json={"prompt": "a lighthouse", "duration_minutes": 0.25, "reference_image": True})
        assert r.status_code == 202 and r.json()["request"]["reference_image"] is False
        assert client.get(f"/api/videos/{r.json()['id']}/image", headers=h).status_code == 404

        assert post(files={"image": ("a.txt", b"not an image", "text/plain")}, data={"request": request}).status_code == 415
        gif = make_png(10, 10, fmt="GIF")
        assert post(files={"image": ("a.gif", gif, "image/gif")}, data={"request": request}).status_code == 415
        big = make_png(1024, 1024, fmt="BMP")  # ~3 MB > 1 MB limit
        assert post(files={"image": ("big.png", big, "image/png")}, data={"request": request}).status_code == 413

        def chunked(image: bytes, req: str, padding: int = 0):
            """A multipart body streamed without Content-Length (Transfer-Encoding: chunked)."""
            yield f'--b\r\nContent-Disposition: form-data; name="request"\r\n\r\n{req}\r\n'.encode()
            if padding:  # a huge non-file part: only the byte counter (not the form parser) answers 413
                yield b'--b\r\nContent-Disposition: form-data; name="padding"\r\n\r\n'
                for _ in range(padding // 65536):
                    yield b"x" * 65536
                yield b"\r\n"
            yield (b'--b\r\nContent-Disposition: form-data; name="image"; filename="a.png"\r\n'
                   b'Content-Type: image/png\r\n\r\n')
            for i in range(0, len(image), 65536):
                yield image[i:i + 65536]
            yield b"\r\n--b--\r\n"

        multipart = {**h, "Content-Type": "multipart/form-data; boundary=b"}
        r = client.post("/api/videos", content=chunked(photo, request, padding=3 * 1024 * 1024), headers=multipart)
        assert r.status_code == 413 and "content-length" not in r.request.headers
        # A small chunked upload is parsed normally (an unknown model is rejected after parsing: no job starts).
        r = client.post("/api/videos", content=chunked(photo, bad_model := json.dumps(
            {"prompt": "a lighthouse", "video_model": "nope"})), headers=multipart)
        assert r.status_code == 422 and "nope" in r.text
        assert post(files={"image": ("a.jpg", photo, "image/jpeg")}).status_code == 422  # no 'request' field
        bad = json.dumps({"prompt": "a lighthouse", "duration_minutes": 11})
        assert post(files={"image": ("a.jpg", photo, "image/jpeg")}, data={"request": bad}).status_code == 422
        assert post(files={"image": ("a.jpg", photo, "image/jpeg")}, data={"request": bad_model}).status_code == 422

        r = post(files={"image": ("me.jpg", photo, "image/jpeg")}, data={"request": request})
        assert r.status_code == 202, r.text
        job_id = r.json()["id"]
        assert r.json()["request"]["reference_image"] is True
        image = client.get(f"/api/videos/{job_id}/image?key=secret")
        assert image.status_code == 200 and image.headers["content-type"] == "image/png"
        assert image.content.startswith(b"\x89PNG")
        import time
        for _ in range(300):
            state = client.get(f"/api/videos/{job_id}", headers=h).json()
            if state["status"] in ("completed", "failed"):
                break
            time.sleep(0.2)
        assert state["status"] == "completed", state
        assert team.images[-1] == image.content
        keyframe = client.get(f"/api/videos/{job_id}/keyframes/0?key=secret")
        assert keyframe.status_code == 200 and keyframe.content == fake_comfy.image_bytes
        assert client.get(f"/api/videos/{job_id}/keyframes/99", headers=h).status_code == 404
        assert client.get(f"/api/videos/{job_id}/keyframes/0").status_code == 401
