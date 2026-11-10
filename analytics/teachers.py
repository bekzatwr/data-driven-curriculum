"""Descriptive teacher workload for one validated subject/grade dataset.

Result means weight student-topic observations equally, matching the original
teachers UI. This intentionally differs from the pupil-weighted overview mean.
Observed teacher/class links estimate upcoming hours; they are not a timetable,
an employment workload, or a rating of teaching quality.
"""
from collections import defaultdict
from statistics import mean

from .common import normalize_settings, paired_rows, percentage, select_records
from .topics import compute_topics
from .teacher_attribution import summarize_teacher_attribution


MISSING_TEACHER_LABEL = "Не указан"


def _teacher_key(row):
    teacher = row.get("teacher_id")
    # Import already trims identifiers. Preserve a supplied nonblank ID exactly;
    # the display label must never be used as an internal identity or sentinel.
    if teacher is None or not teacher.strip():
        teacher = None
    return row["school_id"], teacher


def compute_teachers(records, topics, filters=None, settings=None):
    """Return the UI-compatible teachers/schools/total summary without mutation.

    Teachers are scoped by school. Missing identities form a separate group in
    each school and never count as a known teacher. School pupil counts include
    all selected observations, including those with an unknown teacher, so
    students_per_teacher is a population ratio, not an average of teacher rows.

    ``n_post`` and ``n_pairs`` count student-topic observations; ``students``
    counts unique pupils over both stages. ``n_paired_students`` counts pupils
    with at least one compatible pair; its share uses ``n_post_students`` as
    the denominator. Pairs require the same teacher group
    at both stages in addition to the shared assessment compatibility rules.
    Paired pre/post means use those same observations as the gain, whereas
    ``mean_post_pct`` also includes final results without a pair.
    Curriculum coverage counts only post records after cohort filters, against
    all unique curriculum topics. ``complete_student_share`` uses pupils with
    at least one post as its denominator, not all observed or enrolled pupils.
    Coverage describes result availability, independently of test comparability;
    it remains defined when mixed versions suppress the numerical means.
    Hours per class always use the complete curriculum, even after filtering.
    """
    settings = normalize_settings(settings)
    topics = list(topics)
    selected = select_records(records, filters)
    # Check uniqueness before splitting by teacher: duplicates assigned to two
    # different teachers must not silently become two independent observations.
    paired_rows(selected)
    hours_per_class = sum(topic["current_hours"] for topic in topics)
    topic_ids = list(dict.fromkeys(topic["topic_id"] for topic in topics))
    topic_positions = {topic: index for index, topic in enumerate(topic_ids)}
    curriculum_topics = set(topic_ids)
    topic_count = len(topic_ids)
    by_teacher = defaultdict(list)
    by_school = defaultdict(list)
    for row in selected:
        by_teacher[_teacher_key(row)].append(row)
        by_school[row["school_id"]].append(row)

    teachers = []
    missing_rows = sum(_teacher_key(row)[1] is None for row in selected)
    for (school, teacher_id), rows in sorted(
        by_teacher.items(), key=lambda item: (item[0][0], item[0][1] is None, item[0][1] or "")
    ):
        posts = [row for row in rows if row["stage"] == "post"]
        pairs = paired_rows(rows)
        # Empty curriculum topics cannot contain mixed assessments. Preserve
        # curriculum order while avoiding one empty metric per teacher/topic.
        observed_topics = {row["topic_id"] for row in rows}
        metric_topics = sorted(observed_topics & curriculum_topics, key=topic_positions.__getitem__)
        metrics = compute_topics(rows, {"topic_ids": metric_topics}, settings)
        mixed = [metric["topic_id"] for metric in metrics if len(metric["available_slices"]) > 1]
        class_ids = sorted({row["class_id"] for row in rows})
        post_topics_by_student = defaultdict(set)
        post_topics = set()
        for post in posts:
            student_topics = post_topics_by_student[post["student_id"]]
            if post["topic_id"] in curriculum_topics:
                student_topics.add(post["topic_id"])
                post_topics.add(post["topic_id"])
        post_students = len(post_topics_by_student)
        complete_students = (sum(len(covered) == topic_count for covered in post_topics_by_student.values())
                             if topic_count else 0)
        paired_students = len({post["student_id"] for _, post in pairs})
        warnings = []
        if teacher_id is None:
            warnings.append("Учитель не указан: это группа записей без установленного учителя, а не отдельный педагог.")
        if mixed:
            warnings.append("В одной или нескольких темах смешаны версии или шкалы теста; средний результат и прирост недоступны. Выберите общий срез.")
        if len(pairs) < len(posts):
            warnings.append("Не у всех итоговых записей есть совместимая пара у того же учителя и школы; прирост учитывает только такие пары.")
        if 0 < post_students < settings["min_students"]:
            warnings.append("Мало данных: показатели описывают небольшую группу и не используются для оценки учителя.")
        if 0 < paired_students < settings["min_students"]:
            warnings.append(
                f"Мало учеников в парной выборке: {paired_students}, порог — {settings['min_students']}. "
                "Прирост остаётся описательным; несколько пар по темам одного ученика не увеличивают число учеников."
            )
        if topic_count and complete_students < post_students:
            warnings.append(
                f"Неполное покрытие учебного плана: итоговые результаты есть по {len(post_topics)} из {topic_count} тем; "
                f"все темы покрыты у {complete_students} из {post_students} учеников с итогом. "
                "Средний балл описывает доступные темы; отсутствие записей не означает отсутствие обучения."
            )
        teachers.append({
            "teacher_id": teacher_id if teacher_id is not None else MISSING_TEACHER_LABEL,
            "school_id": school,
            "is_missing_teacher": teacher_id is None,
            "class_ids": class_ids,
            "students": len({row["student_id"] for row in rows}),
            "textbooks": sorted({row["textbook_id"] for row in rows}),
            "n_post": len(posts),
            "n_post_students": post_students,
            "topic_count": topic_count,
            "post_topic_count": len(post_topics),
            "n_complete_students": complete_students,
            "complete_student_share": complete_students / post_students if post_students and topic_count else None,
            "mean_post_pct": mean(percentage(row) for row in posts) if posts and not mixed else None,
            "n_pairs": len(pairs),
            "n_paired_students": paired_students,
            "paired_student_share": paired_students / post_students if post_students else None,
            "mean_pre_paired_pct": mean(percentage(pre) for pre, _ in pairs) if pairs and not mixed else None,
            "mean_post_paired_pct": mean(percentage(post) for _, post in pairs) if pairs and not mixed else None,
            "mean_gain_pp": mean(percentage(post) - percentage(pre) for pre, post in pairs) if pairs and not mixed else None,
            "pair_coverage": len(pairs) / len(posts) if posts else None,
            "upcoming_hours": len(class_ids) * hours_per_class,
            "mixed_topic_ids": mixed,
            "warnings": warnings,
        })

    def school_summary(school_id, rows, teacher_rows):
        known = [teacher for teacher in teacher_rows if not teacher["is_missing_teacher"]]
        teacher_count = len(known)
        students = len({row["student_id"] for row in rows})
        class_links = sum(len(teacher["class_ids"]) for teacher in known)
        return {
            "school_id": school_id,
            "teachers": teacher_count,
            "students": students,
            "classes": len({(row["school_id"], row["class_id"]) for row in rows}),
            "teacher_attribution": summarize_teacher_attribution(rows),
            "students_per_teacher": students / teacher_count if teacher_count else None,
            "classes_per_teacher": class_links / teacher_count if teacher_count else None,
            "hours_per_teacher": class_links * hours_per_class / teacher_count if teacher_count else None,
        }

    warnings = [
        "Нагрузка относится только к предмету, параллели и выбранным записям набора; это не полная ставка или фактическое расписание учителя.",
        "Результаты и прирост описывают учеников; они не оценивают качество работы учителя и не доказывают причинного влияния преподавания или учебника.",
    ]
    if missing_rows:
        warnings.append("Часть записей не связана с известным учителем. Их ученики и классы входят в итоги школы; неизвестные учителя исключены из числа учителей и связей учитель–класс. Средние отношения отражают неполную атрибуцию.")
    class_teachers = defaultdict(set)
    for (school, teacher), rows in by_teacher.items():
        if teacher is not None:
            for row in rows:
                class_teachers[(school, row["class_id"])].add(teacher)
    if any(len(ids) > 1 for ids in class_teachers.values()):
        warnings.append("Один класс связан с несколькими учителями: его часы учитываются у каждого. Сумма нагрузки учителей не равна уникальным часам классов и не подтверждает совместное преподавание или назначение на будущий период.")
    teachers_by_school = defaultdict(list)
    for teacher in teachers:
        teachers_by_school[teacher["school_id"]].append(teacher)
    return {
        "teachers": teachers,
        "schools": [school_summary(school, rows, teachers_by_school[school])
                    for school, rows in sorted(by_school.items())],
        "total": school_summary("Все школы", selected, teachers),
        "hours_per_class": hours_per_class,
        "missing_teacher_rows": missing_rows,
        "warnings": warnings,
    }
