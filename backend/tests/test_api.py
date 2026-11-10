from dataclasses import replace

from fastapi import APIRouter
from fastapi.testclient import TestClient
import pytest

from backend.app.api.datasets import StoreDep
from backend.app.main import create_app
from backend.app.validation import RESULT_FIELDS
from .conftest import send_import


def test_demo_and_filters_are_ready_for_frontend(client):
    response = client.post("/api/datasets/demo")
    assert response.status_code == 201
    data = response.json()
    assert data["dataset"]["source_type"] == "demo"
    assert data["counts"] == {"students": 120, "classes": 4, "topics": 6, "textbooks": 2,
                              "results": 1440, "pre": 720, "post": 720, "pairs": 720}
    dataset_id = data["dataset_id"]
    assert client.post("/api/datasets/demo").json()["dataset_id"] == dataset_id
    filters = client.get(f"/api/datasets/{dataset_id}/filters").json()
    assert [r["student_count"] for r in filters["classes"]] == [30] * 4
    assert len(filters["textbooks"]) == 2 and len(filters["test_versions"]) == 6
    curriculum = client.get(f"/api/datasets/{dataset_id}/curriculum").json()
    assert sum(t["current_hours"] for t in curriculum) == 24
    assert next(t for t in curriculum if t["topic_id"] == "geometry")["is_locked"] is True
    params = [("class_ids", "7A"), ("class_ids", "7B"), ("topic_id", "fractions"),
              ("stage", "post"), ("limit", "17")]
    page1 = client.get(f"/api/datasets/{dataset_id}/results", params=params).json()
    page2 = client.get(f"/api/datasets/{dataset_id}/results", params=params + [("offset", "17")]).json()
    assert page1["total"] == 60 and len(page1["items"]) == 17 and len(page2["items"]) == 17
    assert {r["student_id"] for r in page1["items"]}.isdisjoint(r["student_id"] for r in page2["items"])
    assert client.get(f"/api/datasets/{dataset_id}/results", params={"class_ids": "' OR 1=1 --"}).json()["total"] == 0
    assert client.get(f"/api/datasets/{dataset_id}/results", params={"textbook_ids": "Учебник A", "stage": "pre"}).json()["total"] == 360
    assert client.get(f"/api/datasets/{dataset_id}/results?test_version=unknown").json()["items"] == []


def test_dataset_scoping(client, sample):
    first = send_import(client, sample).json()["dataset_id"]
    sample["metadata"]["name"] = "Другой набор"
    sample["rows"][0]["score"] = 2
    second = send_import(client, sample).json()["dataset_id"]
    assert first != second
    assert client.get("/api/datasets?limit=1").json()["total"] == 2
    assert client.get(f"/api/datasets/{first}/results").json()["total"] == 5
    assert client.get(f"/api/datasets/{second}/results").json()["total"] == 5


@pytest.mark.parametrize("suffix", ["", "/filters", "/curriculum", "/results"])
def test_unknown_dataset_is_404(client, suffix):
    response = client.get("/api/datasets/missing" + suffix)
    assert response.status_code == 404 and response.json()["code"] == "DATASET_NOT_FOUND"


def test_read_only_demo_hides_uploads_and_rejects_import(settings, sample):
    with TestClient(create_app(settings)) as local:
        private_id = send_import(local, sample).json()["dataset_id"]
    with TestClient(create_app(replace(settings, read_only_demo=True))) as public:
        assert send_import(public, sample, dry_run=True).status_code == 403
        assert send_import(public, sample).status_code == 403
        # Trusted demo is seeded at startup, before accepting any public requests.
        assert public.get("/api/datasets").json()["total"] == 1
        for suffix in ("", "/filters", "/curriculum", "/results"):
            assert public.get(f"/api/datasets/{private_id}{suffix}").status_code == 404
        assert public.post("/api/datasets/demo").status_code == 200
        assert public.get("/api/datasets").json()["total"] == 1
        assert public.get("/api/health").json()["read_only_demo"] is True


def test_health_docs_templates_and_cors(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert "/api/datasets/import" in schema["paths"]
    assert "/api/datasets/{dataset_id}/filters" in schema["paths"]
    template = client.get("/api/templates/results.csv")
    assert template.content.decode("utf-8-sig").strip().split(",") == list(RESULT_FIELDS)
    assert "attachment" in template.headers["content-disposition"]
    assert client.get("/api/datasets?limit=1000").json()["code"] == "INVALID_REQUEST"
    assert client.get("/api/unknown").json()["code"] == "HTTP_404"
    cors = client.options("/api/datasets/import", headers={"Origin": "http://localhost:5173",
                                                          "Access-Control-Request-Method": "POST"})
    assert cors.headers["access-control-allow-origin"] == "http://localhost:5173"
    blocked = client.get("/api/health", headers={"Origin": "https://unconfigured.invalid"})
    assert "access-control-allow-origin" not in blocked.headers


def test_teammate_router_receives_all_records(settings):
    router = APIRouter(prefix="/api/team-test")

    @router.get("/{dataset_id}")
    def count_all(dataset_id: str, store: StoreDep):
        return {"count": len(store.load_results(dataset_id))}

    with TestClient(create_app(settings, routers=(router,))) as client:
        dataset_id = client.post("/api/datasets/demo").json()["dataset_id"]
        assert client.get(f"/api/team-test/{dataset_id}").json()["count"] == 1440


def test_optional_frontend_serving(settings, tmp_path):
    dist = tmp_path / "web"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Frontend fixture</title>", encoding="utf-8")
    (dist / "app.js").write_text("/* asset */", encoding="utf-8")
    (tmp_path / "private.txt").write_text("never serve", encoding="utf-8")
    with TestClient(create_app(replace(settings, web_dist=dist))) as client:
        assert "Frontend fixture" in client.get("/dashboard").text
        assert client.get("/app.js").text == "/* asset */"
        assert client.get("/missing.js").status_code == 404
        assert client.get("/api/unknown").json()["code"] == "HTTP_404"
        assert client.get("/%2e%2e/private.txt").status_code == 404
        assert client.get("/docs").status_code == 200
