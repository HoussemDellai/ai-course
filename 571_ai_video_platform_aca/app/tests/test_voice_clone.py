"""Voice cloning: request rules, sample validation, the service client, the pipeline and the API."""

import asyncio
import json

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fakes import FakeNarrator, FakeTeam, make_clip, make_wav, requires_ffmpeg
from generate import parse_request, voice_sample_path
from video_platform import media
from video_platform.api import create_app
from video_platform.config import Settings
from video_platform.jobs import JobManager
from video_platform.schemas import JobStatus, NarrationDelivery, Pronunciation, VideoRequest, VoiceCloneOptions
from video_platform.speech import SpeechError
from video_platform.storage import LocalArtifactStore
from video_platform.video_models import VIDEO_MODELS
from video_platform.voice_clone import (
    CLONE_MODELS, VOICE_SAMPLE, VOICE_SAMPLE_TRANSCRIPT, CloneNarrator, VoiceCloner, VoiceSampleError,
    supports_language, validate_voice_sample,
)
from video_platform.workflow import PipelineDeps, build_video_workflow

CLONE = {"model": "chatterbox", "consent": True}


def test_clone_options_require_consent_and_known_model():
    with pytest.raises(ValidationError, match="right to clone"):
        VoiceCloneOptions(model="qwen3-tts")
    with pytest.raises(ValidationError):
        VoiceCloneOptions(model="bark", consent=True)
    assert VoiceCloneOptions(consent=True, sample_transcript="  ").sample_transcript is None
    assert set(CLONE_MODELS) == {"qwen3-tts", "chatterbox", "openvoice-v2", "fish-s2-pro"}


def test_request_rules_and_stable_fingerprints():
    plain = VideoRequest(prompt="a lighthouse")
    assert "voice_clone" not in plain.model_dump() and "voice_sample" not in plain.model_dump()
    assert VideoRequest(prompt="a lighthouse", voice_clone=CLONE).voice_clone.model == "chatterbox"
    with pytest.raises(ValidationError, match="requires narration"):
        VideoRequest(prompt="a lighthouse", voice_clone=CLONE, narration=False)
    with pytest.raises(ValidationError, match="not both"):
        VideoRequest(prompt="a lighthouse", voice_clone=CLONE, voice="en-US-AndrewMultilingualNeural")
    with pytest.raises(ValidationError, match="style or rate"):
        VideoRequest(prompt="a lighthouse", voice_clone=CLONE, naturalistic=True,
                     delivery=NarrationDelivery(style="cheerful"))
    VideoRequest(prompt="a lighthouse", voice_clone=CLONE, naturalistic=True,
                 delivery=NarrationDelivery(sentence_pause_ms=400, pronunciations=[Pronunciation(text="SQL", alias="sequel")]))


def test_language_support():
    assert supports_language("openvoice-v2", "fr-FR") and not supports_language("openvoice-v2", "de-DE")
    assert supports_language("chatterbox", "nb-NO") and supports_language("fish-s2-pro", "sw-KE")
    assert not supports_language("qwen3-tts", "ar-SA")


@requires_ffmpeg
async def test_voice_sample_validation(tmp_path):
    wav = make_wav(tmp_path / "ok.wav", 4).read_bytes()
    converted = await validate_voice_sample(wav, "ok.wav", 10_000_000)
    seconds, has_audio = await media.probe(_write(tmp_path / "out.wav", converted))
    assert has_audio and 3.9 < seconds < 4.1

    long = make_wav(tmp_path / "long.wav", 40).read_bytes()
    trimmed = await validate_voice_sample(long, "long.wav", 10_000_000)
    assert 29.9 < (await media.probe(_write(tmp_path / "trim.wav", trimmed)))[0] < 30.1

    mp4 = make_clip(tmp_path / "talk.mp4", 4, 12, 64, 36, audio=True).read_bytes()
    assert await validate_voice_sample(mp4, "talk.mp4", 10_000_000)

    async def reject(data, name, text, status=422, limit=10_000_000):
        with pytest.raises(VoiceSampleError, match=text) as e:
            await validate_voice_sample(data, name, limit)
        assert e.value.status_code == status

    await reject(make_wav(tmp_path / "short.wav", 2).read_bytes(), "short.wav", "at least 3 seconds")
    await reject(make_clip(tmp_path / "mute.mp4", 4, 12, 64, 36, audio=False).read_bytes(), "mute.mp4", "no readable audio")
    await reject(wav, "voice.mp3", "WAV", 415)
    await reject(b"", "empty.wav", "empty")
    await reject(wav, "ok.wav", "larger", 413, limit=1000)
    await reject(b"not audio at all" * 10, "fake.wav", "not a valid WAV")
    await reject(wav, "ok.mp4", "not a valid MP4")


