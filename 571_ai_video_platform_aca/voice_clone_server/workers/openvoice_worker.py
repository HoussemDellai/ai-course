"""OpenVoice v2 worker (runs in the `openvoice` virtualenv): MeloTTS speaks the text, then the OpenVoice
tone-color converter re-voices it with the uploaded sample's timbre."""

import argparse
import io
import tempfile
from pathlib import Path

import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, Response, UploadFile
from huggingface_hub import snapshot_download
from melo.api import TTS
from openvoice.api import OpenVoiceBaseClass, ToneColorConverter

# language -> (MeloTTS language code, base-speaker embedding file)
LANGUAGES = {
    "en": ("EN_NEWEST", "en-newest"), "es": ("ES", "es"), "fr": ("FR", "fr"),
    "zh": ("ZH", "zh"), "ja": ("JP", "jp"), "ko": ("KR", "kr"),
}
DEVICE = "cuda:0"


class Converter(ToneColorConverter):
    """ToneColorConverter without the optional wavmark watermark (its __init__ cannot be told to skip it)."""

    def __init__(self, config_path: str, device: str):
        OpenVoiceBaseClass.__init__(self, config_path, device)
        self.watermark_model = None
        self.version = getattr(self.hps, "_version_", "v1")


checkpoints = Path(snapshot_download("myshell-ai/OpenVoiceV2"))
converter = Converter(str(checkpoints / "converter" / "config.json"), DEVICE)
converter.load_ckpt(str(checkpoints / "converter" / "checkpoint.pth"))
base_models: dict[str, TTS] = {}
app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/synthesize")
def synthesize(text: str = Form(...), language: str = Form("en-US"), ref_text: str = Form(""),
               reference: UploadFile = File(...)):
    primary = language.replace("_", "-").split("-")[0].lower()
    if primary not in LANGUAGES:
        raise HTTPException(422, f"OpenVoice v2 does not support language {language}")
    melo_language, embedding = LANGUAGES[primary]
    if melo_language not in base_models:
        base_models[melo_language] = TTS(language=melo_language, device=DEVICE)
    base = base_models[melo_language]
    speaker_id = next(iter(base.hps.data.spk2id.values()))
    source_se = torch.load(checkpoints / "base_speakers" / "ses" / f"{embedding}.pth", map_location=DEVICE)
    with tempfile.TemporaryDirectory() as tmp:
        reference_path, base_path, out_path = (Path(tmp) / n for n in ("reference.wav", "base.wav", "out.wav"))
        reference_path.write_bytes(reference.file.read())
        target_se = converter.extract_se(str(reference_path))
        base.tts_to_file(text, speaker_id, str(base_path), speed=1.0)
        converter.convert(audio_src_path=str(base_path), src_se=source_se, tgt_se=target_se,
                          output_path=str(out_path), message="default")
        audio, sample_rate = sf.read(out_path, dtype="float32")
    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV", subtype="PCM_16")
    return Response(buffer.getvalue(), media_type="audio/wav")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    uvicorn.run(app, host="127.0.0.1", port=parser.parse_args().port)
