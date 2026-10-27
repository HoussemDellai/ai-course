import asyncio

import pytest
from PIL import Image

from fakes import requires_ffmpeg
from generate import parse_request
from test_documents import DocumentTeam, Narrator, make_pdf, make_pptx
from video_platform import documents, media
from video_platform.config import Settings
from video_platform.documents import build_document_workflow, validate_document
from video_platform.jobs import JobManager
from video_platform.schemas import JobStatus, VideoRequest
from video_platform.storage import LocalArtifactStore, read_json
from video_platform.video_models import RESOLUTIONS
from video_platform.workflow import PipelineDeps


def test_document_4k_api_and_cli_contract():
    request = VideoRequest(prompt="Explain these slides", use_case="document", resolution="4k")
    assert request.resolution == "4k" and request.upscaler == "ffmpeg"
    assert VideoRequest(prompt="Explain these slides", use_case="document").resolution == "1080p"
    cli, path = parse_request([
        "Explain the slides", "--use-case", "document", "--document", "deck.pptx",
        "--resolution", "4k", "--orientation", "vertical",
    ])
    assert str(path) == "deck.pptx" and cli.resolution == "4k" and cli.orientation == "vertical"


@requires_ffmpeg
@pytest.mark.parametrize("kind", ["pdf", "pptx"])
@pytest.mark.parametrize("orientation,animate", [("horizontal", False), ("vertical", True)])
async def test_real_4k_document_output_dimensions_audio_and_retry(tmp_path, monkeypatch, kind, orientation, animate):
    # Keep real UHD pixel dimensions; only reduce frame rate and sample narration length.
    assert RESOLUTIONS["4k"] == (3840, 2160)
    if kind == "pptx":
        async def convert(source, settings):
            output = source.with_suffix(".pdf")
            output.write_bytes(make_pdf())
            return output
        monkeypatch.setattr(documents, "convert_powerpoint", convert)
        monkeypatch.setattr("video_platform.jobs.office_available", lambda settings: True)
    settings = Settings(
        local_output_dir=tmp_path / "out", work_dir=tmp_path / "work", output_fps=4,
        speech_endpoint="https://speech.example", comfyui_urls=[],
    )
    store = LocalArtifactStore(settings.local_output_dir)
    narrator, team = Narrator(0.25), DocumentTeam()

    def factory(manager):
        return build_document_workflow(PipelineDeps(
            settings=settings, team=None, comfy=None, narrator=narrator, store=store,
            progress=manager.progress, ops=manager.recorder,
        ), team)

    manager = JobManager(settings, store, factory)
    data = make_pdf() if kind == "pdf" else make_pptx()
    request = VideoRequest(
        prompt="Explain each slide briefly", use_case="document", resolution="4k",
        orientation=orientation, document={"animations": animate},
    )
    state = await manager.create(request, document=validate_document(data, f"slides.{kind}", 100000))
    expected = (3840, 2160) if orientation == "horizontal" else (2160, 3840)
    try:
        await asyncio.wait_for(manager.wait(state.id), 180)
        final = await manager.get(state.id)
        assert final.status == JobStatus.completed, final.error
        assert final.request.resolution == "4k"
        assert final.clips_total == final.clips_done == 2
        assert await media.video_size(store.path(state.id, "final.mp4")) == expected
        duration, audio = await media.probe(store.path(state.id, "final.mp4"))
        assert audio and duration == pytest.approx(2.5, abs=1 / settings.output_fps)
        timing = await read_json(store, state.id, "document/timing.json")
        assert timing["durations"] == [1.25, 1.25]
        for i in range(2):
            assert await media.video_size(store.path(state.id, f"scenes/scene_{i:03d}.mp4")) == expected
            with Image.open(store.path(state.id, f"document/pages/page_{i:03d}.png")) as page:
                # The full page is rasterized to fit, not cropped or stretched.
                assert page.width <= expected[0] and page.height <= expected[1]
                assert page.width == expected[0]
                assert abs(page.width / page.height - 16 / 9) < 0.01
        render = next(op for op in await manager.operations(state.id)
                      if op.attrs.get("step") == "document_render")
        assert render.attrs["resolution"] == f"{expected[0]}x{expected[1]}"
        await manager.progress(state.id, JobStatus.failed, error="Synthetic interrupted job")
        await manager.retry(state.id)
        await asyncio.wait_for(manager.wait(state.id), 180)
        assert (await manager.get(state.id)).status == JobStatus.completed
        assert len(team.pages) == len(narrator.texts) == 2, "Retry reuses original scripts and narration"
    finally:
        await manager.shutdown()
