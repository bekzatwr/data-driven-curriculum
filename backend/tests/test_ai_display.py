"""Display guard: technical field names and status codes never reach the user."""
from fastapi.testclient import TestClient

from backend.app.main import create_app
from collab import ai


ANSWER = (
    "**Главный вывод** Группа A показала +16 п.п., B — +8 п.п. (difference_gain_pp = 8.0 п.п.), "
    "статус сравнения *comparable*. Оба набора покрыты (`pair_coverage` = 1.0), "
    "темы 1 и 3 — «requires_attention/needs_practice», остальные «mastered»; is_demo = true. "
    "Учебник A и Учебник B, mean_post_pct 48 %, below_threshold_share = 0,4, period_v1."
)


def test_humanize_replaces_identifiers_and_keeps_numbers_and_names():
    text = ai.humanize(ANSWER)
    for raw in ("difference_gain_pp", "comparable", "pair_coverage", "requires_attention", "needs_practice",
                "mastered", "is_demo", "mean_post_pct", "below_threshold_share", "period_v1", "`", "*comparable*"):
        assert raw not in text, raw
    for kept in ("**Главный вывод**", "+16 п.п.", "+8 п.п.", "8.0 п.п.", "= 1.0", "48 %", "0,4",
                 "Учебник A", "Учебник B", "разница приростов", "сопоставимо", "охват пар",
                 "требует внимания/нужно закрепление", "«освоено»", "искусственные данные = true",
                 "средний итоговый балл", "доля ниже порога", "план на период"):
        assert kept in text, kept


def test_humanize_touches_only_exact_identifiers():
    assert ai.humanize("not_comparable") == "несопоставимо"
    assert ai.humanize("incomparable mastered_pct masteredness") == "incomparable порог освоения masteredness"
    assert ai.humanize("Обычный текст без полей, 12 ч и 5 п.п.") == "Обычный текст без полей, 12 ч и 5 п.п."


def test_explain_response_is_humanized(settings, monkeypatch):
    monkeypatch.setenv("AI_ENABLED", "true")
    monkeypatch.setenv("AI_ACCOUNT_VERIFIED", "true")
    monkeypatch.setenv("GROQ_API_KEY", "mock-provider-secret")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("AI_PROVIDERS", "groq")
    async def provider(url, payload, headers):
        return {"choices": [{"message": {"content": ANSWER}}]}
    monkeypatch.setattr(ai, "_post_json", provider)
    with TestClient(create_app(settings)) as client:
        dataset = client.post("/api/datasets/demo").json()["dataset_id"]
        response = client.post(f"/api/datasets/{dataset}/ai/explain", json={"kind": "overview", "context": {}})
    assert response.status_code == 200, response.text
    text = response.json()["text"]
    assert "pair_coverage" not in text and "охват пар" in text and "сопоставимо" in text
