from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.event import EventCategory
from app.schemas.event import EventOut


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)


class AreaWatchCreate(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    center_latitude: float = Field(ge=48, le=48.35)
    center_longitude: float = Field(ge=16.9, le=17.35)
    radius_km: Literal[1, 2, 5] = 2
    categories: list[EventCategory] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def unique_categories(self):
        if len(self.categories) != len(set(self.categories)):
            raise ValueError("Categories must be unique")
        return self


class AreaWatchUpdate(StrictModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    center_latitude: float | None = Field(None, ge=48, le=48.35)
    center_longitude: float | None = Field(None, ge=16.9, le=17.35)
    radius_km: Literal[1, 2, 5] | None = None
    categories: list[EventCategory] | None = Field(None, max_length=6)
    active: bool | None = None

    @model_validator(mode="after")
    def validate_update(self):
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError('Provided fields must not be null')
        if (self.center_latitude is None) != (self.center_longitude is None):
            raise ValueError("Provide both coordinates")
        if self.categories is not None and len(self.categories) != len(set(self.categories)):
            raise ValueError("Categories must be unique")
        if not self.model_fields_set:
            raise ValueError("Provide at least one field")
        return self


class SeenRequest(StrictModel):
    watermark: datetime


class AreaWatchSummaryOut(BaseModel):
    id: UUID
    name: str
    radius_km: float
    categories: list[EventCategory]
    active: bool
    locked: bool
    unseen_count: int


class AreaWatchOut(AreaWatchSummaryOut):
    center_latitude: float
    center_longitude: float
    last_viewed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class AreaWatchEventOut(BaseModel):
    event: EventOut
    discovered_at: datetime
    unseen: bool
    explanations: list[str]


class AreaWatchFeedOut(BaseModel):
    items: list[AreaWatchEventOut]
    next_cursor: str | None
    response_watermark: datetime
    unseen_count: int
    lookback_days: int
