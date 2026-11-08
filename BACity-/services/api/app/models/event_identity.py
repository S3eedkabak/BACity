"""Occurrence, offer and reconciliation evidence, independent of discovery cards."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Float, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import relationship
from app.database import Base
from app.models.source import GUID


class EventOccurrence(Base):
    __tablename__ = 'event_occurrences'
    __table_args__ = (UniqueConstraint('event_id','start_time',name='uq_occurrence_identity_start'),)
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    event_id = Column(GUID(), ForeignKey('events.id'), nullable=False, index=True)
    source_url = Column(String, nullable=False)
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    status = Column(String, nullable=False, default='fresh')
    start_precision = Column(String, nullable=False, default='time')
    publisher_event_id = Column(String, index=True)
    event = relationship('Event', back_populates='occurrences', foreign_keys=[event_id])


class EventOffer(Base):
    __tablename__ = 'event_offers'
    __table_args__ = (UniqueConstraint('event_id', 'source_url', 'label', name='uq_offer_event_url_label'),)
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    event_id = Column(GUID(), ForeignKey('events.id'), nullable=False, index=True)
    source_url = Column(String, nullable=False)
    label = Column(String, nullable=False)
    price = Column(Float)
    currency = Column(String)
    valid_from = Column(DateTime)
    valid_until = Column(DateTime)
    event = relationship('Event', back_populates='offers', foreign_keys=[event_id])


class EventReconciliation(Base):
    __tablename__ = 'event_reconciliations'
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    root_id = Column(GUID(), ForeignKey('events.id'), nullable=False, index=True)
    alias_id = Column(GUID(), ForeignKey('events.id'), nullable=False, unique=True)
    reason = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    before = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
