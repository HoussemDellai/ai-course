from __future__ import annotations

import math
import hashlib
from pathlib import Path
from typing import Protocol

from agent_framework import Executor, Workflow, WorkflowBuilder, WorkflowContext, handler
from PIL import Image
from typing_extensions import Never

from . import media
from .agents import music_lyrics
from .config import Settings
from .education_agents import EducationTeam
from .education_schemas import EducationalDraft, EducationalScene, ResearchReport, ReviewResult
from .narration import fingerprint
from .operations import OpKind
from .schemas import CreativeBrief, JobStatus, Scene, VideoRequest
from .storage import read_json, write_json
from .video_models import VideoModel
from .workflow import FINAL_VIDEO, PipelineDeps, VideoJob, VideoResult, make_submit_recorder, pending_resume

DRAFT = "education/draft.json"
APPROVAL = "education/approval.json"


def validate_education_request(request: VideoRequest, settings: Settings) -> None:
    if request.use_case != "educational":
        return
    options = request.education
    assert options is not None
    if not settings.education_search_model:
        raise ValueError("Configure EDUCATION_SEARCH_MODEL before creating educational videos")
    if not settings.speech_endpoint:
        raise ValueError("Educational videos require a Speech endpoint")
    if options.text_model and options.text_model not in {
        settings.foundry_model, *settings.education_text_models,
    }:
        raise ValueError("The selected educational text deployment is not configured")
    if options.image_provider == "comfyui" and not settings.comfy_image_workflow:
        raise ValueError("Configure COMFY_IMAGE_WORKFLOW for text-to-image generation")
    if options.image_provider == "foundry" and not (
        settings.foundry_image_endpoint and settings.foundry_image_model
    ):
        raise ValueError("Configure a Foundry image endpoint and deployment")
    if options.style == "ai_motion" and options.motion_provider == "foundry" and not (
        settings.foundry_video_endpoint and settings.foundry_video_model
    ):
        raise ValueError("Configure a compatible Foundry video endpoint and deployment")


class Visuals(Protocol):
    def companion_assets(self, image: Path, scene: EducationalScene) -> dict[str, Path]: ...
    async def image(self, scene: EducationalScene, width: int, height: int, seed: int, dest: Path,
                    *, provider: str, resume: dict | None = None, on_submitted=None) -> Path: ...
    async def diagram(self, scene: EducationalScene, width: int, height: int, dest: Path) -> Path: ...
    async def motion(self, image: Path, prompt: str, model: VideoModel, seed: int, dest: Path, *,
                     provider: str, resume: dict | None = None, on_submitted=None,
                     width: int | None = None, height: int | None = None,
                     upload_subfolder: str | None = None) -> Path: ...
    async def animate(self, image: Path, scene: EducationalScene, seconds: float, width: int,
                      height: int, fps: int, dest: Path) -> Path: ...


def draft_fingerprint(draft: EducationalDraft, job: VideoJob) -> str:
    return fingerprint({"draft": draft.model_dump(mode="json"), "request": job.request.model_dump(mode="json")})


def scene_durations(audio_seconds: list[float], requested_seconds: float, fps: int) -> list[float]:
    minimum = [math.ceil((seconds + 1.0) * fps) for seconds in audio_seconds]
    target = max(sum(minimum), math.ceil(requested_seconds * fps))
    if target > 600 * fps:
        raise ValueError(f"Approved narration requires {target / fps:.2f}s, exceeding 10 minutes. "
                         "Create a new job with a shorter script.")
    remaining = target - sum(minimum)
    each, extra = divmod(remaining, len(minimum))
    return [(frames + each + (i < extra)) / fps for i, frames in enumerate(minimum)]


def music_indices(draft: EducationalDraft, mode: str) -> list[int]:
    if mode == "off":
        return []
    if mode == "background":
        return list(range(len(draft.scenes)))
    return [i for i, scene in enumerate(draft.scenes) if scene.role in {"intro", "outro"}]


