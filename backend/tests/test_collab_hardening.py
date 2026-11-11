"""P1 integration/security regressions; real SQLite and offline provider doubles."""
import asyncio
import json
import sqlite3
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app
from backend.app.db.backup import backup_database
from collab import ai
from collab.security import RateStore, RateLimited, client_address
from collab.storage import CommentLimits, CommentStore
from .conftest import send_import


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "AI_ENABLED", "AI_ACCOUNT_VERIFIED"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AI_PROVIDERS", "groq,gemini")
    async def forbidden(*args, **kwargs):
        pytest.fail("Unexpected external provider request")
    monkeypatch.setattr(ai, "_post_json", forbidden)


def ready_ai(monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_ACCOUNT_VERIFIED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "mock-provider-secret")


def demo(client):
    return client.post("/api/datasets/demo").json()["dataset_id"]


def comment(**extra):
    return {"target_type": "topic", "target_id": "fractions", "author_name": "Synthetic reviewer",
            "author_school": "", "author_role": "teacher", "text": "Synthetic comment", **extra}


def count(path):
    with sqlite3.connect(path) as db:
        return db.execute("SELECT COUNT(*) FROM collab_comments").fetchone()[0]


@pytest.mark.parametrize("target_type,target_id", [
    ("dataset", "overview"), ("dataset", "teachers"), ("topic", "fractions"),
    ("textbook", "Учебник A"), ("class", "7A"), ("teacher", "teacher-1"),
])
def test_valid_target_ownership(client, target_type, target_id):
    dataset = demo(client)
    if target_type == "teacher":
        target_id = client.app.state.store.load_results(dataset)[0]["teacher_id"]
    response = client.post(f"/api/datasets/{dataset}/comments", json=comment(target_type=target_type, target_id=target_id))
    assert response.status_code == 201, response.text
    assert response.json()["kind"] == "human"


@pytest.mark.parametrize("target_type", ["dataset", "topic", "textbook", "class", "teacher", "plan", "plan_topic"])
def test_missing_targets_never_persist(client, settings, target_type):
    dataset = demo(client)
    before = count(settings.database_path)
    response = client.post(f"/api/datasets/{dataset}/comments", json=comment(target_type=target_type, target_id="missing"))
    assert response.status_code == 404 and response.json()["code"] == "COMMENT_TARGET_NOT_FOUND"
    assert count(settings.database_path) == before


@pytest.mark.parametrize("target_type", ["plan", "plan_topic"])
def test_cross_dataset_plan_rejected(client, settings, sample, target_type):
    dataset = demo(client)
    other = send_import(client, sample).json()["dataset_id"]
    plan_id = client.post(f"/api/datasets/{other}/plans", json={"class_id": "7A"}).json()["plan_id"]
    target = plan_id + (":t1" if target_type == "plan_topic" else "")
    response = client.post(f"/api/datasets/{dataset}/comments", json=comment(target_type=target_type, target_id=target))
    assert response.status_code == 404
    assert count(settings.database_path) == 0


def test_plan_topic_must_exist_in_saved_snapshot(client, settings):
    dataset = demo(client)
    plan = client.post(f"/api/datasets/{dataset}/plans", json={"class_id": "7A"}).json()["plan_id"]
    assert client.post(f"/api/datasets/{dataset}/comments", json=comment(target_type="plan_topic", target_id=f"{plan}:missing")).status_code == 404
    assert client.post(f"/api/datasets/{dataset}/comments", json=comment(target_type="plan_topic", target_id=f"{plan}:fractions")).status_code == 201
    assert count(settings.database_path) == 1


@pytest.mark.parametrize("field,value", [
    ("author_name", ""), ("author_name", " " * 4), ("author_name", "x" * 81),
    ("author_school", "x" * 121), ("text", ""), ("text", "\t\n"), ("text", "x" * 4001),
    ("target_id", ""), ("target_id", "x" * 201), ("target_type", "student"),
    ("author_role", "ai"), ("author_role", "root"), ("kind", "ai"),
])
def test_comment_contract_boundaries(client, settings, field, value):
    dataset = demo(client)
    response = client.post(f"/api/datasets/{dataset}/comments", json=comment(**{field: value}))
    assert response.status_code == 422
    assert count(settings.database_path) == 0


