"""Chatterbox Multilingual zero-shot voice cloning worker (runs in the `chatterbox` virtualenv)."""

import argparse
import io
import tempfile
from pathlib import Path

import soundfile as sf
import uvicorn
from chatterbox.mtl_tts import ChatterboxMultilingualTTS
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile

LANGUAGES = set("ar da de el en es fi fr he hi it ja ko ms nl no pl pt ru sv sw tr zh".split())

model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/synthesize")
def synthesize(text: str = Form(...), language: str = Form("en-US"), ref_text: str = Form(""),
               reference: UploadFile = File(...)):
    primary = language.replace("_", "-").split("-")[0].lower()
    primary = {"nb": "no", "nn": "no"}.get(primary, primary)
    if primary not in LANGUAGES:
        raise HTTPException(422, f"Chatterbox does not support language {language}")
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "reference.wav"
        path.write_bytes(reference.file.read())
        wav = model.generate(text, language_id=primary, audio_prompt_path=str(path))
    buffer = io.BytesIO()
    sf.write(buffer, wav.squeeze().cpu().numpy(), model.sr, format="WAV", subtype="PCM_16")
    return Response(buffer.getvalue(), media_type="audio/wav")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    uvicorn.run(app, host="127.0.0.1", port=parser.parse_args().port)
