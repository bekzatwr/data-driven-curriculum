import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

Identifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: Identifier
    subject: Identifier
    grade: int = Field(ge=1, le=12, strict=True)
    period_start: date
    period_end: date

    @field_validator("period_start", "period_end", mode="before")
    @classmethod
    def iso_date(cls, value):
        if isinstance(value, date):
            return value
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Use YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def ordered_period(self):
        if self.period_start > self.period_end:
            raise ValueError("period_start must not be after period_end")
        return self


class Topic(BaseModel):
    topic_id: str
    topic_name: str
    topic_order: int
    current_hours: int
    min_hours: int
    max_hours: int
    importance: int
    is_locked: bool


class Result(BaseModel):
    student_id: str
    school_id: str
    class_id: str
    teacher_id: str | None
    textbook_id: str
    topic_id: str
    test_version: str
    stage: Literal["pre", "post"]
    score: float
    max_score: float
    tested_at: str


class Counts(BaseModel):
    students: int
    classes: int
    topics: int
    textbooks: int
    results: int
    pre: int
    post: int
    pairs: int


class Dataset(BaseModel):
    id: str
    metadata: Metadata
    source_type: Literal["upload", "demo"]
    content_hash: str
    created_at: str
    counts: Counts


class ImportResponse(BaseModel):
    valid: bool = True
    dry_run: bool
    created: bool = False
    dataset_id: str | None = None
    dataset: Dataset | None = None
    metadata: Metadata
    counts: Counts
    preview: dict[str, list[dict]]
    warnings: list[dict]


class DatasetList(BaseModel):
    items: list[Dataset]
    total: int
    limit: int
    offset: int


class RecordsPage(BaseModel):
    dataset_id: str
    items: list[Result]
    total: int
    limit: int
    offset: int


class ErrorDetail(BaseModel):
    file: str | None = None
    row: int | None = None
    field: str | None = None
    reason: str


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []
    total_errors: int = 0


class ClassFilter(BaseModel):
    id: str
    school_id: str
    student_count: int


class TextbookFilter(BaseModel):
    id: str
    label: str


class TestVersion(BaseModel):
    topic_id: str
    test_version: str
    max_score: float


class Filters(BaseModel):
    dataset_id: str
    classes: list[ClassFilter]
    textbooks: list[TextbookFilter]
    topics: list[Topic]
    test_versions: list[TestVersion]