def _write(path, data):
    path.write_bytes(data)
    return path


def service(handler, **kw) -> VoiceCloner:
    return VoiceCloner("http://clone", "key", poll_seconds=0, retry_seconds=0,
                       transport=httpx.MockTransport(handler), **kw)


@requires_ffmpeg
async def test_cloner_loads_model_then_synthesizes(tmp_path):
    wav = make_wav(tmp_path / "out.wav", 1).read_bytes()
    sample = make_wav(tmp_path / "sample.wav", 4)
    calls, states = [], iter(["loading", "loading", "ready"])

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        assert request.headers["x-api-key"] == "key"
        if request.url.path == "/v1/models/chatterbox/start":
            return httpx.Response(202, json={"state": "loading"})
        if request.url.path == "/v1/models/chatterbox":
            return httpx.Response(200, json={"state": next(states)})
        body = request.read()
        assert b'name="text"' in body and b"hello" in body and b'name="ref_text"' in body
        return httpx.Response(200, content=wav)

    cloner = service(handler)
    narrator = CloneNarrator(cloner, VoiceCloneOptions(model="chatterbox", consent=True), sample, "")
    dest = tmp_path / "scene.wav"
    await narrator.synthesize("hello there", dest, language="en-US")
    assert dest.read_bytes() == wav and narrator.voice_id.startswith("clone:chatterbox:")
    await narrator.synthesize("hello again", dest, language="en-US")
    assert [c for c in calls if c[1] == "/v1/models/chatterbox/start"] == [("POST", "/v1/models/chatterbox/start")]
    await cloner.aclose()


@requires_ffmpeg
async def test_cloner_recovers_from_eviction_unavailability_and_errors(tmp_path):
    wav = make_wav(tmp_path / "out.wav", 1).read_bytes()
    sample = make_wav(tmp_path / "sample.wav", 4)
    synth_responses = iter([httpx.Response(503), httpx.Response(409, json={"detail": "not loaded"}),
                            httpx.Response(200, content=wav)])
    starts = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/start"):
            starts.append(1)
            return httpx.Response(202, json={})
        if request.url.path.startswith("/v1/models/"):
            return httpx.Response(200, json={"state": "ready"})
        return next(synth_responses)

    cloner = service(handler)
    await cloner.synthesize(model="qwen3-tts", text="hi", language="en", sample=sample, ref_text="",
                            pause_ms=250, dest=tmp_path / "a.wav")
    assert len(starts) == 1 and (tmp_path / "a.wav").read_bytes() == wav

    failing = service(lambda r: httpx.Response(200, json={"state": "error", "error": "CUDA out of memory"})
                      if r.method == "GET" else httpx.Response(202, json={}))
    with pytest.raises(SpeechError, match="CUDA out of memory"):
        await failing.ensure_ready("fish-s2-pro")
    denied = service(lambda r: httpx.Response(401, json={"detail": "nope"}))
    with pytest.raises(SpeechError, match="API key"):
        await denied.ensure_ready("qwen3-tts")
    down = service(lambda r: httpx.Response(503), retries=2)
    with pytest.raises(SpeechError, match="unavailable"):
        await down.ensure_ready("qwen3-tts")
    bad = service(lambda r: httpx.Response(200, content=b"not wav"))
    with pytest.raises(SpeechError, match="no valid WAV"):
        await bad.synthesize(model="qwen3-tts", text="hi", language="en", sample=sample, ref_text="",
                             pause_ms=0, dest=tmp_path / "b.wav")
    for c in (cloner, failing, denied, down, bad):
        await c.aclose()


@requires_ffmpeg
async def test_clone_narrator_checks_language_delivery_and_applies_pronunciations(tmp_path):
    sample = make_wav(tmp_path / "sample.wav", 4)
    seen = {}

    class Recorder:
        async def ensure_ready(self, model):
            seen["ready"] = model

        async def synthesize(self, **kw):
            seen.update(kw)
            return kw["dest"]

    narrator = CloneNarrator(Recorder(), VoiceCloneOptions(model="openvoice-v2", consent=True), sample, "")
    with pytest.raises(SpeechError, match="does not support narration language de-DE"):
        await narrator.validate(None, "de-DE", None)
    with pytest.raises(SpeechError, match="style or rate"):
        await narrator.validate(None, "en-US", NarrationDelivery(rate_percent=5))
    delivery = NarrationDelivery(sentence_pause_ms=400, pronunciations=[Pronunciation(text="SQL", alias="sequel")])
    await narrator.synthesize("Use SQL daily.", tmp_path / "x.wav", language="en-US", delivery=delivery)
    assert seen["text"] == "Use sequel daily." and seen["pause_ms"] == 400 and seen["ready"] == "openvoice-v2"


