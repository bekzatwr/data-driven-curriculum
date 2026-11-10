"""Paired, descriptive textbook comparisons for one validated dataset.

Dataset metadata fixes subject, grade and period. The HTTP adapter applies class
and test-version filters before calling this module. No database or HTTP imports
are needed here, and no causal interpretation is produced.
"""
from math import isclose
from statistics import mean

from .common import AnalyticsError, normalize_settings, paired_rows, percentage


DISCLAIMER = (
    "Сравнение описывает эти группы; оно не доказывает причинное влияние учебника. "
    "Различия могут зависеть от преподавания, состава групп и условий обучения."
)


def _group(rows, textbook_id):
    pairs = paired_rows(rows)
    post = [row for row in rows if row["stage"] == "post"]
    scales = sorted({(row["test_version"], row["max_score"]) for row in rows})
    single = len(scales) == 1
    # Teachers describe both stages of the paired population. Import permits
    # different teacher IDs across pre/post; it does not establish staff changes.
    paired_post = [right for _, right in pairs]
    teachers = {(row["school_id"], row["teacher_id"]) for pair in pairs for row in pair if row.get("teacher_id")}
    different_teacher_ids = sum(
        bool(pre.get("teacher_id") and post.get("teacher_id"))
        and (pre["school_id"], pre["teacher_id"]) != (post["school_id"], post["teacher_id"])
        for pre, post in pairs
    )
    classes = {(row["school_id"], row["class_id"]) for row in paired_post}
    n_post = len({row["student_id"] for row in post})
    group = {
        "textbook_id": textbook_id,
        "n_post": n_post,
        "n_pairs": len(pairs),
        "n_classes": len(classes),
        "n_teachers": len(teachers),
        "pair_coverage": len(pairs) / n_post if n_post else None,
        "mean_post_pct": mean(percentage(row) for row in post) if post and single else None,
        "mean_pre_paired_pct": mean(percentage(left) for left, _ in pairs) if pairs and single else None,
        "mean_post_paired_pct": mean(percentage(right) for _, right in pairs) if pairs and single else None,
        "mean_gain_pp": mean(percentage(right) - percentage(left) for left, right in pairs) if pairs and single else None,
        "available_slices": [{"test_version": version, "max_score": maximum} for version, maximum in scales],
    }
    warnings = []
    if len(classes) == 1:
        warnings.append(f"{textbook_id}: парная выборка представлена одним классом; влияние учебника нельзя отделить от особенностей класса.")
    if len(teachers) == 1:
        warnings.append(f"{textbook_id}: в парной выборке указан один известный идентификатор учителя в рамках школы; влияние учебника нельзя отделить от особенностей преподавания.")
    if different_teacher_ids:
        warnings.append(
            f"{textbook_id}: совместимых пар с различающимися указанными идентификаторами учителя на pre/post: {different_teacher_ids}. "
            "Это не подтверждает фактическую смену преподавателя."
        )
    if any(not row.get("teacher_id") for row in rows):
        warnings.append(f"{textbook_id}: идентификатор учителя указан не для всех результатов; число известных учителей неполно.")
    if n_post > len(pairs):
        warnings.append(f"{textbook_id}: {n_post - len(pairs)} итоговых результатов без совместимой пары исключены из прироста.")
    if len(scales) > 1:
        warnings.append(f"{textbook_id}: несколько версий теста или шкал; выберите единый срез. Средние не объединяются.")
    return group, scales, warnings


