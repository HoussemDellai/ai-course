import pytest

from fakes import FakeComfy
from video_platform.agents import fit_shot_count, rebalance_outline, shots_for_duration, strip_speaker_labels
from video_platform.comfyui import (
    ComfyUIError,
    fill_workflow,
    find_outputs,
    find_video_outputs,
    load_workflow,
    IMAGE_EXTENSIONS,
)
from video_platform.schemas import CreativeBrief, SceneOutline, Shot, Storyboard, StoryOutline
from video_platform.video_models import KEYFRAME_WORKFLOW, VIDEO_MODELS

# Node types used by the templates, all checked against the ComfyUI source (comfy_extras/*.py, nodes.py).
KNOWN_NODES = {
    "CLIPLoader", "DualCLIPLoader", "CLIPTextEncode", "VAELoader", "UNETLoader", "LoraLoaderModelOnly",
    "ModelSamplingSD3", "EmptyHunyuanLatentVideo", "EmptyHunyuanVideo15Latent", "KSamplerAdvanced", "VAEDecode",
    "VAEDecodeTiled", "CreateVideo", "SaveVideo", "CheckpointLoaderSimple", "LTXVAudioVAELoader",
    "LTXAVTextEncoderLoader", "LTXVConditioning", "EmptyImage", "ImageScaleBy", "GetImageSize",
    "EmptyLTXVLatentVideo", "LTXVEmptyLatentAudio", "LTXVConcatAVLatent", "RandomNoise", "KSamplerSelect",
    "ManualSigmas", "CFGGuider", "SamplerCustomAdvanced", "LTXVSeparateAVLatent", "LatentUpscaleModelLoader",
    "LTXVLatentUpsampler", "LTXVAudioVAEDecode", "BasicScheduler", "LTXVDualCFGGuider",
    # image-to-video and keyframes (Qwen-Image-Edit)
    "LoadImage", "ImageScale", "WanImageToVideo", "LTXVPreprocess", "LTXVImgToVideoInplace", "LTXVCropGuides",
    "ConditioningZeroOut", "CLIPVisionLoader", "CLIPVisionEncode", "HunyuanVideo15ImageToVideo",
    "FluxKontextImageScale", "ModelSamplingAuraFlow", "CFGNorm", "TextEncodeQwenImageEditPlus",
    "FluxKontextMultiReferenceLatentMethod", "EmptySD3LatentImage", "KSampler", "SaveImage",
}

PARAMS = {"prompt": "a cat", "negative_prompt": "blurry", "seed": 42, "width": 1280, "height": 720,
          "length": 81, "fps": 16.0, "filename_prefix": "aivideo/job/shot_000"}
I2V_PARAMS = {**PARAMS, "image": "aivideo/job/shot_000.png"}


def check_graph(wf: dict, save_type: str, seed_key: str) -> None:
    assert "{{" not in str(wf), "unfilled placeholder"
    save_nodes = [n for n in wf.values() if n["class_type"] == save_type]
    assert len(save_nodes) == 1 and save_nodes[0]["inputs"]["filename_prefix"] == PARAMS["filename_prefix"]
    for node_id, node in wf.items():
        assert node["class_type"] in KNOWN_NODES, node["class_type"]
        for value in node["inputs"].values():
            if isinstance(value, list):  # link: [source_node_id, output_index]
                assert value[0] in wf, f"node {node_id} links to missing node {value[0]}"
                assert isinstance(value[1], int)
    # placeholders keep their JSON type (ComfyUI validates INT/FLOAT inputs strictly)
    seeds = [v for n in wf.values() for k, v in n["inputs"].items() if k == seed_key and not isinstance(v, list)]
    assert 42 in seeds


@pytest.mark.parametrize("key", list(VIDEO_MODELS))
def test_workflow_templates_are_valid_api_graphs(key):
    model = VIDEO_MODELS[key]
    wf = fill_workflow(load_workflow(model.workflow_path), PARAMS)
    check_graph(wf, "SaveVideo", "noise_seed")
    assert not any(n["class_type"] == "LoadImage" for n in wf.values())


@pytest.mark.parametrize("key", list(VIDEO_MODELS))
def test_i2v_workflow_templates_are_valid_api_graphs(key):
    model = VIDEO_MODELS[key]
    with pytest.raises(ValueError, match="image"):
        fill_workflow(load_workflow(model.i2v_workflow_path), PARAMS)
    wf = fill_workflow(load_workflow(model.i2v_workflow_path), I2V_PARAMS)
    check_graph(wf, "SaveVideo", "noise_seed")
    loads = [n for n in wf.values() if n["class_type"] == "LoadImage"]
    assert len(loads) == 1 and loads[0]["inputs"]["image"] == I2V_PARAMS["image"]
    # the start image reaches the image-to-video conditioning node
    load_id = next(i for i, n in wf.items() if n["class_type"] == "LoadImage")
    consumers = {n["class_type"] for n in wf.values() for v in n["inputs"].values() if v == [load_id, 0]}
    assert consumers & {"WanImageToVideo", "ImageScale", "HunyuanVideo15ImageToVideo", "CLIPVisionEncode"}


def test_keyframe_workflow_is_a_valid_api_graph():
    params = {"prompt": "Keep the man from image 1", "image": "aivideo/job/reference.png", "seed": 42,
              "width": 1280, "height": 704, "filename_prefix": PARAMS["filename_prefix"]}
    wf = fill_workflow(load_workflow(KEYFRAME_WORKFLOW), params)
    check_graph(wf, "SaveImage", "seed")
    latent = next(n for n in wf.values() if n["class_type"] == "EmptySD3LatentImage")
    assert (latent["inputs"]["width"], latent["inputs"]["height"]) == (1280, 704)
    prompts = [n["inputs"]["prompt"] for n in wf.values() if n["class_type"] == "TextEncodeQwenImageEditPlus"]
    assert sorted(prompts) == ["", "Keep the man from image 1"]


