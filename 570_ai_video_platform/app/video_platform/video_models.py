from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

WORKFLOWS_DIR = Path(__file__).parent / "comfy_workflows"

# Qwen-Image-Edit-2511 (Apache 2.0) redraws the uploaded photo into each shot's keyframe.
KEYFRAME_WORKFLOW = WORKFLOWS_DIR / "qwen_image_edit_keyframe.json"
KEYFRAME_MODEL_NAME = "Qwen-Image-Edit-2511 (4-step Lightning)"


@dataclass(frozen=True)
class VideoModel:
    key: str
    display_name: str
    workflow_file: str
    i2v_workflow_file: str
    width: int
    height: int
    fps: int
    frames: int
    has_audio: bool
    negative_prompt: str
    prompt_guide: str
    i2v_prompt_guide: str
    license_note: str

    @property
    def clip_seconds(self) -> float:
        return self.frames / self.fps

    @property
    def workflow_path(self) -> Path:
        return WORKFLOWS_DIR / self.workflow_file

    @property
    def i2v_workflow_path(self) -> Path:
        return WORKFLOWS_DIR / self.i2v_workflow_file


VIDEO_MODELS: dict[str, VideoModel] = {
    "wan22": VideoModel(
        key="wan22",
        display_name="Wan 2.2 14B (Alibaba)",
        workflow_file="wan22_t2v.json",
        i2v_workflow_file="wan22_i2v.json",
        width=1280,
        height=720,
        fps=16,
        frames=81,  # 5 s at 16 fps
        has_audio=False,
        negative_prompt=(
            "vivid colors, overexposed, static, blurry details, subtitles, text, watermark, logo, "
            "painting, still image, gray, worst quality, low quality, jpeg artifacts, ugly, deformed, "
            "extra fingers, poorly drawn hands, poorly drawn face, disfigured, fused fingers, "
            "messy background, three legs, many people in the background, walking backwards"
        ),
        prompt_guide=(
            "Wan 2.2 works best with 60-120 word prompts in this order: subject (who/what, with the fixed "
            "character description), action, setting, lighting, camera (shot size, angle, movement such as "
            "'slow dolly in', 'tracking shot', 'aerial'), style/film look. One continuous action per clip. "
            "No dialogue, no on-screen text."
        ),
        i2v_prompt_guide=(
            "Wan 2.2 image-to-video animates a given first frame: the keyframe already fixes who is in the shot, "
            "what they wear, the setting and the lighting. Write 40-80 words about what MOVES: the subject's action "
            "and gestures, facial expression changes, secondary motion (hair, cloth, water, smoke), then the camera "
            "movement ('slow dolly in', 'tracking shot', 'orbit'). Mention the subject briefly so the model keeps it. "
            "One continuous action, no scene change, no dialogue, no on-screen text."
        ),
        license_note="Apache 2.0: commercial use allowed.",
    ),
    "ltx2": VideoModel(
        key="ltx2",
        display_name="LTX-2 19B distilled (Lightricks), video + audio",
        workflow_file="ltx2_t2v.json",
        i2v_workflow_file="ltx2_i2v.json",
        width=1280,
        height=704,  # LTX-2 wants sizes divisible by 64
        fps=24,
        frames=121,  # 5 s at 24 fps (frame count must be 8n+1)
        has_audio=True,
        negative_prompt="",
        prompt_guide=(
            "LTX-2 generates video AND synchronized ambient audio. Write one flowing paragraph (80-150 words) "
            "in present tense: start with the main action, then specific movements and gestures, character "
            "appearance (fixed description), background and environment, camera angle and movement, lighting "
            "and colors, and finally the soundscape (ambient sounds, foley, music mood). Do not ask for speech "
            "or dialogue: the narration is added separately."
        ),
        i2v_prompt_guide=(
            "LTX-2 image-to-video starts from the given keyframe and also generates ambient audio. Write one flowing "
            "paragraph (60-120 words) in present tense that continues the keyframe: the main action, specific "
            "movements and gestures, how the camera moves, how light and atmosphere evolve, and finally the "
            "soundscape (ambient sounds, foley, music mood). Briefly restate the subject and setting so they stay "
            "consistent. No speech or dialogue: the narration is added separately."
        ),
        license_note="LTX-2 Community License: free for organizations under $10M annual revenue.",
    ),
    "ltx25": VideoModel(
        key="ltx25",
        display_name="LTX-2.5 22B distilled (Lightricks), video + audio",
        workflow_file="ltx25_t2v.json",
        i2v_workflow_file="ltx25_i2v.json",
        width=1280,
        height=704,  # LTX-2.5 wants sizes divisible by 32 (720 isn't)
        fps=24,
        frames=121,  # 5 s at 24 fps (frame count must be 8n+1)
        has_audio=True,
        negative_prompt="pc game, console game, video game, cartoon, childish, ugly",
        prompt_guide=(
            "LTX-2.5 generates video AND synchronized ambient audio, and its Gemma 4 text encoder keeps every detail "
            "of a long, dense prompt. Write one flowing paragraph (100-180 words) in present tense: shot type and "
            "the main action, then specific movements and gestures, character appearance (fixed description), "
            "background and environment, camera angle and movement, lighting and colors, and finally the "
            "soundscape (ambient sounds, foley, music mood). One continuous shot, no cuts. Do not ask for speech "
            "or dialogue: the narration is added separately."
        ),
        i2v_prompt_guide=(
            "LTX-2.5 image-to-video starts from the given keyframe and also generates ambient audio. Write one "
            "flowing paragraph (60-120 words) in present tense that continues the keyframe: the main action, "
            "specific movements and gestures, facial expression changes, secondary motion (hair, cloth, water, "
            "smoke), how the camera moves, how light and atmosphere evolve, and finally the soundscape (ambient "
            "sounds, foley, music mood). Briefly restate the subject and setting so they stay consistent. One "
            "continuous shot, no cuts, no speech or dialogue: the narration is added separately."
        ),
        license_note="LTX-2.x Community License: free for organizations under $10M annual revenue.",
    ),
    "hunyuan15": VideoModel(
        key="hunyuan15",
        display_name="HunyuanVideo 1.5 720p (Tencent)",
        workflow_file="hunyuan15_t2v.json",
        i2v_workflow_file="hunyuan15_i2v.json",
        width=1280,
        height=720,
        fps=24,
        frames=121,  # 5 s at 24 fps
        has_audio=False,
        negative_prompt="",
        prompt_guide=(
            "HunyuanVideo 1.5 excels at physical motion (water, cloth, hair, smoke) and cinematic camera moves. "
            "Write 60-120 words: subject with the fixed character description, detailed action and physical "
            "motion, environment, lighting, camera movement (e.g. 'the camera orbits', 'crane shot rising'), "
            "and style. One continuous action per clip, no on-screen text."
        ),
        i2v_prompt_guide=(
            "HunyuanVideo 1.5 image-to-video animates the given keyframe. Write 40-80 words focused on motion: the "
            "subject's action, detailed physical motion (water, cloth, hair, smoke), how the camera moves "
            "('the camera orbits', 'slow push in'), and any change of light. Briefly name the subject and setting "
            "so they stay as in the keyframe. One continuous action, no scene change, no on-screen text."
        ),
        license_note=(
            "Tencent Hunyuan Community License: the license territory reportedly excludes the EU, UK and "
            "South Korea. Check with your legal team before using it in France."
        ),
    ),
}


def get_video_model(key: str) -> VideoModel:
    try:
        return VIDEO_MODELS[key]
    except KeyError:
        raise ValueError(f"Unknown video model '{key}'. Choose one of: {', '.join(VIDEO_MODELS)}") from None
