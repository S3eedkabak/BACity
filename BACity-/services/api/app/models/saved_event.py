"""
Saved Events (spec section 38): join table between users and events.
Kept as its own model rather than a JSON list on User so we can index it,
query "is this event saved by this user" cheaply, and support future
fields (e.g. saved_at, notified) without a migration on User itself.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base
from app.models.source import GUID


class SavedEvent(Base):
    __tablename__ = "saved_events"
    __table_args__ = (UniqueConstraint("user_id", "event_id", name="uq_saved_event_user_event"),)

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    user_id = Column(GUID(), ForeignKey("users.id"), nullable=False, index=True)
    event_id = Column(GUID(), ForeignKey("events.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("Event")