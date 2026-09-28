"""Private user-selected radius watches for newly discovered events."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Index, JSON, String, UniqueConstraint

from app.database import Base
from app.models.source import GUID


class AreaWatch(Base):
    __tablename__ = "area_watches"
    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_area_watch_user_name"),
        CheckConstraint("center_latitude >= 48 AND center_latitude <= 48.35", name="ck_area_watch_latitude"),
        CheckConstraint("center_longitude >= 16.9 AND center_longitude <= 17.35", name="ck_area_watch_longitude"),
        CheckConstraint("radius_km IN (1, 2, 5)", name="ck_area_watch_radius"),
        Index("ix_area_watches_user_active", "user_id", "active"),
    )

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(80), nullable=False)
    center_latitude = Column(Float, nullable=False)
    center_longitude = Column(Float, nullable=False)
    radius_km = Column(Float, nullable=False)
    categories = Column(JSON, nullable=False, default=list)
    active = Column(Boolean, nullable=False, default=True)
    last_viewed_at = Column(DateTime)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
