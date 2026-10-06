from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.security import APIKeyHeader, APIKeyQuery

from .config import Settings
from .gpu import GpuMonitor
from .jobs import JobManager
from .operations import Operation
from .schemas import JobState, VideoRequest
from .storage import LocalArtifactStore, read_json
from .video_models import VIDEO_MODELS
from .workflow import FINAL_VIDEO, PipelineDeps, build_video_workflow

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
SSE_POLL_SECONDS = 2.0
SSE_KEEPALIVE_SECONDS = 15.0


def sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def job_events(manager: JobManager, job_id: str, poll_seconds: float = SSE_POLL_SECONDS,
                     keepalive_seconds: float = SSE_KEEPALIVE_SECONDS) -> AsyncIterator[str]:
    """Server-Sent Events of one job: a snapshot, then live 'state' and 'op' updates, then 'end'.

    Jobs running in this process are streamed from in-memory notifications. Jobs owned by another
    replica (or not started yet) are followed by re-reading their state and operations from the store.
    """
    queue = manager.subscribe(job_id)
    try:
        state = await manager.get(job_id)
        if state is None:
            return
        sent_state = state.model_dump(mode="json")
        sent_ops = {o.id: o.model_dump(mode="json") for o in await manager.operations(job_id)}
        yield sse("state", sent_state)
        for op in sent_ops.values():
            yield sse("op", op)
        last_sent = time.monotonic()

        async def changed_ops() -> list[str]:
            """Operations that changed in the store (the job runs elsewhere, or not yet / any more here)."""
            if manager.is_running_here(job_id):
                return []  # live notifications already cover them
            events = []
            for op in await manager.operations(job_id):
                if (dump := op.model_dump(mode="json")) != sent_ops.get(op.id):
                    sent_ops[op.id] = dump
                    events.append(sse("op", dump))
            return events

        while True:
            # A queued local task (e.g. a retry or a resume waiting for a slot) keeps the stream open.
            if state.is_finished and not manager.is_active(job_id):
                for event in await changed_ops():
                    yield event
                yield sse("end", None)
                return
            try:
                event, data = await asyncio.wait_for(queue.get(), timeout=poll_seconds)
            except TimeoutError:
                state = await manager.get(job_id)
                if state is None:
                    return
                if (current := state.model_dump(mode="json")) != sent_state:
                    sent_state = current
                    yield sse("state", current)
                    last_sent = time.monotonic()
                for event in await changed_ops():
                    yield event
                    last_sent = time.monotonic()
                if time.monotonic() - last_sent >= keepalive_seconds:
                    yield ": keep-alive\n\n"
                    last_sent = time.monotonic()
                continue
            if event == "end":
                yield sse("end", None)
                return
            if event == "state":
                sent_state = data
                state = JobState.model_validate(data)
            elif event == "op":
                sent_ops[data["id"]] = data
            yield sse(event, data)
            last_sent = time.monotonic()
    finally:
        manager.unsubscribe(job_id, queue)


def create_services(settings: Settings):
    """Wires the Azure clients. Uses managed identity in Azure and your az login locally."""
    from agent_framework.foundry import FoundryChatClient
    from azure.identity import DefaultAzureCredential
    from azure.identity.aio import DefaultAzureCredential as AsyncDefaultAzureCredential

    from .agents import FoundryCreativeTeam
    from .comfyui import ComfyUIPool
    from .speech import Narrator
    from .storage import BlobArtifactStore

    async_credential = AsyncDefaultAzureCredential()
    if settings.storage_account_url:
        store = BlobArtifactStore(settings.storage_account_url, settings.storage_container, async_credential)
    else:
        store = LocalArtifactStore(settings.local_output_dir)

    chat_client = FoundryChatClient(
        project_endpoint=settings.foundry_project_endpoint,
        model=settings.foundry_model,
        credential=async_credential,
    )
    narrator = (
        Narrator(settings.speech_endpoint, DefaultAzureCredential(), settings.tts_voice)
        if settings.speech_endpoint
        else None
    )
    comfy = ComfyUIPool.from_urls(settings.comfyui_urls)
    team = FoundryCreativeTeam(chat_client)

    def workflow_factory(manager: JobManager):
        deps = PipelineDeps(settings=settings, team=team, comfy=comfy, narrator=narrator, store=store,
                            progress=manager.progress, ops=manager.recorder)
        return build_video_workflow(deps)

    async def close():
        await comfy.aclose()
        await store.aclose()
        await async_credential.close()

    return store, workflow_factory, close


