from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import shutil
import uuid
from collections.abc import Callable
from typing import Protocol

from agent_framework import WorkflowRunResult

from .education import APPROVAL, DRAFT, draft_fingerprint, validate_education_request
from .education_schemas import DraftUpdate, EducationalDraft, ReviewResult
from .config import Settings
from .documents import DocumentError, DocumentUpload, office_available, validate_document_request
from .document_schemas import DocumentOptions
from .operations import Operation, OperationRecorder, format_error, install_log_capture, load_operations
from .schemas import (
    BatchMembership, JobState, JobStatus, VideoBatchRequest, VideoBatchState, VideoRequest, utcnow,
)
from .storage import LEASE_SECONDS, ArtifactStore, JobLock, read_json, write_json
from .voice_clone import VOICE_SAMPLE, clones_sample, validate_voice_clone_request
from .video_models import VIDEO_MODELS
from .workflow import REFERENCE_IMAGE, VideoResult, new_video_job

log = logging.getLogger(__name__)


class WorkflowRunner(Protocol):
    async def run(self, job) -> WorkflowRunResult: ...


class ReviewConflict(ValueError):
    pass


class JobManager:
    """Runs video workflows as background tasks and persists their state in the artifact store.

    Each running job holds a renewable lease in the store, so when Container Apps briefly runs two
    replicas (e.g. during a revision rollout) a job is never executed twice.
    """

    def __init__(self, settings: Settings, store: ArtifactStore,
                 workflow_factory: Callable[[JobManager], WorkflowRunner]):
        self.settings = settings
        self.store = store
        self._workflow_factory = workflow_factory
        self._slots = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._tasks: dict[str, asyncio.Task] = {}
        self._states: dict[str, JobState] = {}
        self._state_lock = asyncio.Lock()
        self._recorders: dict[str, OperationRecorder] = {}
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        self._batch_locks: dict[str, asyncio.Lock] = {}
        install_log_capture()

    async def create(self, request: VideoRequest, image: bytes | None = None,
                     document: DocumentUpload | None = None, voice_sample: bytes | None = None) -> JobState:
        """Starts a job with a sanitized image or validated document, persisted before the job state."""
        request = self._prepare_request(request, image, document, voice_sample)
        state = JobState(id=uuid.uuid4().hex[:12], request=request)
        await self._upload_inputs(state, image, document, voice_sample)
        await self._save(state)
        self._start(state.id)
        return state

    def _prepare_request(self, request: VideoRequest, image: bytes | None,
                         document: DocumentUpload | None, voice_sample: bytes | None) -> VideoRequest:
        validate_voice_clone_request(request, self.settings, voice_sample is not None)
        key = request.video_model or self.settings.default_video_model
        if key not in VIDEO_MODELS:
            raise ValueError(f"Unknown video_model '{key}'. Choose one of: {', '.join(VIDEO_MODELS)}")
        if request.use_case == "educational" and image is not None:
            raise ValueError("Educational videos do not accept reference photos")
        validate_education_request(request, self.settings)
        validate_document_request(request, self.settings)
        if request.use_case == "document":
            if document is None or image is not None:
                raise DocumentError("Document videos require one document upload and do not accept reference photos")
            if document.key.endswith(".pptx") and not office_available(self.settings):
                raise DocumentError("PowerPoint rendering requires LibreOffice; install it or configure LIBREOFFICE_PATH")
            options = request.document or DocumentOptions()
            request = request.model_copy(update={"document": options.model_copy(update={"filename": document.filename})})
        elif document is not None:
            raise DocumentError("Document uploads require the document use case")
        if request.seed is None:
            request = request.model_copy(update={"seed": random.randint(0, 2**40)})
        return request.model_copy(update={"reference_image": image is not None, "video_model": key,
                                          "voice_sample": voice_sample is not None})

    async def _upload_inputs(self, state: JobState, image: bytes | None,
                             document: DocumentUpload | None, voice_sample: bytes | None) -> None:
        if voice_sample is not None:
            local = self.settings.work_dir / state.id / VOICE_SAMPLE
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(voice_sample)
            await self.store.upload(state.id, VOICE_SAMPLE, local)
        if document is not None:
            local = self.settings.work_dir / state.id / document.key
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(document.data)
            await self.store.upload(state.id, document.key, local)
        if image is not None:
            local = self.settings.work_dir / state.id / REFERENCE_IMAGE
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_bytes(image)
            await self.store.upload(state.id, REFERENCE_IMAGE, local)

    async def create_batch(self, batch: VideoBatchRequest, image: bytes | None = None,
                           document: DocumentUpload | None = None,
                           voice_sample: bytes | None = None) -> VideoBatchState:
        requests = batch.requests()
        if voice_sample is not None and not any(clones_sample(r) for r in requests):
            raise ValueError("A voice sample requires at least one voice-cloning variant")
        # Validate every variant before persisting or starting any of them.
        requests = [self._prepare_request(r, image, document, voice_sample if clones_sample(r) else None)
                    for r in requests]
        seed = batch.request.seed if batch.request.seed is not None else random.randint(0, 2**40)
        concurrency = 1
        note = "Variants run sequentially in the listed order."
        if batch.execution == "auto":
            if any(r.voice_clone for r in requests):
                note = "Sequential: cloned voices share one GPU engine; overlapping models could evict each other."
            else:
                concurrency = min(self.settings.batch_parallel_capacity, len(requests))
                note = (f"Up to {concurrency} variants overlap on independent ComfyUI workers."
                        if concurrency > 1 else
                        "Sequential: parallel variants require distinct COMFYUI_URLS and MAX_CONCURRENT_JOBS > 1.")
        ids = [uuid.uuid4().hex[:12] for _ in requests]
        states = [
            JobState(id=job_id, request=r.model_copy(update={"seed": seed}),
                     batch=BatchMembership(id=ids[0], index=index, total=len(ids), concurrency=concurrency,
                                           previous_job_id=ids[index - concurrency] if index >= concurrency else None))
            for index, (job_id, r) in enumerate(zip(ids, requests))
        ]
        for state in states:
            await self._upload_inputs(state, image, document, voice_sample if clones_sample(state.request) else None)
        result = VideoBatchState(id=ids[0], execution=batch.execution, concurrency=concurrency,
                                 scheduling_note=note, jobs=states)
        # The manifest commits a complete set of inputs before any visible job can be resumed.
        await write_json(self.store, result.id, "batch.json", result.model_dump(mode="json"))
        for state in states:
            await self._save(state)
        for state in states:
            self._start(state.id)
        return result

    async def get_batch(self, batch_id: str) -> VideoBatchState | None:
        data = await read_json(self.store, batch_id, "batch.json")
        if data is None:
            return None
        batch = VideoBatchState.model_validate(data)
        batch.jobs = [await self.get(s.id) or s for s in batch.jobs]
        return batch

    async def get(self, job_id: str) -> JobState | None:
        # Only jobs running in this process are authoritative in memory; others may be owned by another replica.
        if job_id in self._tasks and job_id in self._states:
            return self._states[job_id]
        data = await read_json(self.store, job_id, "state.json")
        return JobState.model_validate(data) if data else None

    def is_active(self, job_id: str) -> bool:
        """True while this process runs (or queues) the job; otherwise its state comes from the store."""
        return job_id in self._tasks

    def is_running_here(self, job_id: str) -> bool:
        """True while this process executes the job (holds its lease): live operations are in memory."""
        return job_id in self._recorders

    def recorder(self, job_id: str) -> OperationRecorder:
        return self._recorders[job_id]

    async def operations(self, job_id: str) -> list[Operation]:
        if recorder := self._recorders.get(job_id):
            return recorder.snapshot()
        return await load_operations(self.store, job_id)

    def subscribe(self, job_id: str) -> asyncio.Queue:
        """Live (event, data) notifications of a job running in this process: 'state', 'op' and 'end'."""
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.setdefault(job_id, set()).add(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue) -> None:
        subscribers = self._subscribers.get(job_id)
        if subscribers is not None:
            subscribers.discard(queue)
            if not subscribers:
                del self._subscribers[job_id]

    def _publish(self, job_id: str, event: str, data: object) -> None:
        for queue in self._subscribers.get(job_id, ()):
            queue.put_nowait((event, data))

    async def list(self) -> list[JobState]:
        states = [s for s in [await self.get(j) for j in await self.store.list_jobs()] if s]
        return sorted(states, key=lambda s: s.created_at, reverse=True)

    async def retry(self, job_id: str) -> JobState | None:
        """Restarts a failed job: finished steps (brief, storyboard, clips, narration) are reused."""
        state = await self.get(job_id)
        if state is None or state.status != JobStatus.failed or job_id in self._tasks:
            return state
        self._start(job_id, from_failed=True)  # no await between the check and the start: atomic
        return state.model_copy(update={"status": JobStatus.queued, "error": None})

    async def resume_unfinished(self) -> None:
        states = await self.list()
        for state in states:
            if state.batch is not None and state.batch.index == 0:
                batch = await self.get_batch(state.batch.id)
                if batch is None:
                    raise RuntimeError(f"Missing manifest for batch {state.batch.id}")
                for sibling in batch.jobs:
                    if not await self.store.exists(sibling.id, "state.json"):
                        await self._save(sibling)
        for state in await self.list():
            if state.status == JobStatus.awaiting_review and not await self.store.exists(state.id, APPROVAL):
                continue
            if not state.is_finished and state.id not in self._tasks:
                self._start(state.id)

    async def draft(self, job_id: str) -> EducationalDraft | None:
        state = await self.get(job_id)
        if state is None or state.request.use_case != "educational":
            return None
        data = await read_json(self.store, job_id, DRAFT)
        return EducationalDraft.model_validate(data) if data is not None else None

    async def review(self, job_id: str, revision: int, *, update: DraftUpdate | None = None,
                     action: str = "approve") -> JobState:
        async with self._state_lock:
            if job_id in self._tasks:
                approved = await read_json(self.store, job_id, APPROVAL)
                if action == "approve" and update is None and approved is not None:
                    if approved["draft"]["revision"] == revision:
                        state = await self.get(job_id)
                        assert state is not None
                        return state
                raise ReviewConflict("The job is still running; wait for the review step to finish")
            lock = await self.store.try_lock(job_id)
            if lock is None:
                raise ReviewConflict("The job is being updated by another worker; retry")
            start = False
            try:
                data = await read_json(self.store, job_id, "state.json")
                if data is None:
                    raise ReviewConflict("Unknown video job")
                state = JobState.model_validate(data)
                draft = await self.draft(job_id)
                if draft is None or draft.revision != revision:
                    raise ReviewConflict("Draft revision changed; reload the review before editing or approving")
                approved = await read_json(self.store, job_id, APPROVAL)
                if approved is not None:
                    if action != "approve" or update is not None or approved["draft"]["revision"] != revision:
                        raise ReviewConflict("Approved content is immutable; create a new job to change it")
                    return state
                if state.status != JobStatus.awaiting_review:
                    raise ReviewConflict(f"Job is not awaiting review (status: {state.status.value})")
                if update is not None:
                    draft = EducationalDraft(
                        revision=revision + 1, brief=update.brief, scenes=update.scenes, research=draft.research,
                    )
                    await write_json(self.store, job_id, DRAFT, draft.model_dump(mode="json"))
                    state = state.model_copy(update={"draft_revision": draft.revision, "title": draft.brief.title,
                                                     "updated_at": utcnow()})
                elif action == "regenerate":
                    state = state.model_copy(update={"draft_revision": revision + 1, "status": JobStatus.queued,
                                                     "updated_at": utcnow()})
                    start = True
                elif action == "approve":
                    validate_education_request(state.request, self.settings)
                    if any(scene.diagram is not None for scene in draft.scenes) and not (
                        self.settings.drawio_mcp_url and self.settings.drawio_export_command
                    ):
                        raise ValueError("This storyboard contains technical diagrams. Configure DRAWIO_MCP_URL "
                                         "and DRAWIO_EXPORT_COMMAND before approval.")
                    job = new_video_job(job_id, state.request, self.settings)
                    await write_json(self.store, job_id, APPROVAL, {
                        "draft": draft.model_dump(mode="json"), "fingerprint": draft_fingerprint(draft, job),
                    })
                    state = state.model_copy(update={"status": JobStatus.queued, "updated_at": utcnow()})
                    start = True
                else:
                    raise ValueError(f"Unknown review action: {action}")
                await self._save(state)
            finally:
                await lock.release()
            self._publish(job_id, "state", state.model_dump(mode="json"))
            if start:
                self._start(job_id)
            return state

    async def resume_forever(self, interval: float = 60.0) -> None:
        """Picks up unfinished jobs whose owner died (its lease expires after LEASE_SECONDS)."""
        while True:
            try:
                await self.resume_unfinished()
            except Exception:
                log.exception("Resume loop failed")
            await asyncio.sleep(interval)

    async def progress(self, job_id: str, status: JobStatus | None = None, **fields) -> None:
        async with self._state_lock:
            state = self._states.get(job_id) or await self.get(job_id)
            if state is None:
                return
            update = dict(fields, updated_at=utcnow())
            if status is not None:
                update["status"] = status
            state = state.model_copy(update=update)
            await self._save(state)
        self._publish(job_id, "state", state.model_dump(mode="json"))

    async def wait(self, job_id: str) -> None:
        if task := self._tasks.get(job_id):
            await asyncio.gather(task, return_exceptions=True)

    async def shutdown(self) -> None:
        for task in list(self._tasks.values()):
            task.cancel()
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    async def _save(self, state: JobState) -> None:
        self._states[state.id] = state
        await write_json(self.store, state.id, "state.json", state.model_dump(mode="json"))

    def _start(self, job_id: str, from_failed: bool = False) -> None:
        task = asyncio.create_task(self._run(job_id, from_failed), name=f"video-job-{job_id}")
        self._tasks[job_id] = task

        def _done(t: asyncio.Task) -> None:
            if self._tasks.get(job_id) is t:
                del self._tasks[job_id]

        task.add_done_callback(_done)

    async def _keep_lease(self, lock: JobLock, owner: asyncio.Task) -> None:
        while True:
            await asyncio.sleep(LEASE_SECONDS / 3)
            try:
                await lock.renew()
            except Exception:
                log.exception("Lost the job lease, stopping the job")
                owner.cancel()
                return

    async def _run(self, job_id: str, from_failed: bool) -> None:
        state = await self.get(job_id)
        if state is None:
            return
        if state.batch is None:
            await self._run_job(job_id, from_failed)
            return
        batch = state.batch
        concurrency = min(batch.concurrency, self.settings.batch_parallel_capacity)
        previous_id = batch.previous_job_id
        if concurrency != batch.concurrency:
            manifest = await self.get_batch(batch.id)
            if manifest is None:
                raise RuntimeError(f"Missing manifest for batch {batch.id}")
            previous_id = manifest.jobs[batch.index - concurrency].id if batch.index >= concurrency else None
        lane = f"{batch.id}-lane-{batch.index % concurrency}"
        # Waiting variants must not consume job slots (including while a draft awaits approval).
        while True:
            previous = await self.get(previous_id) if previous_id else None
            if previous_id is None or (previous is not None and previous.is_finished):
                async with self._batch_locks.setdefault(lane, asyncio.Lock()):
                    lock = await self.store.try_lock(lane)
                    if lock is not None:
                        keeper = asyncio.create_task(self._keep_lease(lock, asyncio.current_task()))
                        try:
                            await self._run_job(job_id, from_failed)
                        finally:
                            keeper.cancel()
                            with contextlib.suppress(asyncio.CancelledError):
                                await keeper
                            await lock.release()
                        return
            await asyncio.sleep(0.5)

    async def _run_job(self, job_id: str, from_failed: bool) -> None:
        async with self._slots:
            lock = await self.store.try_lock(job_id)
            if lock is None:
                return  # another replica owns this job
            keeper = asyncio.create_task(self._keep_lease(lock, asyncio.current_task()))
            try:
                await self._execute(job_id, from_failed)
            finally:
                keeper.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await keeper
                await lock.release()

    async def _execute(self, job_id: str, from_failed: bool) -> None:
        # Re-read under the lease: another replica may have finished the job in the meantime.
        data = await read_json(self.store, job_id, "state.json")
        if not data:
            return
        state = JobState.model_validate(data)
        self._states[job_id] = state
        if (state.status == JobStatus.completed or (state.status == JobStatus.failed and not from_failed)
                or (state.status == JobStatus.awaiting_review and not await self.store.exists(job_id, APPROVAL))):
            return
        recorder = await OperationRecorder.load(self.store, job_id,
                                                publish=lambda event, data: self._publish(job_id, event, data))
        recorder.start_run()
        self._recorders[job_id] = recorder
        try:
            await self._execute_run(job_id, state, from_failed)
        finally:
            try:
                await recorder.close()
            finally:
                del self._recorders[job_id]
                if self._states[job_id].is_finished or self._states[job_id].status == JobStatus.awaiting_review:
                    self._publish(job_id, "end", None)

    async def _execute_run(self, job_id: str, state: JobState, from_failed: bool) -> None:
        if from_failed:
            await self.progress(job_id, JobStatus.queued, error=None)
        job = new_video_job(job_id, state.request, self.settings)
        try:
            workflow = self._workflow_factory(self)
            result = await workflow.run(job)
            outputs = [o for o in result.get_outputs() if isinstance(o, VideoResult)]
            reviews = [o for o in result.get_outputs() if isinstance(o, ReviewResult)]
            if reviews:
                await self._recorders[job_id].safe_flush()
                return
            if not outputs:
                raise RuntimeError(f"Workflow ended without a video (state: {result.get_final_state()})")
            # Operations are persisted before the final status, so readers on other replicas see them complete.
            await self._recorders[job_id].safe_flush()
            await self.progress(job_id, JobStatus.completed, duration_seconds=outputs[0].duration_seconds,
                                error=None)
            shutil.rmtree(job.work_dir, ignore_errors=True)
        except asyncio.CancelledError:
            raise  # shutdown or lost lease: the job stays unfinished and is resumed later
        except Exception as e:
            log.exception("Job %s failed", job_id)
            await self._recorders[job_id].safe_flush()
            await self.progress(job_id, JobStatus.failed, error=format_error(e)[:2000])
