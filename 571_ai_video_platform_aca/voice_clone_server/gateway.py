"""Voice-clone gateway: serves one zero-shot TTS engine at a time on the GPU.

Each engine (Qwen3-TTS, Chatterbox, OpenVoice v2, Fish Audio S2 Pro) runs as its own process inside its own
virtualenv, because their pinned dependencies conflict. The orchestrator starts an engine (POST
/v1/models/{key}/start), polls until it is ready, then synthesizes (POST /v1/synthesize). Starting an engine stops
the previous one to free GPU memory. Long text is split into sentence groups and joined with silence.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
import re
import secrets
import wave
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response

log = logging.getLogger("voice-clone")

VENVS = Path(os.environ.get("VENV_ROOT", "/opt/venvs"))
WORKERS = Path(os.environ.get("WORKERS_DIR", "/app/workers"))
FISH_REPO = Path(os.environ.get("FISH_REPO", "/opt/fish-speech"))
CACHE = Path(os.environ.get("MODEL_CACHE", "/cache/voice-clone"))
API_KEY = os.environ.get("API_KEY", "")
LOAD_TIMEOUT = float(os.environ.get("LOAD_TIMEOUT_SECONDS", "1800"))
MAX_TEXT_CHARS = 8000
CHUNK_CHARS = int(os.environ.get("CHUNK_CHARS", "300"))
FISH_REPO_ID = os.environ.get("FISH_MODEL_REPO", "fishaudio/s2-pro")


@dataclass
class Engine:
    key: str
    name: str
    port: int
    command: list[str]
    cwd: Path | None = None
    health: str = "/health"
    env: dict[str, str] = field(default_factory=dict)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"


def build_engines() -> dict[str, Engine]:
    fish_ckpt = CACHE / "fish-s2-pro"

    def worker(venv: str, script: str, port: int) -> list[str]:
        return [str(VENVS / venv / "bin" / "python"), str(WORKERS / script), "--port", str(port)]

    engines = [
        Engine("qwen3-tts", "Qwen3-TTS", 9101, worker("qwen", "qwen_worker.py", 9101)),
        Engine("chatterbox", "Chatterbox", 9102, worker("chatterbox", "chatterbox_worker.py", 9102)),
        Engine("openvoice-v2", "OpenVoice v2", 9103, worker("openvoice", "openvoice_worker.py", 9103)),
        Engine("fish-s2-pro", "Fish Audio S2 Pro", 9104, [
            str(VENVS / "fish" / "bin" / "python"), "tools/api_server.py", "--listen", "127.0.0.1:9104",
            "--llama-checkpoint-path", str(fish_ckpt), "--decoder-checkpoint-path", str(fish_ckpt / "codec.pth"),
            "--decoder-config-name", "modded_dac_vq",
        ], cwd=FISH_REPO, health="/v1/health"),
    ]
    if os.environ.get("VOICE_CLONE_FP16") == "1":  # GPUs without bfloat16 (T4)
        engines[3].command.append("--half")
    return {e.key: e for e in engines}


def split_text(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Sentence groups of at most ~limit characters (longer sentences are split at commas or spaces)."""
    sentences = [s.strip() for s in re.split(r"(?<=[。！？])|(?<=[.!?…])\s+|\n+", text.strip()) if s and s.strip()]
    pieces: list[str] = []
    for sentence in sentences:
        while len(sentence) > limit:
            cut = max(sentence.rfind(sep, 0, limit) for sep in (",", ";", "，", "、", " "))
            cut = cut + 1 if cut > limit // 3 else limit
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        if sentence:
            pieces.append(sentence)
    chunks: list[str] = []
    for piece in pieces:
        if chunks and len(chunks[-1]) + 1 + len(piece) <= limit:
            chunks[-1] += " " + piece
        else:
            chunks.append(piece)
    return chunks


def join_wavs(parts: list[bytes], pause_ms: int) -> bytes:
    """Concatenates same-format PCM WAV files, with pause_ms of silence between them."""
    out, params, silence = io.BytesIO(), None, b""
    with wave.open(out, "wb") as writer:
        for i, data in enumerate(parts):
            with wave.open(io.BytesIO(data), "rb") as reader:
                if params is None:
                    params = reader.getparams()
                    writer.setparams(params)
                    frame = params.sampwidth * params.nchannels
                    silence = b"\0" * (int(params.framerate * pause_ms / 1000) * frame)
                elif reader.getparams()[:3] != params[:3]:
                    raise ValueError("Engine returned audio in inconsistent formats")
                if i and silence:
                    writer.writeframes(silence)
                writer.writeframes(reader.readframes(reader.getnframes()))
    return out.getvalue()


class NotReady(RuntimeError):
    pass


