"""Video production pipeline as a Microsoft Agent Framework workflow.

    EnhancePrompt -> PlanStoryboard -> GenerateClips -> Narrate -> Assemble

The creative steps are LLM agents (gpt-6-astra in Foundry); the heavy steps are deterministic executors
calling ComfyUI, Azure AI Speech and ffmpeg. Every step persists its artifacts so a job can resume
after a restart without redoing finished work (LLM calls, clips or narration).
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TypeVar

from agent_framework import Executor, Workflow, WorkflowBuilder, WorkflowContext, handler
from typing_extensions import Never

from . import media
from .agents import CreativeTeam, shots_for_duration
from .comfyui import ComfyUIPool
from .config import Settings
from .schemas import CreativeBrief, JobStatus, Scene, Storyboard, VideoRequest
from .speech import Narrator
from .storage import ArtifactStore, read_json, write_json
from .video_models import VideoModel, get_video_model

log = logging.getLogger(__name__)

FINAL_VIDEO = "final.mp4"

T = TypeVar("T")

ProgressCallback = Callable[..., Awaitable[None]]


@dataclass
class PipelineDeps:
    settings: Settings
    team: CreativeTeam
    comfy: ComfyUIPool
    narrator: Narrator | None
    store: ArtifactStore
    progress: ProgressCallback  # async (job_id, status=None, **fields)


@dataclass
class VideoJob:
    """Message flowing through the workflow; each executor enriches it."""

    job_id: str
    request: VideoRequest
    work_dir: Path
    model: VideoModel
    seed: int
    brief: CreativeBrief | None = None
    storyboard: Storyboard | None = None
    clips: list[Path] = field(default_factory=list)
    narrations: list[Path | None] = field(default_factory=list)


@dataclass
class VideoResult:
    job_id: str
    title: str
    blob_name: str
    duration_seconds: float


def clip_name(i: int) -> str:
    return f"clips/shot_{i:03d}.mp4"


def pending_name(i: int) -> str:
    """ComfyUI prompt submitted for a clip that isn't downloaded yet (lets a restarted job reattach to it)."""
    return f"clips/shot_{i:03d}.pending.json"


def narration_name(i: int) -> str:
    return f"narration/scene_{i:03d}.wav"


async def gather_all(coros: list[Awaitable[T]]) -> list[T]:
    """Like asyncio.gather, but cancels the remaining work as soon as one task fails."""
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(c) for c in coros]
    except ExceptionGroup as eg:
        raise eg.exceptions[0] from None
    return [t.result() for t in tasks]


class EnhancePromptExecutor(Executor):
    def __init__(self, deps: PipelineDeps):
        super().__init__(id="enhance_prompt")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[VideoJob]) -> None:
        await self.deps.progress(job.job_id, JobStatus.enhancing)
        saved = await read_json(self.deps.store, job.job_id, "brief.json")
        if saved:
            job.brief = CreativeBrief.model_validate(saved)
        else:
            job.brief = await self.deps.team.enhance(job.request.prompt, job.request.duration_minutes * 60)
            await write_json(self.deps.store, job.job_id, "brief.json", job.brief.model_dump())
        await self.deps.progress(job.job_id, title=job.brief.title)
        await ctx.send_message(job)


class PlanStoryboardExecutor(Executor):
    def __init__(self, deps: PipelineDeps):
        super().__init__(id="plan_storyboard")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[VideoJob]) -> None:
        assert job.brief is not None
        await self.deps.progress(job.job_id, JobStatus.planning)
        saved = await read_json(self.deps.store, job.job_id, "storyboard.json")
        if saved:
            job.storyboard = Storyboard.model_validate(saved)
        else:
            total_shots = shots_for_duration(job.request.duration_minutes * 60, job.model.clip_seconds)
            outline = await self.deps.team.outline(job.brief, total_shots, job.model.clip_seconds)
            # Shot prompts for all scenes are written in parallel.
            shot_lists = await gather_all([
                self.deps.team.write_shots(job.brief, scene, i, len(outline.scenes), job.model)
                for i, scene in enumerate(outline.scenes)
            ])
            job.storyboard = Storyboard(
                brief=job.brief,
                video_model=job.model.key,
                clip_seconds=job.model.clip_seconds,
                scenes=[
                    Scene(title=s.title, summary=s.summary, narration=s.narration, shots=shots)
                    for s, shots in zip(outline.scenes, shot_lists)
                ],
            )
            await write_json(self.deps.store, job.job_id, "storyboard.json", job.storyboard.model_dump())
        await self.deps.progress(job.job_id, clips_total=len(job.storyboard.shots))
        await ctx.send_message(job)


