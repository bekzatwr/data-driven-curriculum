from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

Hours = Annotated[int, Field(strict=True, ge=0, le=10000)]
Identifier = Annotated[str, Field(min_length=1, max_length=120)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Settings(Model):
    mode: Literal["rules_v1", "period"] = "rules_v1"
    target_pct: float = Field(70, ge=0, le=100)
    donor_pct: float = Field(80, ge=0, le=100)
    min_students: int = Field(10, strict=True, ge=10)
    max_change: Hours = 2

    @model_validator(mode="after")
    def ordered(self):
        if self.target_pct > self.donor_pct:
            raise ValueError("Цель не может превышать порог донора")
        return self


class ConstraintFields(Model):
    topic_id: Identifier
    topic_name: str
    topic_order: int = Field(strict=True, ge=0)
    current_hours: Hours
    min_hours: Hours
    max_hours: Hours
    importance: int = Field(strict=True, ge=1, le=3)
    is_locked: bool = Field(strict=True)


class Constraint(ConstraintFields):
    @model_validator(mode="after")
    def bounds(self):
        if not self.min_hours <= self.current_hours <= self.max_hours:
            raise ValueError(f"{self.topic_id}: текущие часы вне границ")
        return self


class PeriodConstraint(ConstraintFields):
    @model_validator(mode="after")
    def bounds(self):
        if self.min_hours > self.max_hours:
            raise ValueError(f"{self.topic_id}: минимум превышает максимум")
        if self.is_locked and not self.min_hours <= self.current_hours <= self.max_hours:
            raise ValueError(f"{self.topic_id}: заблокированные часы вне границ")
        return self


class Override(Model):
    min_hours: Hours | None = None
    max_hours: Hours | None = None
    importance: int | None = Field(None, strict=True, ge=1, le=3)
    is_locked: bool | None = Field(None, strict=True)


class PlanRequest(Model):
    class_id: Identifier
    test_versions: dict[Identifier, Identifier] = Field(default_factory=dict)
    constraints: dict[Identifier, Override] = Field(default_factory=dict)
    settings: Settings = Field(default_factory=Settings)


class SaveRequest(PlanRequest):
    hours_by_topic: dict[Identifier, Hours] | None = None
    comment: str = Field("", max_length=2000)
