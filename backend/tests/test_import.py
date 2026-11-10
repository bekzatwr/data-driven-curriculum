import copy
import csv
from dataclasses import replace
import io
import json

from fastapi.testclient import TestClient
import pytest

from backend.app.demo import csv_bytes
from backend.app.errors import ApiError
from backend.app.main import create_app
from backend.app.validation import RESULT_FIELDS, TOPIC_FIELDS, validate_upload
from .conftest import payload, send_import


def test_preview_commit_repeat_and_persistence(client, sample, settings):
    preview = send_import(client, sample, dry_run=True)
    assert preview.status_code == 200
    assert preview.json()["dataset_id"] is None
    assert preview.json()["counts"] == {"students": 2, "classes": 2, "topics": 2, "textbooks": 2,
                                         "results": 5, "pre": 2, "post": 3, "pairs": 2}
    assert preview.json()["warnings"][0]["code"] == "MISSING_PRE"
    assert client.get("/api/datasets").json()["total"] == 0
    saved = send_import(client, sample)
    assert saved.status_code == 201
    dataset_id = saved.json()["dataset_id"]
    assert saved.json()["created"] is True
    repeated = send_import(client, sample)
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False
    assert repeated.json()["dataset_id"] == dataset_id
    # Reordering records/columns, BOM and numerical notation don't duplicate a dataset.
    rows = [{**r, "score": float(r["score"])} for r in reversed(sample["rows"])]
    raw = (b"\xef\xbb\xbf" + csv_bytes(tuple(reversed(RESULT_FIELDS)), rows),
           csv_bytes(TOPIC_FIELDS, list(reversed(sample["topics"]))), payload(sample)[2])
    assert send_import(client, sample, raw=raw).json()["dataset_id"] == dataset_id
    with TestClient(create_app(settings)) as reopened:
        assert reopened.get(f"/api/datasets/{dataset_id}").json()["counts"]["results"] == 5
        assert reopened.get(f"/api/datasets/{dataset_id}/results").json()["total"] == 5


@pytest.mark.parametrize("field,value", [
    ("student_id", ""), ("school_id", ""), ("topic_id", "unknown"), ("stage", "before"),
    ("score", ""), ("score", "NaN"), ("score", "Infinity"), ("score", "1e999"),
    ("score", "-1"), ("score", "11"), ("score", "4,5"), ("max_score", "0"),
    ("tested_at", "2026-02-30"), ("tested_at", "2025-09-01"), ("tested_at", "01.09.2026"),
    ("student_id", "s" * 121), ("class_id", "class\x00id"),
])
def test_bad_result_rejects_entire_dataset(client, sample, field, value):
    sample["rows"][0][field] = value
    response = send_import(client, sample)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_DATASET"
    assert any(d["field"] == field and d["row"] == 2 for d in response.json()["details"])
    assert client.get("/api/datasets").json()["total"] == 0


@pytest.mark.parametrize("field,value", [("current_hours", 10), ("min_hours", -1),
    ("current_hours", "2.5"), ("importance", 4), ("is_locked", "yes"), ("topic_order", ""),
    ("topic_name", "")])
def test_bad_topic_rejected(client, sample, field, value):
    sample["topics"][0][field] = value
    response = send_import(client, sample)
    assert response.status_code == 422
    assert any(d["file"] == "curriculum.csv" and d["field"] == field for d in response.json()["details"])
    assert client.get("/api/datasets").json()["total"] == 0


@pytest.mark.parametrize("change", ["duplicate_result", "duplicate_topic", "duplicate_order", "student_class",
                                        "class_school", "pair_version", "pair_book", "scale", "date_order"])
def test_cross_record_consistency(client, sample, change):
    if change == "duplicate_result":
        sample["rows"].append(copy.deepcopy(sample["rows"][0]))
    elif change == "duplicate_topic":
        sample["topics"].append({**sample["topics"][0], "topic_order": 3})
    elif change == "duplicate_order":
        sample["topics"][1]["topic_order"] = 1
    elif change == "student_class":
        sample["rows"][1]["class_id"] = "7C"
    elif change == "class_school":
        sample["rows"][2].update(class_id="7A", school_id="school2")
    elif change == "pair_version":
        sample["rows"][1]["test_version"] = "v2"
    elif change == "pair_book":
        sample["rows"][1]["textbook_id"] = "book2"
    elif change == "scale":
        sample["rows"][2]["max_score"] = 100
    else:
        sample["rows"][0]["tested_at"] = "2026-10-20"
    assert send_import(client, sample).status_code == 422
    assert client.get("/api/datasets").json()["total"] == 0


