from __future__ import annotations

import asyncio
import json
import logging
import math
from typing import Protocol, TypeVar

from agent_framework import Agent
from pydantic import BaseModel

from .schemas import CreativeBrief, SceneOutline, SceneShots, Shot, StoryOutline
from .video_models import VideoModel

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
- Never include real people, brands, logos or copyrighted characters.
"""

STORY_OUTLINER_INSTRUCTIONS = """\
You are a screenwriter for narrated short films made of ~5 second AI-generated clips.
Given a creative brief, write the story as a sequence of scenes with a clear beginning, middle and end.
- Each scene has a title, a short summary of what we see, the voice-over narration and a shot_count.
- The sum of shot_count over all scenes MUST equal the requested total number of shots.
- Narration length must fit the scene: about {words_per_shot:.0f} words per shot. Never exceed it.
- Write the narration in the brief's narration language, in the brief's narration style.
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


class CreativeTeam(Protocol):
    async def enhance(self, prompt: str, duration_seconds: float) -> CreativeBrief: ...
    async def outline(self, brief: CreativeBrief, total_shots: int, clip_seconds: float) -> StoryOutline: ...
    async def write_shots(
        self, brief: CreativeBrief, scene: SceneOutline, scene_index: int, total_scenes: int, model: VideoModel
    ) -> list[Shot]: ...


async def _run_structured(agent: Agent, message: str, output_type: type[T], attempts: int = 3) -> T:
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

    async def enhance(self, prompt: str, duration_seconds: float) -> CreativeBrief:
        agent = self._agent("prompt-enhancer", PROMPT_ENHANCER_INSTRUCTIONS)
        message = f"Film length: {duration_seconds / 60:.1f} minutes.\nUser idea:\n{prompt}"
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
        self, brief: CreativeBrief, scene: SceneOutline, scene_index: int, total_scenes: int, model: VideoModel
    ) -> list[Shot]:
        instructions = SHOT_WRITER_INSTRUCTIONS.format(
            model_name=model.display_name, clip_seconds=model.clip_seconds, prompt_guide=model.prompt_guide
        )
        agent = self._agent("shot-writer", instructions)
        message = (
            f"Write exactly {scene.shot_count} shot prompts for scene {scene_index + 1} of {total_scenes}.\n"
            f"Scene:\n{json.dumps(scene.model_dump(), ensure_ascii=False, indent=2)}\n"
            f"Creative brief:\n{brief.model_dump_json(indent=2)}"
        )
        shots = (await _run_structured(agent, message, SceneShots)).shots
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