def compare_textbooks(records, topic_id, book_a, book_b, settings=None):
    """Return paired group statistics and a comparison only when rules permit it.

``difference_gain_pp`` is A minus B and is null for every non-comparable
result. Individual gains, including negative gains, remain descriptive values.
An overlapping student across the two books is an invalid request, even if the
overlap contains only unmatched tests.
    """
    settings = normalize_settings(settings)
    if book_a == book_b:
        raise AnalyticsError("SAME_TEXTBOOK", "Для сравнения выберите два разных учебника.",
                             [{"field": "textbook_b", "reason": "Совпадает с textbook_a"}])
    rows = [row for row in records if row["topic_id"] == topic_id]
    rows_a = [row for row in rows if row["textbook_id"] == book_a]
    rows_b = [row for row in rows if row["textbook_id"] == book_b]
    overlap = {row["student_id"] for row in rows_a} & {row["student_id"] for row in rows_b}
    if overlap:
        raise AnalyticsError("OVERLAPPING_STUDENTS", "Один ученик встречается в обеих группах по выбранной теме.",
                             [{"field": "student_id", "reason": "Группы должны быть непересекающимися", "count": len(overlap)}])
    group_a, scales_a, warnings_a = _group(rows_a, book_a)
    group_b, scales_b, warnings_b = _group(rows_b, book_b)
    reasons = []
    incompatible = False
    insufficient = False
    for group, scales in ((group_a, scales_a), (group_b, scales_b)):
        book = group["textbook_id"]
        if group["n_pairs"] < settings["min_students"]:
            insufficient = True
            reasons.append(f"{book}: {group['n_pairs']} пар; для сопоставления требуется не менее {settings['min_students']}.")
        if group["n_pairs"] == 0 and group["n_post"]:
            reasons.append(f"{book}: нет совместимых входных и итоговых результатов; прирост недоступен.")
        if len(scales) > 1:
            incompatible = True
            reasons.append(f"{book}: смешаны версии теста или шкалы; выберите общий срез.")
    common_scale = len(scales_a) == len(scales_b) == 1 and scales_a[0] == scales_b[0]
    if scales_a and scales_b and not common_scale:
        incompatible = True
        reasons.append("У групп нет единой выбранной версии теста и шкалы max_score.")

    baseline_gap = None
    if common_scale and group_a["mean_pre_paired_pct"] is not None and group_b["mean_pre_paired_pct"] is not None:
        baseline_gap = abs(group_a["mean_pre_paired_pct"] - group_b["mean_pre_paired_pct"])
        limit = settings["max_baseline_gap_pp"]
        if baseline_gap > limit and not isclose(baseline_gap, limit, rel_tol=0, abs_tol=1e-12):
            incompatible = True
            reasons.append(f"Разрыв средних входных результатов {baseline_gap:.1f} п.п. превышает допустимые {limit:g} п.п.")

    status = "not_comparable" if incompatible else "insufficient_data" if insufficient else "comparable"
    difference = group_a["mean_gain_pp"] - group_b["mean_gain_pp"] if status == "comparable" else None
    if difference is not None and isclose(difference, 0, rel_tol=0, abs_tol=1e-12):
        # Match the tie explanation: remove only floating-point cancellation
        # noise in the final difference, without rounding underlying metrics.
        difference = 0.0
    if difference is None:
        conclusion = "Сопоставимый вывод о разнице приростов недоступен. Проверьте причины ограничения."
    elif isclose(difference, 0, rel_tol=0, abs_tol=1e-12):
        conclusion = "Одинаковый наблюдаемый прирост."
    elif difference > 0:
        conclusion = f"В выбранных данных у группы A ({book_a}) наблюдаемый прирост выше на {difference:.1f} п.п."
    else:
        conclusion = f"В выбранных данных у группы B ({book_b}) наблюдаемый прирост выше на {abs(difference):.1f} п.п."
    return {
        "topic_id": topic_id,
        "test_version": scales_a[0][0] if common_scale else None,
        "max_score": scales_a[0][1] if common_scale else None,
        "comparison_status": status,
        "difference_gain_pp": difference,
        "baseline_gap_pp": baseline_gap,
        "group_a": group_a,
        "group_b": group_b,
        "reasons": reasons,
        "warnings": [DISCLAIMER, *warnings_a, *warnings_b],
        "conclusion": conclusion,
    }
