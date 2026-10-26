import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fakes import make_png, make_wav, requires_ffmpeg
from generate import parse_batch_request, parse_request
from test_documents import make_pdf
from video_platform.api import create_app
from video_platform.config import Settings
from video_platform.jobs import JobManager
from video_platform.schemas import JobStatus, VideoBatchRequest, VideoRequest, VoiceCloneOptions
from video_platform.storage import LocalArtifactStore
from video_platform.voice_clone import VOICE_SAMPLE
from video_platform.workflow import REFERENCE_IMAGE, VideoResult


def batch_request(count=3, **kwargs):
    return VideoBatchRequest(
        request=VideoRequest(prompt="Explain a lighthouse", duration_minutes=0.25),
        variants=[{"video_model": ["wan22", "ltx2", "ltx25", "hunyuan15"][i % 4]} for i in range(count)],
        **kwargs,
    )


class Runs:
    def __init__(self):
        self.active = 0
        self.peak = 0
        self.order = []
        self.fail = set()
        self.started = asyncio.Event()
        self.release = None

    def factory(self, manager):
        async def run(job):
            state = await manager.get(job.job_id)
            self.active += 1
            self.peak = max(self.active, self.peak)
            self.order.append(state.batch.index if state.batch else -1)
            self.started.set()
            try:
                await manager.progress(job.job_id, JobStatus.generating)
                if self.release is not None:
                    await self.release.wait()
                await asyncio.sleep(0.03)
                if state.batch and state.batch.index in self.fail:
                    raise RuntimeError("intentional variant failure")
                return SimpleNamespace(get_outputs=lambda: [VideoResult(job.job_id, "Video", "final.mp4", 1)])
            finally:
                self.active -= 1

        return SimpleNamespace(run=run)


@pytest.fixture
def harness(tmp_path):
    settings = Settings(local_output_dir=tmp_path / "out", work_dir=tmp_path / "work",
                        max_concurrent_jobs=4, comfyui_urls=["http://gpu1", "http://gpu2"])
    store = LocalArtifactStore(settings.local_output_dir)
    runs = Runs()
    return settings, store, runs, JobManager(settings, store, runs.factory)


async def wait_batch(manager, batch):
    await asyncio.wait_for(asyncio.gather(*(manager.wait(s.id) for s in batch.jobs)), 10)
    final = await manager.get_batch(batch.id)
    assert all(s.is_finished for s in final.jobs), final
    return final


def test_variant_validation_and_overrides():
    base = VideoRequest(prompt="A lighthouse", naturalistic=True, voice="old-voice")
    batch = VideoBatchRequest(request=base, variants=[
        {"video_model": "wan22", "voice": "new-voice"},
        {"video_model": "ltx25", "voice_clone": {"model": "chatterbox", "consent": True}},
    ])
    first, second = batch.requests()
    assert first.voice == "new-voice" and first.voice_clone is None
    assert second.voice is None and second.voice_clone.model == "chatterbox"
    assert first.naturalistic and second.naturalistic
    for count in (0, 1, 13):
        with pytest.raises(ValidationError):
            batch_request(count)
    for invalid in (
        {"video_model": "wan22", "voice_clone": {"model": "chatterbox"}},
        {"video_model": "wan22", "voice_clone": {"model": "not-a-model", "consent": True}},
        {"video_model": "wan22", "unexpected": True},
    ):
        with pytest.raises(ValidationError):
            VideoBatchRequest(request=base, variants=[invalid, {"video_model": "ltx2"}])
    conflicting = batch.model_copy(update={"request": base.model_copy(update={"narration": False})})
    with pytest.raises(ValidationError, match="requires narration"):
        conflicting.requests()


@pytest.mark.parametrize("execution,workers,slots,expected", [
    ("sequential", ["http://gpu1", "http://gpu2"], 4, 1),
    ("auto", ["http://gpu1", "http://gpu2"], 4, 2),
    ("auto", ["http://gpu1"], 4, 1),
    ("auto", ["http://gpu1", "http://gpu1/"], 4, 1),
    ("auto", ["http://gpu1", "http://gpu2"], 1, 1),
])
async def test_execution_capacity_and_persisted_order(harness, execution, workers, slots, expected):
    settings, store, runs, _ = harness
    manager = JobManager(replace(settings, comfyui_urls=workers, max_concurrent_jobs=slots), store, runs.factory)
    batch = await manager.create_batch(batch_request(4, execution=execution))
    try:
        final = await wait_batch(manager, batch)
        assert batch.concurrency == runs.peak == expected
        if expected == 1:
            assert runs.order == [0, 1, 2, 3]
        assert len({s.id for s in batch.jobs}) == 4
        assert len({s.request.seed for s in batch.jobs}) == 1
        assert all(s.status == JobStatus.completed for s in final.jobs)
        assert [s.request.video_model for s in final.jobs] == ["wan22", "ltx2", "ltx25", "hunyuan15"]
        assert all(s.batch.id == batch.id and s.batch.index == i for i, s in enumerate(final.jobs))
    finally:
        await manager.shutdown()


