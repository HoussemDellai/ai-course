"""Operation recorder: nesting, statuses, log capture, persistence and live notifications."""

import asyncio
import json
import logging

import pytest

from video_platform.operations import (
    OPERATIONS_FILE,
    OperationRecorder,
    OpKind,
    OpStatus,
    install_log_capture,
    load_operations,
)
from video_platform.storage import LocalArtifactStore


@pytest.fixture
def store(tmp_path):
    return LocalArtifactStore(tmp_path)


def by_title(recorder):
    return {o.title: o for o in recorder.snapshot()}


async def test_nesting_and_statuses(store):
    rec = OperationRecorder(store, "job1")
    rec.start_run()
    async with rec.op(OpKind.step, "Step") as step:
        async with rec.op(OpKind.agent, "agent", model="m") as agent:
            agent.set(summary="done")
        async with rec.op(OpKind.clip, "cached", queued=True) as cached:
            cached.reuse()
        async with rec.op(OpKind.narration, "empty") as empty:
            empty.skip("No narration")
        async with rec.op(OpKind.clip, "queued", queued=True) as queued:
            assert queued.op.started_at is None
            queued.start()
            queued.progress(1, 2)
        with pytest.raises(ValueError):
            async with rec.op(OpKind.ffmpeg, "broken"):
                raise ValueError("boom")
        step.update(extra=1)

    ops = by_title(rec)
    assert ops["Step"].parent_id is None and ops["Step"].status == OpStatus.succeeded
    assert all(ops[t].parent_id == ops["Step"].id for t in ["agent", "cached", "empty", "queued", "broken"])
    assert ops["agent"].attrs == {"model": "m"} and ops["agent"].summary == "done"
    assert ops["cached"].status == OpStatus.reused
    assert ops["empty"].status == OpStatus.skipped and ops["empty"].summary == "No narration"
    assert ops["queued"].status == OpStatus.succeeded and ops["queued"].progress_done == 1
    assert ops["broken"].status == OpStatus.failed and ops["broken"].error == "ValueError: boom"
    assert all(o.ended_at and o.started_at and o.run == 1 for o in ops.values())


async def test_cancelled_operation(store):
    rec = OperationRecorder(store, "job1")
    rec.start_run()

    async def work():
        async with rec.op(OpKind.clip, "slow"):
            await asyncio.sleep(10)

    task = asyncio.create_task(work())
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert by_title(rec)["slow"].status == OpStatus.cancelled


async def test_warnings_are_captured_in_the_current_operation_across_tasks(store):
    install_log_capture()
    log = logging.getLogger("video_platform.some_module")
    rec = OperationRecorder(store, "job1")
    rec.start_run()
    log.warning("outside any operation")
    async with rec.op(OpKind.step, "Step"):
        async def clip(i):
            async with rec.op(OpKind.clip, f"clip {i}"):
                log.warning("clip %d retried", i)

        async with asyncio.TaskGroup() as tg:
            for i in range(3):
                tg.create_task(clip(i))
        log.info("info is not captured")
        log.warning("step warning")

    ops = by_title(rec)
    assert [line.message for line in ops["Step"].logs] == ["step warning"]
    for i in range(3):
        assert [(line.level, line.message) for line in ops[f"clip {i}"].logs] == [("warning", f"clip {i} retried")]


async def test_persistence_is_throttled_and_flushed(store, tmp_path):
    rec = OperationRecorder(store, "job1", min_write_interval=3600)
    rec.start_run()
    path = tmp_path / "job1" / OPERATIONS_FILE
    async with rec.op(OpKind.clip, "first"):
        pass
    await asyncio.sleep(0.05)
    assert [o["title"] for o in json.loads(path.read_text())] == ["first"], "the first change is written at once"
    async with rec.op(OpKind.clip, "clip"):
        pass
    await asyncio.sleep(0.05)
    assert len(json.loads(path.read_text())) == 1, "later writes are throttled"
    async with rec.op(OpKind.step, "Step"):
        pass
    assert [o["title"] for o in json.loads(path.read_text())] == ["first", "clip", "Step"], "a finished step flushes"
    async with rec.op(OpKind.clip, "late"):
        pass
    await rec.close()
    assert [o.title for o in await load_operations(store, "job1")] == ["first", "clip", "Step", "late"]


async def test_new_run_keeps_history_and_cancels_leftovers(store):
    rec = OperationRecorder(store, "job1")
    rec.start_run()
    async with rec.op(OpKind.step, "done"):
        pass
    leftover = rec.op(OpKind.step, "interrupted")
    await leftover.__aenter__()  # a process that died while this step was running
    await rec.close()

    rec2 = await OperationRecorder.load(store, "job1")
    assert rec2.start_run() == 2
    async with rec2.op(OpKind.step, "again"):
        pass
    ops = by_title(rec2)
    assert ops["done"].status == OpStatus.succeeded and ops["done"].run == 1
    assert ops["interrupted"].status == OpStatus.cancelled
    assert ops["again"].run == 2 and ops["again"].id.startswith("r2-")


async def test_publishes_every_change(store):
    events = []
    rec = OperationRecorder(store, "job1", publish=lambda event, data: events.append((event, data["status"])))
    rec.start_run()
    async with rec.op(OpKind.clip, "clip", queued=True) as op:
        op.start()
    assert events == [("op", "queued"), ("op", "running"), ("op", "succeeded")]


async def test_unreadable_operations_file_is_ignored(store):
    await store.write_text("job1", OPERATIONS_FILE, json.dumps([{"nope": 1}]))
    assert await load_operations(store, "job1") == []
    assert await load_operations(store, "missing") == []


class SlowStore(LocalArtifactStore):
    def __init__(self, root, delay=0.0, fail=False):
        super().__init__(root)
        self.delay, self.fail = delay, fail

    async def write_text(self, job_id, name, text):
        await asyncio.sleep(self.delay)
        if self.fail:
            raise OSError("storage unavailable")
        await super().write_text(job_id, name, text)


async def test_change_made_during_a_write_is_persisted(tmp_path):
    store = SlowStore(tmp_path, delay=0.2)
    rec = OperationRecorder(store, "job1", min_write_interval=0.1)
    rec.start_run()
    async with rec.op(OpKind.clip, "clip") as op:
        await asyncio.sleep(0.1)  # the first write is in flight
        op.set(summary="LATEST")
        await asyncio.sleep(0.8)
        assert (await load_operations(store, "job1"))[0].summary == "LATEST"


async def test_storage_errors_never_fail_operations(tmp_path):
    store = SlowStore(tmp_path, fail=True)
    rec = OperationRecorder(store, "job1", min_write_interval=0)
    rec.start_run()
    async with rec.op(OpKind.step, "Step"):
        async with rec.op(OpKind.clip, "clip"):
            await asyncio.sleep(0.01)
    await rec.close()
    assert all(o.status == OpStatus.succeeded for o in rec.snapshot())

    async def cancelled_step():
        async with rec.op(OpKind.step, "lease lost"):
            await asyncio.sleep(10)

    task = asyncio.create_task(cancelled_step())
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):  # not replaced by the storage error
        await task