def test_comment_max_lengths_and_trim(client):
    dataset = demo(client)
    response = client.post(f"/api/datasets/{dataset}/comments", json=comment(author_name="x" * 80, author_school="x" * 120, text="x" * 4000))
    assert response.status_code == 201
    trimmed = client.post(f"/api/datasets/{dataset}/comments", json=comment(author_name=" Name ", text=" Text ")).json()
    assert (trimmed["author_name"], trimmed["text"]) == ("Name", "Text")


def test_listing_cap_and_deterministic_sort(client, settings):
    dataset = demo(client)
    first = client.post(f"/api/datasets/{dataset}/comments", json=comment()).json()
    with sqlite3.connect(settings.database_path) as db:
        for i in range(501):
            db.execute("INSERT INTO collab_comments SELECT ?,dataset_id,target_type,target_id,author_name,author_school,author_role,kind,text,? FROM collab_comments WHERE id=?",
                       (f"row-{i:04}", "2030-01-01T00:00:00+00:00", first["id"]))
    result = client.get(f"/api/datasets/{dataset}/comments").json()
    assert result["total"] == 502 and len(result["items"]) == 500
    assert result["items"][0]["id"] == "row-0000" and result["items"][-1]["id"] == "row-0499"
    assert len(client.app.state.comments.list(dataset, limit=9999)["items"]) == 500


@pytest.mark.parametrize("limits", [CommentLimits(total=1), CommentLimits(per_dataset=1), CommentLimits(bytes=1), CommentLimits(database_bytes=1)])
def test_storage_quotas_atomic(client, settings, limits):
    dataset = demo(client)
    assert client.post(f"/api/datasets/{dataset}/comments", json=comment()).status_code == 201
    client.app.state.comments.limits = limits
    response = client.post(f"/api/datasets/{dataset}/comments", json=comment())
    assert response.status_code == 409 and response.json()["code"] == "COMMENT_QUOTA_EXCEEDED"
    assert count(settings.database_path) == 1


def test_comment_response_failure_never_commits(client, settings, monkeypatch):
    dataset = demo(client)
    from collab import api
    def broken(*args, **kwargs):
        raise ValueError("response rendering failed")
    monkeypatch.setattr(api, "JSONResponse", broken)
    with pytest.raises(ValueError, match="rendering"):
        client.post(f"/api/datasets/{dataset}/comments", json=comment())
    assert count(settings.database_path) == 0


def test_comment_insert_failure_rolls_back(client, settings):
    dataset = demo(client)
    with sqlite3.connect(settings.database_path) as db:
        db.execute("CREATE TRIGGER fail_comment AFTER INSERT ON collab_comments BEGIN SELECT RAISE(ABORT, 'test failure'); END")
    with pytest.raises(sqlite3.IntegrityError):
        client.post(f"/api/datasets/{dataset}/comments", json=comment())
    assert count(settings.database_path) == 0


def test_comments_and_plan_survive_live_backup_restore(settings):
    with TestClient(create_app(settings)) as client:
        dataset = demo(client)
        plan = client.post(f"/api/datasets/{dataset}/plans", json={"class_id": "7A"}).json()
        item = client.post(f"/api/datasets/{dataset}/comments", json=comment(target_type="plan_topic", target_id=plan["plan_id"] + ":fractions")).json()
        backup = settings.database_path.with_name("backup.sqlite3")
        assert backup_database(settings.database_path, backup)["integrity"] == "ok"
    restored = settings.database_path.with_name("restored.sqlite3")
    backup_database(backup, restored)
    for path in (settings.database_path, restored):
        with TestClient(create_app(replace(settings, database_path=path))) as restarted:
            assert restarted.get(f"/api/datasets/{dataset}").status_code == 200
            assert restarted.get(f"/api/plans/{plan['plan_id']}").json() == plan
            assert restarted.get(f"/api/datasets/{dataset}/comments").json()["items"] == [item]
    with pytest.raises(FileExistsError):
        backup_database(backup, restored)


