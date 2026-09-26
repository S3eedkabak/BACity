"""
Source Registry (spec section 13). One row per crawlable origin — a venue
site, a university events page, a cultural institution, etc.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Boolean, DateTime, Enum, Integer, JSON, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR

from app.database import Base


class GUID(TypeDecorator):
    """Portable UUID: native uuid on Postgres, CHAR(36) elsewhere (SQLite)."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(str(value)))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid.UUID):
            return uuid.UUID(str(value))
        return value


class SourceType(str, enum.Enum):
    venue = "venue"
    club = "club"
    restaurant = "restaurant"
    theatre = "theatre"
    museum = "museum"
    gallery = "gallery"
    university = "university"
    community = "community"
    sports = "sports"
    festival = "festival"
    government = "government"
    tourism = "tourism"
    blog = "blog"
    event_platform = "event_platform"


class SourceStatus(str, enum.Enum):
    active = "active"
    paused = "paused"
    disabled = "disabled"
    failing = "failing"


class Source(Base):
    __tablename__ = "sources"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=False, unique=True, index=True)
    base_url = Column(String, nullable=False)
    event_url = Column(String, nullable=True)
    source_type = Column(Enum(SourceType), nullable=False, default=SourceType.venue)
    language = Column(String, nullable=False, default="sk")
    city = Column(String, nullable=False, default="Bratislava")

    # Scheduling (spec section 48)
    crawl_frequency_minutes = Column(Integer, nullable=False, default=720)  # 12h default
    last_crawled = Column(DateTime, nullable=True)
    next_crawl = Column(DateTime, nullable=True)

    parser = Column(String, nullable=True)  # name of source-specific parser, if any
    reliability_score = Column(Float, nullable=False, default=0.7)
    status = Column(Enum(SourceStatus), nullable=False, default=SourceStatus.active)
    requires_js = Column(Boolean, nullable=False, default=False)  # Playwright fallback needed

    # Compact operational snapshot. Detailed, bounded history lives in crawler_runs.
    last_attempt_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    crawl_status = Column(String, nullable=False, default="never_run")
    pages_processed = Column(Integer, nullable=False, default=0)
    items_processed = Column(Integer, nullable=False, default=0)
    accepted_events = Column(Integer, nullable=False, default=0)
    rejected_events = Column(Integer, nullable=False, default=0)
    extraction_errors = Column(Integer, nullable=False, default=0)
    consecutive_failures = Column(Integer, nullable=False, default=0)
    last_error = Column(String, nullable=True)
    last_skip_reasons = Column(JSON, nullable=False, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    crawl_runs = relationship("CrawlerRun", back_populates="source", cascade="all, delete-orphan")


class CrawlerRun(Base):
    """Bounded diagnostic summary; never stores response bodies or secrets."""

    __tablename__ = "crawler_runs"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    source_id = Column(GUID(), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False, index=True)
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=False)
    success = Column(Boolean, nullable=False)
    status = Column(String, nullable=False)
    pages_processed = Column(Integer, nullable=False, default=0)
    items_processed = Column(Integer, nullable=False, default=0)
    accepted_events = Column(Integer, nullable=False, default=0)
    rejected_events = Column(Integer, nullable=False, default=0)
    extraction_errors = Column(Integer, nullable=False, default=0)
    skip_reasons = Column(JSON, nullable=False, default=dict)
    error = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    source = relationship("Source", back_populates="crawl_runs")
