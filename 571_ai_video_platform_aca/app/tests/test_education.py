import asyncio
import re
import subprocess
from dataclasses import replace
from types import SimpleNamespace

import pytest
from agent_framework import Content, Message
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fakes import FakeComfy, FakeNarrator, FakeTeam, IndependentComfy, make_clip, make_flac, make_png, requires_ffmpeg
from video_platform import media
from video_platform.api import create_app, job_events
from video_platform.config import Settings
from video_platform.education import (
    APPROVAL, DRAFT, build_educational_workflow, music_indices, scene_durations, validate_education_request,
)
from video_platform.education_agents import FoundryEducationTeam
from video_platform.education_visuals import EducationalVisuals, QWEN_T2I_WORKFLOW
from video_platform.education_schemas import (
    DraftUpdate, EducationalBrief, EducationalDraft, EducationalScene, ResearchReport, ResearchSource,
    TechnicalDiagram,
)
from video_platform.jobs import JobManager, ReviewConflict
from video_platform.schemas import JobStatus, VideoBatchRequest, VideoRequest
from video_platform.storage import LocalArtifactStore, read_json
from video_platform.video_models import RESOLUTIONS, VIDEO_MODELS
from video_platform.workflow import PipelineDeps


def sample_draft(revision=1):
    return EducationalDraft(
        revision=revision,
        brief=EducationalBrief(title="How Pods Work", description="A clear explanation of Kubernetes Pods",
                               audience="Developers", objectives=["Understand Pods"], language="en-US",
                               visual_theme="Clean blue and white vector illustrations"),
        research=ResearchReport(summary="Pods group one or more containers.",
                                sources=[ResearchSource(id="s1", title="Pods",
                                                        url="https://kubernetes.io/docs/concepts/workloads/pods/")]),
        scenes=[EducationalScene(
            title=title, description=f"Show {title}", narration=f"This is the {title.lower()}.",
            image_prompt="A clean illustration of containers", source_ids=["s1"], role=role,
        ) for title, role in [("Introduction", "intro"), ("Explanation", "content"), ("Summary", "outro")]],
    )


class FakeEducationTeam:
    def __init__(self):
        self.research_calls = []
        self.plan_calls = 0

    async def research(self, topic):
        self.research_calls.append(topic)
        return sample_draft().research

    async def plan(self, prompt, options, research, seconds, revision):
        self.plan_calls += 1
        return sample_draft(revision)


class FakeVisuals:
    def __init__(self):
        self.images = []
        self.motion_calls = 0
        self.animation_calls = 0

    def companion_assets(self, image, scene):
        return {"diagram_xml": image.with_suffix(".drawio")}

    async def image(self, scene, width, height, seed, dest, **kwargs):
        self.images.append(scene.image_prompt)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(make_png(width, height))
        return dest

    async def diagram(self, scene, width, height, dest):
        await self.image(scene, width, height, 1, dest)
        dest.with_suffix(".drawio").write_text("<mxfile/>")
        return dest

    async def motion(self, image, prompt, model, seed, dest, **kwargs):
        self.motion_calls += 1
        return await self.animate(image, None, model.clip_seconds, 160, 90, 12, dest)

    async def animate(self, image, scene, seconds, width, height, fps, dest):
        self.animation_calls += 1
        dest.parent.mkdir(parents=True, exist_ok=True)
        await media.run("ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(image),
                        "-vf", f"scale={width}:{height},fps={fps}", "-t", f"{seconds:.9f}",
                        *media.VIDEO_ENCODE, "-an", str(dest))
        return dest


