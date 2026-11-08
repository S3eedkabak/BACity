"""Durable evidence of scheduled event maintenance and retention cleanup."""
import uuid
from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from app.database import Base
from app.models.source import GUID


class EventMaintenanceRun(Base):
    __tablename__ = 'event_maintenance_runs'
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    finished_at = Column(DateTime, nullable=False)
    reconciled_aliases = Column(Integer, nullable=False, default=0)
    expired_events = Column(Integer, nullable=False, default=0)
    expired_occurrences = Column(Integer, nullable=False, default=0)
    archived_occurrences = Column(Integer, nullable=False, default=0)
    archived_offers = Column(Integer, nullable=False, default=0)
    diagnostics = Column(JSON, nullable=False, default=dict)


class EventMaintenanceArchive(Base):
    __tablename__ = 'event_maintenance_archives'
    __table_args__ = (UniqueConstraint('kind', 'record_id', name='uq_maintenance_archive_record'),)
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    kind = Column(String(32), nullable=False)
    record_id = Column(GUID(), nullable=False)
    event_id = Column(GUID(), ForeignKey('events.id'), nullable=False, index=True)
    snapshot = Column(JSON, nullable=False)
    archived_at = Column(DateTime, nullable=False, default=datetime.utcnow)
