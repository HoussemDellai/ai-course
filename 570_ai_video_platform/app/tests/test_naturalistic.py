import asyncio
import json
import math
import shutil
import struct
import subprocess
from pathlib import Path
from types import SimpleNamespace
from xml.etree import ElementTree

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from fakes import FakeNarrator, FakeTeam, make_clip, make_png, make_wav, requires_ffmpeg
from generate import parse_request
from test_pipeline import make_services, settings  # noqa: F401
from video_platform import agents, media
from video_platform.api import create_app
from video_platform.jobs import JobManager
from video_platform.narration import fit_narration
from video_platform.operations import OpKind
from video_platform.schemas import (
    JobStatus, NarrationDelivery, NaturalStoryOutline, Pronunciation, VideoRequest,
)
from video_platform.speech import Narrator, SpeechError, VoiceCapabilities, build_ssml, validate_delivery
from video_platform.storage import LocalArtifactStore, read_json, write_json
from video_platform.video_models import VIDEO_MODELS
from video_platform.workflow import PipelineDeps, build_video_workflow


def test_delivery_validation_and_legacy_defaults():
    request = VideoRequest(prompt="a lighthouse")
    assert not request.naturalistic and request.delivery is None
    for value in (-11, 11, 2.5, "3"):
        with pytest.raises(ValidationError):
            NarrationDelivery(rate_percent=value)
    for value in (-1, 1001, 2.5):
        with pytest.raises(ValidationError):
            NarrationDelivery(sentence_pause_ms=value)
    for kwargs in ({}, {"naturalistic": True, "narration": False}):
        with pytest.raises(ValidationError, match="Delivery controls require"):
            VideoRequest(prompt="a lighthouse", delivery=NarrationDelivery(), **kwargs)
    with pytest.raises(ValidationError, match="unique"):
        NarrationDelivery(pronunciations=[Pronunciation(text="SQL", alias="sequel")] * 2)
    with pytest.raises(ValidationError):
        NarrationDelivery(unknown_control=True)


def test_music_is_opt_in():
    assert not VideoRequest(prompt="a lighthouse").music
    assert not parse_request(["a lighthouse"])[0].music
    assert parse_request(["a lighthouse", "--music"])[0].music


def test_cli_controls():
    request, image = parse_request([
        "a lighthouse", "--naturalistic", "--minutes", "0.25", "--voice", "test-voice",
        "--speech-rate", "-5", "--sentence-pause-ms", "250", "--speech-style", "calm",
        "--pronounce", "SQL=sequel", "--image", "photo.png",
    ])
    assert image == Path("photo.png")
    assert request.naturalistic and request.voice == "test-voice"
    assert request.delivery == NarrationDelivery(
        rate_percent=-5, sentence_pause_ms=250, style="calm",
        pronunciations=[Pronunciation(text="SQL", alias="sequel")],
    )
    with pytest.raises(ValidationError, match="Delivery controls require"):
        parse_request(["a lighthouse", "--speech-rate", "5"])
    with pytest.raises(SystemExit):
        parse_request(["a lighthouse", "--naturalistic", "--pronounce", "invalid"])


def test_ssml_is_structured_and_escaped():
    delivery = NarrationDelivery(rate_percent=-5, sentence_pause_ms=250, style='calm"><voice',
                                 pronunciations=[Pronunciation(text="SQL", alias='sequel & "more"')])
    xml = ElementTree.fromstring(build_ssml('SQL & <friends>. Next sentence!', 'voice"name', "fr-FR", delivery))
    ns = {"s": "http://www.w3.org/2001/10/synthesis", "m": "https://www.w3.org/2001/mstts"}
    assert xml.find("s:voice", ns).attrib["name"] == 'voice"name'
    assert xml.find(".//s:lang", ns).attrib["{http://www.w3.org/XML/1998/namespace}lang"] == "fr-FR"
    assert xml.find(".//s:prosody", ns).attrib["rate"] == "-5%"
    assert xml.find(".//s:break", ns).attrib["time"] == "250ms"
    assert xml.find(".//s:sub", ns).attrib["alias"] == 'sequel & "more"'
    assert xml.find(".//m:express-as", ns).attrib["style"] == 'calm"><voice'
    assert len(xml.findall(".//s:voice", ns)) == 1
    assert build_ssml("One. Two.", "voice", "en-US").count("<break") == 0
    assert build_ssml("你好。再见！", "voice", "zh-CN", NarrationDelivery()).count("<break") == 1


