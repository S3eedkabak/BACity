"""Venue (spec section 22) — deduplicated physical locations events belong to."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.source import GUID


class Venue(Base):
    __tablename__ = "venues"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False, index=True)
    address = Column(String, nullable=True)
    city = Column(String, nullable=False, default="Bratislava")
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    website = Column(String, nullable=True)
    category = Column(String, nullable=True)

    source_id = Column(GUID(), ForeignKey("sources.id"), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    events = relationship("Event", back_populates="venue")
