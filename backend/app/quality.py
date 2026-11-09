"""Structural completeness only; educational metrics belong to the analytics module."""
from collections import defaultdict

from .db import Store


def completeness(rows):
    pre = {(r["student_id"], r["topic_id"]) for r in rows if r["stage"] == "pre"}
    post = {(r["student_id"], r["topic_id"]) for r in rows if r["stage"] == "post"}
    pairs = len(pre & post)
    return {
        "students": len({r["student_id"] for r in rows}), "results": len(rows),
        "pre": len(pre), "post": len(post), "pairs": pairs,
        "post_without_pre": len(post - pre), "pre_without_post": len(pre - post),
        "missing_teacher": sum(r["teacher_id"] is None for r in rows),
        "paired_post_share": pairs / len(post) if post else None,
    }


def dataset_quality(store: Store, dataset_id: str):
    dataset = store.get_dataset(dataset_id)
    rows = store.load_results(dataset_id)
    topics = store.get_topics(dataset_id)
    by_topic, by_class = defaultdict(list), defaultdict(list)
    for row in rows:
        by_topic[row["topic_id"]].append(row)
        by_class[(row["school_id"], row["class_id"])].append(row)
    summary = completeness(rows)
    empty_topics = [t["topic_id"] for t in topics if not by_topic[t["topic_id"]]]
    notices = []
    for code, count, message in (
        ("MISSING_PRE", summary["post_without_pre"], "Итоговые записи без входного теста: прирост для них не вычисляется."),
        ("MISSING_POST", summary["pre_without_post"], "Входные записи без итогового теста."),
        ("MISSING_TEACHER", summary["missing_teacher"], "Записи без идентификатора учителя."),
        ("TOPICS_WITHOUT_RESULTS", len(empty_topics), "Темы учебного плана без результатов тестирования."),
    ):
        if count:
            notices.append({"code": code, "count": count, "message": message})
    return {
        "dataset_id": dataset_id, "source_type": dataset["source_type"],
        "content_hash": dataset["content_hash"], "summary": summary,
        "topics_without_results": empty_topics,
        "by_topic": [{"topic_id": t["topic_id"], "topic_name": t["topic_name"],
                      "classes_with_results": len({r["class_id"] for r in by_topic[t["topic_id"]]}),
                      **completeness(by_topic[t["topic_id"]])} for t in topics],
        "by_class": [{"school_id": school, "class_id": class_id,
                      "topics_with_results": len({r["topic_id"] for r in records}),
                      "topics_without_results": len(topics) - len({r["topic_id"] for r in records}),
                      **completeness(records)} for (school, class_id), records in sorted(by_class.items())],
        "notices": notices,
        "definitions": {
            "pairs": "Число пар ученик + тема с pre и post; это не число уникальных учеников.",
            "paired_post_share": "pairs / post в выбранной группе (0–1); null, если post нет.",
            "students": "Уникальные student_id в имеющихся записях; список всех учащихся школы неизвестен.",
            "missing_teacher": "Число строк результатов с teacher_id=null.",
            "scope": "Полнота имеющихся данных, не оценка качества обучения или причинного эффекта.",
        },
    }
