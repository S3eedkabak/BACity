from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.event import EventCategory
from app.schemas.event import EventOut


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GroupCreate(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    target_date: date
    start_time: time | None = None
    end_time: time | None = None
    categories: list[EventCategory] = Field(default_factory=list, max_length=6)
    max_participants: int = Field(8, ge=2, le=12)

    @model_validator(mode="after")
    def validate_values(self):
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError("Provide both start_time and end_time")
        if len(self.categories) != len(set(self.categories)):
            raise ValueError("Categories must be unique")
        return self


class GroupUpdate(StrictModel):
    name: str | None = Field(None, min_length=1, max_length=80)
    categories: list[EventCategory] | None = Field(None, max_length=6)
    max_participants: int | None = Field(None, ge=2, le=12)

    @model_validator(mode="after")
    def unique_categories(self):
        if self.categories is not None and len(self.categories) != len(set(self.categories)):
            raise ValueError("Categories must be unique")
        return self


class JoinRequest(StrictModel):
    code: str = Field(min_length=32, max_length=128)


class PreferenceUpdate(StrictModel):
    liked_categories: list[EventCategory] = Field(default_factory=list, max_length=6)
    disliked_categories: list[EventCategory] = Field(default_factory=list, max_length=6)
    ready: bool = True

    @model_validator(mode="after")
    def disjoint_categories(self):
        if len(self.liked_categories) != len(set(self.liked_categories)) or len(self.disliked_categories) != len(set(self.disliked_categories)):
            raise ValueError("Preference categories must be unique")
        if set(self.liked_categories) & set(self.disliked_categories):
            raise ValueError("A category cannot be both liked and disliked")
        return self


class MatchRequest(StrictModel):
    latitude: float | None = Field(None, ge=48, le=48.35)
    longitude: float | None = Field(None, ge=16.9, le=17.35)

    @model_validator(mode="after")
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("Provide both coordinates")
        return self


class VoteRequest(StrictModel):
    candidate_id: UUID
    value: Literal[-1, 0, 1]


class GroupParticipantOut(BaseModel):
    id: UUID
    display_name: str
    avatar_url: str | None
    is_host: bool
    ready: bool


class VoteAggregateOut(BaseModel):
    likes: int
    neutral: int
    dislikes: int
    score: int


class GroupCandidateOut(BaseModel):
    id: UUID
    event: EventOut
    explanations: list[str]
    my_vote: Literal[-1, 0, 1] | None = None
    aggregate: VoteAggregateOut | None = None


class GroupRoundOut(BaseModel):
    id: UUID
    number: int
    status: Literal["voting", "completed"]
    voted_participants: int
    participant_count: int
    candidates: list[GroupCandidateOut]


class GroupSummaryOut(BaseModel):
    id: UUID
    name: str
    status: Literal["open", "ready", "voting", "completed", "expired", "cancelled"]
    target_date: date
    starts_at: datetime
    ends_at: datetime
    participant_count: int
    max_participants: int
    role: Literal["host", "participant"]


class GroupDetailOut(GroupSummaryOut):
    categories: list[EventCategory]
    expires_at: datetime
    participants: list[GroupParticipantOut]
    round: GroupRoundOut | None


class GroupCreateOut(BaseModel):
    group: GroupDetailOut
    join_code: str
    join_code_expires_at: datetime


class InviteOut(BaseModel):
    join_code: str
    expires_at: datetime
