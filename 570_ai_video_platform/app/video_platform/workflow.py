"""Video production pipeline as a Microsoft Agent Framework workflow.

    EnhancePrompt -> PlanStoryboard -> GenerateKeyframes -> GenerateClips -> Narrate -> Assemble

The creative steps are LLM agents (gpt-6-astra in Foundry); the heavy steps are deterministic executors
calling ComfyUI, Azure AI Speech and ffmpeg. When the user uploads a reference photo, the agents see it,
every shot gets a keyframe redrawn from the photo (Qwen-Image-Edit) and the clips are rendered image-to-video
from those keyframes; otherwise GenerateKeyframes is skipped and the clips are text-to-video.
Every step persists its artifacts so a job can resume after a restart without redoing finished work
(LLM calls, keyframes, clips or narration).
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
from .agents import CreativeTeam, shots_for_duration, strip_speaker_labels
from .comfyui import ComfyUIPool
from .config import Settings
from .operations import OperationRecorder, OpKind
from .schemas import CreativeBrief, JobStatus, Scene, Storyboard, VideoRequest
from .speech import Narrator
from .storage import ArtifactStore, read_json, write_json
from .video_models import KEYFRAME_MODEL_NAME, VideoModel, get_video_model

log = logging.getLogger(__name__)

FINAL_VIDEO = "final.mp4"
REFERENCE_IMAGE = "input/reference.png"

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
    ops: Callable[[str], OperationRecorder]  # job_id -> live operation log of the current run


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
    reference: Path | None = None  # local copy of the uploaded photo
    keyframes: list[Path] = field(default_factory=list)
    clips: list[Path] = field(default_factory=list)
    narrations: list[Path | None] = field(default_factory=list)

    @property
    def upload_subfolder(self) -> str:
        """ComfyUI input subfolder for this job's images."""
        return f"aivideo/{self.job_id}"


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


def keyframe_name(i: int) -> str:
    return f"keyframes/shot_{i:03d}.png"


def keyframe_pending_name(i: int) -> str:
    return f"keyframes/shot_{i:03d}.pending.json"


def narration_name(i: int) -> str:
    return f"narration/scene_{i:03d}.wav"


def format_seconds(seconds: float) -> str:
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


async def gather_all(coros: list[Awaitable[T]]) -> list[T]:
    """Like asyncio.gather, but cancels the remaining work as soon as one task fails."""
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(c) for c in coros]
    except ExceptionGroup as eg:
        raise eg.exceptions[0] from None
    return [t.result() for t in tasks]


async def load_reference(d: PipelineDeps, job: VideoJob) -> Path | None:
    """Local copy of the job's reference photo (None when the video is text-only)."""
    if not job.request.reference_image:
        return None
    if job.reference is None:
        local = job.work_dir / REFERENCE_IMAGE
        if not (local.exists() or await d.store.download(job.job_id, REFERENCE_IMAGE, local)):
            raise FileNotFoundError(f"The reference photo of job {job.job_id} is missing from the store")
        job.reference = local
    return job.reference


def make_submit_recorder(d: PipelineDeps, job: VideoJob, op, pending: str) -> Callable[[str, str], Awaitable[None]]:
    """on_submitted callback: shows the ComfyUI prompt in the timeline and saves it so a restart can reattach."""
    submissions = 0

    async def remember(server: str, prompt_id: str) -> None:
        nonlocal submissions
        submissions += 1
        op.start()
        op.update(server=server, prompt_id=prompt_id, attempt=submissions)
        op.log(f"Submitted to {server} as prompt {prompt_id}")
        await write_json(d.store, job.job_id, pending, {"server": server, "prompt_id": prompt_id})

    return remember


async def pending_resume(d: PipelineDeps, job: VideoJob, op, pending: str) -> dict | None:
    saved = await read_json(d.store, job.job_id, pending)
    resume = saved if isinstance(saved, dict) else None
    if resume:
        op.start()
        op.update(server=resume.get("server"), prompt_id=resume.get("prompt_id"))
        op.log(f"Reattaching to ComfyUI prompt {resume.get('prompt_id')}")
    return resume


