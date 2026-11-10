import copy
import hashlib
from dataclasses import replace

from fastapi.testclient import TestClient
import pytest

from backend.app.main import create_app
from backend.app.validation import canonical
from .conftest import send_import


def exported(client, sample):
    original = send_import(client, sample).json()
    response = client.get(f'/api/datasets/{original["dataset_id"]}/package')
    assert response.status_code == 200
    assert response.headers["content-disposition"].endswith('.ddc.json"')
    return original, response.json()


def recalculate(package):
    package["checksum"] = hashlib.sha256(canonical(package["data"]).encode("utf-8")).hexdigest()


def test_package_round_trip_preview_new_database_and_duplicate(client, sample, tmp_path, settings):
    original, package = exported(client, sample)
    # Portable document contains no DB IDs, timestamps or trusted source_type.
    assert set(package) == {"format", "version", "checksum", "data"}
    assert set(package["data"]) == {"metadata", "curriculum", "results"}
    with TestClient(create_app(replace(settings, database_path=tmp_path / "destination.db"))) as destination:
        preview = destination.post("/api/datasets/restore", json=package)
        assert preview.status_code == 200 and preview.json()["dry_run"] is True
        assert preview.json()["dataset_id"] is None
        assert destination.get("/api/datasets").json()["total"] == 0
        response = destination.post("/api/datasets/restore?dry_run=false", json=package)
        assert response.status_code == 201
        restored = response.json()
        assert restored["dataset"]["content_hash"] == original["dataset"]["content_hash"]
        assert restored["counts"] == original["counts"]
        assert restored["dataset_id"] != original["dataset_id"]
        again = destination.post("/api/datasets/restore?dry_run=false", json=package)
        assert again.status_code == 200 and again.json()["dataset_id"] == restored["dataset_id"]
        assert destination.get(f'/api/datasets/{restored["dataset_id"]}/package').json() == package
    # CSV upload and package restore share deduplication.
    duplicate = client.post("/api/datasets/restore?dry_run=false", json=package)
    assert duplicate.status_code == 200 and duplicate.json()["dataset_id"] == original["dataset_id"]


def test_export_all_demo_rows_and_no_forged_demo_provenance(client):
    original = client.post("/api/datasets/demo").json()
    package = client.get(f'/api/datasets/{original["dataset_id"]}/package').json()
    assert len(package["data"]["results"]) == 1440
    response = client.post("/api/datasets/restore?dry_run=false", json=package)
    assert response.status_code == 201
    assert response.json()["dataset"]["source_type"] == "upload"
    assert response.json()["dataset_id"] != original["dataset_id"]


def test_changed_payload_rejected_before_database_write(client, sample):
    _, package = exported(client, sample)
    package["data"]["results"][0]["score"] = 5.0
    response = client.post("/api/datasets/restore?dry_run=false", json=package)
    assert response.status_code == 422
    assert response.json()["code"] == "PACKAGE_CHECKSUM_MISMATCH"
    assert client.get("/api/datasets").json()["total"] == 1


@pytest.mark.parametrize("mutation", ["bad_score", "duplicate", "unknown_topic", "bad_date", "incompatible_pair"])
def test_recomputed_checksum_does_not_bypass_data_rules(client, sample, mutation):
    _, package = exported(client, sample)
    row = package["data"]["results"][0]
    if mutation == "bad_score":
        row["score"] = 11.0
    elif mutation == "duplicate":
        package["data"]["results"].append(copy.deepcopy(row))
    elif mutation == "unknown_topic":
        row["topic_id"] = "missing"
    elif mutation == "bad_date":
        row["tested_at"] = "2027-01-01"
    else:
        row["test_version"] = "other-version"
    recalculate(package)
    response = client.post("/api/datasets/restore?dry_run=false", json=package)
    assert response.status_code == 422
    assert response.json()["code"] != "PACKAGE_CHECKSUM_MISMATCH"
    assert client.get("/api/datasets").json()["total"] == 1


@pytest.mark.parametrize("mutation", ["version", "boolean_version", "missing_version", "missing_format", "extra", "source", "string_bool", "string_score", "boolean_hours"])
def test_package_schema_is_strict(client, sample, mutation):
    _, package = exported(client, sample)
    if mutation == "version":
        package["version"] = 2
    elif mutation == "boolean_version":
        package["version"] = True
    elif mutation.startswith("missing_"):
        del package[mutation.removeprefix("missing_")]
    elif mutation == "extra":
        package["data"]["id"] = "forged"
    elif mutation == "source":
        package["data"]["source_type"] = "demo"
    elif mutation == "string_bool":
        package["data"]["curriculum"][0]["is_locked"] = "false"
    elif mutation == "string_score":
        package["data"]["results"][0]["score"] = "4"
    else:
        package["data"]["curriculum"][0]["current_hours"] = True
    response = client.post("/api/datasets/restore?dry_run=false", json=package)
    assert response.status_code == 422 and response.json()["code"] == "INVALID_REQUEST"


@pytest.mark.parametrize("chunked", [False, True])
def test_restore_body_limit_before_json_parsing(settings, chunked):
    with TestClient(create_app(replace(settings, max_package_bytes=128))) as client:
        content = (chunk for chunk in [b" " * 100, b" " * 100]) if chunked else b" " * 200
        response = client.post("/api/datasets/restore", content=content, headers={"Content-Type": "application/json"})
        assert response.status_code == 413
        assert client.get("/api/datasets").json()["total"] == 0


def test_restore_blocked_before_body_parse_in_demo(settings):
    with TestClient(create_app(replace(settings, read_only_demo=True))) as client:
        for path in ("/api/datasets/restore", "/api/datasets/restore?dry_run=false", "/api/datasets/restore/"):
            response = client.post(path, content=b"not-json")
            assert response.status_code == 403 and response.json()["code"] == "READ_ONLY_DEMO"


def test_package_obeys_configured_csv_row_limits(client, sample, settings, tmp_path):
    _, package = exported(client, sample)
    with TestClient(create_app(replace(settings, database_path=tmp_path / "limited.db", max_results=3))) as limited:
        response = limited.post("/api/datasets/restore?dry_run=false", json=package)
        assert response.status_code == 422
        assert limited.get("/api/datasets").json()["total"] == 0


def test_package_uses_json_size_limit_not_regenerated_csv_size(client, sample, settings, tmp_path):
    _, package = exported(client, sample)
    with TestClient(create_app(replace(settings, database_path=tmp_path / "json.db", max_upload_bytes=100))) as destination:
        assert destination.post("/api/datasets/restore?dry_run=false", json=package).status_code == 201
