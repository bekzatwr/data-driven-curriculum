"""Validate a complete upload before any database write takes place."""
import csv
import hashlib
import io
import json
import math
import re
from dataclasses import dataclass
from datetime import date

from pydantic import ValidationError

from .config import Settings
from .errors import ApiError
from .schemas import Metadata

RESULT_FIELDS = (
    "student_id", "school_id", "class_id", "teacher_id", "textbook_id", "topic_id",
    "test_version", "stage", "score", "max_score", "tested_at",
)
TOPIC_FIELDS = (
    "topic_id", "topic_name", "topic_order", "current_hours", "min_hours",
    "max_hours", "importance", "is_locked",
)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class ValidatedUpload:
    metadata: dict
    topics: list[dict]
    results: list[dict]
    counts: dict
    warnings: list[dict]
    content_hash: str
    source_type: str


def validate_upload(results_bytes: bytes, topics_bytes: bytes, metadata_json: str,
                    settings: Settings, source_type="upload", *, enforce_csv_size=True) -> ValidatedUpload:
    if enforce_csv_size and len(results_bytes) + len(topics_bytes) > settings.max_upload_bytes:
        raise ApiError(413, "UPLOAD_TOO_LARGE", "Суммарный размер CSV превышает 10 МБ.")
    errors = []

    def error(file, row, field, reason):
        errors.append({"file": file, "row": row, "field": field, "reason": reason})

    try:
        meta = Metadata.model_validate_json(metadata_json)
    except ValidationError as exc:
        for e in exc.errors(include_input=False, include_url=False, include_context=False):
            error("metadata", None, ".".join(str(x) for x in e["loc"]) or "metadata", e["msg"])
        raise ApiError(422, "INVALID_METADATA", "Проверьте параметры набора.", errors) from None

    def read_csv(payload, file, fields, limit):
        try:
            text = payload.decode("utf-8-sig")
        except UnicodeDecodeError:
            error(file, None, None, "Требуется кодировка UTF-8.")
            return []
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        rows = []
        try:
            header = next(reader, None)
            if header is None:
                error(file, 1, None, "Файл пуст; нужны заголовок и строки данных.")
                return []
            header = [x.strip() for x in header]
            if len(set(header)) != len(header):
                error(file, 1, None, "Заголовки столбцов повторяются.")
                return []
            if set(header) != set(fields):
                missing = sorted(set(fields) - set(header))
                reason = "Неверные столбцы; разделитель должен быть запятой."
                if missing:
                    reason += " Отсутствуют: " + ", ".join(missing) + "."
                if set(header) - set(fields):
                    reason += " Удалите лишние столбцы; используйте шаблон."
                error(file, 1, None, reason)
                return []
            for values in reader:
                if not values:
                    continue
                if len(rows) >= limit:
                    error(file, reader.line_num, None, f"Допустимо не более {limit} строк.")
                    break
                if len(values) != len(header):
                    error(file, reader.line_num, None, "Число значений не совпадает с заголовком.")
                    # Count malformed records towards the row limit too.
                    rows.append((reader.line_num, None))
                else:
                    rows.append((reader.line_num, dict(zip(header, (x.strip() for x in values)))))
        except csv.Error:
            error(file, reader.line_num, None, "Некорректный CSV: проверьте кавычки и длину поля.")
        if not rows:
            error(file, None, None, "В файле нет строк данных.")
        return [(line, row) for line, row in rows if row is not None]

    def string(value, file, line, field, optional=False):
        if optional and not value:
            return None
        if not value or len(value) > 120 or any(ord(c) < 32 for c in value):
            error(file, line, field, "Нужно непустое значение до 120 символов без управляющих знаков.")
        return value

    def integer(value, file, line, field):
        if not re.fullmatch(r"\d{1,9}", value):
            error(file, line, field, "Нужно целое неотрицательное число (до 9 цифр).")
            return None
        return int(value)

    def number(value, file, line, field):
        if len(value) > 40 or not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?", value):
            error(file, line, field, "Нужно конечное число; дробный разделитель — точка.")
            return None
        result = float(value)
        if not math.isfinite(result):
            error(file, line, field, "Число выходит за допустимый диапазон.")
            return None
        return result if result else 0.0

    topics = []
    topic_ids, orders = {}, {}
    for line, row in read_csv(topics_bytes, "curriculum.csv", TOPIC_FIELDS, settings.max_topics):
        initial = len(errors)
        item = {field: string(row[field], "curriculum.csv", line, field) for field in ("topic_id", "topic_name")}
        for field in ("topic_order", "current_hours", "min_hours", "max_hours", "importance"):
            item[field] = integer(row[field], "curriculum.csv", line, field)
        if row["is_locked"].lower() not in {"true", "false"}:
            error("curriculum.csv", line, "is_locked", "Допустимы true и false.")
        item["is_locked"] = row["is_locked"].lower() == "true"
        if all(item[x] is not None for x in ("min_hours", "current_hours", "max_hours")):
            if not item["min_hours"] <= item["current_hours"] <= item["max_hours"]:
                error("curriculum.csv", line, "current_hours", "Нужно min_hours ≤ current_hours ≤ max_hours.")
        if item["importance"] not in (1, 2, 3):
            error("curriculum.csv", line, "importance", "Важность должна быть 1, 2 или 3.")
        for value, seen, field in [(item["topic_id"], topic_ids, "topic_id"), (item["topic_order"], orders, "topic_order")]:
            if value in seen:
                error("curriculum.csv", line, field, f"Повтор значения из строки {seen[value]}.")
            seen[value] = line
        if len(errors) == initial:
            topics.append(item)

    results, by_key, students, classes, scales = [], {}, {}, {}, {}
    for line, row in read_csv(results_bytes, "results.csv", RESULT_FIELDS, settings.max_results):
        initial = len(errors)
        item = {field: string(row[field], "results.csv", line, field, field == "teacher_id") for field in RESULT_FIELDS[:7]}
        item["stage"] = row["stage"]
        if item["stage"] not in {"pre", "post"}:
            error("results.csv", line, "stage", "Допустимы pre и post.")
        for field in ("score", "max_score"):
            item[field] = number(row[field], "results.csv", line, field)
        if item["score"] is not None and item["max_score"] is not None:
            if item["max_score"] <= 0:
                error("results.csv", line, "max_score", "Максимальный балл должен быть больше нуля.")
            if item["score"] < 0 or item["score"] > item["max_score"]:
                error("results.csv", line, "score", "Нужно 0 ≤ score ≤ max_score.")
        item["tested_at"] = row["tested_at"]
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["tested_at"]):
                raise ValueError
            tested = date.fromisoformat(row["tested_at"])
            if not meta.period_start <= tested <= meta.period_end:
                error("results.csv", line, "tested_at", "Дата не входит в период набора.")
        except ValueError:
            error("results.csv", line, "tested_at", "Нужна существующая дата YYYY-MM-DD.")
        if item["topic_id"] not in topic_ids:
            error("results.csv", line, "topic_id", "Тема отсутствует в curriculum.csv.")
        key = (item["student_id"], item["topic_id"], item["stage"])
        if key in by_key:
            error("results.csv", line, "student_id,topic_id,stage", f"Повтор результата из строки {by_key[key][0]}.")
        if len(errors) != initial:
            continue
        membership = (item["school_id"], item["class_id"])
        if item["student_id"] in students and students[item["student_id"]] != membership:
            error("results.csv", line, "student_id", "Ученик относится к разным школам или классам.")
        students[item["student_id"]] = membership
        if item["class_id"] in classes and classes[item["class_id"]] != item["school_id"]:
            error("results.csv", line, "class_id", "Код класса должен относиться к одной школе.")
        classes[item["class_id"]] = item["school_id"]
        scale_key = (item["topic_id"], item["test_version"])
        if scale_key in scales and scales[scale_key] != item["max_score"]:
            error("results.csv", line, "max_score", "У одной версии теста по теме разные шкалы.")
        scales[scale_key] = item["max_score"]
        by_key[key] = (line, item)
        results.append(item)

    pairs = 0
    missing_pre = 0
    for (student, topic, stage), (line, post) in by_key.items():
        if stage != "post":
            continue
        before = by_key.get((student, topic, "pre"))
        if before is None:
            missing_pre += 1
            continue
        pre = before[1]
        for field in ("textbook_id", "test_version", "max_score"):
            if pre[field] != post[field]:
                error("results.csv", line, field, f"Не совпадает с входным тестом в строке {before[0]}.")
        if pre["tested_at"] > post["tested_at"]:
            error("results.csv", line, "tested_at", "Входной тест позже итогового.")
        pairs += 1
    if errors:
        raise ApiError(422, "INVALID_DATASET", "Набор не сохранён. Исправьте ошибки в файлах.", errors)
    warnings = []
    if missing_pre:
        warnings.append({"code": "MISSING_PRE", "count": missing_pre,
                         "message": "Итоговые результаты без входного теста не входят в прирост."})
    missing_teacher = sum(x["teacher_id"] is None for x in results)
    if missing_teacher:
        warnings.append({"code": "MISSING_TEACHER", "count": missing_teacher,
                         "message": "Для части результатов не указан учитель."})
    topics.sort(key=lambda x: x["topic_order"])
    results.sort(key=lambda x: (x["student_id"], x["topic_id"], x["stage"]))
    metadata = meta.model_dump(mode="json")
    payload = {"metadata": metadata, "topics": topics, "results": results, "source_type": source_type}
    counts = {
        "students": len(students), "classes": len(classes), "topics": len(topics),
        "textbooks": len({x["textbook_id"] for x in results}), "results": len(results),
        "pre": sum(x["stage"] == "pre" for x in results),
        "post": sum(x["stage"] == "post" for x in results), "pairs": pairs,
    }
    return ValidatedUpload(metadata, topics, results, counts, warnings,
                           hashlib.sha256(canonical(payload).encode()).hexdigest(), source_type)
