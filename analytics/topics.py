"""Topic and overview metrics, with explicit missing data and cohort boundaries."""

from collections import defaultdict
from statistics import mean

from .common import normalize_settings, paired_rows, percentage, select_records


STATUS_LABELS = {
    "requires_attention": "Требует внимания",
    "needs_practice": "Нужно закрепление",
    "mastered": "Освоено",
    "insufficient_data": "Мало данных",
    "no_data": "Нет данных",
    "mixed_versions": "Выберите версию теста",
}


def _topic_metric(topic_id, rows, settings):
    pairs = paired_rows(rows)
    post = [row for row in rows if row["stage"] == "post"]
    scales = sorted({(row["test_version"], row["max_score"]) for row in rows})
    single = len(scales) == 1
    n_post = len(post)
    warnings = []
    if len(pairs) < n_post:
        warnings.append("Часть итоговых результатов не имеет совместимой пары pre/post; прирост рассчитан только по парам.")
    if len(scales) > 1:
        warnings.append("В теме несколько версий или шкал теста; объединённые средние недоступны. Выберите общий срез.")
    post_mean = mean(percentage(row) for row in post) if post and single else None
    below = sum(percentage(row) < settings["threshold_pct"] for row in post) / n_post if post and single else None
    if not post:
        status, problem = "no_data", None
    elif not single:
        status, problem = "mixed_versions", None
    elif n_post < settings["min_students"]:
        status, problem = "insufficient_data", False
        warnings.append("Мало данных: автоматическая рекомендация по теме не формируется.")
    else:
        if post_mean < settings["threshold_pct"]:
            status = "requires_attention"
        elif post_mean < settings["mastered_pct"]:
            status = "needs_practice"
        else:
            status = "mastered"
        problem = post_mean < settings["threshold_pct"] or below >= settings["problem_share"]
    return {
        "topic_id": topic_id,
        "test_version": scales[0][0] if single else None,
        "max_score": scales[0][1] if single else None,
        "mean_post_pct": post_mean,
        "below_threshold_share": below,
        "n_post": n_post,
        "n_pairs": len(pairs),
        "mean_pre_paired_pct": mean(percentage(pre) for pre, _ in pairs) if pairs and single else None,
        "mean_post_paired_pct": mean(percentage(end) for _, end in pairs) if pairs and single else None,
        "mean_gain_pp": mean(percentage(end) - percentage(pre) for pre, end in pairs) if pairs and single else None,
        "pair_coverage": len(pairs) / n_post if n_post else None,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "problem_topic": problem,
        "warnings": warnings,
        "single_version": single,
        "available_slices": [{"test_version": version, "max_score": maximum} for version, maximum in scales],
    }


def compute_topics(records, filters=None, settings=None):
    """Return one metric per selected curriculum topic in stable input order.

    ``filters.topic_ids`` can include topics without observations. Different test
    versions/scales never share a numerical mean, even with identical maxima.
    """
    settings = normalize_settings(settings)
    selected = select_records(records, filters)
    by_topic = defaultdict(list)
    for row in selected:
        by_topic[row["topic_id"]].append(row)
    ids = (filters or {}).get("topic_ids")
    if ids is None:
        ids = sorted(by_topic)
    return [_topic_metric(topic, by_topic[topic], settings) for topic in dict.fromkeys(ids)]


def compute_overview(records, topic_ids, filters=None, settings=None):
    """Average each pupil first so pupils with more tested topics weigh equally.

    ``n_pairs`` counts student-topic pairs, not unique students. ``pair_coverage``
    divides that count by post records. ``n_paired_students`` counts unique
    pupils with at least one compatible pair; ``paired_student_share`` divides
    it by unique pupils with at least one post, or is null when there are none.
    Complete-topic coverage refers to the provided curriculum topic list after
    cohort filters.
    A mixed-version topic makes the overall mean undefined until a slice is
    chosen, rather than silently changing the overview population.
    """
    topic_ids = list(dict.fromkeys(topic_ids))
    filters = {**(filters or {}), "topic_ids": topic_ids}
    selected = select_records(records, filters)
    metrics = compute_topics(selected, {"topic_ids": topic_ids}, settings)
    posts = [row for row in selected if row["stage"] == "post"]
    pairs = paired_rows(selected)
    n_paired_students = len({post["student_id"] for _, post in pairs})
    scores = defaultdict(list)
    covered = defaultdict(set)
    for row in posts:
        scores[row["student_id"]].append(percentage(row))
        covered[row["student_id"]].add(row["topic_id"])
    mixed_topics = [item["topic_id"] for item in metrics if item["status"] == "mixed_versions"]
    warnings = []
    n_complete = sum(len(topics) == len(topic_ids) for topics in covered.values())
    if scores and n_complete < len(scores):
        warnings.append("Средний балл описывает доступные темы каждого ученика; покрытие всех тем неполное.")
    if mixed_topics:
        warnings.append("Общий средний балл недоступен: выберите единый срез в темах с несколькими версиями или шкалами.")
    return {
        "n_students": len({row["student_id"] for row in selected}),
        "n_post_students": len(scores),
        "n_post_results": len(posts),
        "n_pairs": len(pairs),
        "pair_coverage": len(pairs) / len(posts) if posts else None,
        "n_paired_students": n_paired_students,
        "paired_student_share": n_paired_students / len(scores) if scores else None,
        "mean_post_pct": mean(mean(values) for values in scores.values()) if scores and not mixed_topics else None,
        "n_complete_students": n_complete,
        "topic_count": len(topic_ids),
        "n_problem_topics": sum(item["problem_topic"] is True for item in metrics),
        "mixed_topic_ids": mixed_topics,
        "warnings": warnings,
    }
