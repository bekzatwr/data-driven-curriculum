"""ИИ-пояснения через API: Groq (основной) и Gemini (запасной).

Ключи только в окружении сервера: GROQ_API_KEY, GEMINI_API_KEY. В модель уходят
только разрешённые серверные агрегаты, без персональных данных учеников.
"""
import json
import logging
import os
import asyncio
import re
import httpx
from datetime import datetime, timezone

from analytics.ai_guidance import SYSTEM_PROMPT as ANALYTICS_SYSTEM_PROMPT, TASKS, build_prompt

logger = logging.getLogger(__name__)

DEFAULT_MODELS = {"groq": "openai/gpt-oss-120b", "gemini": "gemini-3.5-flash-lite"}
TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 65536
MAX_OUTPUT_TOKENS = 2048
USER_AGENT = "data-driven-curriculum/0.2 (+https://github.com/bekzatwr/data-driven-curriculum)"

# One methodology source for both providers. The server-only display guard
# addresses the observed hours/percentage hallucination without changing Toni's
# policy or the planning algorithms. Prompts do not guarantee model compliance.
SYSTEM_PROMPT = ANALYTICS_SYSTEM_PROMPT + """
11. Изменения часов описывай только в часах: не вычисляй новые проценты изменения часов и не называй часы процентными пунктами. Меньшее число часов не означает снижение успеваемости. Не показывай имена полей JSON и английские статусы пользователю — используй понятные русские подписи, например: pair_coverage — «охват пар», below_threshold_share — «доля ниже порога», mean_gain_pp — «средний прирост», comparison_status — «статус сравнения», mastered — «освоено», needs_practice — «нужно закрепление», requires_attention — «требует внимания», comparable — «сопоставимо», is_demo — «искусственные данные».
12. Сервер скрывает названия, идентификаторы и свободные тексты. Если причины не переданы, не восстанавливай их по догадке. При omitted_warning_count > 0 или omitted_reason_count > 0 сообщи, что часть ограничений доступна в исходном отчёте; не объявляй данные полными и не делай сравнительного вывода о преимуществе группы."""

# Display guard: prompts do not guarantee that the model hides technical names, so
# known JSON fields, status codes and algorithm ids are replaced with the labels the
# interface itself uses. Only exact identifiers are touched; numbers and text stay.
DISPLAY_LABELS = {
    "pair_coverage": "охват пар", "paired_student_share": "доля учеников с парами",
    "below_threshold_share": "доля ниже порога", "mean_post_pct": "средний итоговый балл",
    "mean_pre_paired_pct": "средний входной балл", "mean_post_paired_pct": "средний итоговый балл по парам",
    "mean_gain_pp": "средний прирост", "difference_gain_pp": "разница приростов",
    "baseline_gap_pp": "стартовый разрыв", "comparison_status": "статус сравнения",
    "problem_topic": "проблемная тема", "single_version": "одна версия теста",
    "n_students": "число учеников", "n_post_students": "учеников с итоговым тестом",
    "n_post_results": "итоговых результатов", "n_post": "итоговых результатов",
    "n_pairs": "пар «ученик–тема»", "n_paired_students": "учеников с парами",
    "n_complete_students": "учеников со всеми темами", "n_problem_topics": "проблемных тем",
    "topic_count": "число тем", "topic_index": "номер темы", "class_index": "номер класса",
    "n_classes": "число классов", "n_teachers": "число учителей", "max_score": "максимальный балл",
    "threshold_pct": "порог", "mastered_pct": "порог освоения", "problem_share": "доля для проблемной темы",
    "target_pct": "цель", "donor_pct": "порог донора", "min_students": "минимум учеников",
    "max_change": "лимит изменения", "total_hours": "всего часов", "current_hours": "текущие часы",
    "min_hours": "минимум часов", "max_hours": "максимум часов", "is_locked": "блокировка",
    "proposed_hours": "часы в плане", "recommended_hours": "рекомендованные часы",
    "manually_modified": "ручная правка", "automatic_eligible": "автоматическая рекомендация",
    "is_demo": "искусственные данные", "upcoming_hours": "предстоящие часы",
    "omitted_warning_count": "скрытые предупреждения", "omitted_reason_count": "скрытые причины",
    "algorithm_version": "алгоритм", "test_version": "версия теста",
    "mastered": "освоено", "needs_practice": "нужно закрепление", "requires_attention": "требует внимания",
    "not_comparable": "несопоставимо", "comparable": "сопоставимо", "insufficient_data": "недостаточно данных",
    "mixed_versions": "разные версии тестов", "no_data": "нет данных",
    "period_v1": "план на период", "rules_v1": "перераспределение",
}
_IDENTIFIER = "|".join(sorted(map(re.escape, DISPLAY_LABELS), key=len, reverse=True))
_WRAPPED = re.compile(r"(`|\*{1,2})(" + _IDENTIFIER + r")\1")
_BARE = re.compile(r"(?<![\w-])(" + _IDENTIFIER + r")(?![\w-])")


