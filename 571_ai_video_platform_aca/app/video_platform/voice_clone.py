"""Zero-shot voice cloning: validates the uploaded sample and talks to the GPU voice-clone service."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from . import media
from .schemas import NarrationDelivery, VoiceCloneOptions
from .speech import SpeechError

log = logging.getLogger(__name__)

VOICE_SAMPLE = "input/voice_sample.wav"
VOICE_SAMPLE_TRANSCRIPT = "input/voice_sample.txt"
MIN_SAMPLE_SECONDS = 3.0
MAX_SAMPLE_SECONDS = 30.0
SAMPLE_RATE = 24000
SAMPLE_SUFFIXES = {".wav", ".mp4"}


@dataclass(frozen=True)
class CloneModelInfo:
    key: str
    name: str
    license: str
    languages: frozenset[str] | None  # primary language subtags; None = the model advertises 80+ languages
    uses_transcript: bool  # a transcript of the sample improves (or is needed for) the clone


CLONE_MODELS: dict[str, CloneModelInfo] = {m.key: m for m in [
    CloneModelInfo("qwen3-tts", "Qwen3-TTS 1.7B Base", "Apache-2.0",
                   frozenset("zh en ja ko de fr ru pt es it".split()), True),
    CloneModelInfo("chatterbox", "Chatterbox Multilingual", "MIT", frozenset(
        "ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh".split()), False),
    CloneModelInfo("openvoice-v2", "OpenVoice v2 (MeloTTS + tone-color converter)", "MIT",
                   frozenset("en es fr zh ja ko".split()), False),
    CloneModelInfo("fish-s2-pro", "Fish Audio S2 Pro", "Fish Audio Research License (non-commercial)", None, True),
]}
_LANGUAGE_ALIASES = {"nb": "no", "nn": "no", "iw": "he"}


def primary_language(language: str) -> str:
    primary = language.replace("_", "-").split("-")[0].lower()
    return _LANGUAGE_ALIASES.get(primary, primary)


def supports_language(model: str, language: str) -> bool:
    languages = CLONE_MODELS[model].languages
    return languages is None or primary_language(language) in languages


class VoiceSampleError(ValueError):
    def __init__(self, message: str, status_code: int = 422):
        super().__init__(message)
        self.status_code = status_code


async def validate_voice_sample(data: bytes, filename: str, max_bytes: int) -> bytes:
    """Checks a .wav/.mp4 upload and returns it as 24 kHz mono PCM WAV (first 30 s, at least 3 s of audio)."""
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    suffix = Path(name).suffix.lower()
    if suffix not in SAMPLE_SUFFIXES:
        raise VoiceSampleError("Use a WAV (.wav) or MP4 (.mp4) voice sample", 415)
    if not data:
        raise VoiceSampleError("The voice sample is empty")
    if len(data) > max_bytes:
        raise VoiceSampleError(f"The voice sample is larger than {max_bytes // (1024 * 1024)} MB", 413)
    is_wav = data[:4] == b"RIFF" and data[8:12] == b"WAVE"
    is_mp4 = data[4:8] == b"ftyp"
    if (suffix == ".wav" and not is_wav) or (suffix == ".mp4" and not is_mp4):
        raise VoiceSampleError(f"The file is not a valid {suffix[1:].upper()} file")
    with tempfile.TemporaryDirectory() as tmp:
        source, output = Path(tmp) / f"input{suffix}", Path(tmp) / "sample.wav"
        source.write_bytes(data)
        try:
            await media.run("ffmpeg", "-v", "error", "-y", "-i", str(source), "-vn", "-map", "0:a:0",
                            "-t", str(MAX_SAMPLE_SECONDS), "-ac", "1", "-ar", str(SAMPLE_RATE),
                            "-c:a", "pcm_s16le", str(output))
            seconds, has_audio = await media.probe(output)
        except media.MediaError:
            raise VoiceSampleError("The voice sample has no readable audio track") from None
        if not has_audio or seconds < MIN_SAMPLE_SECONDS:
            raise VoiceSampleError(
                f"The voice sample must contain at least {MIN_SAMPLE_SECONDS:g} seconds of audio "
                f"(found {max(seconds, 0):.1f} s)")
        return output.read_bytes()


def validate_voice_clone_request(request, settings, has_sample: bool) -> None:
    """The request, the upload and the deployment must agree on whether the voice is cloned."""
    if request.voice_clone is None:
        if has_sample:
            raise VoiceSampleError("A voice sample requires the voice_clone options (model and consent)")
        return
    if not has_sample:
        raise VoiceSampleError("Voice cloning requires a voice sample upload (multipart 'voice_sample' field)")
    if not settings.voice_clone_url:
        raise VoiceSampleError("Voice cloning is not configured on this deployment (VOICE_CLONE_URL)", 503)


class VoiceCloner:
    """Async client of the voice-clone service (see voice_clone_server): start a model, then synthesize."""

    def __init__(self, url: str, api_key: str = "", load_timeout: float = 1800, poll_seconds: float = 5.0,
                 retries: int = 8, retry_seconds: float = 5.0, transport: httpx.AsyncBaseTransport | None = None):
        self.url = url.rstrip("/")
        self.load_timeout = load_timeout
        self.poll_seconds = poll_seconds
        self.retries = retries
        self.retry_seconds = retry_seconds
        headers = {"X-API-Key": api_key} if api_key else {}
        self._client = httpx.AsyncClient(headers=headers, transport=transport,
                                         timeout=httpx.Timeout(300, connect=30))

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Retries while the scale-to-zero GPU replica starts (connection errors, 502/503/504)."""
        last = "no response"
        for attempt in range(self.retries):
            try:
                response = await self._client.request(method, self.url + path, **kwargs)
            except httpx.TransportError as exc:
                last = f"{type(exc).__name__}: {exc}"
            else:
                if response.status_code not in {502, 503, 504}:
                    return response
                last = f"HTTP {response.status_code}"
            log.warning("Voice-clone service not ready (%s); retry %d/%d", last, attempt + 1, self.retries)
            await asyncio.sleep(self.retry_seconds * min(attempt + 1, 6))
        raise SpeechError(f"The voice-clone service is unavailable ({last})")

    @staticmethod
    def _check(response: httpx.Response, action: str) -> None:
        if response.is_success:
            return
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        if response.status_code in {401, 403}:
            detail = "invalid or missing API key"
        raise SpeechError(f"Voice cloning {action} failed (HTTP {response.status_code}): {str(detail)[:500]}")

    async def ensure_ready(self, model: str) -> None:
        info = CLONE_MODELS[model]
        self._check(await self._request("POST", f"/v1/models/{model}/start"), f"start of {info.name}")
        deadline = time.monotonic() + self.load_timeout
        while True:
            response = await self._request("GET", f"/v1/models/{model}")
            self._check(response, f"status of {info.name}")
            status = response.json()
            if status.get("state") == "ready":
                return
            if status.get("state") == "error":
                raise SpeechError(f"{info.name} failed to load: {status.get('error', 'unknown error')}")
            if time.monotonic() > deadline:
                raise SpeechError(f"{info.name} did not load within {self.load_timeout:.0f} s")
            await asyncio.sleep(self.poll_seconds)

    async def synthesize(self, *, model: str, text: str, language: str, sample: Path, ref_text: str,
                         pause_ms: int, dest: Path) -> Path:
        reference = sample.read_bytes()
        for attempt in range(2):
            response = await self._request(
                "POST", "/v1/synthesize",
                data={"model": model, "text": text, "language": language, "ref_text": ref_text,
                      "pause_ms": str(pause_ms)},
                files={"reference": ("reference.wav", reference, "audio/wav")},
            )
            if response.status_code == 409 and attempt == 0:  # evicted from the GPU by another model
                await self.ensure_ready(model)
                continue
            self._check(response, "synthesis")
            break
        if not response.content.startswith(b"RIFF") or response.content[8:12] != b"WAVE":
            raise SpeechError("Voice cloning returned no valid WAV audio")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(response.content)
        return dest


