from __future__ import annotations

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.security import APIKeyHeader, APIKeyQuery

from .config import Settings
from .jobs import JobManager
from .schemas import JobState, VideoRequest
from .storage import LocalArtifactStore, read_json
from .video_models import VIDEO_MODELS
from .workflow import FINAL_VIDEO, PipelineDeps, build_video_workflow

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


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
                            progress=manager.progress)
        return build_video_workflow(deps)

    async def close():
        await comfy.aclose()
        await store.aclose()
        await async_credential.close()

    return store, workflow_factory, close


def create_app(settings: Settings | None = None, services=None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store, workflow_factory, close = services or create_services(settings)
        app.state.jobs = JobManager(settings, store, workflow_factory)
        app.state.store = store
        resume_loop = asyncio.create_task(app.state.jobs.resume_forever())
        yield
        resume_loop.cancel()
        await app.state.jobs.shutdown()
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
