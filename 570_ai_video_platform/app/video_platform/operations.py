"""Live, persisted log of the operations a job performs (shown in the web UI as a Copilot-style timeline).

Operations are nested: pipeline steps contain agent calls, clips, narrations, ffmpeg and upload operations.
The current operation lives in a context variable, so nested operations find their parent automatically and
warnings logged by the platform's modules (LLM retries, ComfyUI retries...) are attached to it.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Callable
from contextvars import ContextVar
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from .schemas import utcnow
from .storage import ArtifactStore, read_json, write_json

log = logging.getLogger(__name__)

OPERATIONS_FILE = "operations.json"
MAX_LOG_LINES = 50
MAX_LOG_CHARS = 2000


class OpKind(str, Enum):
    step = "step"
    agent = "agent"
    clip = "clip"
    narration = "narration"
    ffmpeg = "ffmpeg"
    upload = "upload"


class OpStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    reused = "reused"
    skipped = "skipped"
    cancelled = "cancelled"


ACTIVE = (OpStatus.queued, OpStatus.running)


class LogLine(BaseModel):
    at: datetime = Field(default_factory=utcnow)
    level: str = "info"
    message: str


class Operation(BaseModel):
    id: str
    parent_id: str | None = None
    run: int = 1
    kind: OpKind
    title: str
    summary: str | None = None
    detail: str | None = None
    status: OpStatus = OpStatus.running
    created_at: datetime = Field(default_factory=utcnow)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    progress_done: int | None = None
    progress_total: int | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)
    logs: list[LogLine] = Field(default_factory=list)
    error: str | None = None


_current: ContextVar[OpHandle | None] = ContextVar("current_operation", default=None)

Publisher = Callable[[str, Any], None]


class OpHandle:
    """Mutates one operation and notifies the recorder (persistence + live subscribers)."""

    def __init__(self, recorder: OperationRecorder, op: Operation):
        self._recorder = recorder
        self.op = op

    @property
    def id(self) -> str:
        return self.op.id

    def start(self) -> None:
        if self.op.status == OpStatus.queued:
            self.op.status = OpStatus.running
            self.op.started_at = utcnow()
            self._changed()

    def set(self, *, title: str | None = None, summary: str | None = None, detail: str | None = None) -> None:
        if title is not None:
            self.op.title = title
        if summary is not None:
            self.op.summary = summary
        if detail is not None:
            self.op.detail = detail
        self._changed()

    def update(self, **attrs: Any) -> None:
        self.op.attrs.update(attrs)
        self._changed()

    def progress(self, done: int, total: int) -> None:
        self.op.progress_done, self.op.progress_total = done, total
        self._changed()

    def log(self, message: str, level: str = "info") -> None:
        self.op.logs.append(LogLine(level=level, message=message[:MAX_LOG_CHARS]))
        if len(self.op.logs) > MAX_LOG_LINES:
            del self.op.logs[: len(self.op.logs) - MAX_LOG_LINES]
        self._changed()

    def reuse(self, summary: str | None = None) -> None:
        """The work was already done by a previous run (artifact found in the store)."""
        self._finish_as(OpStatus.reused, summary)

    def skip(self, summary: str | None = None) -> None:
        self._finish_as(OpStatus.skipped, summary)

    def _finish_as(self, status: OpStatus, summary: str | None) -> None:
        self.op.status = status
        if summary is not None:
            self.op.summary = summary
        self._changed()

    def _changed(self) -> None:
        self._recorder._changed(self.op)


class OperationRecorder:
    """Operations of one job, across all its runs (a retry or a resume starts a new run)."""

    def __init__(self, store: ArtifactStore, job_id: str, operations: list[Operation] | None = None,
                 publish: Publisher | None = None, min_write_interval: float = 1.0):
        self.store = store
        self.job_id = job_id
        self._ops: dict[str, Operation] = {o.id: o for o in operations or []}
        self._publish = publish or (lambda event, data: None)
        self._min_write_interval = min_write_interval
        self.run = max((o.run for o in self._ops.values()), default=0)
        self._counter = 0
        self._dirty = False
        self._last_write = float("-inf")
        self._write_lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None

    @classmethod
    async def load(cls, store: ArtifactStore, job_id: str, **kwargs) -> OperationRecorder:
        return cls(store, job_id, await load_operations(store, job_id), **kwargs)

    def start_run(self) -> int:
        """Starts a new run; operations a dead process left active are marked as cancelled."""
        now = utcnow()
        for op in self._ops.values():
            if op.status in ACTIVE:
                op.status, op.ended_at = OpStatus.cancelled, now
                op.started_at = op.started_at or now
                self._changed(op)
        self.run += 1
        self._counter = 0
        return self.run

    def snapshot(self) -> list[Operation]:
        return [o.model_copy(deep=True) for o in self._ops.values()]

    @contextlib.asynccontextmanager
    async def op(self, kind: OpKind, title: str, *, summary: str | None = None, detail: str | None = None,
                 queued: bool = False, **attrs: Any) -> AsyncIterator[OpHandle]:
        """Records an operation; nested calls become its children. Exceptions mark it failed."""
        parent = _current.get()
        self._counter += 1
        now = utcnow()
        op = Operation(
            id=f"r{self.run}-{self._counter}",
            parent_id=parent.id if parent is not None and parent._recorder is self else None,
            run=self.run, kind=kind, title=title, summary=summary, detail=detail, attrs=attrs,
            status=OpStatus.queued if queued else OpStatus.running,
            created_at=now, started_at=None if queued else now,
        )
        self._ops[op.id] = op
        handle = OpHandle(self, op)
        self._changed(op)
        token = _current.set(handle)
        try:
            yield handle
        except asyncio.CancelledError:
            self._end(op, OpStatus.cancelled)
            raise
        except BaseException as e:
            op.error = f"{type(e).__name__}: {e}"[:MAX_LOG_CHARS]
            self._end(op, OpStatus.failed)
            raise
        else:
            self._end(op, OpStatus.succeeded if op.status in ACTIVE else op.status)
        finally:
            _current.reset(token)
            if kind == OpKind.step:
                await self.safe_flush()

    def _end(self, op: Operation, status: OpStatus) -> None:
        op.status = status
        op.ended_at = utcnow()
        op.started_at = op.started_at or op.ended_at
        self._changed(op)

    def _changed(self, op: Operation) -> None:
        self._publish("op", op.model_dump(mode="json"))
        self._dirty = True
        if self._flush_task is None or self._flush_task.done():
            try:
                self._flush_task = asyncio.get_running_loop().create_task(self._delayed_flush())
            except RuntimeError:
                pass  # no event loop: flush() persists later

    async def _delayed_flush(self) -> None:
        # Loop: changes made while a write is in flight must be persisted too.
        while self._dirty:
            await asyncio.sleep(max(0.0, self._last_write + self._min_write_interval - time.monotonic()))
            if not await self.safe_flush():
                return  # storage trouble: the next change, step end or close() retries

    async def safe_flush(self) -> bool:
        """Persists without ever failing the job: the timeline is a display aid, not job state."""
        try:
            await self.flush()
            return True
        except Exception:
            log.warning("Could not persist the operations of job %s", self.job_id, exc_info=True)
            return False

    async def flush(self) -> None:
        async with self._write_lock:
            if not self._dirty:
                return
            self._dirty = False
            self._last_write = time.monotonic()
            try:
                await write_json(self.store, self.job_id, OPERATIONS_FILE,
                                 [o.model_dump(mode="json") for o in self._ops.values()])
            except BaseException:
                self._dirty = True
                raise

    async def close(self) -> None:
        if self._flush_task is not None and not self._flush_task.done():
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._flush_task
        await self.safe_flush()


async def load_operations(store: ArtifactStore, job_id: str) -> list[Operation]:
    data = await read_json(store, job_id, OPERATIONS_FILE)
    if not isinstance(data, list):
        return []
    try:
        return [Operation.model_validate(o) for o in data]
    except ValidationError:
        log.warning("Ignoring unreadable %s of job %s", OPERATIONS_FILE, job_id)
        return []


class _CaptureHandler(logging.Handler):
    """Attaches warnings logged while an operation runs to that operation's logs."""

    def emit(self, record: logging.LogRecord) -> None:
        handle = _current.get()
        if handle is None or record.name == __name__:
            return
        try:
            message = record.getMessage()
        except Exception:
            return
        handle.log(message, record.levelname.lower())


def install_log_capture(logger_name: str = "video_platform") -> None:
    logger = logging.getLogger(logger_name)
    if not any(isinstance(h, _CaptureHandler) for h in logger.handlers):
        logger.addHandler(_CaptureHandler(logging.WARNING))