def test_ten_posts_per_minute_429_and_retry_after(client):
    dataset = demo(client)
    for _ in range(10):
        assert client.post(f"/api/datasets/{dataset}/comments", json=comment()).status_code == 201
    blocked = client.post(f"/api/datasets/{dataset}/comments", json=comment(), headers={"X-Forwarded-For": "203.0.113.9"})
    assert blocked.status_code == 429 and 1 <= int(blocked.headers["Retry-After"]) <= 60
    assert client.get(f"/api/datasets/{dataset}/comments").json()["total"] == 10


def test_rate_limit_survives_restart_and_sliding_window(client, settings):
    now = [1000.0]
    rate = RateStore(settings.database_path, clock=lambda: now[0])
    for _ in range(10):
        rate.acquire("comments", "203.0.113.1")
    restarted = RateStore(settings.database_path, clock=lambda: now[0])
    with pytest.raises(RateLimited):
        restarted.acquire("comments", "203.0.113.1")
    now[0] += 60
    restarted.acquire("comments", "203.0.113.1")


def test_rate_limit_concurrent_requests_cannot_race(client, settings):
    def request(_):
        try:
            RateStore(settings.database_path).acquire("comments", "203.0.113.1")
            return True
        except RateLimited:
            return False
    with ThreadPoolExecutor(max_workers=12) as executor:
        assert sum(executor.map(request, range(20))) == 10


def test_global_comment_quota_bounds_ip_storage(client, settings):
    rate = RateStore(settings.database_path, clock=lambda: 1000)
    for n in range(60):
        rate.acquire("comments", f"203.0.113.{n}")
    with pytest.raises(RateLimited):
        rate.acquire("comments", "203.0.113.100")
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM collab_rate_events").fetchone()[0] == 60


@pytest.mark.parametrize("peer,header,trusted,expected", [
    ("203.0.113.7", "1.2.3.4", (), "203.0.113.7"),
    ("10.0.0.2", "1.2.3.4, 203.0.113.7", ("10.0.0.0/24",), "203.0.113.7"),
    ("10.0.0.2", "203.0.113.7, 10.0.0.3", ("10.0.0.0/24",), "203.0.113.7"),
    ("10.0.0.2", "bad, 203.0.113.7", ("10.0.0.0/24",), "10.0.0.2"),
    ("::1", "2001:db8::1", ("::1/128",), "2001:db8::1"),
])
def test_only_trusted_proxy_controls_client_address(peer, header, trusted, expected):
    assert client_address({"client": (peer, 100), "headers": [(b"x-forwarded-for", header.encode())]}, trusted) == expected


@pytest.mark.parametrize("suffix", ["comments", "ai/explain"])
def test_public_p1_requests_do_not_mutate_any_table(settings, suffix):
    with TestClient(create_app(replace(settings, read_only_demo=True))) as client:
        dataset = demo(client)
        with sqlite3.connect(settings.database_path) as db:
            before = list(db.iterdump())
        response = client.post(f"/api/datasets/{dataset}/{suffix}", content=b"bad json")
        assert response.status_code == 403 and response.json()["code"] == "READ_ONLY_DEMO"
        with sqlite3.connect(settings.database_path) as db:
            assert list(db.iterdump()) == before


def test_comments_feature_flag(settings):
    with TestClient(create_app(replace(settings, comments_enabled=False))) as client:
        dataset = demo(client)
        assert client.get("/api/capabilities").json()["features"]["comments"] is False
        assert client.post(f"/api/datasets/{dataset}/comments", json=comment()).status_code == 503
        assert client.get(f"/api/datasets/{dataset}/comments").status_code == 503


@pytest.mark.parametrize("suffix", ["comments", "ai/explain"])
def test_body_limit_before_json_parsing(client, suffix):
    dataset = demo(client)
    response = client.post(f"/api/datasets/{dataset}/{suffix}", content=b"x" * 65537)
    assert response.status_code == 413
    response = client.post(f"/api/datasets/{dataset}/{suffix}", content=iter([b"x" * 40000, b"x" * 40000]))
    assert response.status_code == 413