class EducationalExecutor(Executor):
    def __init__(self, deps: PipelineDeps, team: EducationTeam, visuals: Visuals):
        super().__init__(id="educational")
        self.deps, self.team, self.visuals = deps, team, visuals

    @handler
    async def run(self, job: VideoJob, ctx: WorkflowContext[Never, VideoResult | ReviewResult]) -> None:
        d, ops = self.deps, self.deps.ops(job.job_id)
        options = job.request.education
        assert options is not None
        await self._manifest(job)
        approved = await read_json(d.store, job.job_id, APPROVAL)
        if approved is None:
            state = await read_json(d.store, job.job_id, "state.json")
            revision = (state or {}).get("draft_revision") or 1
            saved = await read_json(d.store, job.job_id, DRAFT)
            draft = EducationalDraft.model_validate(saved) if saved else None
            if draft is None or draft.revision < revision:
                async with ops.op(OpKind.step, "Research public sources", step="research") as research_op:
                    await d.progress(job.job_id, JobStatus.researching)
                    report = await read_json(d.store, job.job_id, "education/research.json")
                    research = ResearchReport.model_validate(report) if report else await self.team.research(
                        options.public_topic,
                    )
                    if report is not None:
                        research_op.reuse("Previously grounded sources")
                    await write_json(d.store, job.job_id, "education/research.json",
                                     research.model_dump(mode="json"))
                    research_op.update(source_urls=[str(source.url) for source in research.sources])
                async with ops.op(OpKind.step, "Plan educational storyboard", step="education_plan"):
                    await d.progress(job.job_id, JobStatus.planning)
                    draft = await self.team.plan(job.request.prompt, options, research,
                                                 job.request.duration_minutes * 60, revision)
                    await write_json(d.store, job.job_id, DRAFT, draft.model_dump(mode="json"))
            await d.progress(job.job_id, JobStatus.awaiting_review, title=draft.brief.title,
                             draft_revision=draft.revision)
            await d.store.write_text(job.job_id, "education/sources.txt", "\n".join(
                f"[{s.id}] {s.title}\n{s.url}" for s in draft.research.sources
            ))
            await ctx.yield_output(ReviewResult(job_id=job.job_id, revision=draft.revision))
            return
        draft = EducationalDraft.model_validate(approved["draft"])
        digest = draft_fingerprint(draft, job)
        if approved["fingerprint"] != digest:
            raise ValueError("Approved content or request changed; create a new reviewed job")
        prefix = f"education/render/{digest}"
        width, height = job.output_size
        fps = d.settings.output_fps

        async def artifact(name: str) -> tuple[str, Path, bool]:
            key = f"{prefix}/{name}"
            path = job.work_dir / key
            return key, path, await d.store.download(job.job_id, key, path)

        narrations: list[Path] = []
        measured: list[float] = []
        async with ops.op(OpKind.step, "Measure approved narration", step="education_narrate"):
            await d.progress(job.job_id, JobStatus.narrating)
            if d.narrator is None:
                raise ValueError("Educational videos require a configured Speech endpoint")
            for i, scene in enumerate(draft.scenes):
                key, path, exists = await artifact(f"narration/scene_{i:03d}.wav")
                async with ops.op(OpKind.narration, f"Narrate scene {i + 1}", detail=scene.narration) as op:
                    if exists:
                        op.reuse()
                    else:
                        await d.narrator.synthesize(scene.narration, path, voice=job.request.voice,
                                                   language=draft.brief.language, delivery=job.request.delivery,
                                                   transport="rest")
                        await d.store.upload(job.job_id, key, path)
                    duration, has_audio = await media.probe(path)
                    if duration <= 0 or not has_audio:
                        raise ValueError(f"Scene {i + 1} narration contains no usable audio")
                    narrations.append(path)
                    measured.append(duration)
            durations = scene_durations(measured, job.request.duration_minutes * 60, fps)
            await write_json(d.store, job.job_id, f"{prefix}/timing.json",
                             {"durations": durations, "narration_seconds": measured,
                              "total_seconds": sum(durations)})

        images: list[Path] = []
        async with ops.op(OpKind.step, "Generate educational visual assets", step="education_images"):
            await d.progress(job.job_id, JobStatus.keyframing, clips_total=len(draft.scenes), clips_done=0)
            for i, scene in enumerate(draft.scenes):
                key, path, exists = await artifact(f"images/scene_{i:03d}.png")
                async with ops.op(OpKind.keyframe, f"Visual {i + 1}: {scene.title}", detail=scene.image_prompt) as op:
                    if exists:
                        op.reuse()
                        if scene.diagram is not None:
                            for label, companion in self.visuals.companion_assets(path, scene).items():
                                companion_key = companion.relative_to(job.work_dir).as_posix()
                                recovered = await d.store.download(job.job_id, companion_key, companion)
                                if label == "diagram_xml" and not recovered:
                                    raise ValueError(f"Scene {i + 1} diagram XML is missing; cannot restore reveals")
                    elif scene.diagram is not None:
                        await self.visuals.diagram(scene, width, height, path)
                        for companion in self.visuals.companion_assets(path, scene).values():
                            companion_key = companion.relative_to(job.work_dir).as_posix()
                            await d.store.upload(job.job_id, companion_key, companion)
                        await d.store.upload(job.job_id, key, path)
                    else:
                        pending = key + ".pending.json"
                        await self.visuals.image(
                            scene, width, height, job.seed + i, path, provider=options.image_provider,
                            resume=await pending_resume(d, job, op, pending),
                            on_submitted=make_submit_recorder(d, job, op, pending),
                        )
                        await d.store.upload(job.job_id, key, path)
                    with Image.open(path) as generated_image:
                        source_size = generated_image.size
                    if source_size[0] < width or source_size[1] < height:
                        raise ValueError(f"Scene {i + 1} image is {source_size[0]}x{source_size[1]}, below the "
                                         f"requested {width}x{height}; select a capable image deployment/workflow")
                    await write_json(d.store, job.job_id, key + ".metadata.json", {
                        "source_width": source_size[0], "source_height": source_size[1],
                        "canvas_width": width, "canvas_height": height,
                        "provider": "drawio" if scene.diagram else options.image_provider,
                        "resolution_verification": "asset_dimensions",
                        "native_generation": "vector_export" if scene.diagram else "provider_dependent",
                    })
                    op.update(artifact=key, scene=i)
                    images.append(path)

        processed: list[Path] = []
        async with ops.op(OpKind.step, "Animate educational scenes", step="education_animate"):
            await d.progress(job.job_id, JobStatus.generating)
            for i, (scene, image, seconds) in enumerate(zip(draft.scenes, images, durations)):
                key, path, exists = await artifact(f"processed/scene_{i:03d}.mp4")
                async with ops.op(OpKind.ffmpeg, f"Animate scene {i + 1}", scene=i) as op:
                    if exists:
                        op.reuse()
                    elif options.style == "presentation" or scene.diagram is not None:
                        await self.visuals.animate(image, scene, seconds, width, height, fps, path)
                        await d.store.upload(job.job_id, key, path)
                    else:
                        parts: list[Path] = []
                        remaining = seconds
                        clip_budget = math.floor(job.model.clip_seconds * fps) / fps
                        if clip_budget <= 0:
                            raise ValueError("Video model clip duration is shorter than one output frame")
                        count = math.ceil(seconds / clip_budget)
                        for clip_index in range(count):
                            clip_key, clip, clip_exists = await artifact(
                                f"clips/scene_{i:03d}_{clip_index:03d}.mp4",
                            )
                            if not clip_exists:
                                pending = clip_key + ".pending.json"
                                await self.visuals.motion(
                                    image, scene.image_prompt + " Gentle illustrative motion; no text.",
                                    job.model, job.seed + i * 1000 + clip_index, clip,
                                    provider=options.motion_provider,
                                    resume=await pending_resume(d, job, op, pending),
                                    on_submitted=make_submit_recorder(d, job, op, pending),
                                    width=job.render_size[0], height=job.render_size[1],
                                    upload_subfolder=job.upload_subfolder,
                                )
                                await d.store.upload(job.job_id, clip_key, clip)
                            if job.seedvr2:
                                upscale_key, upscale, upscale_exists = await artifact(
                                    f"upscaled/scene_{i:03d}_{clip_index:03d}.mp4",
                                )
                                if not upscale_exists:
                                    source_width, source_height = await media.video_size(clip)
                                    scale = media.fit_scale(source_width, source_height, width, height)
                                    pending = upscale_key + ".pending.json"
                                    await d.comfy.upscale_video(
                                        source=clip, scale=scale, seed=job.seed + i * 1000 + clip_index,
                                        dest=upscale, filename_prefix=f"aivideo/{job.job_id}/education_upscale",
                                        timeout=d.settings.clip_timeout_seconds, retries=d.settings.clip_retries,
                                        resume=await pending_resume(d, job, op, pending),
                                        on_submitted=make_submit_recorder(d, job, op, pending),
                                    )
                                    await d.store.upload(job.job_id, upscale_key, upscale)
                                clip = upscale
                            actual = await media.video_duration(clip)
                            budget = min(remaining, clip_budget)
                            if actual + 0.000001 < budget:
                                raise ValueError(f"Motion clip is shorter than its {budget:g}s scene budget")
                            normalized = clip.with_name(clip.stem + "_normalized.mp4")
                            await media.normalize_clip(clip, normalized, width, height, fps, False, 0,
                                                       naturalistic=True, target_duration=budget)
                            parts.append(normalized)
                            remaining = max(0, remaining - budget)
                        await media.concat(parts, path, exact=True)
                        await d.store.upload(job.job_id, key, path)
                    op.update(artifact=key, scene=i)
                processed.append(path)
                await d.progress(job.job_id, clips_done=i + 1)

        music: dict[int, Path] = {}
        indices = music_indices(draft, options.music_mode)
        async with ops.op(OpKind.step, "Score selected scenes (MiniMax-Music3)", step="education_music") as step:
            if not indices:
                step.skip("Music off")
            else:
                await d.progress(job.job_id, JobStatus.scoring)
                plan_key = f"{prefix}/music.json"
                saved_music = await read_json(d.store, job.job_id, plan_key)
                if saved_music is None:
                    brief = CreativeBrief(
                        title=draft.brief.title, logline=draft.brief.description,
                        visual_style=draft.brief.visual_theme, setting="Educational presentation",
                        tone="Clear, restrained, informative", characters=[], narration_style="Conversational",
                        narration_language=draft.brief.language, reference_notes="",
                    )
                    scenes = [Scene(title=draft.scenes[i].title, summary=draft.scenes[i].description,
                                    narration=draft.scenes[i].narration, shots=[]) for i in indices]
                    plan = await d.team.score(brief, scenes, [durations[i] for i in indices])
                    saved_music = plan.model_dump()
                    await write_json(d.store, job.job_id, plan_key, saved_music)
                for cue_index, i in enumerate(indices):
                    key, path, exists = await artifact(f"music/scene_{i:03d}.flac")
                    async with ops.op(OpKind.music, f"Music for scene {i + 1}", scene=i) as op:
                        if exists:
                            op.reuse()
                        else:
                            pending = key + ".pending.json"
                            await d.comfy.generate_music(
                                caption=saved_music["scenes"][cue_index]["caption"],
                                lyrics=music_lyrics(durations[i]), seconds=durations[i] + 1,
                                seed=job.seed + 10000 + i, dest=path,
                                filename_prefix=f"aivideo/{job.job_id}/education_music_{i:03d}",
                                timeout=d.settings.clip_timeout_seconds, retries=d.settings.clip_retries,
                                resume=await pending_resume(d, job, op, pending),
                                on_submitted=make_submit_recorder(d, job, op, pending),
                            )
                            await d.store.upload(job.job_id, key, path)
                    music[i] = path

        assembled: list[Path] = []
        async with ops.op(OpKind.step, "Assemble educational video", step="education_assemble"):
            await d.progress(job.job_id, JobStatus.assembling)
            for i, video in enumerate(processed):
                key, path, exists = await artifact(f"scenes/scene_{i:03d}.mp4")
                if not exists:
                    voice = path.with_name(path.stem + "_voice.mp4")
                    await media.mix_narration(video, narrations[i], voice, naturalistic=True)
                    if i in music:
                        await media.mix_music(voice, music[i], path, d.settings.music_volume,
                                              d.settings.music_fade_seconds)
                    else:
                        path = voice
                    await d.store.upload(job.job_id, key, path)
                assembled.append(path)
            final = job.work_dir / FINAL_VIDEO
            await media.concat(assembled, final, exact=True)
            actual_size = await media.video_size(final)
            actual_seconds = await media.video_duration(final)
            if actual_size != (width, height) or abs(actual_seconds - sum(durations)) > 1 / fps + 0.001:
                raise ValueError("Educational output dimensions or timeline do not match the approved render")
            await d.store.upload(job.job_id, FINAL_VIDEO, final)
            await d.store.write_text(job.job_id, "education/sources.txt", "\n".join(
                f"[{s.id}] {s.title}\n{s.url}" for s in draft.research.sources
            ))
        await ctx.yield_output(VideoResult(
            job_id=job.job_id, title=draft.brief.title, blob_name=FINAL_VIDEO, duration_seconds=actual_seconds,
        ))

    async def _manifest(self, job: VideoJob) -> None:
        inputs = {
            "request": job.request.model_dump(mode="json"), "model": vars(job.model),
            "fps": self.deps.settings.output_fps, "voice": self.deps.settings.tts_voice,
            "image_model": self.deps.settings.foundry_image_model,
            "video_model": self.deps.settings.foundry_video_model,
            "image_workflow": self.deps.settings.comfy_image_workflow,
            "image_endpoint": self.deps.settings.foundry_image_endpoint,
            "video_endpoint": self.deps.settings.foundry_video_endpoint,
            "speech_endpoint": self.deps.settings.speech_endpoint,
            "font": self.deps.settings.education_font,
            "diagram_exporter": self.deps.settings.drawio_export_command,
            "music_volume": self.deps.settings.music_volume,
            "music_fade": self.deps.settings.music_fade_seconds,
        }
        workflow = Path(self.deps.settings.comfy_image_workflow)
        if self.deps.settings.comfy_image_workflow and workflow.is_file():
            inputs["image_workflow_hash"] = hashlib.sha256(workflow.read_bytes()).hexdigest()
        value = {"fingerprint": fingerprint(inputs)}
        saved = await read_json(self.deps.store, job.job_id, "education/dependencies.json")
        if saved is not None and saved != value:
            raise ValueError("Educational job dependencies changed; create a new job instead of reusing assets")
        if saved is None:
            await write_json(self.deps.store, job.job_id, "education/dependencies.json", value)


def build_educational_workflow(deps: PipelineDeps, team: EducationTeam, visuals: Visuals) -> Workflow:
    return WorkflowBuilder(name="educational-production",
                           start_executor=EducationalExecutor(deps, team, visuals)).build()
