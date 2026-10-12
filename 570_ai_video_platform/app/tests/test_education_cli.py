import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest
from pydantic import ValidationError

import generate
from generate import parse_request, parse_review_command, review_command


def test_educational_defaults_and_public_topic():
    request, image = parse_request([
        "Explain network routing", "--use-case", "educational", "--public-topic", "Public network routing concepts",
    ])
    assert request.use_case == "educational"
    assert request.resolution == "1080p" and request.orientation == "horizontal"
    assert request.narration and not request.naturalistic and not request.music
    assert image is None
    assert request.education.style == "presentation"
    assert request.education.music_mode == "intro_outro"
    assert request.education.audience == "General audience"
    assert request.education.public_topic == "Public network routing concepts"


def test_educational_selectors_and_delivery():
    request, _ = parse_request([
        "Explain routing", "--usecase", "educational", "--public-topic", "Public routing",
        "--style", "ai_motion", "--image-provider", "foundry", "--motion-provider", "foundry",
        "--text-model", "configured-text", "--audience", "Engineers", "--music-mode", "background",
        "--orientation", "vertical", "--resolution", "4k", "--minutes", "0.25",
        "--speech-rate", "0", "--pronounce", "SQL=sequel",
    ])
    assert request.education.style == "ai_motion"
    assert request.education.image_provider == request.education.motion_provider == "foundry"
    assert request.education.text_model == "configured-text"
    assert request.education.audience == "Engineers"
    assert request.education.music_mode == "background"
    assert request.orientation == "vertical" and request.resolution == "4k"
    assert request.duration_minutes == 0.25
    assert request.delivery.pronunciations[0].alias == "sequel"


@pytest.mark.parametrize("mode", ["off", "intro_outro", "background"])
def test_educational_music_placement(mode):
    request, _ = parse_request(["Explain routing", "--use-case", "educational",
                               "--public-topic", "Public routing", "--music-mode", mode])
    assert request.education.music_mode == mode and not request.music


def test_whitespace_public_topic_rejected():
    with pytest.raises(SystemExit):
        parse_request(["Explain routing", "--use-case", "educational", "--public-topic", "   "])


@pytest.mark.parametrize("flags", [
    [], ["--no-narration"], ["--naturalistic"], ["--image", "photo.png"], ["--music"],
])
def test_invalid_educational_combinations(flags):
    argv = ["Explain routing", "--use-case", "educational"]
    if flags:
        argv += ["--public-topic", "Public routing", *flags]
    with pytest.raises(SystemExit):
        parse_request(argv)


@pytest.mark.parametrize("flags", [
    ["--style", "presentation"], ["--public-topic", "Public routing"], ["--image-provider", "foundry"],
    ["--motion-provider", "foundry"], ["--text-model", "text"], ["--audience", "Experts"], ["--music-mode", "off"],
])
def test_educational_flags_not_accepted_for_cinematic(flags):
    with pytest.raises(SystemExit):
        parse_request(["Explain routing", *flags])


def test_cinematic_legacy_defaults_and_selectors():
    default, image = parse_request(["A lighthouse documentary"])
    assert default.use_case == "cinematic" and default.education is None
    assert default.resolution == "720p" and not default.music and image is None
    custom, image = parse_request([
        "A lighthouse documentary", "--model", "wan22", "--naturalistic", "--music",
        "--image", "photo.jpg", "--resolution", "1080p", "--upscaler", "seedvr2",
    ])
    assert custom.naturalistic and custom.music and custom.upscaler == "seedvr2"
    assert image == Path("photo.jpg")
    with pytest.raises(ValidationError):
        parse_request(["Explain routing", "--use-case", "educational", "--public-topic", "Public routing",
                       "--resolution", "720p"])


@pytest.mark.parametrize("argv", [
    ["approve", "abc123"], ["regenerate", "abc123", "--revision", "0"],
    ["update", "abc123", "--revision", "1"], ["draft", "../job"],
    ["approve", "abc123", "--revision", "1", "--output", "draft.json"],
])
def test_review_commands_require_explicit_revision_and_valid_inputs(argv):
    with pytest.raises(SystemExit):
        parse_review_command(argv)


