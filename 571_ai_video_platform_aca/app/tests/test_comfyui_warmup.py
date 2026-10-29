"""Renders wait for a ComfyUI worker that scales to zero to start."""

import httpx
import pytest

from video_platform.comfyui import ComfyUIClient, ComfyUIError, ComfyUIPool
from video_platform.config import Settings
from video_platform.gpu import ServerActivity
from video_platform.video_models import get_video_model

from fakes import FakeComfy


def client_for(handler) -> ComfyUIClient:
    return ComfyUIClient("http://comfy:8188", httpx.AsyncClient(transport=httpx.MockTransport(handler)),
                         poll_interval=0)


async def test_wait_ready_polls_until_the_cold_worker_answers():
    calls = []

    def handler(request: httpx.Request):
        assert request.url.path == "/system_stats"
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectTimeout("scaling from zero")
        if len(calls) < 4:
            return httpx.Response(503)
        return httpx.Response(200, json={})

    await client_for(handler).wait_ready(timeout=30, interval=0)
    assert len(calls) == 4


async def test_wait_ready_gives_up_with_the_last_error():
    client = client_for(lambda request: httpx.Response(504))
    with pytest.raises(ComfyUIError, match="did not become ready within 0s .*HTTP 504"):
        await client.wait_ready(timeout=0, interval=0)


async def test_wait_ready_skips_the_check_right_after_a_success():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        return httpx.Response(200, json={})

    client = client_for(handler)
    await client.wait_ready(timeout=5)
    await client.wait_ready(timeout=5)
    assert len(calls) == 1


async def test_pool_waits_for_the_worker_before_submitting_and_does_not_burn_a_retry(tmp_path):
    fake = FakeComfy()
    stats_calls = 0
    order: list[str] = []

    def handler(request: httpx.Request):
        nonlocal stats_calls
        if request.url.path == "/system_stats":
            stats_calls += 1
            order.append("stats")
            return httpx.Response(200, json={}) if stats_calls >= 3 else httpx.Response(502)
        order.append(request.url.path)
        return fake.handler(request)

    activity = ServerActivity(grace_seconds=0)
    pool = ComfyUIPool([client_for(handler)], activity, warmup_timeout=60)
    model = get_video_model("wan22")
    dest = tmp_path / "clip.mp4"
    await pool.generate_clip(model, "a prompt", 1, dest, "aivideo/test/clip", timeout=30, retries=0)
    assert dest.exists()
    assert order[:3] == ["stats", "stats", "stats"] and order[3] == "/prompt"
    assert not activity.is_active("http://comfy:8188")


async def test_pool_without_warmup_never_calls_system_stats(tmp_path):
    fake = FakeComfy()
    paths = []

    def handler(request: httpx.Request):
        paths.append(request.url.path)
        return fake.handler(request)

    pool = ComfyUIPool([client_for(handler)])
    await pool.generate_clip(get_video_model("wan22"), "a prompt", 1, tmp_path / "clip.mp4", "aivideo/t/c",
                             timeout=30, retries=0)
    assert "/system_stats" not in paths


async def test_unreachable_worker_fails_the_render_after_the_warmup_timeout(tmp_path):
    pool = ComfyUIPool([client_for(lambda request: httpx.Response(503))], warmup_timeout=0.01)
    with pytest.raises(ComfyUIError, match="failed after 1 attempts: ComfyUIError: .*did not become ready"):
        await pool.generate_clip(get_video_model("wan22"), "a prompt", 1, tmp_path / "clip.mp4", "aivideo/t/c",
                                 timeout=30, retries=0)


def test_warmup_timeout_setting(monkeypatch):
    monkeypatch.delenv("COMFYUI_WARMUP_TIMEOUT_SECONDS", raising=False)
    assert Settings.from_env().comfyui_warmup_timeout_seconds == 2400
    monkeypatch.setenv("COMFYUI_WARMUP_TIMEOUT_SECONDS", "90")
    assert Settings.from_env().comfyui_warmup_timeout_seconds == 90