async def test_invalid_later_variant_creates_no_jobs_or_uploads(harness):
    _, store, runs, manager = harness
    batch = batch_request()
    batch.variants[-1].video_model = "unknown"
    with pytest.raises(ValueError, match="Unknown video_model"):
        await manager.create_batch(batch, image=b"sanitized photo")
    assert await store.list_jobs() == []
    assert not list(store.root.iterdir())
    assert runs.order == []


async def test_cloned_variants_are_sequential_and_only_clone_jobs_receive_sample(harness):
    settings, store, runs, _ = harness
    manager = JobManager(replace(settings, voice_clone_url="http://voice"), store, runs.factory)
    batch = batch_request(execution="auto")
    batch.variants[1].voice_clone = VoiceCloneOptions(model="chatterbox", consent=True)
    batch.variants[2].voice_clone = VoiceCloneOptions(model="qwen3-tts", consent=True)
    result = await manager.create_batch(batch, voice_sample=b"validated sample", image=b"sanitized photo")
    try:
        final = await wait_batch(manager, result)
        assert result.concurrency == runs.peak == 1
        assert "share one GPU" in result.scheduling_note
        for i, state in enumerate(final.jobs):
            assert await store.exists(state.id, REFERENCE_IMAGE)
            assert (await store.exists(state.id, VOICE_SAMPLE)) == (i > 0)
            assert state.request.voice_sample == (i > 0)
    finally:
        await manager.shutdown()


async def test_missing_voice_sample_and_unused_sample_rejected(harness):
    settings, store, runs, manager = harness
    with pytest.raises(ValueError, match="at least one"):
        await manager.create_batch(batch_request(), voice_sample=b"sample")
    batch = batch_request()
    batch.variants[-1].voice_clone = VoiceCloneOptions(model="chatterbox", consent=True)
    manager = JobManager(replace(settings, voice_clone_url="http://voice"), store, runs.factory)
    with pytest.raises(ValueError, match="requires a voice sample"):
        await manager.create_batch(batch)
    assert await store.list_jobs() == []


async def test_failure_continues_batch_and_retry_keeps_membership(harness):
    _, _, runs, manager = harness
    runs.fail.add(0)
    batch = await manager.create_batch(batch_request())
    try:
        final = await wait_batch(manager, batch)
        assert [s.status for s in final.jobs] == [JobStatus.failed, JobStatus.completed, JobStatus.completed]
        runs.fail.clear()
        await manager.retry(batch.jobs[0].id)
        await manager.wait(batch.jobs[0].id)
        retried = await manager.get_batch(batch.id)
        assert all(s.status == JobStatus.completed for s in retried.jobs)
        assert retried.jobs[0].batch == batch.jobs[0].batch
        assert runs.peak == 1
    finally:
        await manager.shutdown()


async def test_restart_recovers_order_and_missing_state_from_committed_manifest(harness):
    settings, store, runs, manager = harness
    runs.release = asyncio.Event()
    batch = await manager.create_batch(batch_request())
    await runs.started.wait()
    await manager.shutdown()
    # Simulate interruption between saving the anchor job and the remaining states.
    store.path(batch.jobs[-1].id, "state.json").unlink()
    runs.release = None
    runs.order.clear()
    replacement = JobManager(settings, store, runs.factory)
    try:
        await replacement.resume_unfinished()
        final = await wait_batch(replacement, batch)
        assert runs.order == [0, 1, 2]
        assert len({s.request.seed for s in final.jobs}) == 1
        assert all(s.status == JobStatus.completed for s in final.jobs)
    finally:
        await replacement.shutdown()


async def test_batch_lane_leases_prevent_overlap_between_replicas(harness, monkeypatch):
    settings, store, runs, manager = harness
    held = set()

    class Lock:
        def __init__(self, key):
            self.key = key

        async def renew(self):
            assert self.key in held

        async def release(self):
            held.remove(self.key)

    async def try_lock(key):
        if key in held:
            return None
        held.add(key)
        return Lock(key)

    monkeypatch.setattr(store, "try_lock", try_lock)
    runs.release = asyncio.Event()
    batch = await manager.create_batch(batch_request())
    await runs.started.wait()
    other = JobManager(settings, store, runs.factory)
    try:
        await other.resume_unfinished()
        runs.release.set()
        await wait_batch(manager, batch)
        await wait_batch(other, batch)
        assert runs.peak == 1
        assert runs.order == [0, 1, 2]
        assert not held
    finally:
        await manager.shutdown()
        await other.shutdown()


