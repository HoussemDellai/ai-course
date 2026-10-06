from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from typing import Protocol, TypeVar

from agent_framework import Agent, Content, Message
from pydantic import BaseModel

from .schemas import (
    CreativeBrief,
    KeyframeSceneShots,
    SceneOutline,
    SceneShots,
    Shot,
    StoryOutline,
)
from .video_models import KEYFRAME_MODEL_NAME, VideoModel

log = logging.getLogger(__name__)

WORDS_PER_SECOND = 2.3  # comfortable narration pace (~140 words per minute)

T = TypeVar("T", bound=BaseModel)

PROMPT_ENHANCER_INSTRUCTIONS = """\
You are an award-winning film director and creative producer.
You turn a short user idea into a precise creative brief for a short film made of AI-generated clips.
- Keep the user's intent, subject and language. Fill the gaps with bold but coherent creative choices.
- Define a single consistent visual style (cinematography, lighting, color palette, lens, film look).
- Define every recurring character with a fixed, very concrete visual description (age, ethnicity, face,
  hair, clothing with colors, accessories) that can be repeated word for word in every clip.
- The narration language must be the language of the user's idea unless the user asks otherwise.
- Never include real people, brands, logos or copyrighted characters, except the person(s) shown in the user's
  reference photo when one is attached.
- When a reference photo is attached, the film is built around it:
  * if it shows people, they are the main characters: describe each one faithfully from the photo (apparent age,
    face, skin tone, hair, build, clothing with exact colors, accessories). Never guess their name or identity:
    use a neutral role name (e.g. "the traveler") unless the user names them.
  * if it shows a place or a scene, it defines the setting and the visual style; stay faithful to it.
  * fill reference_notes with what the photo shows (subjects, place, light, colors, framing) and how the film uses it.
- Without a reference photo, reference_notes is an empty string.
"""

STORY_OUTLINER_INSTRUCTIONS = """\
You are a screenwriter for narrated short films made of ~5 second AI-generated clips.
Given a creative brief, write the story as a sequence of scenes with a clear beginning, middle and end.
- Each scene has a title, a short summary of what we see, the voice-over narration and a shot_count.
- The sum of shot_count over all scenes MUST equal the requested total number of shots.
- Narration length must fit the scene: about {words_per_shot:.0f} words per shot. Never exceed it.
- Write the narration in the brief's narration language, in the brief's narration style.
- The narration is read aloud word for word by a text-to-speech voice, as an unseen narrator. Write only the
  spoken words: never start with a speaker name or label ("Narrator:", "Voice-over:", "<character name>:"),
  no "(V.O.)", stage directions, brackets, quotation marks around the whole text or markdown.
"""

SHOT_WRITER_INSTRUCTIONS = """\
You are a prompt engineer for the {model_name} text-to-video model.
You write the prompts for the clips of one scene of a film. Each clip lasts about {clip_seconds:.0f} seconds
and is generated independently, so EVERY prompt must be fully self-contained:
- repeat the full fixed visual description of every character that appears (never just a name),
- repeat the setting, the visual style, the lighting and the color palette,
- describe exactly one continuous action and one camera movement,
- vary shot sizes and angles across the scene (establishing, medium, close-up, detail, reaction),
- make consecutive shots flow naturally so the edit feels continuous.
Write the prompts in English. No on-screen text, subtitles, logos or dialogue.
Model-specific guidance: {prompt_guide}
"""

KEYFRAME_SHOT_WRITER_INSTRUCTIONS = """\
You are a prompt engineer for a film built from the user's reference photo. Every clip lasts about
{clip_seconds:.0f} seconds and is made in two independent steps, so EVERY prompt must be fully self-contained:
1. keyframe_prompt: an instruction for the {keyframe_model} image-edit model. It receives the reference photo as
   "image 1" and must redraw it as this shot's FIRST FRAME (16:9). Write it as an edit instruction, e.g.
   "Keep the woman from image 1 exactly the same (same face, hair, skin tone and build), now wearing ..., standing
   on ..., medium shot from a low angle, golden-hour backlight, 35mm film look." Always say what to keep identical
   from image 1 (the people's faces and bodies, or the place), then the new framing (shot size, angle), pose,
   clothing, setting, lighting, color palette and style from the brief. If the photo shows a place, keep the place
   recognizable and describe the new viewpoint and what happens in it. No text, logos or watermarks.
2. prompt: the {model_name} image-to-video prompt that animates that keyframe.
   Model-specific guidance: {prompt_guide}
Across the scene, vary shot sizes and angles (establishing, medium, close-up, detail, reaction) and make
consecutive shots flow naturally so the edit feels continuous. Write everything in English.
"""