def capabilities(**kwargs):
    return VoiceCapabilities.model_validate({
        "ShortName": "en-US-TestMultilingualNeural", "Locale": "en-US",
        "SecondaryLocaleList": ["fr-FR"], "StyleList": ["calm"], "VoiceType": "Neural", **kwargs,
    })


def test_voice_language_and_style_are_checked():
    validate_delivery(capabilities(), "fr-FR", NarrationDelivery(style="calm"))
    with pytest.raises(SpeechError, match="language"):
        validate_delivery(capabilities(), "de-DE", NarrationDelivery())
    with pytest.raises(SpeechError, match="support style"):
        validate_delivery(capabilities(), "en-US", NarrationDelivery(style="excited"))
    with pytest.raises(SpeechError, match="standard neural"):
        validate_delivery(capabilities(ShortName="en-US-Test:DragonHDLatestNeural"), "en-US", NarrationDelivery())


async def test_voice_capabilities_fetch_and_errors(monkeypatch):
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, request=httpx.Request("GET", url),
                              json=[capabilities().model_dump(by_alias=True)])

    monkeypatch.setattr("video_platform.speech.httpx.get", get)
    narrator = Narrator("https://example.cognitiveservices.azure.com/",
                        SimpleNamespace(get_token=lambda scope: SimpleNamespace(token="test-only")),
                        capabilities().name)
    await narrator.validate(None, "fr-FR", NarrationDelivery())
    await narrator.validate(None, "en-US", NarrationDelivery(style="calm"))
    assert len(calls) == 1 and calls[0][0] == "https://example.cognitiveservices.azure.com/tts/cognitiveservices/voices/list"
    with pytest.raises(SpeechError, match="not available"):
        await narrator.validate("missing", "en-US", NarrationDelivery())

    def fail(url, **kwargs):
        raise httpx.ConnectError("test failure")

    monkeypatch.setattr("video_platform.speech.httpx.get", fail)
    narrator._voices = None
    with pytest.raises(SpeechError, match="Could not load voice capabilities"):
        await narrator.validate(None, "en-US", NarrationDelivery())


async def test_naturalistic_prompts_and_strict_schema(monkeypatch):
    fake = FakeTeam()
    brief = await fake.enhance("a lighthouse", 15)
    natural = await fake.outline(brief, 6, 2.5, naturalistic=True)
    captured = []
    team = agents.FoundryCreativeTeam(None)
    monkeypatch.setattr(team, "_agent", lambda name, instructions: (name, instructions))

    async def run(agent, message, output_type, attempts=3):
        captured.append((agent, message, output_type))
        if output_type is NaturalStoryOutline:
            return NaturalStoryOutline(scenes=natural.scenes)
        return output_type.model_validate({"shots": [{"prompt": "standing still"}]})

    monkeypatch.setattr(agents, "_run_structured", run)
    outline = await team.outline(brief, 6, 2.5, naturalistic=True)
    await team.write_shots(brief, outline.scenes[0], 0, 2, VIDEO_MODELS["ltx2"],
                           naturalistic=True, neighbors=outline.scenes[1].model_dump_json())
    assert "silent beats" in captured[0][0][1]
    assert "static camera" in captured[1][0][1]
    assert "no speech, lyrics" in captured[1][0][1]
    assert "Storm" in captured[1][1] and "screen_direction" in captured[1][1]
    schema = NaturalStoryOutline.model_json_schema()
    scene = schema["$defs"]["NaturalSceneOutline"]
    assert set(scene["required"]) == set(scene["properties"])
    continuity = schema["$defs"]["Continuity"]
    assert set(continuity["required"]) == set(continuity["properties"])