@pytest.fixture
def setup(tmp_path, monkeypatch):
    monkeypatch.setitem(RESOLUTIONS, "1080p", (160, 90))
    monkeypatch.setitem(RESOLUTIONS, "4k", (320, 180))
    settings = Settings(local_output_dir=tmp_path / "out", work_dir=tmp_path / "work", output_fps=12,
                        education_search_model="search", speech_endpoint="https://speech.example",
                        comfy_image_workflow="configured", drawio_mcp_url="http://localhost:3001/mcp",
                        drawio_export_command="configured")
    store = LocalArtifactStore(settings.local_output_dir)
    team, visuals, narrator = FakeEducationTeam(), FakeVisuals(), FakeNarrator(5.25)
    comfy = FakeComfy(music=make_flac(tmp_path / "sample.flac", 12)).pool()

    def factory(manager):
        deps = PipelineDeps(settings=settings, team=FakeTeam(), comfy=comfy, narrator=narrator, store=store,
                            progress=manager.progress, ops=manager.recorder)
        return build_educational_workflow(deps, team, visuals)

    async def close():
        await comfy.aclose()

    return settings, store, team, visuals, narrator, factory, close


def request(**values):
    return VideoRequest(
        prompt="Explain Kubernetes Pods", use_case="educational", duration_minutes=0.25,
        education={"public_topic": "Kubernetes Pods", "music_mode": "off"},
        **values,
    )


@requires_ffmpeg
async def test_sequential_education_batch_waits_for_each_review(setup):
    settings, store, _, _, _, factory, close = setup
    manager = JobManager(settings, store, factory)
    batch = await manager.create_batch(VideoBatchRequest(request=request(), variants=[
        {"video_model": "wan22"}, {"video_model": "ltx25"},
    ]))
    try:
        for index, state in enumerate(batch.jobs):
            await asyncio.wait_for(manager.wait(state.id), 90)
            paused = await manager.get(state.id)
            assert paused.status == JobStatus.awaiting_review
            assert not await store.exists(state.id, "final.mp4")
            if index == 0:
                following = await manager.get(batch.jobs[1].id)
                assert following.status == JobStatus.queued
                assert not await store.exists(following.id, DRAFT)
            await manager.review(state.id, paused.draft_revision, action="approve")
            await asyncio.wait_for(manager.wait(state.id), 90)
            final = await manager.get(state.id)
            assert final.status == JobStatus.completed, final.error
            assert (await media.probe(store.path(state.id, "final.mp4")))[1]
    finally:
        await manager.shutdown()
        await close()


def test_educational_defaults_and_validation():
    assert request().resolution == "1080p"
    assert request().orientation == "horizontal"
    assert VideoRequest(prompt="A story").resolution == "720p"
    for values in [{"narration": False}, {"naturalistic": True}, {"resolution": "720p"},
                   {"reference_image": True}]:
        with pytest.raises(ValidationError):
            request(**values)
    with pytest.raises(ValidationError, match="public_topic"):
        VideoRequest(prompt="Teach something", use_case="educational")
    with pytest.raises(ValidationError, match="existing nodes"):
        TechnicalDiagram(nodes=[{"id": "one", "label": "Pod", "icon_query": "Kubernetes Pod"}],
                         edges=[{"source": "one", "target": "absent"}])
    with pytest.raises(ValidationError, match="research sources"):
        draft = sample_draft().model_dump()
        draft["scenes"][0]["source_ids"] = ["fabricated"]
        EducationalDraft.model_validate(draft)
    with pytest.raises(ValidationError):
        EducationalScene.model_validate({**sample_draft().scenes[0].model_dump(), "narration": "   "})


def test_measured_duration_and_selective_music():
    assert scene_durations([9, 9, 9], 15, 24) == [10, 10, 10]
    assert sum(scene_durations([2.21, 2.4], 15, 24)) == 15
    assert all(abs(d * 24 - round(d * 24)) < 1e-8 for d in scene_durations([2.21, 2.4], 15, 24))
    with pytest.raises(ValueError, match="exceeding 10 minutes"):
        scene_durations([300, 300], 600, 24)
    draft = sample_draft()
    assert music_indices(draft, "intro_outro") == [0, 2]
    assert music_indices(draft, "off") == []
    assert music_indices(draft, "background") == [0, 1, 2]


