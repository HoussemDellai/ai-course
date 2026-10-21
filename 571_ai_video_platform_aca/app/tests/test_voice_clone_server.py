"""The GPU voice-clone gateway: text splitting, audio joining and the HTTP contract (engines are faked)."""

import asyncio
import io
import sys
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "voice_clone_server"))

import gateway  # noqa: E402


def make_wav(frames: int, rate: int = 24000) -> bytes:
    out = io.BytesIO()
    with wave.open(out, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x01\x00" * frames)
    return out.getvalue()


def test_split_text_groups_sentences_and_splits_long_ones():
    assert gateway.split_text("One. Two! Three?", 100) == ["One. Two! Three?"]
    assert gateway.split_text("First sentence here. Second sentence here.", 25) == [
        "First sentence here.", "Second sentence here."]
    assert gateway.split_text("你好。今天很好。", 5) == ["你好。", "今天很好。"]
    long = "word " * 100
    chunks = gateway.split_text(long, 60)
    assert all(len(c) <= 60 for c in chunks) and " ".join(chunks).split() == long.split()
    assert gateway.split_text("   ") == []


def test_join_wavs_inserts_silence_and_rejects_mixed_formats():
    joined = gateway.join_wavs([make_wav(2400), make_wav(2400)], 100)
    with wave.open(io.BytesIO(joined)) as w:
        assert w.getnframes() == 2400 + 2400 + 2400
    assert gateway.join_wavs([make_wav(10)], 500)
    with pytest.raises(ValueError, match="inconsistent"):
        gateway.join_wavs([make_wav(10), make_wav(10, rate=16000)], 0)


class FakeManager(gateway.EngineManager):
    def __init__(self):
        super().__init__({"qwen3-tts": gateway.Engine("qwen3-tts", "Qwen3-TTS", 1, [])})
        self.ready = False
        self.requests = []

    def start(self, key):
        self.ready = True
        self.states[key] = "ready"
        return "loading"

    async def synthesize(self, key, text, language, ref_text, reference, pause_ms):
        if not self.ready:
            raise gateway.NotReady("not loaded")
        self.requests.append((text, language, ref_text, reference, pause_ms))
        return make_wav(100)


def test_gateway_http_contract(monkeypatch):
    monkeypatch.setattr(gateway, "API_KEY", "secret")
    manager = FakeManager()
    h = {"X-API-Key": "secret"}
    form = {"model": "qwen3-tts", "text": "Hello.", "language": "en-US", "ref_text": " hi ", "pause_ms": "99999"}
    with TestClient(gateway.create_app(manager)) as client:
        assert client.get("/healthz").json() == {"status": "ok"}
        assert client.get("/v1/models").status_code == 401
        assert client.get("/v1/models/nope", headers=h).status_code == 404
        assert client.post("/v1/models/nope/start", headers=h).status_code == 404
        files = {"reference": ("r.wav", make_wav(10), "audio/wav")}
        assert client.post("/v1/synthesize", headers=h, data=form, files=files).status_code == 409
        r = client.post("/v1/models/qwen3-tts/start", headers=h)
        assert r.status_code == 202
        assert client.get("/v1/models/qwen3-tts", headers=h).json()["state"] == "ready"
        r = client.post("/v1/synthesize", headers=h, data=form, files=files)
        assert r.status_code == 200 and r.content.startswith(b"RIFF")
        assert manager.requests[0][2] == "hi" and manager.requests[0][4] == 2000
        assert client.post("/v1/synthesize", headers=h, data={**form, "text": " "}, files=files).status_code == 422
        bad = {"reference": ("r.wav", b"nope", "audio/wav")}
        assert client.post("/v1/synthesize", headers=h, data=form, files=bad).status_code == 422
        assert client.post("/v1/synthesize", headers=h, data={**form, "model": "x"}, files=files).status_code == 404


def test_voice_clone_infrastructure_is_private_scale_to_zero_gpu():
    infra = Path(__file__).parents[2] / "infra"
    service = (infra / "voice_clone.tf").read_text()
    assert "external_enabled           = false" in service and "min_replicas                     = 0" in service
    assert "workload_profile_name        = var.voice_clone_workload_profile" in service
    assert 'default     = "GPU-NC8as-T4"' in (infra / "variables.tf").read_text()
    app = (infra / "container_app.tf").read_text()
    assert "VOICE_CLONE_URL" in app and "VOICE_CLONE_API_KEY" in app


async def test_fish_is_rejected_on_gpus_that_are_too_small(monkeypatch):
    async def small_gpu():
        return 15.0

    monkeypatch.setattr(gateway, "gpu_memory_gib", small_gpu)
    manager = gateway.EngineManager({"fish-s2-pro": gateway.Engine("fish-s2-pro", "Fish Audio S2 Pro", 1, [])})
    manager.start("fish-s2-pro")
    await asyncio.gather(*manager._tasks)
    assert manager.states["fish-s2-pro"] == "error"
    assert "at least 24 GiB" in manager.errors["fish-s2-pro"]
    await manager.aclose()