class FakeCloner:
    def __init__(self):
        self.calls, self.ready = [], []

    async def ensure_ready(self, model):
        self.ready.append(model)

    async def synthesize(self, *, model, text, language, sample, ref_text, pause_ms, dest):
        self.calls.append({"model": model, "text": text, "ref_text": ref_text, "language": language,
                           "sample": sample.read_bytes()})
        dest.parent.mkdir(parents=True, exist_ok=True)
        return make_wav(dest, 3.0)

    async def aclose(self):
        pass


@requires_ffmpeg
async def test_cinematic_job_narrated_in_cloned_voice(tmp_path, monkeypatch):
    settings = Settings(local_output_dir=tmp_path / "out", work_dir=tmp_path / "work", output_fps=12, clip_retries=0,
                        voice_clone_url="http://clone")
    from fakes import FakeComfy, tiny_model
    from video_platform.video_models import RESOLUTIONS

    for key, size in {"720p": (320, 180)}.items():
        monkeypatch.setitem(RESOLUTIONS, key, size)
    model = tiny_model(VIDEO_MODELS["wan22"], frames=16, fps=16)
    monkeypatch.setitem(VIDEO_MODELS, "wan22", model)
    clip = make_clip(tmp_path / "clip.mp4", 1, 16, 320, 176, audio=False)
    pool = FakeComfy(clip).pool(servers=1)
    store = LocalArtifactStore(settings.local_output_dir)
    cloner, azure = FakeCloner(), FakeNarrator(3.0)

    def factory(manager):
        return build_video_workflow(PipelineDeps(settings=settings, team=FakeTeam(), comfy=pool, narrator=azure,
                                                 store=store, progress=manager.progress, ops=manager.recorder,
                                                 cloner=cloner))

    manager = JobManager(settings, store, factory)
    sample = await validate_voice_sample(make_wav(tmp_path / "s.wav", 5).read_bytes(), "s.wav", 10_000_000)
    request = VideoRequest(prompt="a lighthouse keeper", duration_minutes=0.25, video_model="wan22",
                           voice_clone={"model": "qwen3-tts", "consent": True})
    with pytest.raises(VoiceSampleError, match="requires a voice sample"):
        await manager.create(request)
    with pytest.raises(VoiceSampleError, match="not configured"):
        await JobManager(Settings(work_dir=tmp_path / "w2"), store, factory).create(request, voice_sample=sample)
    state = await manager.create(request, voice_sample=sample)
    assert state.request.voice_sample is True
    await asyncio.wait_for(manager.wait(state.id), 120)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error
    assert azure.texts == [], "Azure Speech is not used for narration"
    assert [c["text"] for c in cloner.calls] == ["The island wakes up.", "The storm comes."]
    assert {c["model"] for c in cloner.calls} == {"qwen3-tts"} and cloner.ready == ["qwen3-tts"]
    assert {c["ref_text"] for c in cloner.calls} == {"transcribed sample"}, "sample transcribed automatically"
    assert cloner.calls[0]["sample"] == sample
    assert await store.exists(state.id, VOICE_SAMPLE) and await store.exists(state.id, VOICE_SAMPLE_TRANSCRIPT)
    narrate = next(o for o in await manager.operations(state.id) if o.attrs.get("step") == "narrate")
    assert narrate.attrs["voice"].startswith("clone:qwen3-tts:")
    _, has_audio = await media.probe(store.path(state.id, "final.mp4"))
    assert has_audio
    await pool.aclose()