@requires_ffmpeg
@pytest.mark.parametrize("style,scene_count,upscaler", [
    ("hybrid", 3, "ffmpeg"), ("ai_motion", 1, "ffmpeg"), ("ai_motion", 3, "seedvr2"),
])
async def test_educational_gpu_stages_use_independent_workers_in_order(
    setup, tmp_path, monkeypatch, style, scene_count, upscaler,
):
    settings, store, team, fake_visuals, narrator, _, close = setup
    settings = replace(settings, comfy_image_workflow=str(QWEN_T2I_WORKFLOW), clip_retries=0)
    narrator.seconds = 1
    model = replace(VIDEO_MODELS["wan22"], frames=24, fps=12, width=160, height=90)
    monkeypatch.setitem(VIDEO_MODELS, "wan22", model)
    clip = make_clip(tmp_path / "parallel.mp4", 2, 12, 160, 90, audio=False)
    fake = IndependentComfy(2, clip, music=make_flac(tmp_path / "parallel.flac", 16))
    for worker in fake.workers.values():
        worker.image_bytes = make_png(160, 96)
    # A single scene has one image/music cue, but must still render several clips in parallel.
    fake._first_wave.set()
    fake.delay_first_worker = True
    pool = fake.pool()
    visuals = EducationalVisuals(settings, pool, None)
    visuals.animate = fake_visuals.animate
    progress = []
    fail_final = True
    original_concat = media.concat

    async def concat(parts, dest, **kwargs):
        nonlocal fail_final
        if dest.name == "final.mp4":
            assert [path.stem for path in parts] == [f"scene_{i:03d}" for i in range(scene_count)]
            if fail_final:
                fail_final = False
                raise RuntimeError("restart after all persisted GPU artifacts")
        return await original_concat(parts, dest, **kwargs)

    monkeypatch.setattr(media, "concat", concat)

    async def plan(prompt, options, research, seconds, revision):
        draft = sample_draft(revision)
        draft.scenes = draft.scenes[:scene_count]
        return draft

    team.plan = plan

    def factory(manager):
        async def record(job_id, status=None, **fields):
            if "clips_done" in fields:
                progress.append(fields["clips_done"])
            await manager.progress(job_id, status, **fields)
        return build_educational_workflow(PipelineDeps(
            settings=settings, team=FakeTeam(), comfy=pool, narrator=narrator, store=store,
            progress=record, ops=manager.recorder,
        ), team, visuals)

    body = request(upscaler=upscaler).model_dump()
    body["education"].update(style=style, music_mode="background")
    manager = JobManager(settings, store, factory)
    try:
        state = await manager.create(VideoRequest.model_validate(body))
        await manager.wait(state.id)
        await manager.review(state.id, 1)
        await asyncio.wait_for(manager.wait(state.id), 90)
        final = await manager.get(state.id)
        assert final.status == JobStatus.failed
        assert final.error == "RuntimeError: restart after all persisted GPU artifacts"
        assert fake.peak == 2
        assert set(fake.completed) == {"comfy0", "comfy1"}
        assert fake.peak_by_stage["motion"] == 2
        expected_stages = ["image", "motion"]
        if upscaler == "seedvr2":
            expected_stages.append("upscale")
            assert fake.peak_by_stage["upscale"] == 2
        expected_stages.append("music")
        assert list(dict.fromkeys(fake.stages)) == expected_stages
        if scene_count > 1:
            assert fake.peak_by_stage["image"] == fake.peak_by_stage["music"] == 2
            assert fake.completed[0] == "comfy1", "Completion order must differ from scene order"
        assert progress == list(range(scene_count + 1))
        operations = await manager.operations(state.id)
        motion = [op for op in operations if op.kind == "clip"]
        assert len(motion) >= 2
        assert len({(op.attrs["scene"], op.attrs["clip"]) for op in motion}) == len(motion)
        assert all(op.attrs.get("server") and op.attrs.get("prompt_id") for op in motion)
        approved = await read_json(store, state.id, APPROVAL)
        prefix = f"education/render/{approved['fingerprint']}"
        for i in range(scene_count):
            assert await store.exists(state.id, f"{prefix}/processed/scene_{i:03d}.mp4")
        submitted_before = sum(len(w.submitted) for w in fake.workers.values())
        await manager.retry(state.id)
        await manager.wait(state.id)
        assert (await manager.get(state.id)).status == JobStatus.completed
        assert sum(len(w.submitted) for w in fake.workers.values()) == submitted_before
        assert progress == list(range(scene_count + 1)) * 2
        assert await media.video_size(store.path(state.id, "final.mp4")) == (160, 90)
        assert await media.video_duration(store.path(state.id, "final.mp4")) == pytest.approx(15, abs=1 / 12)
    finally:
        await visuals.aclose()
        await pool.aclose()
        await close()