def test_api_accepts_controls_in_json_and_multipart(settings, monkeypatch):
    store = LocalArtifactStore(settings.local_output_dir)
    monkeypatch.setattr(JobManager, "_start", lambda *args, **kwargs: None)

    async def close():
        pass

    app = create_app(settings, services=(store, lambda manager: None, close))
    body = {"prompt": "a lighthouse", "naturalistic": True, "voice": "test-voice",
            "delivery": {"rate_percent": -5, "sentence_pause_ms": 250}}
    with TestClient(app) as client:
        for kwargs in ({"json": body}, {"data": {"request": json.dumps(body)},
                                      "files": {"image": ("photo.png", make_png(), "image/png")}}):
            response = client.post("/api/videos", **kwargs)
            assert response.status_code == 202, response.text
            request = response.json()["request"]
            assert request["naturalistic"] and request["delivery"]["rate_percent"] == -5
        invalid = client.post("/api/videos", json={**body, "narration": False})
        assert invalid.status_code == 422
        invalid = client.post("/api/videos", json={**body, "delivery": {"sentence_pause_ms": 1001}})
        assert invalid.status_code == 422
        schema = client.get("/openapi.json").json()["components"]["schemas"]["VideoRequest"]
        assert "naturalistic" in schema["properties"] and "delivery" in schema["properties"]
        assert schema["properties"]["music"]["default"] is False
        asyncio.run(write_json(store, "test", "storyboard.json", {"narration": "original"}))
        asyncio.run(write_json(store, "test", "storyboard.narrated.json", {"narration": "accepted"}))
        assert client.get("/api/videos/test/storyboard").json() == {"narration": "accepted"}


@requires_ffmpeg
@pytest.mark.parametrize("model_key,narration", [
    ("wan22", True), ("ltx2", True), ("ltx25", True), ("hunyuan15", False),
])
async def test_naturalistic_pipeline(settings, tmp_path, monkeypatch, model_key, narration):
    store, factory, close, comfy, team, narrator = make_services(
        settings, tmp_path, monkeypatch, model_key, narration_seconds=3,
    )
    original_synthesize = narrator.synthesize

    async def synthesize(*args, **kwargs):
        assert not comfy.submitted, "narration must be accepted before any GPU rendering"
        return await original_synthesize(*args, **kwargs)

    monkeypatch.setattr(narrator, "synthesize", synthesize)
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25,
                                              video_model=model_key, naturalistic=True, narration=narration),
                                  image=make_png() if model_key == "ltx2" else None)
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error
    assert abs(await media.video_duration(store.path(state.id, "final.mp4")) - 15) <= 1 / settings.output_fps
    storyboard = await read_json(store, state.id, "storyboard.json")
    assert all(s["continuity"]["screen_direction"] == "left to right" for s in storyboard["scenes"])
    assert all(team.neighbors)
    steps = [op.attrs["step"] for op in await manager.operations(state.id) if op.kind == OpKind.step]
    assert steps == ["enhance_prompt", "plan_storyboard", "prepare_narration",
                     "generate_keyframes", "generate_clips", "process_shots", "generate_music", "assemble"]
    assert len(narrator.deliveries) == (2 if narration else 0)
    assert all(delivery == NarrationDelivery() for delivery in narrator.deliveries)
    await close()


@requires_ffmpeg
async def test_naturalistic_pipeline_with_music_keeps_exact_durations(settings, tmp_path, monkeypatch):
    store, factory, close, comfy, team, _ = make_services(settings, tmp_path, monkeypatch, "ltx25",
                                                           narration_seconds=3)
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, video_model="ltx25",
                                              naturalistic=True, music=True))
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.completed, final.error
    assert abs(await media.video_duration(store.path(state.id, "final.mp4")) - 15) <= 1 / settings.output_fps
    # Naturalistic scenes are exactly their shots' frame-aligned budget: 3 shots of 2.5 s.
    assert team.music_durations == pytest.approx([7.5, 7.5], abs=1 / settings.output_fps)
    assert sum(any(n["class_type"] == "SaveAudio" for n in w.values()) for w in comfy.submitted) == 2
    await close()


@requires_ffmpeg
async def test_overrun_fails_before_gpu_and_retry_does_not_reset_budget(settings, tmp_path, monkeypatch):
    store, factory, close, comfy, team, narrator = make_services(
        settings, tmp_path, monkeypatch, "wan22", narration_seconds=9,
    )
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, naturalistic=True))
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.failed and "two corrections" in final.error
    assert not comfy.submitted
    count = len(narrator.texts)
    assert count <= 6
    await manager.retry(state.id)
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.failed
    assert len(narrator.texts) <= 6 and not comfy.submitted
    journals = list(store.path(state.id, "narration").rglob("takes.json"))
    assert all(len(json.loads(p.read_text())["takes"]) <= 3 for p in journals)
    await close()


