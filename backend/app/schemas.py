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


class Completeness(BaseModel):
    students: int
    results: int
    pre: int
    post: int
    pairs: int
    post_without_pre: int
    pre_without_post: int
    missing_teacher: int
    paired_post_share: float | None


class TopicQuality(Completeness):
    topic_id: str
    topic_name: str
    classes_with_results: int


class ClassQuality(Completeness):
    class_id: str
    school_id: str
    topics_with_results: int
    topics_without_results: int


class QualityNotice(BaseModel):
    code: str
    count: int
    message: str


class DatasetQuality(BaseModel):
    dataset_id: str
    source_type: Literal["upload", "demo"]
    content_hash: str
    summary: Completeness
    topics_without_results: list[str]
    by_topic: list[TopicQuality]
    by_class: list[ClassQuality]
    notices: list[QualityNotice]
    definitions: dict[str, str]


class PackageTopic(Topic):
    model_config = ConfigDict(strict=True, extra="forbid")


class PackageResult(Result):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class PackageData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    metadata: Metadata
    curriculum: list[PackageTopic] = Field(min_length=1, max_length=100)
    results: list[PackageResult] = Field(min_length=1, max_length=10_000)


class DatasetPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")
    format: Literal["ddc-dataset"]
    version: int = Field(strict=True, ge=1, le=1)
    checksum: str = Field(pattern=r"^[0-9a-f]{64}$")
    data: PackageData


class ApiLimits(BaseModel):
    csv_files_bytes: int
    multipart_body_bytes: int
    package_body_bytes: int
    results_per_dataset: int
    topics_per_dataset: int
    results_per_page: int


class Capabilities(BaseModel):
    version: str
    mode: Literal["local", "read_only_demo"]
    limits: ApiLimits
    features: dict[str, bool]
    links: dict[str, str]