@requires_ffmpeg
@pytest.mark.parametrize("style", ["presentation", "ai_motion", "hybrid"])
async def test_pause_edit_approve_resume_and_exact_output(setup, style):
    settings, store, team, visuals, narrator, factory, close = setup
    manager = JobManager(settings, store, factory)
    body = request().model_dump()
    body["education"]["style"] = style
    state = await manager.create(VideoRequest.model_validate(body))
    await manager.wait(state.id)
    paused = await manager.get(state.id)
    assert paused.status == JobStatus.awaiting_review
    assert not visuals.images and not narrator.texts
    assert team.research_calls == ["Kubernetes Pods"]
    operations = await read_json(store, state.id, "operations.json")
    research_op = next(op for op in operations if op["attrs"].get("step") == "research")
    assert research_op["attrs"]["source_urls"] == [
        "https://kubernetes.io/docs/concepts/workloads/pods/",
    ]
    manager = JobManager(settings, store, factory)
    await manager.resume_unfinished()
    assert not manager.is_active(state.id)
    events = [event async for event in job_events(manager, state.id)]
    assert events[-1].startswith("event: end")
    draft = await manager.draft(state.id)
    content = draft.model_dump(include={"revision", "brief", "scenes"})
    content["scenes"][1]["narration"] = "My approved explanation must remain unchanged."
    await manager.review(state.id, 1, update=DraftUpdate.model_validate(content), action="update")
    with pytest.raises(ReviewConflict, match="revision changed"):
        await manager.review(state.id, 1)
    await manager.review(state.id, 2)
    await manager.review(state.id, 2)  # repeated approval is idempotent even while rendering
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error
    assert narrator.texts[1] == content["scenes"][1]["narration"]
    assert final.duration_seconds == pytest.approx(18.75, abs=0.085)
    assert await media.video_size(store.path(state.id, "final.mp4")) == (160, 90)
    assert len(visuals.images) == 3 and team.plan_calls == 1
    if style == "hybrid":
        assert visuals.motion_calls == 3
        assert visuals.animation_calls == 6
    with pytest.raises(ReviewConflict, match="immutable"):
        await manager.review(state.id, 2, update=DraftUpdate.model_validate({**content, "revision": 2}))
    approved = await read_json(store, state.id, APPROVAL)
    assert approved["draft"]["revision"] == 2
    assert await store.exists(state.id, "education/sources.txt")
    await close()


@requires_ffmpeg
async def test_regenerate_retains_research_and_invalidates_stale_revision(setup):
    settings, store, team, visuals, narrator, factory, close = setup
    manager = JobManager(settings, store, factory)
    state = await manager.create(request())
    await manager.wait(state.id)
    await manager.review(state.id, 1, action="regenerate")
    await manager.wait(state.id)
    assert (await manager.draft(state.id)).revision == 2
    assert team.plan_calls == 2 and len(team.research_calls) == 1
    assert not visuals.images
    operations = await read_json(store, state.id, "operations.json")
    research_ops = [op for op in operations if op["attrs"].get("step") == "research"]
    assert len(research_ops) == 2
    assert all(op["attrs"]["source_urls"] == [
        "https://kubernetes.io/docs/concepts/workloads/pods/",
    ] for op in research_ops)
    await close()


@requires_ffmpeg
async def test_failed_render_reuses_approved_assets(setup):
    settings, store, team, visuals, narrator, factory, close = setup
    manager = JobManager(settings, store, factory)
    state = await manager.create(request())
    await manager.wait(state.id)
    original = visuals.animate

    async def fail(*args, **kwargs):
        raise RuntimeError("fixture render failure")

    visuals.animate = fail
    await manager.review(state.id, 1)
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.failed
    assert (await manager.get(state.id)).error == "RuntimeError: fixture render failure"
    assert len(visuals.images) == 3
    visuals.animate = original
    await manager.retry(state.id)
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.completed
    assert len(visuals.images) == 3 and len(narrator.texts) == 3
    await close()


