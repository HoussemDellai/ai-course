from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.security import APIKeyHeader, APIKeyQuery
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile

from .config import Settings
from .gpu import GpuMonitor
from .images import ImageError, sanitize_image
from .jobs import JobManager, ReviewConflict
from .education import build_educational_workflow, validate_education_request
from .education_schemas import DraftRevision, DraftUpdate, EducationalDraft
from .documents import (
    DocumentError, DocumentUpload, FoundryDocumentTeam, build_document_workflow,
    office_available, validate_document, validate_document_request,
)
from .operations import Operation
from .schemas import JobState, VideoRequest
from .storage import LocalArtifactStore, read_json
from .video_models import VIDEO_MODELS
from .workflow import FINAL_VIDEO, REFERENCE_IMAGE, PipelineDeps, build_video_workflow, keyframe_name

log = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"
SSE_POLL_SECONDS = 2.0
SSE_KEEPALIVE_SECONDS = 15.0
MULTIPART_OVERHEAD_BYTES = 1024 * 1024  # room for the 'request' JSON field and multipart boundaries
# The only job files /media serves: generated, upscaled and processed shots, assembled scenes and their mixes, and
# the final video. A strict allowlist, so a name can never reach state.json, the reference photo or another job.
MEDIA_NAME = re.compile(r"(?:(?:clips|upscaled|processed)/shot_\d{3}|scenes/scene_\d{3}(?:_voice|_music)?|final)\.mp4")
EDUCATION_ARTIFACT = re.compile(
    r"(?:sources\.txt|render/[a-f0-9]{64}/(?:images/scene_\d{3}\.(?:png|png\.metadata\.json|drawio)|"
    r"(?:processed|scenes)/scene_\d{3}\.mp4|timing\.json))"
)

CREATE_VIDEO_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {"schema": {"$ref": "#/components/schemas/VideoRequest"}},
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["request"],
                    "properties": {
                        "request": {"type": "string", "description": "VideoRequest as a JSON string"},
                        "image": {"type": "string", "format": "binary",
                                  "description": "Optional reference photo (PNG, JPEG or WebP) of a person or a scene"},
                    },
                }
            },
        },
    }
}

