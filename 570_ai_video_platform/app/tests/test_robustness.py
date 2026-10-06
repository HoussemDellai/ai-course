"""Robustness: restarts, concurrent retries, multiple replicas, audio sync."""

import asyncio
import json
import subprocess

from fakes import make_clip, requires_ffmpeg
from test_pipeline import make_services, settings  # noqa: F401 (fixture)
from video_platform import media
from video_platform.jobs import JobManager
from video_platform.schemas import JobStatus, VideoRequest
from video_platform.storage import write_json

pytestmark = requires_ffmpeg


async def test_resume_reattaches_to_submitted_comfyui_prompt(settings, tmp_path, monkeypatch):
    store, factory, close, fake_comfy, *_ = make_services(settings, tmp_path, monkeypatch, "wan22")
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, video_model="wan22"))
    await manager.shutdown()  # "crash" right away
    # A previous orchestrator submitted shot 0 to ComfyUI before dying.
    await write_json(store, state.id, "clips/shot_000.pending.json",
                     {"server": "http://comfy0:8188", "prompt_id": "already-rendering"})
    fake_comfy.submitted.clear()
    manager2 = JobManager(settings, store, factory)
    await manager2.resume_unfinished()
    await manager2.wait(state.id)
    assert (await manager2.get(state.id)).status == JobStatus.completed
    assert len(fake_comfy.submitted) == 5, "shot 0 must be collected from the existing prompt, not re-rendered"
    await close()


async def test_concurrent_retries_start_one_run(settings, tmp_path, monkeypatch):
    store, factory, close, fake_comfy, team, _ = make_services(settings, tmp_path, monkeypatch, "wan22")
    fake_comfy.fail_first = 10_000
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, video_model="wan22"))
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.failed
    fake_comfy.fail_first = 0
    enhance_calls = team.calls.count("enhance")
    submitted_before = len(fake_comfy.submitted)
    results = await asyncio.gather(manager.retry(state.id), manager.retry(state.id), manager.retry(state.id))
    assert results[0].status == JobStatus.queued
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.completed
    assert len(fake_comfy.submitted) - submitted_before == 6, "exactly one run must render the 6 clips"
    assert team.calls.count("enhance") == enhance_calls, "brief is reused"
    await close()


async def test_job_locked_by_another_replica_is_not_run(settings, tmp_path, monkeypatch):
    store, factory, close, fake_comfy, *_ = make_services(settings, tmp_path, monkeypatch, "wan22")

    async def locked(job_id):
        return None

    monkeypatch.setattr(store, "try_lock", locked)
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, video_model="wan22"))
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.queued
    assert fake_comfy.submitted == []
    await close()


async def test_normalize_pads_short_ambient_audio(tmp_path):
    src = tmp_path / "short_audio.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=size=320x180:rate=24:duration=2",
                    "-f", "lavfi", "-i", "sine=duration=1", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    str(src)], check=True)
    out = await media.normalize_clip(src, tmp_path / "n.mp4", 320, 180, 12, keep_audio=True, audio_volume=0.5)
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,duration",
                                      "-of", "json", str(out)], capture_output=True, text=True, check=True).stdout)
    durations = {s["codec_type"]: float(s["duration"]) for s in info["streams"]}
    assert abs(durations["audio"] - durations["video"]) < 0.1, durations


async def test_normalize_adds_silence_when_no_audio(tmp_path):
    src = make_clip(tmp_path / "silent.mp4", 1.5, 16, 320, 176, audio=False)
    out = await media.normalize_clip(src, tmp_path / "n.mp4", 320, 180, 12, keep_audio=True, audio_volume=0.5)
    duration, has_audio = await media.probe(out)
    assert has_audio and abs(duration - 1.5) < 0.15