class GenerateClipsExecutor(Executor):
    def __init__(self, deps: PipelineDeps):
        super().__init__(id="generate_clips")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[VideoJob]) -> None:
        assert job.storyboard is not None
        d = self.deps
        shots = job.storyboard.shots
        await d.progress(job.job_id, JobStatus.generating)
        done = 0
        lock = asyncio.Lock()

        async def one(i: int) -> Path:
            nonlocal done
            local = job.work_dir / clip_name(i)
            if not local.exists() and not await d.store.download(job.job_id, clip_name(i), local):
                pending = await read_json(d.store, job.job_id, pending_name(i))

                async def remember(server: str, prompt_id: str) -> None:
                    await write_json(d.store, job.job_id, pending_name(i), {"server": server, "prompt_id": prompt_id})

                await d.comfy.generate_clip(
                    model=job.model,
                    prompt=shots[i].prompt,
                    seed=job.seed + i,
                    dest=local,
                    filename_prefix=f"aivideo/{job.job_id}/shot_{i:03d}",
                    timeout=d.settings.clip_timeout_seconds,
                    retries=d.settings.clip_retries,
                    resume=pending if isinstance(pending, dict) else None,
                    on_submitted=remember,
                )
                await d.store.upload(job.job_id, clip_name(i), local)
            async with lock:
                done += 1
                await d.progress(job.job_id, clips_done=done)
            return local

        # As many clips in flight as there are ComfyUI servers (the pool queues the rest).
        job.clips = await gather_all([one(i) for i in range(len(shots))])
        await ctx.send_message(job)


class NarrateExecutor(Executor):
    def __init__(self, deps: PipelineDeps):
        super().__init__(id="narrate")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[VideoJob]) -> None:
        assert job.storyboard is not None
        d = self.deps
        scenes = job.storyboard.scenes
        if not job.request.narration or d.narrator is None:
            job.narrations = [None] * len(scenes)
            await ctx.send_message(job)
            return
        await d.progress(job.job_id, JobStatus.narrating)
        language = job.storyboard.brief.narration_language or "en-US"

        async def one(i: int, scene: Scene) -> Path | None:
            if not scene.narration.strip():
                return None
            local = job.work_dir / narration_name(i)
            if not local.exists() and not await d.store.download(job.job_id, narration_name(i), local):
                await d.narrator.synthesize(scene.narration, local, voice=job.request.voice, language=language)
                await d.store.upload(job.job_id, narration_name(i), local)
            return local

        job.narrations = await gather_all([one(i, s) for i, s in enumerate(scenes)])
        await ctx.send_message(job)


class AssembleExecutor(Executor):
    def __init__(self, deps: PipelineDeps):
        super().__init__(id="assemble")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[Never, VideoResult]) -> None:
        assert job.storyboard is not None
        d = self.deps
        s = d.settings
        await d.progress(job.job_id, JobStatus.assembling)
        work = job.work_dir / "assembly"
        encoders = asyncio.Semaphore(s.ffmpeg_concurrency)  # a 10 min video has ~120 clips

        async def normalize(i: int, clip: Path) -> Path:
            async with encoders:
                return await media.normalize_clip(
                    clip, work / f"norm_{i:03d}.mp4", s.output_width, s.output_height, s.output_fps,
                    keep_audio=job.model.has_audio, audio_volume=s.ambient_audio_volume,
                )

        normalized = await gather_all([normalize(i, clip) for i, clip in enumerate(job.clips)])
        scene_files: list[Path] = []
        index = 0
        for i, scene in enumerate(job.storyboard.scenes):
            parts = normalized[index : index + len(scene.shots)]
            index += len(scene.shots)
            raw = await media.concat(list(parts), work / f"scene_{i:03d}_raw.mp4")
            narration = job.narrations[i] if i < len(job.narrations) else None
            scene_files.append(await media.mix_narration(raw, narration, work / f"scene_{i:03d}.mp4"))
        final = await media.concat(scene_files, job.work_dir / FINAL_VIDEO)
        duration, _ = await media.probe(final)
        await d.store.upload(job.job_id, FINAL_VIDEO, final)
        await ctx.yield_output(
            VideoResult(job_id=job.job_id, title=job.storyboard.brief.title, blob_name=FINAL_VIDEO,
                        duration_seconds=duration)
        )


def build_video_workflow(deps: PipelineDeps) -> Workflow:
    enhance = EnhancePromptExecutor(deps)
    plan = PlanStoryboardExecutor(deps)
    clips = GenerateClipsExecutor(deps)
    narrate = NarrateExecutor(deps)
    assemble = AssembleExecutor(deps)
    return (
        WorkflowBuilder(name="video-production", start_executor=enhance)
        .add_edge(enhance, plan)
        .add_edge(plan, clips)
        .add_edge(clips, narrate)
        .add_edge(narrate, assemble)
        .build()
    )


def new_video_job(job_id: str, request: VideoRequest, settings: Settings) -> VideoJob:
    model = get_video_model(request.video_model or settings.default_video_model)
    return VideoJob(
        job_id=job_id,
        request=request,
        work_dir=settings.work_dir / job_id,
        model=model,
        seed=request.seed if request.seed is not None else random.randint(0, 2**40),
    )