async def test_restart_downgrades_parallel_batch_when_only_one_worker_remains(harness):
    settings, store, runs, manager = harness
    batch = await manager.create_batch(batch_request(execution="auto"))
    await manager.shutdown()
    replacement = JobManager(replace(settings, comfyui_urls=["http://only-gpu"]), store, runs.factory)
    try:
        await replacement.resume_unfinished()
        await wait_batch(replacement, batch)
        assert runs.peak == 1
        assert runs.order == [0, 1, 2]
    finally:
        await replacement.shutdown()


def test_cli_batch_options(tmp_path):
    path = tmp_path / "variants.json"
    path.write_text(json.dumps([{"video_model": "wan22", "voice": "voice-a"},
                                {"video_model": "ltx2", "voice": "voice-b"}]))
    argv = ["A lighthouse", "--variants", str(path), "--batch-execution", "auto"]
    request, _ = parse_request(argv)
    batch = parse_batch_request(argv, request)
    assert batch.execution == "auto" and [r.voice for r in batch.requests()] == ["voice-a", "voice-b"]
    assert parse_batch_request(["A lighthouse"], request) is None
    with pytest.raises(SystemExit):
        parse_batch_request(["A lighthouse", "--batch-execution", "auto"], request)
    path.write_text("[]")
    with pytest.raises(ValidationError):
        parse_batch_request(argv, request)


def test_batch_api_auth_validation_config_and_openapi(harness):
    settings, store, runs, _ = harness

    async def close():
        pass

    app = create_app(replace(settings, api_key="secret"), services=(store, runs.factory, close))
    headers = {"X-API-Key": "secret"}
    with TestClient(app) as client:
        body = batch_request().model_dump(mode="json")
        assert client.post("/api/video-batches", json=body).status_code == 401
        assert client.get("/api/video-batches/missing", headers=headers).status_code == 404
        invalid = json.loads(json.dumps(body))
        invalid["variants"][-1]["video_model"] = "unknown"
        assert client.post("/api/video-batches", json=invalid, headers=headers).status_code == 422
        assert not list(store.root.glob("*/state.json"))
        response = client.post("/api/video-batches", json=body, headers=headers)
        assert response.status_code == 202, response.text
        batch = response.json()
        assert len(batch["jobs"]) == 3 and batch["concurrency"] == 1
        loaded = client.get(f"/api/video-batches/{batch['id']}", headers=headers).json()
        assert [j["id"] for j in loaded["jobs"]] == [j["id"] for j in batch["jobs"]]
        assert client.get("/api/config", headers=headers).json()["batch"]["parallel_capacity"] == 2
        schema = client.get("/openapi.json").json()
        assert "VideoBatchRequest" in schema["components"]["schemas"]
        assert "VideoVariant" in schema["components"]["schemas"]
        assert schema["components"]["schemas"]["VideoBatchRequest"]["properties"]["variants"]["maxItems"] == 12


@requires_ffmpeg
@pytest.mark.parametrize("use_case", ["cinematic", "educational", "document"])
def test_batch_api_shared_uploads_all_use_cases(harness, tmp_path, use_case):
    settings, store, runs, _ = harness
    settings = replace(settings, voice_clone_url="http://voice", speech_endpoint="https://speech",
                       education_search_model="search", comfy_image_workflow="configured")

    async def close():
        pass

    batch = batch_request(2)
    if use_case == "educational":
        batch.request = VideoRequest(prompt="Teach lighthouse optics", use_case=use_case,
                                     education={"public_topic": "Lighthouse optics", "music_mode": "off"})
    elif use_case == "document":
        batch.request = VideoRequest(prompt="Explain the slides", use_case=use_case)
    batch.variants[1].voice_clone = VoiceCloneOptions(model="chatterbox", consent=True)
    files = {"voice_sample": ("voice.wav", make_wav(tmp_path / "voice.wav", 4).read_bytes(), "audio/wav")}
    if use_case == "document":
        files["document"] = ("slides.pdf", make_pdf(), "application/pdf")
    elif use_case == "cinematic":
        files["image"] = ("photo.png", make_png(64, 64), "image/png")
    endpoint = "/api/video-batches" + ("/document" if use_case == "document" else "")
    with TestClient(create_app(settings, services=(store, runs.factory, close))) as client:
        response = client.post(endpoint, data={"request": batch.model_dump_json()}, files=files)
        assert response.status_code == 202, response.text
        states = response.json()["jobs"]
        assert all(s["request"]["use_case"] == use_case for s in states)
        assert not store.path(states[0]["id"], VOICE_SAMPLE).exists()
        assert store.path(states[1]["id"], VOICE_SAMPLE).exists()
        if use_case == "document":
            assert all(store.path(s["id"], "input/document.pdf").read_bytes() == make_pdf() for s in states)
        elif use_case == "cinematic":
            assert all(store.path(s["id"], REFERENCE_IMAGE).exists() for s in states)