class EnhancePromptExecutor(Executor):
    def __init__(self, deps: PipelineDeps):
        super().__init__(id="enhance_prompt")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[VideoJob]) -> None:
        d = self.deps
        ops = d.ops(job.job_id)
        async with ops.op(OpKind.step, "Enhance prompt", step=self.id) as step:
            await d.progress(job.job_id, JobStatus.enhancing)
            saved = await read_json(d.store, job.job_id, "brief.json")
            if saved:
                job.brief = CreativeBrief.model_validate(saved)
                step.reuse()
            else:
                reference = await load_reference(d, job)
                summary = "Writing the creative brief" + (" from the reference photo" if reference else "")
                async with ops.op(OpKind.agent, "prompt-enhancer", summary=summary,
                                  model=d.settings.foundry_model, reference_image=reference is not None) as agent:
                    image = reference.read_bytes() if reference else None
                    job.brief = await d.team.enhance(job.request.prompt, job.request.duration_minutes * 60, image)
                    count = len(job.brief.characters)
                    detail = f"{job.brief.logline}\n\nStyle: {job.brief.visual_style}\nTone: {job.brief.tone}"
                    if job.brief.reference_notes:
                        detail += f"\nReference photo: {job.brief.reference_notes}"
                    agent.set(summary=f"{count} character{'' if count == 1 else 's'} · {job.brief.narration_language}",
                              detail=detail)
                await write_json(d.store, job.job_id, "brief.json", job.brief.model_dump())
            step.set(summary=job.brief.title)
            await d.progress(job.job_id, title=job.brief.title)
        await ctx.send_message(job)


class PlanStoryboardExecutor(Executor):
    def __init__(self, deps: PipelineDeps):
        super().__init__(id="plan_storyboard")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[VideoJob]) -> None:
        assert job.brief is not None
        d = self.deps
        ops = d.ops(job.job_id)
        model = d.settings.foundry_model
        async with ops.op(OpKind.step, "Plan storyboard", step=self.id) as step:
            await d.progress(job.job_id, JobStatus.planning)
            saved = await read_json(d.store, job.job_id, "storyboard.json")
            if saved:
                job.storyboard = Storyboard.model_validate(saved)
                step.reuse()
            else:
                total_shots = shots_for_duration(job.request.duration_minutes * 60, job.model.clip_seconds)
                async with ops.op(OpKind.agent, "story-outliner", summary=f"Outlining {total_shots} shots",
                                  model=model) as agent:
                    outline = await d.team.outline(job.brief, total_shots, job.model.clip_seconds)
                    agent.set(summary=f"{len(outline.scenes)} scenes · {total_shots} shots",
                              detail="\n".join(f"{i + 1}. {s.title} ({s.shot_count} shots)"
                                               for i, s in enumerate(outline.scenes)))

                async def write_shots(i: int, scene) -> list:
                    async with ops.op(OpKind.agent, f"shot-writer · scene {i + 1}/{len(outline.scenes)}",
                                      summary=scene.title, model=model) as agent:
                        shots = await d.team.write_shots(job.brief, scene, i, len(outline.scenes), job.model,
                                                         keyframes=job.request.reference_image)
                        agent.set(summary=f"{scene.title} · {len(shots)} prompts")
                        return shots

                # Shot prompts for all scenes are written in parallel.
                shot_lists = await gather_all([write_shots(i, scene) for i, scene in enumerate(outline.scenes)])
                names = [c.name for c in job.brief.characters]
                job.storyboard = Storyboard(
                    brief=job.brief,
                    video_model=job.model.key,
                    clip_seconds=job.model.clip_seconds,
                    scenes=[
                        Scene(title=s.title, summary=s.summary, narration=strip_speaker_labels(s.narration, names),
                              shots=shots)
                        for s, shots in zip(outline.scenes, shot_lists)
                    ],
                )
                await write_json(d.store, job.job_id, "storyboard.json", job.storyboard.model_dump())
            step.set(summary=f"{len(job.storyboard.scenes)} scenes · {len(job.storyboard.shots)} shots")
            await d.progress(job.job_id, clips_total=len(job.storyboard.shots))
        await ctx.send_message(job)