@pytest.mark.parametrize("flags", [{}, {"AI_ENABLED": "true"}, {"AI_ACCOUNT_VERIFIED": "true"}])
def test_model_name_and_key_do_not_imply_availability(client, monkeypatch, flags):
    monkeypatch.setenv("GROQ_API_KEY", "mock-secret")
    for key, value in flags.items():
        monkeypatch.setenv(key, value)
    dataset = demo(client)
    assert client.get("/api/ai/status").json()["configured"] is False
    response = client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": "overview", "context": {}})
    assert response.status_code == 503 and response.json()["code"] == "AI_NOT_CONFIGURED"


@pytest.mark.parametrize("payload,code", [
    ({"kind": "overview", "context": {"student_id": "private"}}, "AI_CONTEXT_SELECTORS_ONLY"),
    ({"kind": "overview", "context": {"api_key": "secret"}}, "AI_CONTEXT_SELECTORS_ONLY"),
    ({"kind": "overview", "context": {}, "question": "my password"}, "AI_FREE_TEXT_DISABLED"),
    ({"kind": "teachers", "context": {}}, "AI_KIND_NOT_READY"),
    ({"kind": "comments", "context": {}}, "AI_KIND_NOT_READY"),
    ({"kind": "overview", "context": {"x": "я" * 15000}}, "AI_CONTEXT_TOO_LARGE"),
])
def test_unsafe_ai_context_never_leaves_server(client, monkeypatch, payload, code):
    ready_ai(monkeypatch)
    dataset = demo(client)
    response = client.post(f"/api/datasets/{dataset}/ai/explain", json=payload)
    assert response.status_code in (422, 503) and response.json()["code"] == code


def test_ai_only_server_aggregates_and_no_automatic_writes(client, settings, monkeypatch):
    ready_ai(monkeypatch)
    sent = []
    async def provider(url, payload, headers):
        sent.append(payload["messages"][1]["content"])
        return {"choices": [{"message": {"content": "Synthetic explanation mock-provider-secret"}}]}
    monkeypatch.setattr(ai, "_post_json", provider)
    dataset = demo(client)
    before = count(settings.database_path)
    response = client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": "overview", "context": {}})
    assert response.status_code == 200 and "[REDACTED]" in response.json()["text"]
    assert "mock-provider-secret" not in response.text
    aggregate = json.loads(sent[0].split("<data>\n", 1)[1].split("\n</data>", 1)[0])
    assert aggregate["metrics"]["n_students"] == 120
    assert not any(value in sent[0] for value in ("student_id", "teacher_id", "school_id", dataset, "Учебник A", "Synthetic reviewer"))
    assert count(settings.database_path) == before
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("SELECT COUNT(*) FROM aidana_plan_snapshots").fetchone()[0] == 0


def test_ai_upload_data_not_sent(client, sample, monkeypatch):
    ready_ai(monkeypatch)
    dataset = send_import(client, sample).json()["dataset_id"]
    response = client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": "overview", "context": {}})
    assert response.status_code == 403 and response.json()["code"] == "AI_DEMO_ONLY"


def test_ai_per_ip_and_daily_quotas(client, settings):
    now = [1000.0]
    rate = RateStore(settings.database_path, clock=lambda: now[0])
    for _ in range(3):
        rate.acquire("ai", "same")
    with pytest.raises(RateLimited):
        rate.acquire("ai", "same")
    for n in range(97):
        now[0] += 61
        rate.acquire("ai", str(n))
    with pytest.raises(RateLimited) as denied:
        rate.acquire("ai", "new-client")
    assert denied.value.retry_after > 60


def test_ai_total_deadline_and_no_secret_in_errors(client, monkeypatch, caplog):
    ready_ai(monkeypatch)
    monkeypatch.setattr(ai, "TIMEOUT_SECONDS", 0.01)
    async def hang(*args):
        await asyncio.sleep(1)
    monkeypatch.setattr(ai, "_post_json", hang)
    dataset = demo(client)
    response = client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": "overview", "context": {}})
    assert response.status_code == 502 and response.json()["code"] == "AI_PROVIDER_ERROR"
    assert "mock-provider-secret" not in response.text + caplog.text