class CreativeTeam(Protocol):
    async def enhance(self, prompt: str, duration_seconds: float, image: bytes | None = None) -> CreativeBrief: ...
    async def outline(self, brief: CreativeBrief, total_shots: int, clip_seconds: float) -> StoryOutline: ...
    async def write_shots(
        self, brief: CreativeBrief, scene: SceneOutline, scene_index: int, total_scenes: int, model: VideoModel,
        keyframes: bool = False,
    ) -> list[Shot]: ...


async def _run_structured(agent: Agent, message: str | Message, output_type: type[T], attempts: int = 3) -> T:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            response = await agent.run(message, options={"response_format": output_type})
            value = response.value
            if isinstance(value, output_type):
                return value
            return output_type.model_validate_json(response.text)
        except Exception as e:  # malformed JSON, transient service errors...
            last_error = e
            log.warning("%s attempt %d failed: %s", agent.name, attempt + 1, e)
            await asyncio.sleep(2**attempt)
    raise RuntimeError(f"{agent.name} failed after {attempts} attempts: {last_error}")


class FoundryCreativeTeam:
    """Creative agents backed by a model deployed in Microsoft Foundry (e.g. gpt-6-astra)."""

    def __init__(self, chat_client):
        self._client = chat_client

    def _agent(self, name: str, instructions: str) -> Agent:
        return Agent(client=self._client, name=name, instructions=instructions)

    async def enhance(self, prompt: str, duration_seconds: float, image: bytes | None = None) -> CreativeBrief:
        agent = self._agent("prompt-enhancer", PROMPT_ENHANCER_INSTRUCTIONS)
        text = f"Film length: {duration_seconds / 60:.1f} minutes.\nUser idea:\n{prompt}"
        if image is None:
            return await _run_structured(agent, text, CreativeBrief)
        message = Message(role="user", contents=[
            Content.from_text(text + "\n\nThe user's reference photo is attached: build the film around it."),
            Content.from_data(data=image, media_type="image/png"),
        ])
        return await _run_structured(agent, message, CreativeBrief)

    async def outline(self, brief: CreativeBrief, total_shots: int, clip_seconds: float) -> StoryOutline:
        instructions = STORY_OUTLINER_INSTRUCTIONS.format(words_per_shot=clip_seconds * WORDS_PER_SECOND * 0.85)
        agent = self._agent("story-outliner", instructions)
        suggested_scenes = max(1, round(total_shots / 6))
        message = (
            f"Total number of shots: {total_shots} (about {suggested_scenes} scenes).\n"
            f"Creative brief:\n{brief.model_dump_json(indent=2)}"
        )
        outline = await _run_structured(agent, message, StoryOutline)
        return rebalance_outline(outline, total_shots)

    async def write_shots(
        self, brief: CreativeBrief, scene: SceneOutline, scene_index: int, total_scenes: int, model: VideoModel,
        keyframes: bool = False,
    ) -> list[Shot]:
        if keyframes:
            instructions = KEYFRAME_SHOT_WRITER_INSTRUCTIONS.format(
                model_name=model.display_name, clip_seconds=model.clip_seconds, prompt_guide=model.i2v_prompt_guide,
                keyframe_model=KEYFRAME_MODEL_NAME,
            )
        else:
            instructions = SHOT_WRITER_INSTRUCTIONS.format(
                model_name=model.display_name, clip_seconds=model.clip_seconds, prompt_guide=model.prompt_guide
            )
        agent = self._agent("shot-writer", instructions)
        message = (
            f"Write exactly {scene.shot_count} shot prompts for scene {scene_index + 1} of {total_scenes}.\n"
            f"Scene:\n{json.dumps(scene.model_dump(), ensure_ascii=False, indent=2)}\n"
            f"Creative brief:\n{brief.model_dump_json(indent=2)}"
        )
        if keyframes:
            result = await _run_structured(agent, message, KeyframeSceneShots)
            shots = [Shot(prompt=s.prompt, keyframe_prompt=s.keyframe_prompt) for s in result.shots]
        else:
            shots = [Shot(prompt=s.prompt) for s in (await _run_structured(agent, message, SceneShots)).shots]
        return fit_shot_count(shots, scene.shot_count)


def shots_for_duration(duration_seconds: float, clip_seconds: float) -> int:
    return max(1, math.ceil(duration_seconds / clip_seconds))