class EngineManager:
    def __init__(self, engines: dict[str, Engine], load_timeout: float = LOAD_TIMEOUT):
        self.engines = engines
        self.load_timeout = load_timeout
        self.states = {key: "stopped" for key in engines}
        self.errors: dict[str, str] = {}
        self._gpu = asyncio.Lock()  # one load or synthesis on the GPU at a time
        self._proc: asyncio.subprocess.Process | None = None
        self._current: str | None = None
        self._tasks: set[asyncio.Task] = set()
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(600, connect=10))

    async def aclose(self) -> None:
        for task in self._tasks:
            task.cancel()
        await self._stop()
        await self._http.aclose()

    def start(self, key: str) -> str:
        if self.states[key] in {"loading", "ready"}:
            return self.states[key]
        self.states[key] = "loading"
        self.errors.pop(key, None)
        task = asyncio.create_task(self._load(key))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return "loading"

    async def _stop(self) -> None:
        proc, self._proc = self._proc, None
        if self._current is not None:
            self.states[self._current] = "stopped"
            self._current = None
        if proc is not None and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), 30)
            except TimeoutError:
                proc.kill()
                await proc.wait()

    async def _prepare(self, engine: Engine) -> None:
        if engine.key != "fish-s2-pro" or (CACHE / "fish-s2-pro" / "codec.pth").exists():
            return
        from huggingface_hub import snapshot_download

        log.info("Downloading %s", FISH_REPO_ID)
        await asyncio.to_thread(snapshot_download, FISH_REPO_ID, local_dir=str(CACHE / "fish-s2-pro"))

    async def _load(self, key: str) -> None:
        engine = self.engines[key]
        async with self._gpu:
            try:
                await self._stop()
                await self._prepare(engine)
                env = {**os.environ, **engine.env, "HF_HOME": os.environ.get("HF_HOME", str(CACHE / "hf"))}
                self._proc = await asyncio.create_subprocess_exec(*engine.command, cwd=engine.cwd, env=env)
                loop = asyncio.get_running_loop()
                deadline = loop.time() + self.load_timeout
                while True:
                    if self._proc.returncode is not None:
                        raise RuntimeError(f"{engine.name} exited with code {self._proc.returncode}")
                    try:
                        if (await self._http.get(engine.url + engine.health, timeout=5)).is_success:
                            break
                    except httpx.HTTPError:
                        pass
                    if loop.time() > deadline:
                        raise TimeoutError(f"{engine.name} did not start within {self.load_timeout:.0f} s")
                    await asyncio.sleep(3)
                self._current, self.states[key] = key, "ready"
                log.info("%s ready", engine.name)
            except Exception as exc:
                log.exception("Loading %s failed", engine.name)
                await self._stop()
                self.states[key], self.errors[key] = "error", str(exc)

    async def _synthesize_chunk(self, engine: Engine, text: str, language: str, ref_text: str,
                                reference: bytes) -> bytes:
        if engine.key == "fish-s2-pro":
            import ormsgpack

            body = ormsgpack.packb({
                "text": text, "format": "wav", "chunk_length": 200, "normalize": True,
                "references": [{"audio": reference, "text": ref_text}],
            })
            response = await self._http.post(engine.url + "/v1/tts", content=body,
                                             headers={"content-type": "application/msgpack"})
        else:
            response = await self._http.post(
                engine.url + "/synthesize", data={"text": text, "language": language, "ref_text": ref_text},
                files={"reference": ("reference.wav", reference, "audio/wav")},
            )
        if not response.is_success:
            raise RuntimeError(f"{engine.name} failed (HTTP {response.status_code}): {response.text[:300]}")
        return response.content

    async def synthesize(self, key: str, text: str, language: str, ref_text: str, reference: bytes,
                         pause_ms: int) -> bytes:
        engine = self.engines[key]
        async with self._gpu:
            if self._current != key or self._proc is None or self._proc.returncode is not None:
                self.states[key] = "stopped"
                raise NotReady(f"{engine.name} is not loaded")
            parts = [await self._synthesize_chunk(engine, chunk, language, ref_text, reference)
                     for chunk in split_text(text)]
        if not parts:
            raise ValueError("The text has nothing to speak")
        return join_wavs(parts, pause_ms)


def create_app(manager: EngineManager | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.manager = manager or EngineManager(build_engines())
        yield
        await app.state.manager.aclose()

    app = FastAPI(title="Voice clone service", lifespan=lifespan)

    def require_key(x_api_key: str | None = Header(default=None)) -> None:
        if API_KEY and not (x_api_key and secrets.compare_digest(x_api_key, API_KEY)):
            raise HTTPException(401, "Missing or invalid API key")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    @app.get("/v1/models", dependencies=[Depends(require_key)])
    async def list_models():
        m: EngineManager = app.state.manager
        return [{"key": k, "state": m.states[k], "error": m.errors.get(k)} for k in m.engines]

    @app.post("/v1/models/{key}/start", status_code=202, dependencies=[Depends(require_key)])
    async def start_model(key: str):
        m: EngineManager = app.state.manager
        if key not in m.engines:
            raise HTTPException(404, f"Unknown model {key}")
        return {"key": key, "state": m.start(key)}

    @app.get("/v1/models/{key}", dependencies=[Depends(require_key)])
    async def model_status(key: str):
        m: EngineManager = app.state.manager
        if key not in m.engines:
            raise HTTPException(404, f"Unknown model {key}")
        return {"key": key, "state": m.states[key], "error": m.errors.get(key)}

    @app.post("/v1/synthesize", dependencies=[Depends(require_key)])
    async def synthesize(model: str = Form(...), text: str = Form(...), language: str = Form("en-US"),
                         ref_text: str = Form(""), pause_ms: int = Form(250), reference: UploadFile = File(...)):
        m: EngineManager = app.state.manager
        if model not in m.engines:
            raise HTTPException(404, f"Unknown model {model}")
        if not text.strip() or len(text) > MAX_TEXT_CHARS:
            raise HTTPException(422, f"Text must contain 1-{MAX_TEXT_CHARS} characters")
        sample = await reference.read()
        if not sample.startswith(b"RIFF"):
            raise HTTPException(422, "The reference must be a WAV file")
        try:
            audio = await m.synthesize(model, text, language, ref_text.strip(), sample, min(max(pause_ms, 0), 2000))
        except NotReady as exc:
            raise HTTPException(409, str(exc)) from None
        except (RuntimeError, ValueError, httpx.HTTPError) as exc:
            log.exception("Synthesis failed")
            raise HTTPException(500, str(exc)) from None
        return Response(audio, media_type="audio/wav")

    return app


app = create_app()
