import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from .conftest import send_import


def test_quality_counts_gaps_and_includes_empty_topics(client, sample):
    sample["topics"].append({**sample["topics"][0], "topic_id": "t3", "topic_name": "Пустая тема", "topic_order": 3})
    sample["rows"][0]["teacher_id"] = ""
    sample["rows"] = sample["rows"][:-1]  # t2 now has pre only.
    dataset_id = send_import(client, sample).json()["dataset_id"]
    response = client.get(f"/api/datasets/{dataset_id}/quality")
    assert response.status_code == 200
    quality = response.json()
    assert quality["summary"] == {
        "students": 2, "results": 4, "pre": 2, "post": 2, "pairs": 1,
        "post_without_pre": 1, "pre_without_post": 1, "missing_teacher": 1, "paired_post_share": 0.5,
    }
    assert quality["topics_without_results"] == ["t3"]
    topics = {t["topic_id"]: t for t in quality["by_topic"]}
    assert topics["t1"]["classes_with_results"] == 2
    assert topics["t2"]["paired_post_share"] is None
    assert topics["t3"]["results"] == 0 and topics["t3"]["paired_post_share"] is None
    classes = {c["class_id"]: c for c in quality["by_class"]}
    assert classes["7A"]["topics_without_results"] == 1
    assert classes["7B"]["paired_post_share"] == 0
    assert len(quality["notices"]) == 4
    assert "student_id" not in quality["summary"]


def test_quality_demo_not_truncated_to_first_page(client):
    dataset_id = client.post("/api/datasets/demo").json()["dataset_id"]
    quality = client.get(f"/api/datasets/{dataset_id}/quality").json()
    assert quality["summary"]["results"] == 1440
    assert quality["summary"]["pairs"] == 720
    assert quality["summary"]["students"] == 120
    assert quality["summary"]["paired_post_share"] == 1
    assert len(quality["by_class"]) == 4 and len(quality["by_topic"]) == 6
    assert quality["notices"] == []


@pytest.mark.parametrize("suffix", ["quality", "package"])
def test_new_routes_hide_uploads_in_public_mode(client, sample, settings, suffix):
    dataset_id = send_import(client, sample).json()["dataset_id"]
    with TestClient(create_app(Settings(database_path=settings.database_path, read_only_demo=True))) as public:
        response = public.get(f"/api/datasets/{dataset_id}/{suffix}")
        assert response.status_code == 404
        assert response.json()["code"] == "DATASET_NOT_FOUND"
    assert client.get(f"/api/datasets/missing/{suffix}").status_code == 404


@pytest.mark.parametrize("readonly", [False, True])
def test_capabilities_match_enforced_mode(tmp_path, readonly):
    with TestClient(create_app(Settings(database_path=tmp_path / "caps.db", read_only_demo=readonly))) as client:
        caps = client.get("/api/capabilities").json()
        assert caps["version"] == client.get("/api/health").json()["version"]
        assert caps["version"] == client.get("/openapi.json").json()["info"]["version"]
        assert caps["mode"] == ("read_only_demo" if readonly else "local")
        assert caps["features"]["csv_import"] is (not readonly)
        assert caps["features"]["package_restore"] is (not readonly)
        assert caps["limits"]["results_per_dataset"] == 10000
        assert caps["limits"]["package_body_bytes"] == 32 * 1024 * 1024
        assert str(tmp_path) not in str(caps)
