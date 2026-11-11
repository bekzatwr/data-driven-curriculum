import json
from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from starlette.concurrency import run_in_threadpool
from backend.app.errors import ApiError
from analytics.models import Error
from .context import build_context, Selectors

from . import ai

TargetType = Literal["dataset", "topic", "textbook", "class", "teacher", "plan", "plan_topic"]
Role = Literal["teacher", "methodist", "admin"]
MAX_CONTEXT_BYTES = 30_000


class CommentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    target_type: TargetType
    target_id: str = Field(min_length=1, max_length=200)
    author_name: str = Field(min_length=1, max_length=80)
    author_school: str = Field(default="", max_length=120)
    author_role: Role = "teacher"
    text: str = Field(min_length=1, max_length=4000)

    @field_validator("target_id", "author_name", "author_school", "text")
    @classmethod
    def strip(cls, value: str) -> str:
        return value.strip()


class Comment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    dataset_id: str
    target_type: TargetType
    target_id: str = Field(min_length=1, max_length=200)
    author_name: str = Field(min_length=1, max_length=80)
    author_school: str = Field(max_length=120)
    author_role: Literal["teacher", "methodist", "admin", "ai"]
    kind: Literal["human", "ai"]
    text: str = Field(min_length=1, max_length=4000)
    created_at: str


class CommentList(BaseModel):
    items: list[Comment]
    total: int


class ExplainIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["overview", "topic", "comparison", "plan", "teachers", "comments"]
    context: dict[str, Any] = Field(description="At most 30000 UTF-8 JSON bytes; only server-validated selectors. Arbitrary aggregates/text are rejected.",
                                    json_schema_extra={"x-selector-schema": Selectors.model_json_schema()})
    question: str | None = Field(default=None, max_length=500, description="Reserved; nonempty free text currently rejected with AI_FREE_TEXT_DISABLED.")


class Explanation(BaseModel):
    text: str
    provider: str
    model: str
    created_at: str


class AiStatus(BaseModel):
    configured: bool
    providers: list[str]
    models: dict[str, str]


def _error(status, code, message, details=None):
    details = details or []
    return JSONResponse(status_code=status, content={
        "code": code, "message": message, "details": details, "total_errors": len(details)})


router = APIRouter(prefix="/api", tags=["Collaboration"], responses={
    status: {"model": Error, "description": description}
    for status, description in {
        403: "Read-only demo or non-synthetic AI data", 404: "Dataset or comment target not found",
        409: "Comment storage quota exceeded", 413: "JSON body exceeds 64 KiB",
        422: "Invalid input or unsafe AI context", 429: "Rate limited; see Retry-After seconds",
        502: "AI provider failure", 503: "Feature disabled, AI not configured or database unavailable",
    }.items()})


@router.get("/datasets/{dataset_id}/comments", response_model=CommentList)
def list_comments(dataset_id: str, request: Request,
                  target_type: TargetType | None = Query(default=None),
                  target_id: str | None = Query(default=None, max_length=200)):
    request.app.state.store.get_dataset(dataset_id)
    if not request.app.state.settings.comments_enabled:
        raise ApiError(503, "COMMENTS_DISABLED", "Комментарии отключены администратором.")
    return request.app.state.comments.list(dataset_id, target_type=target_type, target_id=target_id)


@router.post("/datasets/{dataset_id}/comments", status_code=201, response_model=Comment)
def add_comment(dataset_id: str, payload: CommentIn, request: Request):
    request.app.state.store.get_dataset(dataset_id)
    for field in ("target_id", "author_name", "text"):
        if not getattr(payload, field):
            return _error(422, "INVALID_COMMENT", "Заполните имя и текст комментария.",
                          [{"field": field, "reason": "Пустое значение"}])
    data = payload.model_dump()
    return request.app.state.comments.add(dataset_id, kind="human", **data,
        response_factory=lambda row: JSONResponse(status_code=201, content=row))


@router.get("/ai/status", response_model=AiStatus)
def ai_status(request: Request):
    return ai.status() if request.app.state.settings.ai_allowed else {"configured": False, "providers": [], "models": {}}


@router.post("/datasets/{dataset_id}/ai/explain", response_model=Explanation)
async def ai_explain(dataset_id: str, payload: ExplainIn, request: Request):
    await run_in_threadpool(request.app.state.store.get_dataset, dataset_id)
    try:
        size = len(json.dumps(payload.context, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (ValueError, UnicodeError):
        return _error(422, "AI_INVALID_CONTEXT", "Некорректный JSON context.")
    if size > MAX_CONTEXT_BYTES:
        return _error(422, "AI_CONTEXT_TOO_LARGE", "Слишком много данных для ИИ-пояснения.",
                      [{"field": "context", "reason": f"{size} байт > {MAX_CONTEXT_BYTES}"}])
    try:
        if not ai.status()["configured"]:
            raise ai.AiError(503, "AI_NOT_CONFIGURED", "ИИ не подключён на сервере.")
        context = await run_in_threadpool(build_context, request, dataset_id, payload.kind, payload.context, payload.question)
        if len(json.dumps(context, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_CONTEXT_BYTES:
            raise ai.AiError(422, "AI_CONTEXT_TOO_LARGE", "Агрегированный контекст превышает 30 КБ. Уточните фильтры.")
        return await ai.explain(payload.kind, context)
    except ai.AiError as exc:
        return _error(exc.status, exc.code, exc.message, exc.details)
