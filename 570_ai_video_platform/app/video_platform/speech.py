from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from xml.sax.saxutils import escape, quoteattr

import httpx
from azure.core.credentials import TokenCredential
from pydantic import BaseModel, Field, TypeAdapter

from .schemas import NarrationDelivery

log = logging.getLogger(__name__)


class SpeechError(RuntimeError):
    pass


class VoiceCapabilities(BaseModel):
    name: str = Field(alias="ShortName")
    locale: str = Field(alias="Locale")
    secondary_locales: list[str] = Field(default_factory=list, alias="SecondaryLocaleList")
    styles: list[str] = Field(default_factory=list, alias="StyleList")
    voice_type: str = Field(alias="VoiceType")


def validate_delivery(voice: VoiceCapabilities, language: str, delivery: NarrationDelivery) -> None:
    locales = {v.lower() for v in [voice.locale, *voice.secondary_locales]}
    if language.lower() not in locales:
        raise SpeechError(f"Voice {voice.name} does not advertise language {language}; choose a compatible voice")
    if voice.voice_type != "Neural" or "HD" in voice.name:
        raise SpeechError(f"Naturalistic delivery requires a standard neural voice, not {voice.name}")
    if delivery.style and delivery.style not in voice.styles:
        raise SpeechError(f"Voice {voice.name} does not support style {delivery.style!r}; "
                          f"supported styles: {', '.join(voice.styles) or 'none'}")


def build_ssml(text: str, voice: str, language: str, delivery: NarrationDelivery | None = None) -> str:
    def spoken(value: str) -> str:
        if not delivery or not delivery.pronunciations:
            return escape(value)
        aliases = {p.text: p.alias for p in delivery.pronunciations}
        pattern = re.compile("|".join(re.escape(word) for word in sorted(aliases, key=len, reverse=True)))
        parts, end = [], 0
        for match in pattern.finditer(value):
            parts += [escape(value[end:match.start()]),
                      f"<sub alias={quoteattr(aliases[match.group()])}>{escape(match.group())}</sub>"]
            end = match.end()
        return "".join(parts) + escape(value[end:])

    if delivery:
        sentences = re.split(r"(?<=[。！？])\s*|(?<=[.!?])\s+|\n+", text.strip())
        body = f'<break time="{delivery.sentence_pause_ms}ms"/>'.join(spoken(s) for s in sentences if s)
        body = f'<prosody rate="{delivery.rate_percent:+d}%">{body}</prosody>'
        if delivery.style:
            body = f"<mstts:express-as style={quoteattr(delivery.style)}>{body}</mstts:express-as>"
    else:
        body = escape(text)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" '
        f'xmlns:mstts="https://www.w3.org/2001/mstts" xml:lang={quoteattr(language)}>'
        f'<voice name={quoteattr(voice)}><lang xml:lang={quoteattr(language)}>{body}</lang></voice></speak>'
    )


class Narrator:
    """Azure AI Speech text-to-speech using Microsoft Entra ID (no keys) on the Foundry resource custom domain."""

    def __init__(self, endpoint: str, credential: TokenCredential, voice: str):
        self.endpoint = endpoint
        self.credential = credential
        self.voice = voice
        self._voices: list[VoiceCapabilities] | None = None

    def _validate(self, voice: str, language: str, delivery: NarrationDelivery) -> None:
        if self._voices is None:
            token = self.credential.get_token("https://cognitiveservices.azure.com/.default")
            try:
                response = httpx.get(
                    self.endpoint.rstrip("/") + "/tts/cognitiveservices/voices/list",
                    headers={"Authorization": f"Bearer {token.token}"}, timeout=30,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SpeechError(f"Could not load voice capabilities from the Speech endpoint: {exc}") from exc
            self._voices = TypeAdapter(list[VoiceCapabilities]).validate_python(response.json())
        capability = next((v for v in self._voices if v.name == voice), None)
        if capability is None:
            raise SpeechError(f"Voice {voice!r} is not available at this Speech endpoint")
        validate_delivery(capability, language, delivery)

    async def validate(self, voice: str | None, language: str, delivery: NarrationDelivery) -> None:
        await asyncio.to_thread(self._validate, voice or self.voice, language, delivery)

    def _synthesize(
        self, text: str, dest: Path, voice: str, language: str, delivery: NarrationDelivery | None = None,
    ) -> Path:
        import azure.cognitiveservices.speech as speechsdk

        if delivery is not None:
            self._validate(voice, language, delivery)
        config = speechsdk.SpeechConfig(token_credential=self.credential, endpoint=self.endpoint)
        config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm)
        dest.parent.mkdir(parents=True, exist_ok=True)
        audio = speechsdk.audio.AudioOutputConfig(filename=str(dest))
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=audio)
        ssml = build_ssml(text, voice, language, delivery)
        result = synthesizer.speak_ssml_async(ssml).get()
        del synthesizer  # releases the output file handle
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            details = getattr(result, "cancellation_details", None)
            reason = f"{details.reason}: {details.error_details}" if details else str(result.reason)
            raise SpeechError(f"Speech synthesis failed ({reason})")
        return dest

    async def synthesize(
        self, text: str, dest: Path, voice: str | None = None, language: str = "en-US",
        delivery: NarrationDelivery | None = None,
    ) -> Path:
        return await asyncio.to_thread(self._synthesize, text, dest, voice or self.voice, language, delivery)
