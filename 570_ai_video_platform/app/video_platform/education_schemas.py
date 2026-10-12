from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, StringConstraints, model_validator


class EducationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    style: Literal["presentation", "ai_motion"] = "presentation"
    image_provider: Literal["comfyui", "foundry"] = "comfyui"
    motion_provider: Literal["comfyui", "foundry"] = "comfyui"
    text_model: str | None = Field(default=None, max_length=100)
    audience: str = Field(default="General audience", min_length=1, max_length=300)
    music_mode: Literal["off", "intro_outro", "background"] = "intro_outro"
    public_topic: str = Field(min_length=3, max_length=1000,
                              description="Public topic sent to web search. Never include private information.")


class ResearchSource(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^s[1-9]\d*$")
    title: str = Field(min_length=1, max_length=500)
    url: HttpUrl


class ResearchReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str = Field(min_length=1, max_length=20000)
    sources: list[ResearchSource] = Field(min_length=1, max_length=30)

    @model_validator(mode="after")
    def unique_sources(self) -> ResearchReport:
        ids = [s.id for s in self.sources]
        if len(ids) != len(set(ids)):
            raise ValueError("Source IDs must be unique")
        return self


class EducationalBrief(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    audience: str = Field(min_length=1, max_length=300)
    objectives: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]] = Field(
        min_length=1, max_length=10,
    )
    language: str = Field(pattern=r"^[a-zA-Z]{2,3}-[a-zA-Z0-9]{2,8}(?:-[a-zA-Z0-9]{2,8})*$",
                          description="Speech locale including region, such as en-US, fr-FR, or ar-TN.")
    visual_theme: str = Field(min_length=1, max_length=1500)


class DiagramNode(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    id: str = Field(pattern=r"^[a-zA-Z][a-zA-Z0-9_-]{0,39}$")
    label: str = Field(min_length=1, max_length=100)
    icon_query: str = Field(min_length=1, max_length=100,
                            description="Specific native draw.io shape search, e.g. Azure Kubernetes Service")


class DiagramEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    source: str
    target: str
    label: str = Field(default="", max_length=100)


class TechnicalDiagram(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nodes: list[DiagramNode] = Field(min_length=1, max_length=16)
    edges: list[DiagramEdge] = Field(default_factory=list, max_length=32)

    @model_validator(mode="after")
    def valid_graph(self) -> TechnicalDiagram:
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Diagram node IDs must be unique")
        if any(e.source not in ids or e.target not in ids for e in self.edges):
            raise ValueError("Diagram connections must refer to existing nodes")
        return self


class EducationalScene(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=150)
    description: str = Field(min_length=1, max_length=2000)
    narration: str = Field(min_length=1, max_length=6000)
    image_prompt: str = Field(min_length=1, max_length=2000)
    animation: Literal["zoom_in", "zoom_out", "pan", "reveal"] = "zoom_in"
    role: Literal["intro", "content", "outro"] = "content"
    source_ids: list[str] = Field(min_length=1, max_length=30)
    diagram: TechnicalDiagram | None = None


class EducationalContent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief: EducationalBrief
    scenes: list[EducationalScene] = Field(min_length=1, max_length=60)


class EducationalDraft(EducationalContent):
    revision: int = Field(default=1, ge=1)
    research: ResearchReport

    @model_validator(mode="after")
    def valid_citations(self) -> EducationalDraft:
        ids = {s.id for s in self.research.sources}
        if any(source not in ids for scene in self.scenes for source in scene.source_ids):
            raise ValueError("Scene citations must refer to research sources")
        if any(scene.role == "intro" and i != 0 or scene.role == "outro" and i != len(self.scenes) - 1
               for i, scene in enumerate(self.scenes)):
            raise ValueError("Intro/outro roles must be at the beginning/end of the video")
        return self


class DraftUpdate(EducationalContent):
    revision: int = Field(ge=1)


class DraftRevision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: int = Field(ge=1)


class EducationalApproval(BaseModel):
    revision: int
    fingerprint: str


class ReviewResult(BaseModel):
    job_id: str
    revision: int