@pytest.mark.parametrize("command,method,endpoint", [
    ("draft", "GET", "draft"), ("approve", "POST", "approve"), ("regenerate", "POST", "regenerate"),
])
def test_review_command_api_contract(monkeypatch, capsys, command, method, endpoint):
    calls = []

    def open_request(request, timeout):
        calls.append(request)
        assert timeout == 60
        return io.BytesIO(b'{"revision": 3}')

    monkeypatch.setattr(generate, "urlopen", open_request)
    args = parse_review_command([command, "abc123", "--revision", "3",
                                 "--api-url", "http://localhost:8000/", "--api-key", "test-key"])
    review_command(args)
    request = calls[0]
    assert request.method == method
    assert request.full_url == f"http://localhost:8000/api/videos/abc123/{endpoint}"
    assert request.get_header("X-api-key") == "test-key"
    assert request.data is None if command == "draft" else json.loads(request.data) == {"revision": 3}
    assert '"revision": 3' in capsys.readouterr().out


def test_update_uses_explicit_revision_and_only_mutable_content(monkeypatch):
    data = {
        "revision": 1, "brief": {
            "title": "Routing", "description": "How routing works", "audience": "Engineers",
            "objectives": ["Learn routing"], "language": "en-US", "visual_theme": "Clear diagrams",
        },
        "scenes": [{
            "title": "Routing", "description": "Packets travel", "narration": "Packets travel through networks.",
            "image_prompt": "An illustrated network", "source_ids": ["s1"],
        }],
        "research": {"summary": "Cannot edit research", "sources": []},
    }
    monkeypatch.setattr(Path, "read_text", lambda *a, **k: json.dumps(data))
    calls = []
    monkeypatch.setattr(generate, "urlopen", lambda request, **k: calls.append(request) or io.BytesIO(b'{"revision": 5}'))
    review_command(parse_review_command(["update", "abc123", "--revision", "4", "--file", "draft.json"]))
    payload = json.loads(calls[0].data)
    assert calls[0].method == "PUT"
    assert payload["revision"] == 4
    assert set(payload) == {"revision", "brief", "scenes"}
    assert payload["scenes"][0]["narration"] == data["scenes"][0]["narration"]


def test_conflict_is_visible_without_automatic_retry(monkeypatch):
    calls = []

    def fail(request, **kwargs):
        calls.append(request)
        raise HTTPError(request.full_url, 409, "Conflict", {}, io.BytesIO(b'{"detail":"stale revision"}'))

    monkeypatch.setattr(generate, "urlopen", fail)
    with pytest.raises(RuntimeError, match="409.*stale revision"):
        review_command(parse_review_command(["approve", "abc123", "--revision", "1"]))
    assert len(calls) == 1


def test_draft_output_is_saved_locally(monkeypatch, capsys):
    writes = []
    monkeypatch.setattr(generate, "urlopen", lambda *a, **k: io.BytesIO(b'{"revision": 2}'))
    monkeypatch.setattr(Path, "write_text", lambda path, text, **k: writes.append((path, text, k)))
    review_command(parse_review_command(["draft", "abc123", "--output", "reviewed.json"]))
    assert writes[0][0] == Path("reviewed.json")
    assert json.loads(writes[0][1]) == {"revision": 2}
    assert writes[0][2] == {"encoding": "utf-8"}
    assert '"revision": 2' in capsys.readouterr().out


def test_main_review_dispatch_does_not_create_a_job(monkeypatch):
    calls = []
    monkeypatch.setattr(generate, "review_command", lambda args: calls.append((args.command, args.revision)))
    monkeypatch.setattr(generate, "create_services", lambda *args: pytest.fail("Review must not start local generation"))
    asyncio.run(generate.main(["approve", "abc123", "--revision", "2"]))
    assert calls == [("approve", 2)]


def test_main_plans_without_approving(monkeypatch, capsys):
    state = SimpleNamespace(id="abc123", status="awaiting_review", draft_revision=2,
                            model_dump_json=lambda **kwargs: '{"status":"awaiting_review"}')
    calls = []

    class Manager:
        def __init__(self, *args):
            pass

        async def create(self, request, image):
            calls.append("create")
            return state

        async def wait(self, job_id):
            calls.append("wait")

        async def get(self, job_id):
            return state

    async def close():
        calls.append("close")

    monkeypatch.setattr(generate.Settings, "from_env", lambda: SimpleNamespace())
    monkeypatch.setattr(generate, "create_services", lambda settings: (None, None, close))
    monkeypatch.setattr(generate, "JobManager", Manager)
    asyncio.run(generate.main(["Explain routing", "--use-case", "educational", "--public-topic", "Public routing"]))
    assert calls == ["create", "wait", "close"]
    output = capsys.readouterr().out
    assert "awaiting_review: revision 2" in output
    assert "approve abc123 --revision <current-revision>" in output
