from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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
    venue_id: Optional[UUID] = None
    source_id: Optional[UUID] = None
    extraction_confidence: float = 0.5
    source_reliability: float = 0.5


class EventOut(EventBase):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: EventStatus
    extraction_confidence: float
    source_reliability: float
    venue: Optional[VenueSummary] = None
    created_at: datetime
    updated_at: datetime


class EventListResponse(BaseModel):
    total: int
    items: list[EventOut]
