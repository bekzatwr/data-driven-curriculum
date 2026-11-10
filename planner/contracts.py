"""Transport contracts for Aidana's existing P0 implementation; no planning logic."""
from typing import Literal
from pydantic import BaseModel, Field
from .models import Constraint, Settings


class Metric(BaseModel):
    topic_id: str
    mean_post_pct: float | None = Field(ge=0, le=100)
    n_post: int = Field(ge=0)
    single_version: bool
    test_version: str | None
    max_score: float | None


class PlanItem(Constraint):
    mean_post_pct: float | None
    n_post: int
    test_version: str | None
    max_score: float | None
    automatic_eligible: bool
    proposed_hours: int
    delta: int
    reason: str


class SavedItem(PlanItem):
    recommended_hours: int
    recommendation_reason: str
    manually_modified: bool


class Transfer(BaseModel):
    from_topic_id: str
    to_topic_id: str
    hours: int


class AppliedFilters(BaseModel):
    class_ids: list[str]
    test_versions: dict[str, str]


class SourceMetadata(BaseModel):
    name: str
    subject: str
    grade: int
    period_start: str
    period_end: str


class PlanSource(BaseModel):
    id: str
    source_type: Literal['upload', 'demo']
    metadata: SourceMetadata
    counts: dict[str, int]
    # The isolated demo does not contain these database-specific fields.
    content_hash: str | None = None
    created_at: str | None = None


class PlanBase(BaseModel):
    total_hours: int
    dataset_id: str
    class_id: str
    applied_filters: AppliedFilters
    source: PlanSource
    is_demo: bool
    metrics: list[Metric]
    warnings: list[str]
    settings: Settings
    algorithm_version: str


class PlanPreview(PlanBase):
    items: list[PlanItem]
    transfers: list[Transfer]


class SavedPlan(PlanBase):
    plan_id: str
    created_at: str
    items: list[SavedItem]
    manually_modified: bool
    comment: str
    recommendation_transfers: list[Transfer]


class PlanErrorResponse(BaseModel):
    code: str
    message: str
    details: list[dict]
    total_errors: int = 0
