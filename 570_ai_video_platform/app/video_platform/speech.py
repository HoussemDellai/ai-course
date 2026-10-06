from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from xml.sax.saxutils import escape

from azure.core.credentials import TokenCredential

log = logging.getLogger(__name__)


class SpeechError(RuntimeError):
    pass


class Narrator:
    """Azure AI Speech text-to-speech using Microsoft Entra ID (no keys) on the Foundry resource custom domain."""

    def __init__(self, endpoint: str, credential: TokenCredential, voice: str):
        self.endpoint = endpoint
        self.credential = credential
        self.voice = voice

    def _synthesize(self, text: str, dest: Path, voice: str, language: str) -> Path:
        import azure.cognitiveservices.speech as speechsdk

        config = speechsdk.SpeechConfig(token_credential=self.credential, endpoint=self.endpoint)
        config.set_speech_synthesis_output_format(speechsdk.SpeechSynthesisOutputFormat.Riff48Khz16BitMonoPcm)
        dest.parent.mkdir(parents=True, exist_ok=True)
        audio = speechsdk.audio.AudioOutputConfig(filename=str(dest))
        synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=audio)
        ssml = (
            f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{escape(language)}">'
            f'<voice name="{escape(voice)}"><lang xml:lang="{escape(language)}">{escape(text)}</lang></voice></speak>'
        )
        result = synthesizer.speak_ssml_async(ssml).get()
        del synthesizer  # releases the output file handle
        if result.reason != speechsdk.ResultReason.SynthesizingAudioCompleted:
            details = getattr(result, "cancellation_details", None)
            reason = f"{details.reason}: {details.error_details}" if details else str(result.reason)
            raise SpeechError(f"Speech synthesis failed ({reason})")
        return dest

    async def synthesize(self, text: str, dest: Path, voice: str | None = None, language: str = "en-US") -> Path:
        return await asyncio.to_thread(self._synthesize, text, dest, voice or self.voice, language)
