from types import SimpleNamespace

import httpx
import pytest

from video_platform.schemas import NarrationDelivery
from video_platform.speech import Narrator, SpeechError, VoiceCapabilities


def narrator():
    instance = Narrator("https://speech.example/", SimpleNamespace(
        get_token=lambda scope: SimpleNamespace(token="fixture-token"),
    ), "en-US-Voice")
    instance._voices = [VoiceCapabilities(ShortName="en-US-Voice", Locale="en-US", VoiceType="Neural")]
    return instance


async def test_educational_rest_transport_preserves_delivery_and_wav(monkeypatch, tmp_path):
    calls = []
    wav = b"RIFF" + b"\0" * 4 + b"WAVE" + b"fixture"

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(200, content=wav, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    path = await narrator().synthesize(
        "Approved <text> & facts.", tmp_path / "voice.wav", language="en-US",
        delivery=NarrationDelivery(sentence_pause_ms=250), transport="rest",
    )
    assert path.read_bytes() == wav
    url, kwargs = calls[0]
    assert url == "https://speech.example/tts/cognitiveservices/v1"
    assert kwargs["headers"]["X-Microsoft-OutputFormat"] == "riff-48khz-16bit-mono-pcm"
    assert b"Approved &lt;text&gt; &amp; facts." in kwargs["content"]
    assert kwargs["timeout"] == 120


@pytest.mark.parametrize("failure", ["http", "invalid_audio"])
async def test_rest_failures_are_explicit_without_sdk_fallback(monkeypatch, tmp_path, failure):
    def post(url, **kwargs):
        return httpx.Response(503 if failure == "http" else 200, content=b"invalid",
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    instance = narrator()
    monkeypatch.setattr(instance, "_synthesize", lambda *args: pytest.fail("Must not silently use SDK"))
    with pytest.raises(SpeechError, match="REST synthesis"):
        await instance.synthesize("Approved script", tmp_path / "voice.wav", transport="rest")
    assert not (tmp_path / "voice.wav").exists()


async def test_legacy_sdk_is_still_default_and_unknown_transport_fails(monkeypatch, tmp_path):
    instance = narrator()
    path = tmp_path / "voice.wav"
    monkeypatch.setattr(instance, "_synthesize", lambda *args: path)
    assert await instance.synthesize("Legacy narration", path) == path
    with pytest.raises(SpeechError, match="Unsupported"):
        await instance.synthesize("Narration", path, transport="unsupported")
