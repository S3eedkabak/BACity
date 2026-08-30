"""CRUD for saved events (spec section 38: save/unsave/list)."""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.saved_event import SavedEvent
from app.models.event import Event, EventStatus


def save_event(db: Session, *, user_id: UUID, event_id: UUID) -> SavedEvent:
    existing = db.scalar(
        select(SavedEvent).where(SavedEvent.user_id == user_id, SavedEvent.event_id == event_id)
    )
    if existing:
        return existing
    saved = SavedEvent(user_id=user_id, event_id=event_id)
    db.add(saved)
    db.commit()
    db.refresh(saved)
    return saved


def unsave_event(db: Session, *, user_id: UUID, event_id: UUID) -> bool:
    existing = db.scalar(
        select(SavedEvent).where(SavedEvent.user_id == user_id, SavedEvent.event_id == event_id)
    )
    if not existing:
        return False
    db.delete(existing)
    db.commit()
    return True


def list_saved_events(db: Session, *, user_id: UUID) -> list[Event]:
    stmt = (
        select(Event)
        .join(SavedEvent, SavedEvent.event_id == Event.id)
        .where(SavedEvent.user_id == user_id)
        .where(Event.status.in_([EventStatus.fresh, EventStatus.stale]))
        .order_by(Event.start_time.asc())
    )
    return list(db.scalars(stmt))


def is_event_saved(db: Session, *, user_id: UUID, event_id: UUID) -> bool:
    existing = db.scalar(
        select(SavedEvent).where(SavedEvent.user_id == user_id, SavedEvent.event_id == event_id)
    )
    return existing is not None