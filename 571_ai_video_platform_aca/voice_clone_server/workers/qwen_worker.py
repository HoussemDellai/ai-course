"""Qwen3-TTS 1.7B Base zero-shot voice cloning worker (runs in the `qwen` virtualenv)."""

import argparse
import io
import os
import tempfile
from pathlib import Path

import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from qwen_tts import Qwen3TTSModel

MODEL_ID = os.environ.get("QWEN_TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-Base")
LANGUAGES = {
    "zh": "Chinese", "en": "English", "ja": "Japanese", "ko": "Korean", "de": "German",
    "fr": "French", "ru": "Russian", "pt": "Portuguese", "es": "Spanish", "it": "Italian",
}

model = Qwen3TTSModel.from_pretrained(MODEL_ID, device_map="cuda:0", dtype=torch.bfloat16)
app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/synthesize")
def synthesize(text: str = Form(...), language: str = Form("en-US"), ref_text: str = Form(""),
               reference: UploadFile = File(...)):
    primary = language.replace("_", "-").split("-")[0].lower()
    if primary not in LANGUAGES:
        raise HTTPException(422, f"Qwen3-TTS does not support language {language}")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "reference.wav"
        path.write_bytes(reference.file.read())
        # Without a transcript only the speaker embedding is used (lower fidelity, still the same voice).
        wavs, sample_rate = model.generate_voice_clone(
            text=text, language=LANGUAGES[primary], ref_audio=str(path),
            ref_text=ref_text or None, x_vector_only_mode=not ref_text,
        )
    buffer = io.BytesIO()
    sf.write(buffer, wavs[0], sample_rate, format="WAV", subtype="PCM_16")
    return Response(buffer.getvalue(), media_type="audio/wav")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    uvicorn.run(app, host="127.0.0.1", port=parser.parse_args().port)