CREATE_DOCUMENT_OPENAPI = {
    "requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {
        "type": "object", "required": ["request", "document"],
        "properties": {
            "request": {"type": "string", "description": "VideoRequest JSON with use_case=document"},
            "document": {"type": "string", "format": "binary", "description": "PowerPoint (.pptx) or PDF (.pdf)"},
        },
    }}}},
}


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
            if (state.is_finished or state.status == "awaiting_review") and not manager.is_active(job_id):
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
    from .education_agents import FoundryEducationTeam
    from .education_visuals import EducationalVisuals
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
    clients = {settings.foundry_model: chat_client}

    def education_client(model: str) -> FoundryChatClient:
        if model not in clients:
            clients[model] = FoundryChatClient(
                project_endpoint=settings.foundry_project_endpoint, model=model, credential=async_credential,
            )
        return clients[model]

    education_team = FoundryEducationTeam(settings, education_client)
    visuals = EducationalVisuals(settings, comfy, async_credential)

    def workflow_factory(manager: JobManager):
        deps = PipelineDeps(settings=settings, team=team, comfy=comfy, narrator=narrator, store=store,
                            progress=manager.progress, ops=manager.recorder)
        cinematic = build_video_workflow(deps)
        educational = build_educational_workflow(deps, education_team, visuals)
        document = build_document_workflow(deps, FoundryDocumentTeam(chat_client))

        class UseCaseWorkflow:
            async def run(self, job):
                workflow = {"educational": educational, "document": document}.get(job.request.use_case, cinematic)
                return await workflow.run(job)

        return UseCaseWorkflow()

    async def close():
        await visuals.aclose()
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
             "resolution": f"{m.width}x{m.height}", "vertical_resolution": f"{m.height}x{m.width}",
             "native_audio": m.has_audio, "license": m.license_note,
             "default": m.key == settings.default_video_model}
            for m in VIDEO_MODELS.values()
        ]

    @app.get("/api/config", dependencies=[Depends(require_api_key)])
    async def get_config():
        return {"max_image_mb": settings.max_image_mb, "document": {
            "max_document_mb": settings.max_document_mb, "max_pages": 60,
            "pdf_configured": True, "powerpoint_configured": office_available(settings),
            "narration_configured": bool(settings.speech_endpoint),
        }, "education": {
            "text_models": list(dict.fromkeys([settings.foundry_model, *settings.education_text_models])),
            "search_configured": bool(settings.education_search_model),
            "images": {"comfyui": bool(settings.comfy_image_workflow),
                       "foundry": bool(settings.foundry_image_endpoint and settings.foundry_image_model)},
            "motion": {"comfyui": True,
                       "foundry": bool(settings.foundry_video_endpoint and settings.foundry_video_model)},
            "diagrams_configured": bool(settings.drawio_mcp_url and settings.drawio_export_command),
            "narration_configured": bool(settings.speech_endpoint),
        }}

    @app.get("/api/gpu", dependencies=[Depends(require_api_key)])
    async def gpu_stats(request: Request):
        return await request.app.state.gpu.snapshot()

    @app.post("/api/videos", status_code=status.HTTP_202_ACCEPTED, response_model=JobState,
              dependencies=[Depends(require_api_key)], openapi_extra=CREATE_VIDEO_OPENAPI)
    async def create_video(request: Request):
        """JSON body (text-to-video), or multipart with a 'request' JSON field and an optional 'image' photo."""
        return await submit_video(request)

    @app.post("/api/videos/document", status_code=status.HTTP_202_ACCEPTED, response_model=JobState,
              dependencies=[Depends(require_api_key)], openapi_extra=CREATE_DOCUMENT_OPENAPI)
    async def create_document_video(request: Request):
        """Multipart document-to-video creation, with independent document upload limits."""
        return await submit_video(request, document_mode=True)

    async def submit_video(request: Request, document_mode: bool = False):
        image: bytes | None = None
        document: DocumentUpload | None = None
        content_type = request.headers.get("content-type", "")
        try:
            if content_type.startswith("multipart/form-data"):
                body, image, document = await read_multipart(request, document_mode)
            else:
                if document_mode:
                    raise HTTPException(422, "Document videos require multipart 'request' and 'document' fields")
                body = VideoRequest.model_validate_json(await request.body())
        except ValidationError as e:
            raise RequestValidationError(e.errors(include_url=False)) from None
        if (body.use_case == "document") != document_mode:
            raise HTTPException(422, "Use multipart POST /api/videos/document with use_case=document for document uploads")
        try:
            validate_document_request(body, settings)
        except DocumentError as e:
            raise HTTPException(e.status_code, str(e)) from None
        if body.use_case == "educational":
            if image is not None:
                raise HTTPException(422, "Educational videos do not accept reference photos")
            try:
                validate_education_request(body, settings)
            except ValueError as e:
                raise HTTPException(422, str(e)) from None
        key = body.video_model or settings.default_video_model
        if key not in VIDEO_MODELS:
            raise HTTPException(422,
                                f"Unknown video_model '{key}'. Choose one of: {', '.join(VIDEO_MODELS)}")
        try:
            return await jobs(request).create(body.model_copy(update={"video_model": key}),
                                               image=image, document=document)
        except DocumentError as e:
            raise HTTPException(e.status_code, str(e)) from None

    async def read_multipart(request: Request, document_mode: bool = False
                             ) -> tuple[VideoRequest, bytes | None, DocumentUpload | None]:
        max_bytes = settings.max_document_bytes if document_mode else settings.max_image_bytes
        max_mb = settings.max_document_mb if document_mode else settings.max_image_mb
        label = "document" if document_mode else "image"
        limit = max_bytes + MULTIPART_OVERHEAD_BYTES
        too_large = HTTPException(status.HTTP_413_CONTENT_TOO_LARGE,
                                  f"The {label} is larger than {max_mb} MB")
        if int(request.headers.get("content-length") or 0) > limit:
            raise too_large
        # Count the bytes ourselves: chunked uploads have no Content-Length, and Starlette's form parser
        # doesn't cap file sizes. The capped body is cached on the request, so form() parses it from memory.
        chunks, size = [], 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > limit:
                raise too_large
            chunks.append(chunk)
        request._body = b"".join(chunks)
        async with request.form(max_files=2, max_fields=4) as form:
            if any(name not in {"request", label} for name in form):
                raise HTTPException(422, f"Only 'request' and '{label}' form fields are supported")
            if any(len(form.getlist(name)) != 1 for name in form):
                raise HTTPException(422, "Duplicate form fields are not supported")
            raw = form.get("request")
            if not isinstance(raw, str):
                raise HTTPException(422, "Missing 'request' form field (the VideoRequest as JSON)")
            body = VideoRequest.model_validate_json(raw)
            upload = form.get(label)
            if upload is None or (isinstance(upload, UploadFile) and not upload.filename and upload.size == 0):
                if document_mode:
                    raise HTTPException(422, "Missing 'document' file")
                return body, None, None
            if not isinstance(upload, UploadFile):
                raise HTTPException(422, f"'{label}' must be a file")
            data = await upload.read(max_bytes + 1)
            filename = upload.filename or ""
        if document_mode:
            try:
                document = await run_in_threadpool(validate_document, data, filename, max_bytes)
                return body, None, document
            except DocumentError as e:
                raise HTTPException(e.status_code, str(e)) from None
        try:
            return body, await run_in_threadpool(sanitize_image, data, settings.max_image_bytes), None
        except ImageError as e:
            raise HTTPException(e.status_code, str(e)) from None

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
        draft = await jobs(request).draft(job_id)
        if draft is not None:
            return draft.model_dump(mode="json")
        state = await jobs(request).get(job_id)
        if state is not None and state.request.use_case == "document":
            script = await read_json(request.app.state.store, job_id, "document/script.json")
            if script is None:
                raise HTTPException(404, "Document narration script not ready yet")
            return script
        storyboard = await read_json(request.app.state.store, job_id, "storyboard.narrated.json")
        if storyboard is None:
            storyboard = await read_json(request.app.state.store, job_id, "storyboard.json")
        if storyboard is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Storyboard not ready yet")
        return storyboard

    @app.get("/api/videos/{job_id}/draft", response_model=EducationalDraft,
             dependencies=[Depends(require_api_key)])
    async def get_draft(job_id: str, request: Request):
        draft = await jobs(request).draft(job_id)
        if draft is None:
            raise HTTPException(404, "Educational draft not ready")
        return draft

    async def review_action(job_id: str, request: Request, revision: int, action: str,
                            update: DraftUpdate | None = None):
        if await jobs(request).get(job_id) is None:
            raise HTTPException(404, "Unknown video job")
        try:
            return await jobs(request).review(job_id, revision, action=action, update=update)
        except ReviewConflict as e:
            raise HTTPException(409, str(e)) from None
        except ValidationError as e:
            raise RequestValidationError(e.errors(include_url=False)) from None
        except ValueError as e:
            raise HTTPException(422, str(e)) from None

    @app.put("/api/videos/{job_id}/draft", response_model=JobState, dependencies=[Depends(require_api_key)])
    async def update_draft(job_id: str, body: DraftUpdate, request: Request):
        return await review_action(job_id, request, body.revision, "update", body)

    @app.post("/api/videos/{job_id}/approve", response_model=JobState, dependencies=[Depends(require_api_key)])
    async def approve_draft(job_id: str, body: DraftRevision, request: Request):
        return await review_action(job_id, request, body.revision, "approve")

    @app.post("/api/videos/{job_id}/regenerate", response_model=JobState, dependencies=[Depends(require_api_key)])
    async def regenerate_draft(job_id: str, body: DraftRevision, request: Request):
        return await review_action(job_id, request, body.revision, "regenerate")

    @app.get("/api/videos/{job_id}/education/{name:path}", dependencies=[Depends(require_api_key)])
    async def education_artifact(job_id: str, name: str, request: Request):
        state = await jobs(request).get(job_id)
        if state is None or state.request.use_case != "educational" or not EDUCATION_ARTIFACT.fullmatch(name):
            raise HTTPException(404, "Unknown educational artifact")
        content_type = {
            ".png": "image/png", ".mp4": "video/mp4", ".drawio": "application/xml",
            ".txt": "text/plain", ".json": "application/json",
        }[Path(name).suffix]
        return await serve_artifact(request, job_id, f"education/{name}", content_type,
                                    filename=Path(name).name if name.endswith((".drawio", ".txt")) else None)

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
        return await serve_artifact(request, job_id, FINAL_VIDEO, "video/mp4", filename=f"{job_id}.mp4")

    @app.get("/api/videos/{job_id}/image", dependencies=[Depends(require_api_key)])
    async def get_reference_image(job_id: str, request: Request):
        state = await jobs(request).get(job_id)
        if state is None or not state.request.reference_image:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "This video has no reference photo")
        return await serve_artifact(request, job_id, REFERENCE_IMAGE, "image/png", cache=True)

    @app.get("/api/videos/{job_id}/keyframes/{shot}", dependencies=[Depends(require_api_key)])
    async def get_keyframe(job_id: str, shot: int, request: Request):
        state = await jobs(request).get(job_id)
        if state is None or not state.request.reference_image or shot < 0:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown keyframe")
        return await serve_artifact(request, job_id, keyframe_name(shot), "image/png", cache=True)

    @app.get("/api/videos/{job_id}/media/{name:path}", dependencies=[Depends(require_api_key)])
    async def get_media(job_id: str, name: str, request: Request):
        """Intermediate and final videos of a job, as soon as they exist (supports Range requests for seeking)."""
        if not MEDIA_NAME.fullmatch(name) or await jobs(request).get(job_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown media")
        # The UI adds ?v=<operation id>, so a file re-rendered by a later run gets a new URL.
        return await serve_artifact(request, job_id, name, "video/mp4", cache=True)

    async def serve_artifact(request: Request, job_id: str, name: str, media_type: str,
                             filename: str | None = None, cache: bool = False):
        # Photos and keyframes never change once written: let the browser keep them (and the redirect to the
        # short-lived SAS URL, valid 2 h) instead of fetching them again on every live update of the timeline.
        headers = {"Cache-Control": "private, max-age=3600"} if cache else None
        store = request.app.state.store
        if isinstance(store, LocalArtifactStore):
            path = store.path(job_id, name)
            if not path.exists():
                raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
            return FileResponse(path, media_type=media_type, filename=filename, headers=headers)
        if not await store.exists(job_id, name):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
        url = await store.download_url(job_id, name)
        return RedirectResponse(url, status_code=status.HTTP_307_TEMPORARY_REDIRECT, headers=headers)

    return app
