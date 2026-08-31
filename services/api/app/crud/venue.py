from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.venue import Venue
from app.models.event import Event, EventStatus


def get_venue(db: Session, venue_id: UUID) -> Optional[Venue]:
    return db.get(Venue, venue_id)


def get_venue_events(db: Session, venue_id: UUID, limit: int = 50) -> list[Event]:
    stmt = (
        select(Event)
        .where(Event.venue_id == venue_id)
        .where(Event.status.in_([EventStatus.fresh, EventStatus.stale]))
        .order_by(Event.start_time.asc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def find_or_create_venue(db: Session, *, name: str, address: str | None,
                          latitude: float | None, longitude: float | None,
                          city: str = "Bratislava") -> Venue:
    """
    Used by the processing pipeline (crawler side) so repeated crawls of
    the same physical place don't create duplicate Venue rows (spec section 22).
    Matches on normalized name + city; good enough for MVP, a fuzzier match
    can replace this once real data volume justifies it.
    """
    stmt = select(Venue).where(
        Venue.city == city, Venue.name.ilike(name.strip())
    )
    existing = db.scalar(stmt)
    if existing:
        return existing

    venue = Venue(name=name.strip(), address=address, city=city,
                   latitude=latitude, longitude=longitude)
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return venue