def test_new_routes_and_errors_in_openapi(client):
    paths = client.get("/openapi.json").json()["paths"]
    for path in ("/api/datasets/{dataset_id}/comments", "/api/datasets/{dataset_id}/ai/explain"):
        assert {"201" if path.endswith("comments") else "200", "403", "404", "422", "429", "503"} <= paths[path]["post"]["responses"].keys()
    assert "get" in paths["/api/ai/status"]


@pytest.mark.parametrize("kind", ["topic", "plan"])
def test_ai_scoped_aggregate_context(client, monkeypatch, kind):
    ready_ai(monkeypatch)
    seen = []
    async def provider(url, payload, headers):
        seen.append(payload["messages"][1]["content"])
        return {"choices": [{"message": {"content": "Synthetic explanation"}}]}
    monkeypatch.setattr(ai, "_post_json", provider)
    dataset = demo(client)
    context = {"topic_id": "fractions", "class_ids": ["7A"]}
    if kind == "plan":
        plan = client.post(f"/api/datasets/{dataset}/plans", json={"class_id": "7A", "comment": "Never send this secret"}).json()
        context = {"plan_id": plan["plan_id"]}
    response = client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": kind, "context": context})
    assert response.status_code == 200
    assert "Never send this secret" not in seen[0] and dataset not in seen[0]
    assert "student_id" not in seen[0] and "7A" not in seen[0]


def test_ai_http_429_and_question_length(client, monkeypatch):
    ready_ai(monkeypatch)
    dataset = demo(client)
    for _ in range(3):
        assert client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": "overview", "context": {}, "question": "x" * 501}).status_code == 422
    blocked = client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": "overview", "context": {}})
    assert blocked.status_code == 429 and int(blocked.headers["Retry-After"]) > 0


def test_public_ai_opt_in_allows_demo_explanations_but_no_writes(settings, monkeypatch):
    ready_ai(monkeypatch)
    async def provider(url, payload, headers):
        return {"choices": [{"message": {"content": "Synthetic public explanation"}}]}
    monkeypatch.setattr(ai, "_post_json", provider)
    with TestClient(create_app(replace(settings, read_only_demo=True, ai_public_demo=True))) as client:
        features = client.get("/api/capabilities").json()["features"]
        assert features["ai_explain"] is True
        assert features["plan_save"] is False and features["comments_write"] is False and features["csv_import"] is False
        assert client.get("/api/ai/status").json()["configured"] is True
        dataset = demo(client)
        response = client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": "overview", "context": {}})
        assert response.status_code == 200 and response.json()["text"] == "Synthetic public explanation"
        # The AI opt-in never opens public writes.
        response = client.post(f"/api/datasets/{dataset}/comments", json=comment())
        assert response.status_code == 403 and response.json()["code"] == "READ_ONLY_DEMO"


def test_public_ai_stays_off_without_opt_in_or_keys(settings, monkeypatch):
    ready_ai(monkeypatch)
    with TestClient(create_app(replace(settings, read_only_demo=True))) as client:
        assert client.get("/api/capabilities").json()["features"]["ai_explain"] is False
        assert client.get("/api/ai/status").json()["configured"] is False
    monkeypatch.delenv("GROQ_API_KEY")
    other = replace(settings, database_path=settings.database_path.with_name("no-keys.sqlite3"),
                    read_only_demo=True, ai_public_demo=True)
    with TestClient(create_app(other)) as client:
        assert client.get("/api/capabilities").json()["features"]["ai_explain"] is False
        dataset = demo(client)
        response = client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": "overview", "context": {}})
        assert response.status_code == 503 and response.json()["code"] == "AI_NOT_CONFIGURED"


@pytest.mark.parametrize("value,expected", [("true", True), ("1", True), ("false", False), ("0", False)])
def test_ai_public_demo_env_flag(monkeypatch, value, expected):
    monkeypatch.setenv("AI_PUBLIC_DEMO", value)
    assert Settings.from_env().ai_public_demo is expected


def test_ai_public_demo_env_flag_rejects_unknown_values(monkeypatch):
    monkeypatch.setenv("AI_PUBLIC_DEMO", "yes")
    with pytest.raises(ValueError, match="AI_PUBLIC_DEMO"):
        Settings.from_env()