@pytest.mark.parametrize("style", ["ai_motion", "hybrid"])
def test_motion_styles_require_configured_foundry_provider(style):
    body = request().model_dump()
    body["education"].update(style=style, motion_provider="foundry")
    settings = Settings(education_search_model="search", speech_endpoint="https://speech.example",
                        comfy_image_workflow="configured")
    with pytest.raises(ValueError, match="Foundry video endpoint"):
        validate_education_request(VideoRequest.model_validate(body), settings)
    validate_education_request(VideoRequest.model_validate(body), replace(
        settings, foundry_video_endpoint="https://video.example", foundry_video_model="video",
    ))


@requires_ffmpeg
@pytest.mark.parametrize("scene_count,narration_seconds,has_tail", [
    (5, 1.0, False), (3, 1.0, False), (3, 5.25, True),
])
async def test_hybrid_short_exact_and_long_scenes(setup, scene_count, narration_seconds, has_tail):
    settings, store, team, visuals, narrator, factory, close = setup
    narrator.seconds = narration_seconds

    async def plan(prompt, options, research, seconds, revision):
        draft = sample_draft(revision)
        draft.scenes = [draft.scenes[0], *[draft.scenes[1]] * (scene_count - 2), draft.scenes[-1]]
        return draft

    team.plan = plan
    body = request().model_dump()
    body["education"]["style"] = "hybrid"
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest.model_validate(body))
    await manager.wait(state.id)
    await manager.review(state.id, 1)
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error
    assert visuals.motion_calls == scene_count
    assert visuals.animation_calls == scene_count * (2 if has_tail else 1)
    assert final.duration_seconds == pytest.approx(max(15, scene_count * (narration_seconds + 1)), abs=1 / 12)
    approved = await read_json(store, state.id, APPROVAL)
    prefix = f"education/render/{approved['fingerprint']}"
    for i in range(scene_count):
        assert await store.exists(state.id, f"{prefix}/presentation/scene_{i:03d}.mp4") == has_tail
        assert not await store.exists(state.id, f"{prefix}/clips/scene_{i:03d}_001.mp4")
    await close()


@requires_ffmpeg
async def test_hybrid_diagrams_and_retry_reuse_persisted_motion_and_tail(setup, monkeypatch):
    settings, store, team, visuals, narrator, factory, close = setup
    body = request().model_dump()
    body["education"]["style"] = "hybrid"
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest.model_validate(body))
    await manager.wait(state.id)
    draft = (await manager.draft(state.id)).model_dump(include={"revision", "brief", "scenes"})
    draft["scenes"][1]["diagram"] = {
        "nodes": [{"id": "pod", "label": "Pod", "icon_query": "Kubernetes Pod"}], "edges": [],
    }
    await manager.review(state.id, 1, update=DraftUpdate.model_validate(draft))
    original = media.normalize_clip
    failed = False

    async def interrupt_tail(src, *args, **kwargs):
        nonlocal failed
        if src.parent.name == "presentation" and not failed:
            failed = True
            raise RuntimeError("restart after persisted hybrid tail")
        return await original(src, *args, **kwargs)

    monkeypatch.setattr(media, "normalize_clip", interrupt_tail)
    await manager.review(state.id, 2)
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.failed
    assert visuals.motion_calls == 2 and visuals.animation_calls == 3
    for path in (settings.work_dir / state.id).rglob("*"):
        if path.is_file():
            path.unlink()
    await manager.retry(state.id)
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error
    assert final.duration_seconds == pytest.approx(18.75, abs=1 / 12)
    assert visuals.motion_calls == 2
    assert visuals.animation_calls == 5
    assert len(narrator.texts) == 3 and len(visuals.images) == 3
    assert await media.video_size(store.path(state.id, "final.mp4")) == (160, 90)
    await close()


