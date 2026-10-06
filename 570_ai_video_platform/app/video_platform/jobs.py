from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import shutil
import uuid
from collections.abc import Callable

from agent_framework import Workflow

from .config import Settings
from .operations import Operation, OperationRecorder, install_log_capture, load_operations
from .schemas import JobState, JobStatus, VideoRequest, utcnow
from .storage import LEASE_SECONDS, ArtifactStore, JobLock, read_json, write_json
from .workflow import VideoResult, new_video_job

log = logging.getLogger(__name__)


class JobManager:
    """Runs video workflows as background tasks and persists their state in the artifact store.

    Each running job holds a renewable lease in the store, so when Container Apps briefly runs two
    replicas (e.g. during a revision rollout) a job is never executed twice.
    """

    def __init__(self, settings: Settings, store: ArtifactStore, workflow_factory: Callable[[JobManager], Workflow]):
        self.settings = settings
        self.store = store
        self._workflow_factory = workflow_factory
        self._slots = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._tasks: dict[str, asyncio.Task] = {}
        self._states: dict[str, JobState] = {}
        self._state_lock = asyncio.Lock()
        self._recorders: dict[str, OperationRecorder] = {}
        self._subscribers: dict[str, set[asyncio.Queue]] = {}
        install_log_capture()

    async def create(self, request: VideoRequest) -> JobState:
        if request.seed is None:
            request = request.model_copy(update={"seed": random.randint(0, 2**40)})
        state = JobState(id=uuid.uuid4().hex[:12], request=request)
        await self._save(state)
        self._start(state.id)
        return state

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
        for state in await self.list():
            if not state.is_finished and state.id not in self._tasks:
                self._start(state.id)

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
        if state.status == JobStatus.completed or (state.status == JobStatus.failed and not from_failed):
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
                if self._states[job_id].is_finished:
                    self._publish(job_id, "end", None)

    async def _execute_run(self, job_id: str, state: JobState, from_failed: bool) -> None:
        if from_failed:
            await self.progress(job_id, JobStatus.queued, error=None)
        job = new_video_job(job_id, state.request, self.settings)
        try:
            workflow = self._workflow_factory(self)
            result = await workflow.run(job)
            outputs = [o for o in result.get_outputs() if isinstance(o, VideoResult)]
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
            await self.progress(job_id, JobStatus.failed, error=f"{type(e).__name__}: {e}"[:2000])
