"""P1 input structure owned by Bekzat; review matching, metrics and routes are separate modules."""
from datetime import date
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .errors import ApiError
from .schemas import Identifier, Metadata

ActualHours = Annotated[int, Field(strict=True, ge=0, le=999_999_999)]


class PlanReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    followup_dataset_id: Identifier
    started_on: date
    completed_on: date
    actual_hours_by_topic: dict[Identifier, ActualHours] = Field(min_length=1, max_length=100)
    identity_mapping_confirmed: bool = Field(strict=True)
    comment: str = Field(default="", max_length=2000)

    @field_validator("actual_hours_by_topic", mode="before")
    @classmethod
    def unique_topic_keys(cls, value):
        if isinstance(value, dict):
            keys = [key.strip() if isinstance(key, str) else key for key in value]
            if len(set(keys)) != len(keys):
                raise ValueError("Topic IDs must remain unique after trimming whitespace")
        return value

    @field_validator("started_on", "completed_on", mode="before")
    @classmethod
    def iso_date(cls, value):
        return Metadata.iso_date(value)

    @model_validator(mode="after")
    def date_order(self):
        if self.started_on > self.completed_on:
            raise ValueError("started_on must not be after completed_on")
        return self


def validate_review_structure(payload: dict, topic_ids: set[str]) -> PlanReviewInput:
    """Called by Aidana before calculation. False identity confirmation is kept for explicit handling.

    This checks structure and topic coverage, not whether individual test results are comparable.
    Toni must check identity confirmation, compatible tests and baseline <= start <= end <= follow-up.
    """
    try:
        result = PlanReviewInput.model_validate(payload)
    except ValidationError as exc:
        details = [{"file": "request", "row": None, "field": ".".join(map(str, e["loc"])), "reason": e["msg"]}
                   for e in exc.errors(include_input=False, include_url=False, include_context=False)]
        raise ApiError(422, "INVALID_REVIEW", "Проверьте параметры повторного тестирования.", details) from None
    missing = topic_ids - result.actual_hours_by_topic.keys()
    extra = result.actual_hours_by_topic.keys() - topic_ids
    if missing or extra:
        details = [{"file": "request", "row": None, "field": "actual_hours_by_topic",
                    "reason": f"Укажите часы ровно по темам плана. Пропущены: {', '.join(sorted(missing)) or 'нет'}; "
                              f"лишние: {', '.join(sorted(extra)) or 'нет'}."}]
        raise ApiError(422, "INVALID_REVIEW", "Список тем не совпадает с планом.", details)
    return result
