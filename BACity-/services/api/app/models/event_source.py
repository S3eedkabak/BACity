"""All evidence remains attached when multiple publishers describe one event."""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.source import GUID


class EventSource(Base):
    __tablename__ = 'event_sources'
    __table_args__ = (UniqueConstraint('source_url', 'start_time', 'title_key', name='uq_event_source_occurrence'),)
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    event_id = Column(GUID(), ForeignKey('events.id', ondelete='CASCADE'), nullable=False, index=True)
    source_id = Column(GUID(), ForeignKey('sources.id'), nullable=True)
    source_url = Column(String, nullable=False)
    original_source_url = Column(String, nullable=True)
    source_name = Column(String, nullable=True)
    start_time = Column(DateTime, nullable=False)
    title_key = Column(String, nullable=False)
    reliability = Column(Float, nullable=False)
    dedup_confidence = Column(Float, nullable=False, default=1)
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    event = relationship('Event', back_populates='sources')
