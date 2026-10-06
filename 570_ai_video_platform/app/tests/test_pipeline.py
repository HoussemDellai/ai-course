"""End-to-end: real Agent Framework workflow + real ffmpeg, fake ComfyUI / LLM / Speech."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from fakes import FakeComfy, FakeNarrator, FakeTeam, make_clip, requires_ffmpeg, tiny_model
from video_platform import media
from video_platform.api import create_app, job_events
from video_platform.config import Settings
from video_platform.jobs import JobManager
from video_platform.operations import OpKind, OpStatus, load_operations
from video_platform.schemas import JobStatus, VideoRequest
from video_platform.storage import LocalArtifactStore
from video_platform.video_models import VIDEO_MODELS
from video_platform.workflow import PipelineDeps, build_video_workflow

pytestmark = requires_ffmpeg


@pytest.fixture
def settings(tmp_path):
    return Settings(local_output_dir=tmp_path / "out", work_dir=tmp_path / "work", output_width=320,
                    output_height=180, output_fps=12, clip_retries=0)


def make_services(settings, tmp_path, monkeypatch, model_key: str, clip_seconds=2.5, narration_seconds=9.0):
    base = VIDEO_MODELS[model_key]
    model = tiny_model(base, frames=int(clip_seconds * base.fps), fps=base.fps)
    monkeypatch.setitem(VIDEO_MODELS, model_key, model)
    clip = make_clip(tmp_path / "sample.mp4", clip_seconds, base.fps, 320, 176, audio=model.has_audio)
    fake_comfy = FakeComfy(clip)
    team, narrator = FakeTeam(), FakeNarrator(narration_seconds)
    store = LocalArtifactStore(settings.local_output_dir)
    pool = fake_comfy.pool(servers=2)

    def factory(manager):
        return build_video_workflow(PipelineDeps(settings=settings, team=team, comfy=pool, narrator=narrator,
                                                 store=store, progress=manager.progress, ops=manager.recorder))

    async def close():
        await pool.aclose()

    return store, factory, close, fake_comfy, team, narrator


@pytest.mark.parametrize("model_key", ["wan22", "ltx2"])
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

    ops = await manager.operations(state.id)
    steps = [o for o in ops if o.kind == OpKind.step]
    assert [s.attrs["step"] for s in steps] == ["enhance_prompt", "plan_storyboard", "generate_clips", "narrate",
                                                "assemble"]
    assert all(s.status == OpStatus.succeeded and s.run == 1 for s in steps)
    step_ids = {s.attrs["step"]: s.id for s in steps}
    agents = [o for o in ops if o.kind == OpKind.agent]
    assert [a.title for a in agents][:2] == ["prompt-enhancer", "story-outliner"] and len(agents) == 4
    clips = [o for o in ops if o.kind == OpKind.clip]
    assert len(clips) == 6 and all(c.parent_id == step_ids["generate_clips"] for c in clips)
    assert all(c.status == OpStatus.succeeded and c.attrs["server"].startswith("http://comfy")
               and c.attrs["prompt_id"] for c in clips)
    assert sum(o.kind == OpKind.narration for o in ops) == 2
    assert any(o.kind == OpKind.upload and o.parent_id == step_ids["assemble"] for o in ops)
    assert steps[2].progress_done == steps[2].progress_total == 6
    assert [o.id for o in await load_operations(store, state.id)] == [o.id for o in ops], "persisted"
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
                    "generate_clips": OpStatus.reused, "narrate": OpStatus.reused, "assemble": OpStatus.succeeded}
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
        assert len(client.get("/api/models", headers=h).json()) == 3
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
        assert sum(o["kind"] == "step" for o in ops) == 5 and all(o["status"] == "succeeded" for o in ops)
        assert client.get("/api/videos/nope/operations", headers=h).status_code == 404
        assert client.get(f"/api/videos/{job_id}/events").status_code == 401
        with client.stream("GET", f"/api/videos/{job_id}/events?key=secret") as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            events = [line.removeprefix("event: ") for line in r.iter_lines() if line.startswith("event: ")]
        assert events[0] == "state" and events.count("op") == len(ops) and events[-1] == "end"
        r = client.get(f"/api/videos/{job_id}/download?key=secret")
        assert r.status_code == 200 and r.headers["content-type"] == "video/mp4" and len(r.content) > 1000
        assert client.get("/").status_code == 200