@requires_ffmpeg
async def test_hybrid_motion_failure_does_not_silently_use_presentation(setup):
    settings, store, team, visuals, narrator, factory, close = setup
    body = request().model_dump()
    body["education"]["style"] = "hybrid"
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest.model_validate(body))
    await manager.wait(state.id)

    async def fail_motion(*args, **kwargs):
        raise RuntimeError("motion provider unavailable")

    visuals.motion = fail_motion
    await manager.review(state.id, 1)
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.failed
    assert final.error == "RuntimeError: motion provider unavailable"
    assert visuals.animation_calls == 0
    assert not await store.exists(state.id, "final.mp4")
    await close()


@requires_ffmpeg
async def test_foundry_education_providers_remain_sequential(setup):
    settings, store, team, visuals, narrator, _, close = setup
    settings = replace(
        settings, foundry_image_endpoint="https://images.example", foundry_image_model="image",
        foundry_video_endpoint="https://video.example", foundry_video_model="video",
    )
    pool = FakeComfy().pool()

    def factory(manager):
        return build_educational_workflow(PipelineDeps(
            settings=settings, team=FakeTeam(), comfy=pool, narrator=narrator, store=store,
            progress=manager.progress, ops=manager.recorder,
        ), team, visuals)

    active = {"image": 0, "motion": 0}
    original_image, original_motion = visuals.image, visuals.motion

    async def image(*args, **kwargs):
        assert kwargs["provider"] == "foundry"
        active["image"] += 1
        try:
            assert active["image"] == 1
            await asyncio.sleep(0)
            return await original_image(*args, **kwargs)
        finally:
            active["image"] -= 1

    async def motion(*args, **kwargs):
        assert kwargs["provider"] == "foundry"
        active["motion"] += 1
        try:
            assert active["motion"] == 1
            await asyncio.sleep(0)
            return await original_motion(*args, **kwargs)
        finally:
            active["motion"] -= 1

    visuals.image, visuals.motion = image, motion
    body = request().model_dump()
    body["education"].update(style="hybrid", image_provider="foundry", motion_provider="foundry")
    manager = JobManager(settings, store, factory)
    try:
        state = await manager.create(VideoRequest.model_validate(body))
        await manager.wait(state.id)
        await manager.review(state.id, 1)
        await manager.wait(state.id)
        final = await manager.get(state.id)
        assert final.status == JobStatus.completed, final.error
        assert len(visuals.images) == visuals.motion_calls == 3
    finally:
        await pool.aclose()
        await close()


@requires_ffmpeg
def test_authenticated_review_api_and_safe_artifacts(setup):
    settings, store, team, visuals, narrator, factory, close = setup
    app = create_app(replace(settings, api_key="fixture-key"), services=(store, factory, close))
    with TestClient(app) as client:
        assert client.get("/api/config").status_code == 401
        client.headers["X-API-Key"] = "fixture-key"
        body = request().model_dump(mode="json")
        response = client.post("/api/videos", json=body)
        assert response.status_code == 202, response.text
        job_id = response.json()["id"]
        client.portal.call(app.state.jobs.wait, job_id)
        draft = client.get(f"/api/videos/{job_id}/draft").json()
        assert draft["revision"] == 1
        update = {k: draft[k] for k in ("revision", "brief", "scenes")}
        update["scenes"][0]["source_ids"] = ["s99"]
        assert client.put(f"/api/videos/{job_id}/draft", json=update).status_code == 422
        assert client.post(f"/api/videos/{job_id}/approve", json={"revision": 99}).status_code == 409
        assert client.get(f"/api/videos/{job_id}/education/sources.txt").status_code == 200
        for name in ["approval.json", "draft.json", "render/xxx/images/scene_000.png"]:
            assert client.get(f"/api/videos/{job_id}/education/{name}").status_code == 404
        assert client.post(f"/api/videos/{job_id}/regenerate", json={"revision": 1}).status_code == 200
        client.portal.call(app.state.jobs.wait, job_id)
        assert client.get(f"/api/videos/{job_id}/draft").json()["revision"] == 2