class CloneNarrator:
    """Drop-in for speech.Narrator that speaks in the voice of the job's uploaded sample."""

    def __init__(self, cloner: VoiceCloner, options: VoiceCloneOptions, sample: Path, ref_text: str):
        self.cloner = cloner
        self.options = options
        self.sample = sample
        self.ref_text = ref_text
        digest = hashlib.sha256(sample.read_bytes()).hexdigest()[:16]
        self.voice = self.voice_id = f"clone:{options.model}:{digest}"
        self._ready = False
        self._lock = asyncio.Lock()  # the GPU service synthesizes one request at a time; don't queue them on its side

    async def validate(self, voice: str | None, language: str, delivery: NarrationDelivery | None) -> None:
        info = CLONE_MODELS[self.options.model]
        if not supports_language(info.key, language):
            raise SpeechError(f"{info.name} does not support narration language {language}; choose another "
                              f"voice-cloning model ({', '.join(sorted(info.languages or ()))} are supported)")
        if delivery is not None and (delivery.style or delivery.rate_percent):
            raise SpeechError("Cloned voices support pronunciations and sentence pauses, not style or rate")
        if not self._ready:
            await self.cloner.ensure_ready(info.key)
            self._ready = True

    async def synthesize(self, text: str, dest: Path, voice: str | None = None, language: str = "en-US",
                         delivery: NarrationDelivery | None = None, transport: str = "sdk") -> Path:
        await self.validate(voice, language, delivery)
        if delivery and delivery.pronunciations:
            aliases = {p.text: p.alias for p in delivery.pronunciations}
            pattern = re.compile("|".join(re.escape(w) for w in sorted(aliases, key=len, reverse=True)))
            text = pattern.sub(lambda m: aliases[m.group()], text)
        async with self._lock:
            return await self.cloner.synthesize(
                model=self.options.model, text=text, language=language, sample=self.sample,
                ref_text=self.ref_text, pause_ms=delivery.sentence_pause_ms if delivery else 250, dest=dest,
            )
