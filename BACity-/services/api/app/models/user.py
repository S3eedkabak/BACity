"""Minimal user model to support register/login/save-events for the MVP (section 37)."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON

from app.database import Base
from app.models.source import GUID


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    interests = Column(JSON, nullable=False, default=list)  # e.g. ["techno","student"]

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