@requires_ffmpeg
async def test_diagram_companions_survive_lost_work_directory(setup):
    settings, store, team, visuals, narrator, factory, close = setup
    manager = JobManager(settings, store, factory)
    state = await manager.create(request())
    await manager.wait(state.id)
    draft = await manager.draft(state.id)
    body = draft.model_dump(include={"revision", "brief", "scenes"})
    body["scenes"][1]["diagram"] = {
        "nodes": [{"id": "pod", "label": "Pod", "icon_query": "Kubernetes Pod"}], "edges": [],
    }
    await manager.review(state.id, 1, update=DraftUpdate.model_validate(body))
    original = visuals.animate
    uploaded = []
    original_upload = store.upload

    async def recording_upload(job_id, name, path):
        uploaded.append(name)
        await original_upload(job_id, name, path)

    store.upload = recording_upload

    async def interrupted(*args, **kwargs):
        raise RuntimeError("simulated restart after visual assets")

    visuals.animate = interrupted
    await manager.review(state.id, 2)
    await manager.wait(state.id)
    diagram_key = next(name for name in uploaded if name.endswith("images/scene_001.drawio"))
    assert uploaded.index(diagram_key) < uploaded.index(diagram_key.removesuffix(".drawio") + ".png")
    for path in (settings.work_dir / state.id).rglob("*"):
        if path.is_file():
            path.unlink()
    visuals.animate = original
    await manager.retry(state.id)
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.completed
    assert len(visuals.images) == 3
    await close()


@requires_ffmpeg
async def test_intro_outro_music_has_no_content_cue_or_audible_music(setup):
    settings, store, team, visuals, narrator, factory, close = setup
    manager = JobManager(settings, store, factory)
    body = request().model_dump()
    body["education"]["music_mode"] = "intro_outro"
    state = await manager.create(VideoRequest.model_validate(body))
    await manager.wait(state.id)
    await manager.review(state.id, 1)
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error
    approved = await read_json(store, state.id, APPROVAL)
    prefix = f"education/render/{approved['fingerprint']}"
    assert await store.exists(state.id, f"{prefix}/music/scene_000.flac")
    assert not await store.exists(state.id, f"{prefix}/music/scene_001.flac")
    assert await store.exists(state.id, f"{prefix}/music/scene_002.flac")

    def music_peak(index):
        path = store.path(state.id, f"{prefix}/scenes/scene_{index:03d}.mp4")
        result = subprocess.run([
            "ffmpeg", "-hide_banner", "-ss", "5.85", "-t", "0.15", "-i", str(path),
            "-af", "bandpass=f=330:t=h:w=10,volumedetect", "-f", "null", "-",
        ], capture_output=True, text=True, check=True)
        peak = re.search(r"max_volume: (-?[\d.]+|-inf) dB", result.stderr)
        if peak is None:
            assert "n_samples: 0" in result.stderr, result.stderr
            return float("-inf")
        return float(peak.group(1))

    assert music_peak(0) > music_peak(1) + 10
    assert music_peak(2) > music_peak(1) + 10
    await close()


async def test_search_requires_actual_tool_evidence_and_citations(monkeypatch):
    import video_platform.education_agents as module
    responses = [
        SimpleNamespace(text="I searched", messages=[Message("assistant", "No evidence")]),
        SimpleNamespace(text="Verified", messages=[Message("assistant", contents=[
            Content.from_search_tool_call(call_id="a", tool_name="web_search", status="completed"),
            Content("text", text="Verified", annotations=[{"type": "url_citation", "url": "https://example.com",
                                                          "title": "Source"}]),
        ])]),
    ]

    class Agent:
        def __init__(self, **kwargs):
            pass

        async def run(self, topic, **kwargs):
            return responses.pop(0)

    monkeypatch.setattr(module, "Agent", Agent)
    team = FoundryEducationTeam(Settings(education_search_model="search"),
                               lambda model: SimpleNamespace(get_web_search_tool=lambda **kwargs: object()))
    with pytest.raises(ValueError, match="no completed"):
        await team.research("Public topic")
    research = await team.research("Public topic")
    assert research.sources[0].id == "s1"
