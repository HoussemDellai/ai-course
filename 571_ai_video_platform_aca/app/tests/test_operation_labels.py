from dataclasses import replace

import pytest

from fakes import FakeComfy, FakeTeam, make_flac, requires_ffmpeg
from test_education import setup as education_setup  # noqa: F401
from video_platform.config import Settings
from video_platform.education import build_educational_workflow
from video_platform.education_schemas import TechnicalDiagram
from video_platform.jobs import JobManager
from video_platform.schemas import JobStatus, VideoRequest, VoiceCloneOptions
from video_platform.voice_clone import CLONE_MODELS
from video_platform.workflow import PipelineDeps, narration_metadata


def test_narration_attribution_uses_the_actual_configured_voice_or_cloning_model():
    settings = Settings(tts_voice="fr-FR-default")
    assert narration_metadata(VideoRequest(prompt="A film"), settings) == {
        "tool": "Azure AI Speech", "voice": "fr-FR-default",
    }
    assert narration_metadata(VideoRequest(prompt="A film", voice="en-US-selected"), settings) == {
        "tool": "Azure AI Speech", "voice": "en-US-selected",
    }
    for model in CLONE_MODELS.values():
        request = VideoRequest(prompt="A film", voice_clone=VoiceCloneOptions(model=model.key, consent=True))
        assert narration_metadata(request, settings) == {"tool": "Voice-clone service", "model": model.name}


@requires_ffmpeg
@pytest.mark.parametrize("provider", ["comfyui", "foundry"])
async def test_educational_operation_metadata_distinguishes_models_diagrams_and_cpu_tools(
    education_setup, tmp_path, monkeypatch, provider,
):
    settings, store, team, visuals, narrator, _, close = education_setup
    settings = replace(
        settings, foundry_image_endpoint="https://images.example", foundry_image_model="image-deployment",
        foundry_video_endpoint="https://motion.example", foundry_video_model="motion-deployment",
    )
    original_plan = team.plan

    async def plan(*args, **kwargs):
        draft = await original_plan(*args, **kwargs)
        draft.scenes[0].diagram = TechnicalDiagram(
            nodes=[{"id": "one", "label": "Server", "icon_query": "server"}], edges=[],
        )
        return draft

    monkeypatch.setattr(team, "plan", plan)
    narrator.seconds = 1
    pool = FakeComfy(music=make_flac(tmp_path / "label-music.flac", 12)).pool()

    def configured_factory(manager):
        return build_educational_workflow(PipelineDeps(
            settings=settings, team=FakeTeam(), comfy=pool, narrator=narrator,
            store=store, progress=manager.progress, ops=manager.recorder,
        ), team, visuals)

    manager = JobManager(settings, store, configured_factory)
    request = VideoRequest(
        prompt="Explain server concepts", use_case="educational", duration_minutes=0.25,
        education={"public_topic": "Public server concepts", "style": "hybrid",
                   "image_provider": provider, "motion_provider": provider, "music_mode": "background"},
    )
    try:
        state = await manager.create(request)
        await manager.wait(state.id)
        paused = await manager.get(state.id)
        assert paused.status == JobStatus.awaiting_review, paused.error
        await manager.review(state.id, paused.draft_revision, action="approve")
        await manager.wait(state.id)
        completed = await manager.get(state.id)
        assert completed.status == JobStatus.completed, completed.error
        operations = await manager.operations(state.id)
        steps = {op.attrs["step"]: op for op in operations if op.kind == "step"}
        assert all(op.attrs.get("tool") for op in steps.values())
        assert steps["research"].attrs["model"] == settings.education_search_model
        assert steps["education_plan"].attrs["model"] == settings.foundry_model
        assert steps["education_narrate"].attrs["voice"] == settings.tts_voice
        assert steps["education_assemble"].attrs["tool"] == "ffmpeg"
        diagram = next(op for op in operations if op.kind == "keyframe" and "Visual 1:" in op.title)
        assert diagram.attrs["tool"] == "draw.io MCP + exporter" and diagram.attrs["model"] is None
        illustration = next(op for op in operations if op.kind == "keyframe" and "Visual 2:" in op.title)
        motion = next(op for op in operations if op.kind == "clip")
        if provider == "foundry":
            assert illustration.attrs["tool"] == motion.attrs["tool"] == "Microsoft Foundry"
            assert illustration.attrs["model"] == "image-deployment"
            assert motion.attrs["model"] == "motion-deployment"
        else:
            assert illustration.attrs["tool"] == motion.attrs["tool"] == "ComfyUI"
            assert illustration.attrs["model"] is None
            assert motion.attrs["model"].startswith("Wan")
        assert all(op.attrs["model"] == "MiniMax-Music3" for op in operations if op.kind == "music")
    finally:
        await manager.shutdown()
        await pool.aclose()
        await close()