def rebalance_outline(outline: StoryOutline, total_shots: int) -> StoryOutline:
    """Makes the scene shot counts add up to exactly total_shots (LLMs are not great at arithmetic)."""
    scenes = [s.model_copy() for s in outline.scenes if s.shot_count > 0] or [s.model_copy() for s in outline.scenes]
    if not scenes:
        raise ValueError("The story outline has no scenes")
    if len(scenes) > total_shots:
        scenes = scenes[:total_shots]
    for s in scenes:
        s.shot_count = max(1, s.shot_count)
    diff = total_shots - sum(s.shot_count for s in scenes)
    i = 0
    while diff != 0:
        s = scenes[i % len(scenes)]
        if diff > 0:
            s.shot_count += 1
            diff -= 1
        elif s.shot_count > 1:
            s.shot_count -= 1
            diff += 1
        i += 1
    return StoryOutline(scenes=scenes)


def fit_shot_count(shots: list[Shot], count: int) -> list[Shot]:
    if not shots:
        raise ValueError("The shot writer returned no shots")
    if len(shots) >= count:
        return shots[:count]
    # Pad by re-using the last prompts: each clip gets a different seed so it still looks different.
    padded = list(shots)
    while len(padded) < count:
        padded.append(shots[len(padded) % len(shots)])
    return padded


NARRATOR_LABELS = {
    "narrator", "narration", "narrative voice", "voice-over", "voiceover", "voice over", "v.o.", "vo", "speaker",
    "narrateur", "narratrice", "voix off", "voix-off", "narrador", "narradora", "narración", "voz en off",
    "erzähler", "erzählerin", "sprecher", "sprecherin", "narratore", "voce narrante", "locutor", "locutora",
}
_ARTICLES = {"the", "a", "an", "le", "la", "les", "l'", "el", "los", "las", "der", "die", "das", "il", "lo", "o", "os"}
_LABEL = re.compile(
    r"^(?P<lead>[ \t]*)[*_\[]*[ \t]*(?P<label>[^\n:：*_\[\]]{1,60}?)[ \t]*[*_\]]*[ \t]*[:：][ \t]*[*_]*[ \t]*",
    re.MULTILINE,
)
_PAREN = re.compile(r"\s*\(([^)]*)\)\s*$")
_SCREENPLAY_MARK = re.compile(r"^(v\.?\s*o\.?|o\.?\s*s\.?|o\.?\s*c\.?|voice[\s-]?over|off|voix[\s-]?off|en off)$")
_QUOTES = {'"': '"', "“": "”", "«": "»", "„": "“", "'": "'"}


def _speaker_names(names: list[str]) -> set[str]:
    result: set[str] = set()
    for name in names:
        words = name.lower().split()
        if not words:
            continue
        result.add(" ".join(words))
        if words[0] in _ARTICLES and len(words) > 1:
            result.add(" ".join(words[1:]))
        elif len(words) > 1:
            result.add(words[0])  # "Maya Chen" is often labelled just "Maya:"
    return result


def _is_speaker_label(label: str, names: set[str]) -> bool:
    label = " ".join(label.lower().split())
    marker = _PAREN.search(label)
    base = label[: marker.start()].strip() if marker else label
    if base in NARRATOR_LABELS or base in names:
        return True
    # "Anyone (V.O.):" is a screenplay voice-over label even when the name is unknown.
    return bool(marker and _SCREENPLAY_MARK.match(marker.group(1).strip()) and 0 < len(base.split()) <= 4)


def _unquote(text: str) -> str:
    stripped = text.strip()
    if len(stripped) >= 2 and _QUOTES.get(stripped[0]) == stripped[-1] and stripped[0] not in stripped[1:-1]:
        return stripped[1:-1].strip()
    return text


def strip_speaker_labels(text: str, names: list[str] | None = None) -> str:
    """Removes screenplay-style speaker labels ("Narrator:", "Maya (V.O.):") so TTS never reads them aloud.

    A label is only removed when it is a narrator word, a character name from the brief or carries a
    voice-over marker, so ordinary sentences such as "Day one: the island wakes up." are kept.
    """
    known = _speaker_names(names or [])
    lines = []
    for line in text.splitlines():
        m = _LABEL.match(line)
        if m and _is_speaker_label(m.group("label"), known):
            line = m.group("lead") + _unquote(line[m.end():])
        lines.append(line)
    return "\n".join(lines).strip()