@requires_ffmpeg
def test_api_voice_sample_upload(tmp_path):
    settings = Settings(local_output_dir=tmp_path / "out", work_dir=tmp_path / "work", api_key="secret",
                        voice_clone_url="http://clone", max_voice_sample_mb=1)
    store = LocalArtifactStore(settings.local_output_dir)
    created = []

    class Manager:
        async def shutdown(self):
            pass

        async def create(self, request, image=None, document=None, voice_sample=None):
            created.append((request, voice_sample))
            from video_platform.schemas import JobState
            return JobState(id="abc", request=request)

    async def no_close():
        pass

    app = create_app(settings, services=(store, lambda manager: None, no_close))
    h = {"X-API-Key": "secret"}
    wav = make_wav(tmp_path / "v.wav", 4).read_bytes()
    request = json.dumps({"prompt": "a lighthouse keeper", "duration_minutes": 0.25, "voice_clone": CLONE})
    with TestClient(app) as client:
        client.app.state.jobs = Manager()
        post = lambda **kw: client.post("/api/videos", headers=h, **kw)
        config = client.get("/api/config", headers=h).json()["voice_clone"]
        assert config["configured"] and config["min_sample_seconds"] == 3
        assert [m["key"] for m in config["models"]] == ["qwen3-tts", "chatterbox", "openvoice-v2", "fish-s2-pro"]

        r = post(files={"voice_sample": ("v.wav", wav, "audio/wav")}, data={"request": request})
        assert r.status_code == 202, r.text
        assert created[-1][1] is not None and created[-1][0].voice_clone.model == "chatterbox"
        assert post(data={"request": request}, files={"x": ("x.txt", b"x")}).status_code == 422
        assert post(json={"prompt": "a lighthouse keeper", "voice_clone": CLONE}).status_code == 422, "needs a sample"
        plain = json.dumps({"prompt": "a lighthouse keeper"})
        assert post(files={"voice_sample": ("v.wav", wav)}, data={"request": plain}).status_code == 422
        no_consent = json.dumps({"prompt": "a lighthouse keeper", "voice_clone": {"model": "chatterbox"}})
        assert post(files={"voice_sample": ("v.wav", wav)}, data={"request": no_consent}).status_code == 422
        short = make_wav(tmp_path / "short.wav", 1).read_bytes()
        r = post(files={"voice_sample": ("short.wav", short)}, data={"request": request})
        assert r.status_code == 422 and "3 seconds" in r.text
        assert post(files={"voice_sample": ("v.mp3", wav)}, data={"request": request}).status_code == 415
        big = make_wav(tmp_path / "big.wav", 60).read_bytes()
        assert len(big) > 1024 * 1024
        assert post(files={"voice_sample": ("big.wav", big)}, data={"request": request}).status_code == 413
        assert len(created) == 1

    unconfigured = Settings(local_output_dir=tmp_path / "out", work_dir=tmp_path / "work")
    app = create_app(unconfigured, services=(store, lambda manager: None, no_close))
    with TestClient(app) as client:
        client.app.state.jobs = Manager()
        r = client.post("/api/videos", files={"voice_sample": ("v.wav", wav)}, data={"request": request})
        assert r.status_code == 503 and "not configured" in r.text
        assert client.get("/api/config").json()["voice_clone"]["configured"] is False


def test_cli_voice_cloning_options(tmp_path):
    sample = tmp_path / "me.wav"
    argv = ["A documentary", "--voice-sample", str(sample), "--clone-model", "fish-s2-pro", "--voice-consent",
            "--sample-transcript", "hello"]
    request, _ = parse_request(argv)
    assert request.voice_clone.model == "fish-s2-pro" and request.voice_clone.sample_transcript == "hello"
    assert voice_sample_path(argv) == sample
    assert voice_sample_path(["A documentary"]) is None
    assert parse_request(["A documentary", "--voice-sample", "me.wav", "--voice-consent"])[0].voice_clone.model == "qwen3-tts"
    for bad in (["--voice-sample", "me.wav"], ["--clone-model", "chatterbox"],
                ["--voice-sample", "me.wav", "--voice-consent", "--voice", "en-US-AndrewMultilingualNeural"]):
        with pytest.raises(SystemExit):
            parse_request(["A documentary", *bad])


def test_settings_from_env_reads_voice_clone_configuration(monkeypatch):
    monkeypatch.setenv("VOICE_CLONE_URL", "https://clone.internal/")
    monkeypatch.setenv("VOICE_CLONE_API_KEY", "k")
    monkeypatch.setenv("MAX_VOICE_SAMPLE_MB", "7")
    settings = Settings.from_env()
    assert settings.voice_clone_url == "https://clone.internal" and settings.voice_clone_api_key == "k"
    assert settings.max_voice_sample_bytes == 7 * 1024 * 1024
    monkeypatch.delenv("VOICE_CLONE_URL")
    assert Settings.from_env().voice_clone_url == ""
