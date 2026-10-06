from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

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
    narration: str = Field(description="Voice-over text read during this scene.")
    shot_count: int


class StoryOutline(BaseModel):
    scenes: list[SceneOutline]


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
    video_model: str | None = Field(default=None, description="wan22, ltx2 or hunyuan15")
    narration: bool = True
    voice: str | None = None
    seed: int | None = None
    reference_image: bool = Field(
        default=False,
        description="Set by the server when a reference photo is uploaded (multipart 'image' field).",
    )


class JobStatus(str, Enum):
    queued = "queued"
    enhancing = "enhancing"
    planning = "planning"
    keyframing = "keyframing"
    generating = "generating"
    narrating = "narrating"
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
