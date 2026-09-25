from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator, field_serializer
from urllib.parse import urlsplit

from app.models.event import EventCategory, EventStatus


class VenueSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class EventBase(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    timezone: str = "Europe/Bratislava"
    address: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    category: EventCategory = EventCategory.other
    tags: list[str] = []
    price: Optional[float] = None
    currency: Optional[str] = "EUR"
    image_url: Optional[str] = None
    source_url: str
    language: str = "sk"


class EventCreate(EventBase):
    title: str = Field(min_length=2, max_length=500)
    status: EventStatus = EventStatus.fresh
    original_source_url: Optional[str] = None
    venue_id: Optional[UUID] = None
    source_id: Optional[UUID] = None
    venue_name: Optional[str] = None
    source_name: Optional[str] = None
    extraction_confidence: float = Field(default=0.5, ge=0.5, le=1)
    source_reliability: float = Field(default=0.5, ge=0, le=1)

    @model_validator(mode='after')
    def validate_ingestion(self):
        url = urlsplit(self.source_url)
        if url.scheme not in ('http', 'https') or not url.hostname or url.username:
            raise ValueError('source_url must be a public HTTP(S) URL')
        if self.end_time:
            start = self.start_time.replace(tzinfo=timezone.utc) if self.start_time.tzinfo is None else self.start_time
            end = self.end_time.replace(tzinfo=timezone.utc) if self.end_time.tzinfo is None else self.end_time
            if end < start:
                raise ValueError('end_time precedes start_time')
        if self.latitude is not None or self.longitude is not None:
            if self.latitude is None or self.longitude is None or not (48 <= self.latitude <= 48.35 and 16.9 <= self.longitude <= 17.35):
                raise ValueError('coordinates must be within Bratislava')
        return self


class EventSourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source_url: str
    original_source_url: Optional[str] = None
    source_name: Optional[str] = None
    reliability: float
    dedup_confidence: float
    last_seen_at: datetime


class EventOut(EventBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: EventStatus
    extraction_confidence: float
    source_reliability: float
    venue: Optional[VenueSummary] = None
    created_at: datetime
    updated_at: datetime
    sources: list[EventSourceOut] = []
    last_seen_at: Optional[datetime] = None
    trust_level: str = 'Unverified'
    contributor_id: Optional[UUID] = None
    organization_id: Optional[UUID] = None
    ticket_url: Optional[str] = None
    neighborhood: Optional[str] = None

    @field_serializer('start_time', 'end_time', 'created_at', 'updated_at', 'last_seen_at')
    def serialize_utc(self, value):
        if value is None:
            return None
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()


class EventListResponse(BaseModel):
    total: int
    items: list[EventOut]


class SaveEventResponse(BaseModel):
    event_id: UUID
    saved: bool
