"""Shared, HTTP/database-independent rules for validated assessment records."""

from collections.abc import Mapping
from math import isfinite


DEFAULT_SETTINGS = {
    "threshold_pct": 60.0,
    "mastered_pct": 80.0,
    "min_students": 10,
    "problem_share": 0.4,
    "max_baseline_gap_pp": 10.0,
}


class AnalyticsError(ValueError):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or []


def normalize_settings(settings=None):
    """Validate prototype thresholds; never lower the minimum cohort below ten."""
    if settings is not None and hasattr(settings, "model_dump"):
        settings = settings.model_dump()
    if settings is not None and not isinstance(settings, Mapping):
        raise AnalyticsError("INVALID_SETTINGS", "Настройки должны быть объектом.")
    supplied = dict(settings or {})
    unknown = set(supplied) - set(DEFAULT_SETTINGS)
    if unknown:
        raise AnalyticsError("INVALID_SETTINGS", "Неизвестные настройки: " + ", ".join(sorted(unknown)))
    result = {**DEFAULT_SETTINGS, **supplied}
    for name in ("threshold_pct", "mastered_pct", "problem_share", "max_baseline_gap_pp"):
        value = result[name]
        upper = 1 if name == "problem_share" else 100
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) or not 0 <= value <= upper:
            raise AnalyticsError("INVALID_SETTINGS", f"{name}: ожидается число от 0 до {upper}.")
    minimum = result["min_students"]
    if isinstance(minimum, bool) or not isinstance(minimum, int) or minimum < 10:
        raise AnalyticsError("INVALID_SETTINGS", "min_students: ожидается целое число не меньше 10.")
    if result["threshold_pct"] > result["mastered_pct"]:
        raise AnalyticsError("INVALID_SETTINGS", "Порог освоения не может быть ниже порога низкого результата.")
    return result


def select_records(records, filters=None):
    """Apply the same cohort filters to pre and post records without mutating input."""
    filters = filters or {}
    classes = set(filters.get("class_ids") or [])
    books = set(filters.get("textbook_ids") or [])
    topics = set(filters["topic_ids"]) if filters.get("topic_ids") is not None else None
    version = filters.get("test_version")
    return [
        row for row in records
        if (not classes or row["class_id"] in classes)
        and (not books or row["textbook_id"] in books)
        and (topics is None or row["topic_id"] in topics)
        and (version is None or row["test_version"] == version)
    ]


def percentage(row):
    return 100 * row["score"] / row["max_score"]


def paired_rows(records):
    """Return compatible pre/post pairs; reject duplicates instead of overwriting.

    Import validates the record schema and score range. The analytics boundary
    still guards uniqueness because silent dictionary overwrites change weights.
    Mismatched pairs remain valid descriptive post observations, but never gains.
    """
    stages = {}
    for row in records:
        key = (row["student_id"], row["topic_id"], row["stage"])
        if key in stages:
            raise AnalyticsError(
                "DUPLICATE_RESULT", "Повторный результат ученика по теме и этапу.",
                [{"student_id": key[0], "topic_id": key[1], "stage": key[2]}],
            )
        if row["stage"] not in {"pre", "post"}:
            raise AnalyticsError("INVALID_RECORDS", "Неизвестный этап тестирования.")
        stages[key] = row
    result = []
    matching_fields = ("textbook_id", "test_version", "max_score", "school_id", "class_id")
    for (student, topic, stage), post in stages.items():
        if stage != "post":
            continue
        pre = stages.get((student, topic, "pre"))
        if pre is not None and all(pre.get(field) == post.get(field) for field in matching_fields):
            result.append((pre, post))
    return result
