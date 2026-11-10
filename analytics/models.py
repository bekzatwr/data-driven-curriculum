"""Public response schemas. Values remain unrounded; clients format decimals."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class Model(BaseModel):
    model_config = ConfigDict(extra='allow', allow_inf_nan=False)


class Slice(Model):
    test_version: str
    max_score: float


class TopicMetrics(Model):
    topic_id: str
    topic_name: str | None = None
    topic_order: int | None = None
    test_version: str | None
    max_score: float | None
    mean_post_pct: float | None
    below_threshold_share: float | None
    n_post: int
    n_pairs: int
    mean_pre_paired_pct: float | None
    mean_post_paired_pct: float | None
    mean_gain_pp: float | None
    pair_coverage: float | None
    status: Literal['requires_attention', 'needs_practice', 'mastered', 'insufficient_data', 'no_data', 'mixed_versions']
    status_label: str
    problem_topic: bool | None
    single_version: bool
    available_slices: list[Slice]
    warnings: list[str]


class Filters(Model):
    class_ids: list[str]
    textbook_ids: list[str]
    test_version: str | None


class AnalyticsSettings(Model):
    threshold_pct: float
    mastered_pct: float
    min_students: int
    problem_share: float
    max_baseline_gap_pp: float


class Envelope(Model):
    dataset_id: str
    is_demo: bool
    source: dict
    applied_filters: Filters
    settings: AnalyticsSettings
    warnings: list[str]


class ClassMetrics(Model):
    school_id: str
    class_id: str
    metrics: TopicMetrics


class OverviewMetrics(Model):
    n_students: int
    n_post_students: int
    n_post_results: int
    n_pairs: int
    n_paired_students: int
    pair_coverage: float | None
    paired_student_share: float | None
    mean_post_pct: float | None
    n_complete_students: int
    topic_count: int
    n_problem_topics: int
    mixed_topic_ids: list[str]
    warnings: list[str]


class Overview(Envelope):
    metrics: OverviewMetrics
    topics: list[TopicMetrics]
    heatmap: list[ClassMetrics]


class TopicDetail(Envelope):
    metrics: TopicMetrics
    by_class: list[ClassMetrics]
    slices: list[TopicMetrics]


class BookGroup(Model):
    textbook_id: str
    n_post: int
    n_pairs: int
    n_classes: int
    n_teachers: int
    pair_coverage: float | None
    mean_post_pct: float | None
    mean_pre_paired_pct: float | None
    mean_post_paired_pct: float | None
    mean_gain_pp: float | None
    available_slices: list[Slice]


class Comparison(Envelope):
    topic_id: str
    test_version: str | None
    max_score: float | None
    comparison_status: Literal['comparable', 'insufficient_data', 'not_comparable']
    difference_gain_pp: float | None
    baseline_gap_pp: float | None
    group_a: BookGroup
    group_b: BookGroup
    reasons: list[str]
    conclusion: str


class TeacherMetrics(Model):
    teacher_id: str
    school_id: str
    is_missing_teacher: bool
    class_ids: list[str]
    students: int
    textbooks: list[str]
    upcoming_hours: int
    n_post: int
    n_post_students: int
    topic_count: int
    post_topic_count: int
    n_complete_students: int
    complete_student_share: float | None
    mean_post_pct: float | None
    mean_pre_paired_pct: float | None
    mean_post_paired_pct: float | None
    mean_gain_pp: float | None
    n_pairs: int
    n_paired_students: int
    paired_student_share: float | None
    pair_coverage: float | None
    mixed_topic_ids: list[str]
    warnings: list[str]


class TeacherAttribution(Model):
    fully_attributed_students: int = Field(ge=0)
    partially_attributed_students: int = Field(ge=0)
    unattributed_students: int = Field(ge=0)
    fully_attributed_student_share: float | None = Field(ge=0, le=1)
    missing_teacher_rows: int = Field(ge=0)


class SchoolWorkload(Model):
    school_id: str
    teachers: int
    students: int
    classes: int
    teacher_attribution: TeacherAttribution
    students_per_teacher: float | None
    classes_per_teacher: float | None
    hours_per_teacher: float | None


class Teachers(Envelope):
    teachers: list[TeacherMetrics]
    schools: list[SchoolWorkload]
    total: SchoolWorkload
    hours_per_class: int
    missing_teacher_rows: int
    definitions: dict[str, str]


class Error(Model):
    code: str
    message: str
    details: list[dict]
    total_errors: int