@requires_ffmpeg
async def test_fit_correction_reuse_invalidation_and_interrupted_publication(tmp_path):
    team, narrator = FakeTeam(), FakeNarrator(4)
    store = LocalArtifactStore(tmp_path / "out")
    brief = await team.enhance("lighthouse", 15)
    original = narrator.synthesize

    async def synthesize(text, *args, **kwargs):
        narrator.seconds = 4 if text == "The island wakes up." else 1
        return await original(text, *args, **kwargs)

    narrator.synthesize = synthesize
    kwargs = dict(team=team, narrator=narrator, store=store, job_id="fit", work_dir=tmp_path / "work",
                  scene_index=0, text="The island wakes up.", brief=brief, voice="test-voice",
                  delivery=NarrationDelivery(), budget=4)
    path, text, seconds, reused = await fit_narration(**kwargs)
    assert text == "The island wakes." and seconds == 1 and not reused
    assert len(narrator.texts) == 2 and team.calls.count("shorten") == 1
    assert (await fit_narration(**kwargs))[3] is True
    assert len(narrator.texts) == 2
    record_path = store.path("fit", str(path.relative_to(tmp_path / "work").parent / "takes.json"))
    record = json.loads(record_path.read_text())
    record["accepted"] = None
    record["takes"][-1]["duration"] = None
    record["takes"][-1]["sha256"] = None
    await write_json(store, "fit", str(record_path.relative_to(store.path("fit", ""))), record)
    assert (await fit_narration(**kwargs))[3] is True, "recover audio published before checkpoint"
    assert len(narrator.texts) == 2
    changed = await fit_narration(**{**kwargs, "text": "New narration."})
    assert changed[0] != path and len(narrator.texts) == 3
    audio = store.path("fit", str(path.relative_to(tmp_path / "work")))
    audio.write_bytes(b"corrupt")
    with pytest.raises(SpeechError, match="checksum"):
        await fit_narration(**kwargs)


@requires_ffmpeg
async def test_naturalistic_resume_and_incompatible_manifest(settings, tmp_path, monkeypatch):
    store, factory, close, comfy, team, narrator = make_services(
        settings, tmp_path, monkeypatch, "wan22", narration_seconds=3,
    )
    comfy.fail_first = 1000
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, naturalistic=True))
    await manager.wait(state.id)
    assert (await manager.get(state.id)).status == JobStatus.failed
    assert len(narrator.texts) == 2
    comfy.fail_first = 0
    manager2 = JobManager(settings, store, factory)
    await manager2.retry(state.id)
    await manager2.wait(state.id)
    assert (await manager2.get(state.id)).status == JobStatus.completed
    assert len(narrator.texts) == 2 and team.calls.count("enhance") == 1
    stored = await read_json(store, state.id, "state.json")
    stored["status"] = "failed"
    stored["request"]["delivery"] = {"rate_percent": 5}
    await write_json(store, state.id, "state.json", stored)
    await manager2.retry(state.id)
    await manager2.wait(state.id)
    final = await manager2.get(state.id)
    assert final.status == JobStatus.failed and "dependencies changed" in final.error
    await close()