class GenerateKeyframesExecutor(Executor):
    """Redraws the reference photo into the first frame of every shot (skipped for text-only videos)."""

    def __init__(self, deps: PipelineDeps):
        super().__init__(id="generate_keyframes")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[VideoJob]) -> None:
        assert job.storyboard is not None
        d = self.deps
        ops = d.ops(job.job_id)
        async with ops.op(OpKind.step, "Generate keyframes", step=self.id, model=KEYFRAME_MODEL_NAME,
                          servers=d.comfy.size) as step:
            reference = await load_reference(d, job)
            if reference is None:
                job.keyframes = []
                step.skip("No reference photo")
            else:
                job.keyframes = await self._render_all(job, reference, step)
        await ctx.send_message(job)

    async def _render_all(self, job: VideoJob, reference: Path, step) -> list[Path]:
        d = self.deps
        ops = d.ops(job.job_id)
        shots = job.storyboard.shots
        scene_titles = [scene.title for scene in job.storyboard.scenes for _ in scene.shots]
        step.progress(0, len(shots))
        await d.progress(job.job_id, JobStatus.keyframing)
        done = reused = 0
        lock = asyncio.Lock()

        async def one(i: int) -> Path:
            nonlocal done, reused
            local = job.work_dir / keyframe_name(i)
            # Storyboards written without keyframe prompts (should not happen) fall back to the clip prompt.
            prompt = shots[i].keyframe_prompt or shots[i].prompt
            async with ops.op(OpKind.keyframe, f"Keyframe {i + 1}/{len(shots)}", summary=scene_titles[i],
                              detail=prompt, queued=True, seed=job.seed + i, shot=i) as op:
                if local.exists() or await d.store.download(job.job_id, keyframe_name(i), local):
                    op.reuse()
                    reused += 1
                else:
                    await d.comfy.generate_keyframe(
                        reference=reference,
                        prompt=prompt,
                        seed=job.seed + i,
                        width=job.model.width,
                        height=job.model.height,
                        dest=local,
                        filename_prefix=f"aivideo/{job.job_id}/keyframe_{i:03d}",
                        timeout=d.settings.clip_timeout_seconds,
                        retries=d.settings.clip_retries,
                        resume=await pending_resume(d, job, op, keyframe_pending_name(i)),
                        on_submitted=make_submit_recorder(d, job, op, keyframe_pending_name(i)),
                        upload_subfolder=job.upload_subfolder,
                    )
                    await d.store.upload(job.job_id, keyframe_name(i), local)
            async with lock:
                done += 1
                step.progress(done, len(shots))
            return local

        keyframes = await gather_all([one(i) for i in range(len(shots))])
        if reused == len(shots):
            step.reuse(f"{len(shots)} keyframes")
        else:
            step.set(summary=f"{len(shots)} keyframes" + (f" · {reused} reused" if reused else ""))
        return keyframes


class GenerateClipsExecutor(Executor):
    def __init__(self, deps: PipelineDeps):
        super().__init__(id="generate_clips")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[VideoJob]) -> None:
        assert job.storyboard is not None
        d = self.deps
        ops = d.ops(job.job_id)
        shots = job.storyboard.shots
        scene_titles = [scene.title for scene in job.storyboard.scenes for _ in scene.shots]
        done = reused = 0
        lock = asyncio.Lock()

        async with ops.op(OpKind.step, "Generate clips", step=self.id, model=job.model.display_name,
                          servers=d.comfy.size, mode="image-to-video" if job.keyframes else "text-to-video") as step:
            step.progress(0, len(shots))
            await d.progress(job.job_id, JobStatus.generating)

            async def one(i: int) -> Path:
                nonlocal done, reused
                local = job.work_dir / clip_name(i)
                start_image = job.keyframes[i] if job.keyframes else None
                extra = {"shot": i, "keyframe": True} if start_image else {"shot": i}
                async with ops.op(OpKind.clip, f"Shot {i + 1}/{len(shots)}", summary=scene_titles[i],
                                  detail=shots[i].prompt, queued=True, seed=job.seed + i, **extra) as op:
                    if local.exists() or await d.store.download(job.job_id, clip_name(i), local):
                        op.reuse()
                        reused += 1
                    else:
                        await d.comfy.generate_clip(
                            model=job.model,
                            prompt=shots[i].prompt,
                            seed=job.seed + i,
                            dest=local,
                            filename_prefix=f"aivideo/{job.job_id}/shot_{i:03d}",
                            timeout=d.settings.clip_timeout_seconds,
                            retries=d.settings.clip_retries,
                            resume=await pending_resume(d, job, op, pending_name(i)),
                            on_submitted=make_submit_recorder(d, job, op, pending_name(i)),
                            start_image=start_image,
                            upload_subfolder=job.upload_subfolder,
                        )
                        await d.store.upload(job.job_id, clip_name(i), local)
                async with lock:
                    done += 1
                    step.progress(done, len(shots))
                    await d.progress(job.job_id, clips_done=done)
                return local

            # As many clips in flight as there are ComfyUI servers (the pool queues the rest).
            job.clips = await gather_all([one(i) for i in range(len(shots))])
            if reused == len(shots):
                step.reuse(f"{len(shots)} clips")
            else:
                step.set(summary=f"{len(shots)} clips" + (f" · {reused} reused" if reused else ""))
        await ctx.send_message(job)


