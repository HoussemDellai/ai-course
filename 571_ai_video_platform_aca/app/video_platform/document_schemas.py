from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DocumentOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    language: str = Field(default="en-US", pattern=r"^[a-z]{2,3}-[A-Z]{2}$")
    cinematic_cutaways: bool = Field(
        default=False, strict=True, exclude_if=lambda value: not value,
        description="Replace page visuals with 5-second GPU cinematic clips at 30s, 60s, etc., "
                    "only where a full clip fits. Narration and duration remain unchanged.",
    )
    animations: bool = Field(
        default=False, strict=True, exclude_if=lambda value: not value,
        description="Animate each page with a gentle zoom and fade in/out. Pages are never cropped; "
                    "narration and duration remain unchanged. Runs on CPU with ffmpeg only.",
    )
    filename: str | None = Field(default=None, max_length=255,
                                 description="Set by the server from the uploaded PDF or PowerPoint filename.")


class DocumentPage(BaseModel):
    number: int = Field(ge=1)
    text: str = Field(max_length=20000)
    notes: str = Field(default="", max_length=20000)


class PageNarration(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    narration: str = Field(min_length=1, max_length=12000)


class DocumentScript(BaseModel):
    pages: list[PageNarration] = Field(min_length=1, max_length=60)
