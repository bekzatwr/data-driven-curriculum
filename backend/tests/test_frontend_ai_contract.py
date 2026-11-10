"""Контракт фронтенда (web/src/api/client.ts → aiExplain) с AI API из PR #6.

Фронтенд отправляет только селекторы и question=null. Здесь — ровно те формы запросов,
которые строят страницы обзора, темы, сравнения и плана. Провайдер подменён: внешних
вызовов нет. Код бэкенда не меняется — тест лишь фиксирует совместимость.
"""
import pytest

from collab import ai


@pytest.fixture(autouse=True)
def mocked_provider(monkeypatch):
    for key in ("GEMINI_API_KEY",):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_ACCOUNT_VERIFIED", "true")
    monkeypatch.setenv("AI_PROVIDERS", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "mock-provider-secret")

    async def provider(url, payload, headers):
        return {"choices": [{"message": {"content": "Synthetic explanation"}}]}

    monkeypatch.setattr(ai, "_post_json", provider)


def demo(client):
    return client.post("/api/datasets/demo").json()["dataset_id"]


FRONTEND_PAYLOADS = {
    # OverviewPage: applied_filters → class_ids / textbook_ids / test_version (пустые убираются)
    "overview_all": {"kind": "overview", "context": {}, "question": None},
    "overview_filtered": {"kind": "overview", "context": {"class_ids": ["7A"], "textbook_ids": ["Учебник A"]}, "question": None},
    # TopicDrawer: topic_id + фильтры
    "topic": {"kind": "topic", "context": {"topic_id": "fractions", "class_ids": ["7A"]}, "question": None},
    # ComparisonPage: topic_id + textbook_a/b (+ class_ids/test_version)
    "comparison": {"kind": "comparison", "context": {"topic_id": "equations", "textbook_a": "Учебник A", "textbook_b": "Учебник B"}, "question": None},
}


@pytest.mark.parametrize("name", sorted(FRONTEND_PAYLOADS))
def test_frontend_selector_payloads_are_accepted(client, name):
    dataset = demo(client)
    response = client.post(f"/api/datasets/{dataset}/ai/explain", json=FRONTEND_PAYLOADS[name])
    assert response.status_code == 200, response.text
    assert response.json()["text"] == "Synthetic explanation"


def test_frontend_plan_payload_uses_saved_plan_id(client):
    # PlannerPage (после сохранения) и ReportPage: только plan_id сохранённого снимка
    dataset = demo(client)
    saved = client.post(f"/api/datasets/{dataset}/plans", json={"class_id": "7A", "comment": ""})
    assert saved.status_code == 201, saved.text
    payload = {"kind": "plan", "context": {"plan_id": saved.json()["plan_id"]}, "question": None}
    response = client.post(f"/api/datasets/{dataset}/ai/explain", json=payload)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize("payload,code", [
    # прежний фронтенд PR #4 отправлял показатели и тексты — теперь это отклоняется
    ({"kind": "overview", "context": {"metrics": {"n_students": 120}}}, "AI_CONTEXT_SELECTORS_ONLY"),
    ({"kind": "overview", "context": {}, "question": "почему?"}, "AI_FREE_TEXT_DISABLED"),
    ({"kind": "teachers", "context": {}}, "AI_KIND_NOT_READY"),
])
def test_retired_frontend_payloads_are_rejected(client, payload, code):
    dataset = demo(client)
    response = client.post(f"/api/datasets/{dataset}/ai/explain", json=payload)
    assert response.status_code in (422, 503) and response.json()["code"] == code
