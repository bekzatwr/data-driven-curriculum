import copy
import json

from fastapi.testclient import TestClient
import pytest

from backend.app.config import Settings
from backend.app.demo import csv_bytes
from backend.app.main import create_app
from backend.app.validation import RESULT_FIELDS, TOPIC_FIELDS


@pytest.fixture
def sample():
    topics = [
        {"topic_id": "t1", "topic_name": "Дроби", "topic_order": 1, "current_hours": 5,
         "min_hours": 2, "max_hours": 8, "importance": 3, "is_locked": "false"},
        {"topic_id": "t2", "topic_name": "Геометрия", "topic_order": 2, "current_hours": 3,
         "min_hours": 2, "max_hours": 4, "importance": 2, "is_locked": "true"},
    ]
    base = {"student_id": "s1", "school_id": "school1", "class_id": "7A", "teacher_id": "teacher1",
            "textbook_id": "book1", "topic_id": "t1", "test_version": "v1", "stage": "pre",
            "score": 4, "max_score": 10, "tested_at": "2026-09-01"}
    rows = [base, {**base, "stage": "post", "score": 7, "tested_at": "2026-10-01"},
            {**base, "student_id": "s2", "class_id": "7B", "teacher_id": "teacher2",
             "textbook_id": "book2", "stage": "post", "score": 6, "tested_at": "2026-10-01"},
            {**base, "topic_id": "t2"},
            {**base, "topic_id": "t2", "stage": "post", "score": 8, "tested_at": "2026-10-01"}]
    meta = {"name": "Проверка импорта", "subject": "Математика", "grade": 7,
            "period_start": "2026-09-01", "period_end": "2026-10-31"}
    return copy.deepcopy({"rows": rows, "topics": topics, "metadata": meta})


def payload(sample):
    return (csv_bytes(RESULT_FIELDS, sample["rows"]), csv_bytes(TOPIC_FIELDS, sample["topics"]),
            json.dumps(sample["metadata"], ensure_ascii=False))


def send_import(client, sample, *, dry_run=False, error_format="json", raw=None):
    results, curriculum, metadata = raw or payload(sample)
    return client.post("/api/datasets/import", params={"dry_run": str(dry_run).lower(), "error_format": error_format},
                       files={"results_file": ("results.csv", results, "text/csv"),
                              "curriculum_file": ("curriculum.csv", curriculum, "text/csv")},
                       data={"metadata": metadata})


@pytest.fixture
def settings(tmp_path):
    return Settings(database_path=tmp_path / "db.sqlite3")


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as client:
        yield client
