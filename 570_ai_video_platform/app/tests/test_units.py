import pytest

from fakes import FakeComfy
from video_platform.agents import fit_shot_count, rebalance_outline, shots_for_duration
from video_platform.comfyui import ComfyUIError, fill_workflow, find_video_outputs, load_workflow
from video_platform.schemas import SceneOutline, Shot, StoryOutline
from video_platform.video_models import VIDEO_MODELS

# Node types used by the templates, all checked against the ComfyUI source (comfy_extras/*.py, nodes.py).
KNOWN_NODES = {
    "CLIPLoader", "DualCLIPLoader", "CLIPTextEncode", "VAELoader", "UNETLoader", "LoraLoaderModelOnly",
    "ModelSamplingSD3", "EmptyHunyuanLatentVideo", "EmptyHunyuanVideo15Latent", "KSamplerAdvanced", "VAEDecode",
    "VAEDecodeTiled", "CreateVideo", "SaveVideo", "CheckpointLoaderSimple", "LTXVAudioVAELoader",
    "LTXAVTextEncoderLoader", "LTXVConditioning", "EmptyImage", "ImageScaleBy", "GetImageSize",
    "EmptyLTXVLatentVideo", "LTXVEmptyLatentAudio", "LTXVConcatAVLatent", "RandomNoise", "KSamplerSelect",
    "ManualSigmas", "CFGGuider", "SamplerCustomAdvanced", "LTXVSeparateAVLatent", "LatentUpscaleModelLoader",
    "LTXVLatentUpsampler", "LTXVAudioVAEDecode", "BasicScheduler",
}

PARAMS = {"prompt": "a cat", "negative_prompt": "blurry", "seed": 42, "width": 1280, "height": 720,
          "length": 81, "fps": 16.0, "filename_prefix": "aivideo/job/shot_000"}


@pytest.mark.parametrize("key", list(VIDEO_MODELS))
def test_workflow_templates_are_valid_api_graphs(key):
    model = VIDEO_MODELS[key]
    wf = fill_workflow(load_workflow(model.workflow_path), PARAMS)
    text = str(wf)
    assert "{{" not in text, "unfilled placeholder"
    save_nodes = [n for n in wf.values() if n["class_type"] == "SaveVideo"]
    assert len(save_nodes) == 1 and save_nodes[0]["inputs"]["filename_prefix"] == PARAMS["filename_prefix"]
    for node_id, node in wf.items():
        assert node["class_type"] in KNOWN_NODES, node["class_type"]
        for value in node["inputs"].values():
            if isinstance(value, list):  # link: [source_node_id, output_index]
                assert value[0] in wf, f"node {node_id} links to missing node {value[0]}"
                assert isinstance(value[1], int)
    # placeholders keep their JSON type (ComfyUI validates INT/FLOAT inputs strictly)
    seeds = [v for n in wf.values() for k, v in n["inputs"].items() if k == "noise_seed" and not isinstance(v, list)]
    assert 42 in seeds


def test_model_clip_settings():
    for m in VIDEO_MODELS.values():
        assert 4.5 < m.clip_seconds < 5.5
        assert m.workflow_path.exists()
    assert (VIDEO_MODELS["ltx2"].frames - 1) % 8 == 0 and VIDEO_MODELS["ltx2"].width % 64 == 0
    assert VIDEO_MODELS["ltx2"].height % 64 == 0
    assert (VIDEO_MODELS["wan22"].frames - 1) % 4 == 0


def test_fill_workflow_reports_missing_params():
    with pytest.raises(ValueError, match="seed"):
        fill_workflow({"1": {"class_type": "RandomNoise", "inputs": {"noise_seed": "{{seed}}"}}}, {})


def test_find_video_outputs():
    entry = {"outputs": {"9": {"images": [{"filename": "a.png"}]},
                         "16": {"images": [{"filename": "clip_00001_.mp4", "subfolder": "x", "type": "output"}],
                                "animated": [True]}}}
    assert find_video_outputs(entry) == [{"filename": "clip_00001_.mp4", "subfolder": "x", "type": "output"}]


async def test_comfy_pool_generates_and_downloads(tmp_path):
    fake = FakeComfy()
    pool = fake.pool()
    dest = await pool.generate_clip(VIDEO_MODELS["wan22"], "a cat", 7, tmp_path / "c.mp4", "aivideo/j/shot_000",
                                    timeout=5, retries=0)
    assert dest.read_bytes() == b"fake-mp4"
    assert fake.submitted[0]["2"]["inputs"]["text"] == "a cat"
    assert fake.submitted[0]["12"]["inputs"]["noise_seed"] == 7
    await pool.aclose()


async def test_comfy_pool_retries_with_new_seed(tmp_path):
    fake = FakeComfy(fail_first=1)
    pool = fake.pool()
    await pool.generate_clip(VIDEO_MODELS["hunyuan15"], "x", 1, tmp_path / "c.mp4", "p", timeout=5, retries=1)
    assert len(fake.submitted) == 2
    await pool.aclose()


async def test_comfy_pool_gives_up(tmp_path):
    fake = FakeComfy(fail_first=5)
    pool = fake.pool()
    with pytest.raises(ComfyUIError, match="after 2 attempts"):
        await pool.generate_clip(VIDEO_MODELS["ltx2"], "x", 1, tmp_path / "c.mp4", "p", timeout=5, retries=1)
    await pool.aclose()


def test_shots_for_duration():
    assert shots_for_duration(600, 81 / 16) == 119
    assert shots_for_duration(300, 121 / 24) == 60
    assert shots_for_duration(1, 5) == 1


def _outline(*counts):
    return StoryOutline(scenes=[SceneOutline(title=f"s{i}", summary="", narration="", shot_count=c)
                                for i, c in enumerate(counts)])


@pytest.mark.parametrize("counts,total", [((5, 5, 5), 20), ((10, 10, 10), 12), ((0, 3, 2), 5), ((1, 1, 1, 1), 2)])
def test_rebalance_outline(counts, total):
    result = rebalance_outline(_outline(*counts), total)
    assert sum(s.shot_count for s in result.scenes) == total
    assert all(s.shot_count >= 1 for s in result.scenes)


def test_fit_shot_count():
    shots = [Shot(prompt="a"), Shot(prompt="b")]
    assert [s.prompt for s in fit_shot_count(shots, 5)] == ["a", "b", "a", "b", "a"]
    assert len(fit_shot_count(shots, 1)) == 1
