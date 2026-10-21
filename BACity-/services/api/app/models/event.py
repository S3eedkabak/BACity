"""
Event (spec section 21) — the central entity. Fields map directly to the
spec's data model; `extraction_confidence` / `source_reliability` feed
ranking (section 34) and the low-confidence -> advanced-extraction path
(section 19).
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Float, Date, DateTime, ForeignKey, Text, Enum, JSON, Boolean
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.source import GUID


class EventCategory(str, enum.Enum):
    music = "Music"
    nightlife = "Nightlife"
    culture = "Culture"
    arts = "Arts"
    theatre = "Theatre"
    sports = "Sports"
    food_drink = "Food & Drink"
    education = "Education"
    workshops = "Workshops"
    community = "Community"
    networking = "Networking"
    family = "Family"
    markets = "Markets"
    festivals = "Festivals"
    student = "Student"
    technology = "Technology"
    comedy = "Comedy"
    exhibitions = "Exhibitions"
    other = "Other"


class EventStatus(str, enum.Enum):
    fresh = "fresh"
    stale = "stale"
    expired = "expired"
    removed = "removed"
    cancelled = "cancelled"
    postponed = "postponed"


class Event(Base):
    __tablename__ = "events"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)

    merged_into_id = Column(GUID(), ForeignKey("events.id"), nullable=True, index=True)
    identity_kind = Column(String, nullable=False, default="single")
    occurrences = relationship("EventOccurrence", back_populates="event", lazy="select", foreign_keys="EventOccurrence.event_id")
    offers = relationship("EventOffer", back_populates="event", lazy="selectin", foreign_keys="EventOffer.event_id")

    title = Column(String, nullable=False, index=True)
    description = Column(Text, nullable=True)

    start_time = Column(DateTime, nullable=False, index=True)  # stored UTC
    end_time = Column(DateTime, nullable=True)
    end_date = Column(Date, nullable=True)  # Inclusive publisher date; closing clock unknown.
    timezone = Column(String, nullable=False, default="Europe/Bratislava")

    venue_id = Column(GUID(), ForeignKey("venues.id"), nullable=True)
    address = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    category = Column(Enum(EventCategory, values_callable=lambda cls: [e.value for e in cls]), nullable=False, default=EventCategory.other)
    tags = Column(JSON, nullable=False, default=list)

    price = Column(Float, nullable=True)  # null = unknown, 0 = free
    currency = Column(String, nullable=True, default="EUR")
    image_url = Column(String, nullable=True)

    source_url = Column(String, nullable=False)
    source_id = Column(GUID(), ForeignKey("sources.id"), nullable=True)
    contributor_id = Column(GUID(), ForeignKey('users.id'), nullable=True, index=True)
    organization_id = Column(GUID(), ForeignKey('organizations.id'), nullable=True, index=True)
    trust_level = Column(String, nullable=False, default='Unverified')
    ticket_url = Column(String)
    neighborhood = Column(String)
    language = Column(String, nullable=False, default="sk")

    extraction_confidence = Column(Float, nullable=False, default=0.5)
    source_reliability = Column(Float, nullable=False, default=0.5)

    status = Column(Enum(EventStatus), nullable=False, default=EventStatus.fresh)
    is_manual_override = Column(Boolean, nullable=False, default=False)  # section 52

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_verified_at = Column(DateTime, default=datetime.utcnow)

    venue = relationship("Venue", back_populates="events")
    sources = relationship("EventSource", back_populates="event", cascade="all, delete-orphan", lazy="selectin")

    @property
    def start_precision(self):
        start=getattr(self,'next_occurrence_start',None) or self.start_time
        matching=[source for source in self.sources if source.start_time==start]
        if any((source.facts or {}).get('start_precision')=='time' for source in matching):
            return 'time'
        if any((source.facts or {}).get('start_precision')=='date' for source in matching):
            return 'date'
        from datetime import timezone
        from zoneinfo import ZoneInfo
        local=start.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava'))
        if local.hour==local.minute==0 and any((source.facts or {}).get('method')=='event_card' for source in matching):
            return 'date'
        return 'time'

    @property
    def recurrence_label(self):
        if self.identity_kind != 'recurring':
            return None
        rules = {(source.facts or {}).get('recurrence_rule') for source in self.sources}
        rules.discard(None)
        if len(rules) == 1:
            parts = dict(part.split('=', 1) for part in rules.pop().split(';') if '=' in part)
            if parts.get('FREQ') == 'WEEKLY' and parts.get('INTERVAL', '1') == '1':
                days = {'MO':'Monday','TU':'Tuesday','WE':'Wednesday','TH':'Thursday','FR':'Friday','SA':'Saturday','SU':'Sunday'}
                if parts.get('BYDAY') in days:
                    return 'Every ' + days[parts['BYDAY']]
                if not parts.get('BYDAY'):
                    return 'Weekly'
        return 'Selected dates'

    @property
    def last_seen_at(self):
        return self.last_verified_at
