from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Structured outputs produced by the LLM agents (all fields required for strict JSON schema).
# ---------------------------------------------------------------------------


class Character(BaseModel):
    name: str
    visual_description: str = Field(
        description="Fixed, very concrete physical description (age, face, hair, clothing, colors) "
        "repeated verbatim in every shot to keep the character consistent across clips."
    )


class CreativeBrief(BaseModel):
    title: str
    logline: str
    visual_style: str = Field(description="Cinematography, lighting, color palette, lens, film look.")
    setting: str
    tone: str
    characters: list[Character]
    narration_style: str
    narration_language: str = Field(description="BCP-47 language of the narration, e.g. en-US or fr-FR.")
    reference_notes: str = Field(
        description="What the user's reference photo shows (subjects, faces, clothing, place, light, framing) and "
        "how the film uses it. Empty string when no photo was given."
    )

    @model_validator(mode="before")
    @classmethod
    def _older_briefs(cls, data: Any) -> Any:
        # Briefs saved before reference photos existed have no reference_notes (kept required for the LLM schema).
        if isinstance(data, dict) and "reference_notes" not in data:
            data = {**data, "reference_notes": ""}
        return data


class SceneOutline(BaseModel):
    title: str
    summary: str
    narration: str = Field(
        description="Voice-over text read aloud as-is during this scene: only the spoken words, "
        "no speaker name or label (e.g. no 'Narrator:'), no stage directions."
    )
    shot_count: int


class StoryOutline(BaseModel):
    scenes: list[SceneOutline]


class Continuity(BaseModel):
    wardrobe_and_props: str
    lighting_and_location: str
    screen_direction: str
    start_state: str
    end_state: str


class NaturalSceneOutline(SceneOutline):
    continuity: Continuity


class NaturalStoryOutline(BaseModel):
    scenes: list[NaturalSceneOutline]


class NarrationRewrite(BaseModel):
    text: str = Field(min_length=1)


class ShotPrompt(BaseModel):
    prompt: str = Field(description="Self-contained text-to-video prompt for one ~5 second clip.")


class SceneShots(BaseModel):
    shots: list[ShotPrompt]


class KeyframeShotPrompt(BaseModel):
    keyframe_prompt: str = Field(
        description="Image-edit instruction that turns the reference photo (image 1) into this shot's first frame."
    )
    prompt: str = Field(description="Image-to-video prompt describing the motion and camera of the ~5 second clip.")


class KeyframeSceneShots(BaseModel):
    shots: list[KeyframeShotPrompt]


class MusicCue(BaseModel):
    caption: str = Field(
        description="MiniMax Music 3 caption for one scene's instrumental background music, in three parts: "
        "'Global Metadata: ...' (genre, BPM, key, mood arc, production), 'Vocal Details: Instrumental only. No vocals, "
        "no singing, no humming, no choir, no spoken words.' and 'Arrangement: ...' (instruments, groove, textures)."
    )


class MusicPlan(BaseModel):
    theme: str = Field(description="Musical identity shared by every scene: instrument palette, key family, tempo range.")
    scenes: list[MusicCue]


# ---------------------------------------------------------------------------
# Platform data
# ---------------------------------------------------------------------------


class Shot(BaseModel):
    prompt: str
    keyframe_prompt: str | None = None  # set when the video is built from a reference photo


class Scene(BaseModel):
    title: str
    summary: str
    narration: str
    shots: list[Shot]
    continuity: Continuity | None = None


class Pronunciation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=100)
    alias: str = Field(min_length=1, max_length=100)


class NarrationDelivery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rate_percent: int = Field(default=0, ge=-10, le=10, strict=True)
    sentence_pause_ms: int = Field(default=180, ge=0, le=1000, strict=True)
    style: str | None = Field(default=None, min_length=1, max_length=60)
    pronunciations: list[Pronunciation] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_pronunciations(self) -> NarrationDelivery:
        words = [p.text for p in self.pronunciations]
        if len(words) != len(set(words)):
            raise ValueError("Pronunciation text entries must be unique")
        return self


class Storyboard(BaseModel):
    brief: CreativeBrief
    video_model: str
    clip_seconds: float
    scenes: list[Scene]

    @property
    def shots(self) -> list[Shot]:
        return [shot for scene in self.scenes for shot in scene.shots]


class VideoRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)
    duration_minutes: float = Field(default=5.0, ge=0.25, le=10.0)
    video_model: str | None = Field(default=None, description="wan22, ltx2, ltx25 or hunyuan15")
    narration: bool = True
    voice: str | None = None
    seed: int | None = None
    naturalistic: bool = False
    music: bool = Field(default=False, description="Instrumental background music per scene (MiniMax-Music3).")
    delivery: NarrationDelivery | None = None
    reference_image: bool = Field(
        default=False,
        description="Set by the server when a reference photo is uploaded (multipart 'image' field).",
    )

    @model_validator(mode="after")
    def delivery_requires_narration(self) -> VideoRequest:
        if self.delivery is not None and not (self.naturalistic and self.narration):
            raise ValueError("Delivery controls require naturalistic mode and narration")
        return self


class JobStatus(str, Enum):
    queued = "queued"
    enhancing = "enhancing"
    planning = "planning"
    keyframing = "keyframing"
    generating = "generating"
    narrating = "narrating"
    scoring = "scoring"
    assembling = "assembling"
    completed = "completed"
    failed = "failed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobState(BaseModel):
    id: str
    status: JobStatus = JobStatus.queued
    request: VideoRequest
    title: str | None = None
    clips_total: int = 0
    clips_done: int = 0
    duration_seconds: float | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    @property
    def is_finished(self) -> bool:
        return self.status in (JobStatus.completed, JobStatus.failed)
