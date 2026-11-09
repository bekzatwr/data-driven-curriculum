"""Deterministic synthetic transport fixture for the demo endpoint, not an analytics model."""
import csv
import io
import json
import random

from .validation import RESULT_FIELDS, TOPIC_FIELDS

METADATA = {
    "name": "Демо: математика, 7 класс", "subject": "Математика", "grade": 7,
    "period_start": "2026-09-01", "period_end": "2026-10-31",
}


def csv_bytes(fields, rows):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def demo_files():
    rng = random.Random(20261109)
    specs = [
        ("fractions", "Дроби", 6, 3, 8, 3, False, 35, 10),
        ("equations", "Уравнения", 5, 3, 8, 3, False, 50, 16),
        ("proportions", "Пропорции", 4, 2, 6, 2, False, 45, 12),
        ("geometry", "Геометрия", 3, 2, 5, 2, True, 60, 14),
        ("statistics", "Статистика", 4, 2, 5, 1, False, 77, 8),
        ("revision", "Повторение", 2, 1, 4, 1, False, 50, 12),
    ]
    topics, results = [], []
    for order, (tid, name, hours, lower, upper, importance, locked, base, gain) in enumerate(specs, 1):
        topics.append(dict(zip(TOPIC_FIELDS, [tid, name, order, hours, lower, upper, importance, str(locked).lower()])))
        for student in range(120):
            group = student // 30
            pre = max(0, min(100, base + rng.randint(-10, 10)))
            post = max(0, min(100, pre + gain + (4 if group < 2 else 0) + rng.randint(-3, 3)))
            for stage, score, day in [("pre", pre, "2026-09-01"), ("post", post, "2026-10-01")]:
                results.append(dict(zip(RESULT_FIELDS, [
                    f"S{student + 1:03d}", "DEMO-SCHOOL", f"7{chr(65 + group)}", f"T{group + 1}",
                    "Учебник A" if group < 2 else "Учебник B", tid, "v1", stage, score, 100, day,
                ])))
    return csv_bytes(RESULT_FIELDS, results), csv_bytes(TOPIC_FIELDS, topics), json.dumps(METADATA, ensure_ascii=False)
