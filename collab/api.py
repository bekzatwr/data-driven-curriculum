import json
from typing import Any, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import ai

TargetType = Literal["dataset", "topic", "textbook", "class", "teacher", "plan", "plan_topic"]
Role = Literal["teacher", "methodist", "admin", "ai"]
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
    id: str
    dataset_id: str
    target_type: str
    target_id: str
    author_name: str
    author_school: str
    author_role: str
    kind: Literal["human", "ai"]
    text: str
    created_at: str


class CommentList(BaseModel):
    items: list[Comment]
    total: int


class ExplainIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["overview", "topic", "comparison", "plan", "teachers", "comments"]
    context: dict[str, Any]
    question: str | None = Field(default=None, max_length=500)


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


router = APIRouter(prefix="/api", tags=["Collaboration"])


@router.get("/datasets/{dataset_id}/comments", response_model=CommentList)
def list_comments(dataset_id: str, request: Request,
                  target_type: TargetType | None = Query(default=None),
                  target_id: str | None = Query(default=None, max_length=200)):
    request.app.state.store.get_dataset(dataset_id)
    return request.app.state.comments.list(dataset_id, target_type=target_type, target_id=target_id)


@router.post("/datasets/{dataset_id}/comments", status_code=201, response_model=Comment)
def add_comment(dataset_id: str, payload: CommentIn, request: Request):
    request.app.state.store.get_dataset(dataset_id)
    for field in ("target_id", "author_name", "text"):
        if not getattr(payload, field):
            return _error(422, "INVALID_COMMENT", "Заполните имя и текст комментария.",
                          [{"field": field, "reason": "Пустое значение"}])
    data = payload.model_dump()
    kind = "ai" if payload.author_role == "ai" else "human"
    return request.app.state.comments.add(dataset_id, kind=kind, **data)


@router.get("/ai/status", response_model=AiStatus)
def ai_status():
    return ai.status()


@router.post("/datasets/{dataset_id}/ai/explain", response_model=Explanation)
def ai_explain(dataset_id: str, payload: ExplainIn, request: Request):
    request.app.state.store.get_dataset(dataset_id)
    size = len(json.dumps(payload.context, ensure_ascii=False).encode("utf-8"))
    if size > MAX_CONTEXT_BYTES:
        return _error(422, "AI_CONTEXT_TOO_LARGE", "Слишком много данных для ИИ-пояснения.",
                      [{"field": "context", "reason": f"{size} байт > {MAX_CONTEXT_BYTES}"}])
    try:
        return ai.explain(payload.kind, payload.context, payload.question)
    except ai.AiError as exc:
        return _error(exc.status, exc.code, exc.message, exc.details)
