from pydantic import BaseModel, Field, ConfigDict


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectInput(Strict):
    name: str = Field(min_length=1, max_length=100)
    brief: str = Field(default="", max_length=4000)


class Selection(Strict):
    id: str = Field(min_length=1, max_length=80)
    asset_id: str
    moment_id: str | None = None
    start_frame: int = Field(ge=0, strict=True)
    end_frame: int = Field(gt=0, strict=True)
    note: str = Field(default="", max_length=1000)


class Section(Strict):
    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    purpose: str = Field(default="", max_length=1000)
    selections: list[Selection] = Field(default_factory=list, max_length=100)


class BoardInput(Strict):
    revision: int
    sections: list[Section] = Field(max_length=30)


class MomentInput(Strict):
    start_frame: int = Field(ge=0)
    end_frame: int = Field(gt=0)
    description: str = Field(min_length=1, max_length=1000)


class AnalysisInput(Strict):
    asset_ids: list[str] = Field(min_length=1, max_length=30)


class SearchInput(Strict):
    query: str = Field(default="", max_length=1000)
    semantic: bool = False


class FeedbackInput(Strict):
    moment_id: str
    section: str = Field(min_length=1, max_length=1000)
    query: str = Field(default="", max_length=1000)
    rating: int = Field(ge=0, le=2)
    reason: str = Field(default="", max_length=1000)
    footage_group: str = Field(min_length=1, max_length=100)


class Observation(Strict):
    start_seconds: float = Field(ge=0, allow_inf_nan=False)
    end_seconds: float = Field(gt=0, allow_inf_nan=False)
    description: str = Field(min_length=1, max_length=1200)
    uncertainty: str = Field(default="", max_length=500)


class Observations(Strict):
    moments: list[Observation] = Field(max_length=30)


class ProposedSection(Strict):
    title: str = Field(min_length=1, max_length=120)
    purpose: str = Field(min_length=1, max_length=1000)
    candidate_ids: list[str] = Field(max_length=5)


class Proposal(Strict):
    sections: list[ProposedSection] = Field(min_length=1, max_length=8)


class Rerank(Strict):
    candidate_ids: list[str] = Field(max_length=5)
    explanation: str = Field(max_length=1000)