def test_model_clip_settings():
    for m in VIDEO_MODELS.values():
        assert 4.5 < m.clip_seconds < 5.5
        assert m.workflow_path.exists() and m.i2v_workflow_path.exists()
        assert m.i2v_prompt_guide
    assert KEYFRAME_WORKFLOW.exists()
    assert (VIDEO_MODELS["ltx2"].frames - 1) % 8 == 0 and VIDEO_MODELS["ltx2"].width % 64 == 0
    assert VIDEO_MODELS["ltx2"].height % 64 == 0
    ltx25 = VIDEO_MODELS["ltx25"]
    assert (ltx25.frames - 1) % 8 == 0 and ltx25.width % 32 == 0 and ltx25.height % 32 == 0
    # stage 1 renders at half size before the x2 latent upscaler: the half size must stay a multiple of 32
    assert (ltx25.width // 2) % 32 == 0 and (ltx25.height // 2) % 32 == 0 and ltx25.has_audio
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


def test_find_image_outputs():
    entry = {"outputs": {"16": {"images": [{"filename": "kf_00001_.png", "subfolder": "x", "type": "output"}]}}}
    assert find_outputs(entry, IMAGE_EXTENSIONS) == [{"filename": "kf_00001_.png", "subfolder": "x", "type": "output"}]
    assert find_video_outputs(entry) == []


async def test_comfy_pool_generates_keyframe_from_reference(tmp_path):
    fake = FakeComfy()
    pool = fake.pool()
    reference = tmp_path / "reference.png"
    reference.write_bytes(fake.image_bytes)
    dest = await pool.generate_keyframe(reference, "Keep the man from image 1", 9, 1280, 720, tmp_path / "k.png",
                                        "aivideo/j/keyframe_000", timeout=5, retries=0, upload_subfolder="aivideo/j")
    assert dest.read_bytes() == fake.image_bytes
    assert fake.uploads == [("comfy0", "aivideo/j", "reference.png")]
    wf = fake.submitted[0]
    assert wf["4"]["inputs"]["image"] == "aivideo/j/reference.png"
    assert wf["9"]["inputs"]["prompt"] == "Keep the man from image 1" and wf["14"]["inputs"]["seed"] == 9
    await pool.aclose()


async def test_comfy_pool_image_to_video_uploads_to_each_attempts_server(tmp_path):
    fake = FakeComfy(fail_first=1)
    pool = fake.pool(servers=2)
    keyframe = tmp_path / "shot_003.png"
    keyframe.write_bytes(fake.image_bytes)
    await pool.generate_clip(VIDEO_MODELS["wan22"], "she turns", 1, tmp_path / "c.mp4", "p", timeout=5, retries=1,
                             start_image=keyframe, upload_subfolder="aivideo/j")
    assert len(fake.submitted) == 2 and len(fake.uploads) == 2, "re-uploaded for the retry"
    for wf in fake.submitted:
        assert any(n["class_type"] == "WanImageToVideo" for n in wf.values())
        assert wf["11"]["inputs"]["image"] == "aivideo/j/shot_003.png"
    await pool.aclose()


def test_older_artifacts_still_load():
    brief = {"title": "t", "logline": "l", "visual_style": "v", "setting": "s", "tone": "t", "characters": [],
             "narration_style": "n", "narration_language": "en-US"}
    assert CreativeBrief.model_validate(brief).reference_notes == ""
    old = Storyboard.model_validate({"brief": brief, "video_model": "wan22", "clip_seconds": 5.0, "scenes": [
        {"title": "a", "summary": "b", "narration": "c", "shots": [{"prompt": "p"}]}]})
    assert old.shots[0].keyframe_prompt is None
    # LLM output schemas stay strict: every field is required.
    assert set(CreativeBrief.model_json_schema()["required"]) >= {"reference_notes"}


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


@pytest.mark.parametrize("text, expected", [
    ("Narrator: The island wakes up.", "The island wakes up."),
    ("NARRATOR : The island wakes up.", "The island wakes up."),
    ("**Narrator:** The island wakes up.", "The island wakes up."),
    ("[Voice-over]: The island wakes up.", "The island wakes up."),
    ("Narrator (softly): The island wakes up.", "The island wakes up."),
    ("Narrateur : L'île se réveille.", "L'île se réveille."),
    ("Erzähler: Die Insel erwacht.", "Die Insel erwacht."),
    ("Yann: I have kept this light for forty years.", "I have kept this light for forty years."),
    ("Maya: She looks at the sea.", "She looks at the sea."),
    ("The Traveler: Dust everywhere.", "Dust everywhere."),
    ("Old Sailor (V.O.): The sea gives, the sea takes.", "The sea gives, the sea takes."),
    ('Narrator: "The storm comes."', "The storm comes."),
    ("Narrator: Dawn.\nYann: Night falls.", "Dawn.\nNight falls."),
    # ordinary sentences with a colon are kept
    ("Day one: the island wakes up.", "Day one: the island wakes up."),
    ("One rule: never leave the light.", "One rule: never leave the light."),
    ("At 6:30 the boat leaves.", "At 6:30 the boat leaves."),
    ("The island wakes up.", "The island wakes up."),
    ("  ", ""),
])
def test_strip_speaker_labels(text, expected):
    assert strip_speaker_labels(text, ["Yann", "Maya Chen", "the traveler"]) == expected
