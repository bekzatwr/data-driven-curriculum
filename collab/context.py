"""Only server-calculated aggregates may cross the provider boundary.

No supplied context values, free text, object names or identifiers are forwarded.
The analytics/planner algorithms remain owned by Toni/Aidana.
"""
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from analytics import api as analytics_api
from backend.app.errors import ApiError
from .storage import validate_target


class Selectors(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    class_ids: list[str] | None = Field(default=None, max_length=100)
    textbook_ids: list[str] | None = Field(default=None, max_length=100)
    test_version: str | None = Field(default=None, min_length=1, max_length=120)
    topic_id: str | None = Field(default=None, min_length=1, max_length=120)
    textbook_a: str | None = Field(default=None, min_length=1, max_length=120)
    textbook_b: str | None = Field(default=None, min_length=1, max_length=120)
    plan_id: str | None = Field(default=None, min_length=1, max_length=120)


METRICS = frozenset({
    "n_students", "n_post_students", "n_post_results", "n_pairs", "n_paired_students",
    "pair_coverage", "paired_student_share", "mean_post_pct", "n_complete_students",
    "topic_count", "n_problem_topics", "max_score", "below_threshold_share", "n_post",
    "mean_pre_paired_pct", "mean_post_paired_pct", "mean_gain_pp", "problem_topic",
    "single_version", "n_classes", "n_teachers", "difference_gain_pp", "baseline_gap_pp",
    "total_hours", "current_hours", "min_hours", "max_hours", "importance", "is_locked",
    "proposed_hours", "recommended_hours", "delta", "manually_modified",
})


def numbers(data):
    return {key: value for key, value in data.items() if key in METRICS
            and (value is None or type(value) in (int, float, bool))}


def build_context(request, dataset_id, kind, context, question):
    if question and question.strip():
        raise ApiError(422, "AI_FREE_TEXT_DISABLED", "Свободный вопрос пока отключён: он может содержать персональные данные или секреты.")
    try:
        selected = Selectors.model_validate(context)
    except ValidationError:
        raise ApiError(422, "AI_CONTEXT_SELECTORS_ONLY", "context принимает только селекторы из API-контракта; показатели рассчитывает сервер.")
    if any(len(value) > 120 or not value.strip() for field in (selected.class_ids, selected.textbook_ids) for value in (field or [])):
        raise ApiError(422, "AI_CONTEXT_SELECTORS_ONLY", "Некорректный селектор.")
    dataset = request.app.state.store.get_dataset(dataset_id)
    if dataset["source_type"] != "demo":
        raise ApiError(403, "AI_DEMO_ONLY", "ИИ разрешён только для встроенного синтетического демонабора.")
    if kind in {"teachers", "comments"}:
        raise ApiError(503, "AI_KIND_NOT_READY", "Этот вид ИИ-пояснения ожидает контракт и методологическое review команды.")
    filters = dict(class_ids=selected.class_ids, textbook_ids=selected.textbook_ids, test_version=selected.test_version)
    result = {"is_demo": True}
    allowed = {"class_ids", "textbook_ids", "test_version"}
    if kind == "overview":
        data = analytics_api.overview(dataset_id, request, **filters)
        result.update(metrics=numbers(data["metrics"]), topics=[
            {"topic_index": index, **numbers(item)} for index, item in enumerate(data["topics"], 1)])
    elif kind == "topic":
        allowed.add("topic_id")
        if not selected.topic_id:
            raise ApiError(422, "AI_SELECTOR_REQUIRED", "Укажите topic_id.")
        data = analytics_api.topic_detail(dataset_id, selected.topic_id, request, **filters)
        result.update(metrics=numbers(data["metrics"]), by_class=[
            {"class_index": index, **numbers(item["metrics"])} for index, item in enumerate(data["by_class"], 1)])
    elif kind == "comparison":
        allowed = {"class_ids", "test_version", "topic_id", "textbook_a", "textbook_b"}
        if not all((selected.topic_id, selected.textbook_a, selected.textbook_b)):
            raise ApiError(422, "AI_SELECTOR_REQUIRED", "Укажите topic_id, textbook_a и textbook_b.")
        data = analytics_api.comparison(dataset_id, request, selected.topic_id, selected.textbook_a,
                                        selected.textbook_b, selected.class_ids, selected.test_version)
        result.update(numbers(data))
        result.update(comparison_status=data["comparison_status"], group_a=numbers(data["group_a"]),
                      group_b=numbers(data["group_b"]))
    elif kind == "plan":
        allowed = {"plan_id"}
        if not selected.plan_id:
            raise ApiError(422, "AI_SELECTOR_REQUIRED", "Укажите plan_id сохранённого плана.")
        with request.app.state.store.connect() as db:
            validate_target(db, dataset_id, "plan", selected.plan_id)
        data = request.app.state.plan_snapshots.get(selected.plan_id)
        result.update(numbers(data))
        result["items"] = [{"topic_index": index, **numbers(item)} for index, item in enumerate(data["items"], 1)]
    if set(context) - allowed:
        raise ApiError(422, "AI_CONTEXT_SELECTORS_ONLY", "Селектор не применим к выбранному kind.")
    return result