@pytest.mark.parametrize("change", ["bad_encoding", "semicolon", "duplicate_header", "unknown_column",
                                        "short_row", "unclosed_quote", "empty", "headers_only"])
def test_csv_structure_rejected(client, sample, change):
    results, topics, metadata = payload(sample)
    lines = results.decode().splitlines()
    if change == "bad_encoding":
        results = results + b"\xff"
    elif change == "semicolon":
        results = results.replace(b",", b";")
    elif change == "duplicate_header":
        results = results.replace(b"school_id", b"student_id", 1)
    elif change == "unknown_column":
        results = results.replace(b"school_id", b"extra", 1)
    elif change == "short_row":
        results = (lines[0] + "\ns1,school1\n").encode()
    elif change == "unclosed_quote":
        results = (lines[0] + '\n"s1,school1\n').encode()
    elif change == "empty":
        results = b""
    else:
        results = (lines[0] + "\n").encode()
    assert send_import(client, sample, raw=(results, topics, metadata)).status_code == 422


@pytest.mark.parametrize("patch", [{"grade": "7"}, {"grade": True}, {"grade": 13}, {"unknown": "x"},
    {"name": ""}, {"period_end": "2026-08-31"}, {"period_start": "2026/09/01"}])
def test_invalid_metadata(client, sample, patch):
    sample["metadata"].update(patch)
    response = send_import(client, sample)
    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_METADATA"


def test_optional_teacher_and_zero_score_are_preserved(client, sample):
    sample["rows"][0].update(teacher_id="", score=0)
    response = send_import(client, sample)
    assert response.status_code == 201
    assert {w["code"] for w in response.json()["warnings"]} == {"MISSING_PRE", "MISSING_TEACHER"}
    records = client.get(f'/api/datasets/{response.json()["dataset_id"]}/results?stage=pre').json()["items"]
    record = next(r for r in records if r["topic_id"] == "t1")
    assert record["teacher_id"] is None and record["score"] == 0


def test_error_preview_limited_but_csv_is_complete(client, sample):
    base = sample["rows"][0]
    sample["rows"] = [{**base, "student_id": f"bad{i}", "score": "missing"} for i in range(130)]
    response = send_import(client, sample)
    assert len(response.json()["details"]) == 100 and response.json()["total_errors"] == 130
    csv_response = send_import(client, sample, error_format="csv")
    assert csv_response.status_code == 422
    assert "import-errors.csv" in csv_response.headers["content-disposition"]
    records = list(csv.DictReader(io.StringIO(csv_response.content.decode("utf-8-sig"))))
    assert len(records) == 130 and records[-1]["row"] == "131"


def test_limits(settings, sample):
    for settings, status in [(replace(settings, max_results=4), 422), (replace(settings, max_topics=1), 422),
                             (replace(settings, max_upload_bytes=100), 413)]:
        with pytest.raises(ApiError) as exc:
            validate_upload(*payload(sample), settings)
        assert exc.value.status == status


def test_multipart_body_limit_including_chunked_requests(settings):
    with TestClient(create_app(replace(settings, max_upload_bytes=100))) as client:
        large = b"x" * 70_000
        assert client.post("/api/datasets/import", content=large).status_code == 413
        # A generator causes Transfer-Encoding: chunked instead of Content-Length.
        assert client.post("/api/datasets/import", content=iter([large[:35000], large[35000:]])).status_code == 413
        assert client.get("/api/datasets").json()["total"] == 0


def test_multipart_csv_byte_limit(settings, sample):
    with TestClient(create_app(replace(settings, max_upload_bytes=100))) as client:
        assert send_import(client, sample).status_code == 413


def test_import_defaults_to_preview_and_reports_bad_request(client, sample):
    results, curriculum, metadata = payload(sample)
    files = {"results_file": ("results.csv", results), "curriculum_file": ("curriculum.csv", curriculum)}
    response = client.post("/api/datasets/import", files=files, data={"metadata": metadata})
    assert response.json()["dry_run"] is True
    assert client.get("/api/datasets").json()["total"] == 0
    missing = client.post("/api/datasets/import", data={"metadata": metadata})
    assert missing.status_code == 422 and missing.json()["code"] == "INVALID_REQUEST"
    files["results_file"] = ("results.exe", results)
    assert client.post("/api/datasets/import", files=files, data={"metadata": metadata}).json()["code"] == "INVALID_FILE_TYPE"