@requires_ffmpeg
async def test_naturalistic_mixing_ducks_audio_and_preserves_frames(tmp_path):
    source = make_clip(tmp_path / "input.mp4", 5, 24, 160, 96, audio=True)
    video = await media.normalize_clip(source, tmp_path / "video.mp4", 160, 96, 24, True, 1,
                                       naturalistic=True, target_duration=5)
    narration = make_wav(tmp_path / "voice.wav", 2)
    output = await media.mix_narration(video, narration, tmp_path / "mixed.mp4", naturalistic=True)
    assert abs(await media.video_duration(output) - 5) < 1 / 24
    frames = json.loads(await media.run(
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_frames", "-of", "json", str(output),
    ))
    assert int(frames["streams"][0]["nb_read_frames"]) == 120
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(output), "-vn", "-ac", "1",
                          "-ar", "48000", "-f", "f32le", "-"], check=True, capture_output=True).stdout
    samples = struct.unpack(f"<{len(raw) // 4}f", raw)

    def amplitude(start, frequency):
        window = samples[int(start * 48000):int((start + 0.2) * 48000)]
        real = sum(v * math.cos(2 * math.pi * frequency * i / 48000) for i, v in enumerate(window))
        imag = sum(v * math.sin(2 * math.pi * frequency * i / 48000) for i, v in enumerate(window))
        return 2 * math.hypot(real, imag) / len(window)

    assert amplitude(1.0, 440) < amplitude(4.0, 440) * 0.5, "ambience must duck under speech then recover"
    assert amplitude(1.0, 220) > 0.05, "narration must remain audible"
    assert max(abs(v) for v in samples) < 1.0, "decoded AAC must not clip"
    with pytest.raises(media.MediaError, match="never freezes"):
        await media.mix_narration(video, make_wav(tmp_path / "long.wav", 5),
                                   tmp_path / "overrun.mp4", naturalistic=True)
    silent = await media.mix_narration(video, None, tmp_path / "no-narration.mp4", naturalistic=True)
    assert abs(await media.video_duration(silent) - 5) < 1 / 24
    with pytest.raises(media.MediaError, match="shorter"):
        await media.normalize_clip(source, tmp_path / "short.mp4", 160, 96, 24, True, 1,
                                   naturalistic=True, target_duration=6)


@requires_ffmpeg
async def test_fractional_clip_timing_does_not_accumulate_drift(tmp_path):
    source = make_clip(tmp_path / "wan.mp4", 81 / 16, 16, 160, 96, audio=False)
    budget = math.floor(81 / 16 * 24) / 24
    clip = await media.normalize_clip(source, tmp_path / "normalized.mp4", 160, 96, 24, False, 0.25,
                                      naturalistic=True, target_duration=budget)
    scene = await media.concat([clip] * 3, tmp_path / "scene.mp4", exact=True)
    final = await media.concat([scene] * 3, tmp_path / "final.mp4", exact=True)
    assert abs(await media.video_duration(final) - budget * 9) < 1 / 24
    frames = json.loads(await media.run(
        "ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0",
        "-show_entries", "stream=nb_read_frames", "-of", "json", str(final),
    ))
    assert int(frames["streams"][0]["nb_read_frames"]) == 121 * 9


@requires_ffmpeg
async def test_narration_loudness_is_consistent(tmp_path):
    source = make_clip(tmp_path / "source.mp4", 5, 24, 160, 96, audio=False)
    video = await media.normalize_clip(source, tmp_path / "video.mp4", 160, 96, 24, False, 0.25,
                                       naturalistic=True, target_duration=5)
    voice = make_wav(tmp_path / "voice.wav", 3)
    quiet = tmp_path / "quiet.wav"
    await media.run("ffmpeg", "-y", "-i", str(voice), "-af", "volume=0.1", str(quiet))
    loudness = []
    for i, narration in enumerate([voice, quiet]):
        output = await media.mix_narration(video, narration, tmp_path / f"mix{i}.mp4", naturalistic=True)
        measurement = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", str(output), "-af",
             "loudnorm=I=-18:TP=-3:LRA=7:print_format=json", "-vn", "-f", "null", "-"],
            capture_output=True, text=True, check=True,
        ).stderr
        stats = json.loads(measurement[measurement.rfind("{"):measurement.rfind("}") + 1])
        loudness.append(float(stats["input_i"]))
        assert float(stats["input_tp"]) < 0
    assert all(-19 <= level <= -17 for level in loudness), loudness
    assert abs(loudness[0] - loudness[1]) < 0.5, loudness