def humanize(text):
    """Replace technical identifiers in a model answer with Russian interface labels."""
    text = _WRAPPED.sub(lambda m: DISPLAY_LABELS[m.group(2)], text)
    return _BARE.sub(lambda m: DISPLAY_LABELS[m.group(1)], text)


class AiError(Exception):
    def __init__(self, status, code, message, details=None):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details or []


def providers():
    if os.getenv("AI_ENABLED", "false").lower() != "true" or os.getenv("AI_ACCOUNT_VERIFIED", "false").lower() != "true":
        return []
    order = [p.strip() for p in os.getenv("AI_PROVIDERS", "groq,gemini").split(",") if p.strip()]
    keys = {"groq": os.getenv("GROQ_API_KEY", "").strip(), "gemini": os.getenv("GEMINI_API_KEY", "").strip()}
    return list(dict.fromkeys(p for p in order if p in keys and keys[p] and re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._/-]{0,99}", models()[p])))


def models():
    return {"groq": os.getenv("GROQ_MODEL", DEFAULT_MODELS["groq"]),
            "gemini": os.getenv("GEMINI_MODEL", DEFAULT_MODELS["gemini"])}


def status():
    active = providers()
    return {"configured": bool(active), "providers": active, "models": {p: models()[p] for p in active}}


async def _post_json(url, payload, headers):
    # Fixed provider URLs, no redirects, no environment proxy/secret forwarding.
    async with httpx.AsyncClient(timeout=httpx.Timeout(10, connect=5), follow_redirects=False, trust_env=False) as client:
        async with client.stream("POST", url, json=payload,
                                 headers={"Content-Type": "application/json", "User-Agent": USER_AGENT, **headers}) as response:
            response.raise_for_status()
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise ValueError("provider response too large")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError("provider response must be an object")
            return result


async def _groq(system, user):
    model = models()["groq"]
    payload = {"model": model, "temperature": 0.3, "max_tokens": MAX_OUTPUT_TOKENS,
               "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if model.startswith("openai/gpt-oss"):
        # Модель рассуждает перед ответом: короткое рассуждение не съедает лимит токенов и быстрее.
        payload["reasoning_effort"] = "low"
    body = await _post_json("https://api.groq.com/openai/v1/chat/completions", payload,
                      {"Authorization": f"Bearer {os.environ['GROQ_API_KEY'].strip()}"})
    text = (body.get("choices") or [{}])[0].get("message", {}).get("content") or ""
    return model, text


async def _gemini(system, user):
    model = models()["gemini"]
    body = await _post_json(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
        {"systemInstruction": {"parts": [{"text": system}]},
         "contents": [{"role": "user", "parts": [{"text": user}]}],
         "generationConfig": {"temperature": 0.3, "maxOutputTokens": MAX_OUTPUT_TOKENS}},
        {"x-goog-api-key": os.environ["GEMINI_API_KEY"].strip()},
    )
    parts = ((body.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
    return model, "".join(p.get("text", "") for p in parts)


CALLS = {"groq": _groq, "gemini": _gemini}


async def explain(kind, context, question=None):
    active = providers()
    if not active:
        raise AiError(503, "AI_NOT_CONFIGURED", "ИИ не подключён: требуется разрешённый аккаунт, ключ и явное включение администратором.")
    prompt = build_prompt(kind, context, question)
    failures = []
    try:
        # One total deadline for the whole fallback chain, including response reads.
        async with asyncio.timeout(TIMEOUT_SECONDS):
            for name in active:
                try:
                    model, text = await CALLS[name](SYSTEM_PROMPT, prompt)
                    if not isinstance(text, str) or not text.strip() or len(text) > 15000:
                        raise ValueError("invalid provider text")
                except httpx.HTTPStatusError as exc:
                    failures.append({"field": name, "reason": f"HTTP {exc.response.status_code}"})
                    logger.warning("AI provider %s failed with HTTP %s", name, exc.response.status_code)
                    continue
                except (httpx.HTTPError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
                    failures.append({"field": name, "reason": type(exc).__name__})
                    logger.warning("AI provider %s failed: %s", name, type(exc).__name__)
                    continue
                # Provider errors/bodies and credentials never enter logs or responses.
                for variable in ("GROQ_API_KEY", "GEMINI_API_KEY"):
                    secret = os.getenv(variable, "").strip()
                    if secret:
                        text = text.replace(secret, "[REDACTED]")
                return {"text": humanize(text).strip(), "provider": name, "model": model,
                        "created_at": datetime.now(timezone.utc).isoformat()}
    except TimeoutError:
        failures.append({"field": "providers", "reason": "deadline exceeded"})
    raise AiError(502, "AI_PROVIDER_ERROR", "ИИ-сервис не ответил. Повторите позже.", failures)