def create_app(settings: Settings | None = None, services=None, gpu_monitor: GpuMonitor | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store, workflow_factory, close = services or create_services(settings)
        app.state.jobs = JobManager(settings, store, workflow_factory)
        app.state.store = store
        app.state.gpu = gpu_monitor or GpuMonitor(settings.gpu_stats_urls)
        resume_loop = asyncio.create_task(app.state.jobs.resume_forever())
        yield
        resume_loop.cancel()
        await app.state.jobs.shutdown()
        await app.state.gpu.aclose()
        await close()

    app = FastAPI(title="AI Video Platform", version="1.0.0", lifespan=lifespan)
    api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
    api_key_query = APIKeyQuery(name="key", auto_error=False)

    def require_api_key(
        key: str | None = Depends(api_key_header), query_key: str | None = Depends(api_key_query)
    ) -> None:
        key = key or query_key  # the query string lets <video src> and download links work in a browser
        if settings.api_key and not (key and secrets.compare_digest(key, settings.api_key)):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing or invalid API key")

    def jobs(request: Request) -> JobManager:
        return request.app.state.jobs

    @app.get("/healthz", include_in_schema=False)
    async def healthz():
        return {"status": "ok"}

    @app.get("/", include_in_schema=False)
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/models", dependencies=[Depends(require_api_key)])
    async def list_models():
        return [
            {"key": m.key, "name": m.display_name, "clip_seconds": round(m.clip_seconds, 2),
             "resolution": f"{m.width}x{m.height}", "native_audio": m.has_audio, "license": m.license_note,
             "default": m.key == settings.default_video_model}
            for m in VIDEO_MODELS.values()
        ]

    @app.get("/api/gpu", dependencies=[Depends(require_api_key)])
    async def gpu_stats(request: Request):
        return await request.app.state.gpu.snapshot()

    @app.post("/api/videos", status_code=status.HTTP_202_ACCEPTED, response_model=JobState,
              dependencies=[Depends(require_api_key)])
    async def create_video(body: VideoRequest, request: Request):
        key = body.video_model or settings.default_video_model
        if key not in VIDEO_MODELS:
            raise HTTPException(422,
                                f"Unknown video_model '{key}'. Choose one of: {', '.join(VIDEO_MODELS)}")
        return await jobs(request).create(body.model_copy(update={"video_model": key}))

    @app.get("/api/videos", response_model=list[JobState], dependencies=[Depends(require_api_key)])
    async def list_videos(request: Request):
        return await jobs(request).list()

    @app.get("/api/videos/{job_id}", response_model=JobState, dependencies=[Depends(require_api_key)])
    async def get_video(job_id: str, request: Request):
        state = await jobs(request).get(job_id)
        if state is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown video job")
        return state

    @app.get("/api/videos/{job_id}/storyboard", dependencies=[Depends(require_api_key)])
    async def get_storyboard(job_id: str, request: Request):
        storyboard = await read_json(request.app.state.store, job_id, "storyboard.json")
        if storyboard is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Storyboard not ready yet")
        return storyboard

    @app.get("/api/videos/{job_id}/operations", response_model=list[Operation],
             dependencies=[Depends(require_api_key)])
    async def get_operations(job_id: str, request: Request):
        if await jobs(request).get(job_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown video job")
        return await jobs(request).operations(job_id)

    @app.get("/api/videos/{job_id}/events", dependencies=[Depends(require_api_key)])
    async def stream_events(job_id: str, request: Request):
        if await jobs(request).get(job_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown video job")
        return StreamingResponse(job_events(jobs(request), job_id), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/videos/{job_id}/retry", response_model=JobState, dependencies=[Depends(require_api_key)])
    async def retry_video(job_id: str, request: Request):
        state = await jobs(request).get(job_id)
        if state is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown video job")
        if state.status != "failed":
            raise HTTPException(status.HTTP_409_CONFLICT, f"Only failed jobs can be retried (status: {state.status})")
        return await jobs(request).retry(job_id)

    @app.get("/api/videos/{job_id}/download", dependencies=[Depends(require_api_key)])
    async def download_video(job_id: str, request: Request):
        state = await jobs(request).get(job_id)
        if state is None or state.status != "completed":
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Video not ready")
        store = request.app.state.store
        if isinstance(store, LocalArtifactStore):
            return FileResponse(store.path(job_id, FINAL_VIDEO), media_type="video/mp4",
                                filename=f"{job_id}.mp4")
        url = await store.download_url(job_id, FINAL_VIDEO)
        return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

    return app