@requires_ffmpeg
async def test_missing_speech_and_unsupported_delivery_fail_before_gpu(settings, tmp_path, monkeypatch):
    store, factory, close, comfy, team, narrator = make_services(
        settings, tmp_path, monkeypatch, "wan22", narration_seconds=3,
    )

    async def validate(*args):
        raise SpeechError("Unsupported selected voice style")

    monkeypatch.setattr(narrator, "validate", validate)
    manager = JobManager(settings, store, factory)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, naturalistic=True))
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.failed and "Unsupported selected voice style" in final.error
    assert not comfy.submitted and not narrator.texts
    pool = comfy.pool()

    def missing_speech(manager):
        return build_video_workflow(PipelineDeps(
            settings=settings, store=store, team=team, narrator=None, comfy=pool,
            progress=manager.progress, ops=manager.recorder,
        ))

    manager = JobManager(settings, store, missing_speech)
    state = await manager.create(VideoRequest(prompt="a lighthouse", duration_minutes=0.25, naturalistic=True))
    await manager.wait(state.id)
    final = await manager.get(state.id)
    assert final.status == JobStatus.failed and "configured Speech endpoint" in final.error
    assert not comfy.submitted
    await pool.aclose()
    await close()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is required for the UI behavior test")
def test_browser_composer_request_and_controls():
    script = r"""
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const html = fs.readFileSync(process.argv[1], "utf8");
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
const elements = new Map();
for (const match of html.matchAll(/\bid="([^"]+)"/g)) {
  const attributes = html.slice(html.lastIndexOf("<", match.index), html.indexOf(">", match.index));
  elements.set(match[1], {
    value: attributes.match(/\bvalue="([^"]*)"/)?.[1] || "",
    checked: /\bchecked\b/.test(attributes), disabled: /\bdisabled\b/.test(attributes),
    style: {}, classList: {add() {}, remove() {}, toggle() {}},
    addEventListener() {}, focus() {}, querySelectorAll() {return []}
  });
}
const el = id => {
  assert(elements.has(id), `Missing DOM element ${id}`);
  return elements.get(id);
};
const posts = [], alerts = [];
const context = {
  document: {getElementById: el, addEventListener() {}, querySelectorAll() {return []}, hidden: true},
  window: {addEventListener() {}}, localStorage: {getItem() {return ""}},
  location: {hash: ""}, setInterval() {}, clearInterval() {}, setTimeout() {}, clearTimeout() {},
  alert(message) {alerts.push(message)}, console, URL, FormData,
  async fetch(url, options) {
    if (options.method === "POST") {
      posts.push(JSON.parse(options.body));
      return {ok: true, status: 202, async json() {return {id: "created", request: posts.at(-1)}}};
    }
    return {ok: true, async json() {return []}};
  },
};
vm.createContext(context);
vm.runInContext(script, context);
(async () => {
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(el("deliveryControls").disabled, true);
  el("naturalistic").checked = true;
  el("naturalistic").onchange();
  assert.equal(el("deliveryControls").disabled, false);
  el("prompt").value = "A lighthouse";
  el("voice").value = "test-voice";
  el("speechRate").value = "-5";
  el("sentencePause").value = "250";
  el("speechStyle").value = "calm";
  el("pronunciations").value = "SQL=sequel";
  await el("form").onsubmit({preventDefault() {}});
  assert.equal(posts.length, 1);
  assert.equal(posts[0].naturalistic, true);
  assert.equal(posts[0].voice, "test-voice");
  assert.deepEqual(posts[0].delivery, {
    rate_percent: -5, sentence_pause_ms: 250, style: "calm",
    pronunciations: [{text: "SQL", alias: "sequel"}],
  });
  el("pronunciations").value = "invalid";
  await el("form").onsubmit({preventDefault() {}});
  assert.equal(posts.length, 1);
  assert.match(alerts.pop(), /TEXT=ALIAS/);
  el("narration").checked = false;
  el("narration").onchange();
  assert.equal(el("deliveryControls").disabled, true);
  await el("form").onsubmit({preventDefault() {}});
  assert.equal(posts.at(-1).delivery, undefined);
  el("naturalistic").checked = false;
  el("naturalistic").onchange();
  await el("form").onsubmit({preventDefault() {}});
  assert.equal(posts.at(-1).naturalistic, false);
  assert.equal(el("send").disabled, false);
})().catch(error => {console.error(error); process.exitCode = 1;});
"""
    html = Path(__file__).parents[1] / "video_platform" / "static" / "index.html"
    subprocess.run(["node", "-e", script, str(html)], check=True, capture_output=True, text=True)