class NarrateExecutor(Executor):
    def __init__(self, deps: PipelineDeps):
        super().__init__(id="narrate")
        self.deps = deps

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[VideoJob]) -> None:
        assert job.storyboard is not None
        d = self.deps
        ops = d.ops(job.job_id)
        scenes = job.storyboard.scenes
        async with ops.op(OpKind.step, "Narrate", step=self.id) as step:
            if not job.request.narration or d.narrator is None:
                job.narrations = [None] * len(scenes)
                step.skip("Narration disabled" if not job.request.narration
                          else "No Azure AI Speech endpoint configured")
            else:
                await d.progress(job.job_id, JobStatus.narrating)
                language = job.storyboard.brief.narration_language or "en-US"
                step.update(voice=job.request.voice or d.settings.tts_voice, language=language)
                names = [c.name for c in job.storyboard.brief.characters]
                reused = 0

                async def one(i: int, scene: Scene) -> Path | None:
                    nonlocal reused
                    # Storyboards saved before labels were stripped are cleaned here too (job retries).
                    text = strip_speaker_labels(scene.narration, names)
                    async with ops.op(OpKind.narration, f"Scene {i + 1}/{len(scenes)}", summary=scene.title,
                                      detail=text, characters=len(text)) as op:
                        if not text:
                            op.skip("No narration")
                            return None
                        local = job.work_dir / narration_name(i)
                        if local.exists() or await d.store.download(job.job_id, narration_name(i), local):
                            op.reuse()
                            reused += 1
                        else:
                            await d.narrator.synthesize(text, local, voice=job.request.voice,
                                                        language=language)
                            await d.store.upload(job.job_id, narration_name(i), local)
                        return local

                job.narrations = await gather_all([one(i, s) for i, s in enumerate(scenes)])
                voiced = sum(1 for n in job.narrations if n is not None)
                if voiced and reused == voiced:
                    step.reuse(f"{voiced} scenes")
                else:
                    step.set(summary=f"{voiced} scenes" + (f" · {reused} reused" if reused else ""))
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
        ops = d.ops(job.job_id)
        scenes = job.storyboard.scenes
        async with ops.op(OpKind.step, "Assemble video", step=self.id,
                          resolution=f"{s.output_width}x{s.output_height}", fps=s.output_fps) as step:
            await d.progress(job.job_id, JobStatus.assembling)
            work = job.work_dir / "assembly"
            encoders = asyncio.Semaphore(s.ffmpeg_concurrency)  # a 10 min video has ~120 clips

            async with ops.op(OpKind.ffmpeg, f"Normalize {len(job.clips)} clips",
                              summary=f"{s.output_width}x{s.output_height} @ {s.output_fps} fps",
                              concurrency=s.ffmpeg_concurrency) as norm:
                norm.progress(0, len(job.clips))
                normalized_count = 0

                async def normalize(i: int, clip: Path) -> Path:
                    nonlocal normalized_count
                    async with encoders:
                        out = await media.normalize_clip(
                            clip, work / f"norm_{i:03d}.mp4", s.output_width, s.output_height, s.output_fps,
                            keep_audio=job.model.has_audio, audio_volume=s.ambient_audio_volume,
                        )
                    normalized_count += 1
                    norm.progress(normalized_count, len(job.clips))
                    return out

                normalized = await gather_all([normalize(i, clip) for i, clip in enumerate(job.clips)])

            scene_files: list[Path] = []
            index = 0
            for i, scene in enumerate(scenes):
                parts = normalized[index : index + len(scene.shots)]
                index += len(scene.shots)
                narration = job.narrations[i] if i < len(job.narrations) else None
                title = f"Scene {i + 1}/{len(scenes)}: concat {len(parts)} clips" + (" + mix narration" if narration else "")
                async with ops.op(OpKind.ffmpeg, title, summary=scene.title):
                    raw = await media.concat(list(parts), work / f"scene_{i:03d}_raw.mp4")
                    scene_files.append(await media.mix_narration(raw, narration, work / f"scene_{i:03d}.mp4"))

            async with ops.op(OpKind.ffmpeg, f"Concatenate {len(scene_files)} scenes") as op:
                final = await media.concat(scene_files, job.work_dir / FINAL_VIDEO)
                duration, _ = await media.probe(final)
                op.set(summary=format_seconds(duration))
            async with ops.op(OpKind.upload, f"Upload {FINAL_VIDEO}",
                              summary=f"{final.stat().st_size / 1e6:.1f} MB"):
                await d.store.upload(job.job_id, FINAL_VIDEO, final)
            step.set(summary=f"{format_seconds(duration)} video")
        await ctx.yield_output(
            VideoResult(job_id=job.job_id, title=job.storyboard.brief.title, blob_name=FINAL_VIDEO,
                        duration_seconds=duration)
        )


def build_video_workflow(deps: PipelineDeps) -> Workflow:
    enhance = EnhancePromptExecutor(deps)
    plan = PlanStoryboardExecutor(deps)
    keyframes = GenerateKeyframesExecutor(deps)
    clips = GenerateClipsExecutor(deps)
    narrate = NarrateExecutor(deps)
    assemble = AssembleExecutor(deps)
    return (
        WorkflowBuilder(name="video-production", start_executor=enhance)
        .add_edge(enhance, plan)
        .add_edge(plan, keyframes)
        .add_edge(keyframes, clips)
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
