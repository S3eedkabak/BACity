"""Minimal user model to support register/login/save-events for the MVP (section 37)."""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, JSON, Boolean, Integer, Text

from app.database import Base
from app.models.source import GUID


class User(Base):
    __tablename__ = "users"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    interests = Column(JSON, nullable=False, default=list)  # e.g. ["techno","student"]
    role = Column(String, nullable=False, default='USER')
    email_verified = Column(Boolean, nullable=False, default=False)
    identity_verified = Column(Boolean, nullable=False, default=False)
    reputation = Column(Integer, nullable=False, default=0)
    token_version = Column(Integer, nullable=False, default=0)
    active = Column(Boolean, nullable=False, default=True)
    avatar_url = Column(String)
    bio = Column(Text)
    city = Column(String, nullable=False, default='Bratislava')
    neighborhood = Column(String)
    public_profile = Column(Boolean, nullable=False, default=True)
    allow_general_messages = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
