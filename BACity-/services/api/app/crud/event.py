"""
Event CRUD + query helpers.

`nearby_events` is the one place that cares which database is running:
on Postgres it issues an ST_DWithin query against a PostGIS geography
built on the fly from lat/lng (no dedicated geometry column needed yet —
see docs/architecture.md); everywhere else (SQLite, for tests/local dev)
it does a cheap bounding-box prefilter plus a haversine distance check in
Python. Same inputs, same result shape, either way.
"""
import math
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.event import Event, EventStatus

EARTH_RADIUS_KM = 6371.0


def get_event(db: Session, event_id: UUID) -> Optional[Event]:
    return db.get(Event, event_id)


def create_event(db: Session, event: Event) -> Event:
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_events(
    db: Session,
    *,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    free_only: bool = False,
    starts_after: Optional[datetime] = None,
    starts_before: Optional[datetime] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[int, list[Event]]:
    stmt = select(Event).where(Event.status.in_([EventStatus.fresh, EventStatus.stale]))
    if category:
        stmt = stmt.where(Event.category == category)
    if free_only:
        stmt = stmt.where(Event.price == 0)
    if starts_after:
        stmt = stmt.where(Event.start_time >= starts_after)
    if starts_before:
        stmt = stmt.where(Event.start_time <= starts_before)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    stmt = stmt.order_by(Event.start_time.asc()).limit(limit).offset(offset)
    items = list(db.scalars(stmt))

    if tag:
        items = [e for e in items if tag in (e.tags or [])]

    return total, items


def search_events(db: Session, query: str, limit: int = 20) -> list[Event]:
    """
    Naive text search for the MVP path that doesn't go through OpenSearch
    (see services/api/app/api/routes/events.py). Good enough for local dev
    and for keeping the API usable before the search-indexing worker exists;
    section 32-34 describe the OpenSearch-backed version this is a stand-in for.
    """
    like = f"%{query.lower()}%"
    stmt = (
        select(Event)
        .where(Event.status.in_([EventStatus.fresh, EventStatus.stale]))
        .where(func.lower(Event.title).like(like) | func.lower(Event.description).like(like))
        .order_by(Event.start_time.asc())
        .limit(limit)
    )
    return list(db.scalars(stmt))


def nearby_events(
    db: Session, *, lat: float, lng: float, radius_km: float = 5.0, limit: int = 50
) -> list[Event]:
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"

    if dialect == "postgresql":
        # ST_DistanceSphere gives great-circle distance in meters directly
        # from two points, no separate geometry column required.
        distance = func.ST_DistanceSphere(
            func.ST_MakePoint(Event.longitude, Event.latitude),
            func.ST_MakePoint(lng, lat),
        )
        stmt = (
            select(Event)
            .where(Event.latitude.isnot(None), Event.longitude.isnot(None))
            .where(Event.status.in_([EventStatus.fresh, EventStatus.stale]))
            .where(distance <= radius_km * 1000)
            .order_by(distance.asc())
            .limit(limit)
        )
        return list(db.scalars(stmt))

    # Portable fallback: bounding-box prefilter in SQL, exact haversine in Python.
    deg_pad = radius_km / 111.0  # ~111km per degree latitude
    stmt = (
        select(Event)
        .where(Event.latitude.isnot(None), Event.longitude.isnot(None))
        .where(Event.status.in_([EventStatus.fresh, EventStatus.stale]))
        .where(Event.latitude.between(lat - deg_pad, lat + deg_pad))
        .where(Event.longitude.between(lng - deg_pad, lng + deg_pad))
    )
    candidates = list(db.scalars(stmt))

    def haversine_km(lat1, lon1, lat2, lon2):
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
        return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

    scored = [
        (haversine_km(lat, lng, e.latitude, e.longitude), e)
        for e in candidates
    ]
    scored = [s for s in scored if s[0] <= radius_km]
    scored.sort(key=lambda s: s[0])
    return [e for _, e in scored[:limit]]


def viewport_events(
    db: Session,
    *,
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    limit: int = 200,
) -> list[Event]:
    """Return only mapped events inside the current map viewport."""
    stmt = (
        select(Event)
        .where(Event.latitude.isnot(None), Event.longitude.isnot(None))
        .where(Event.status.in_([EventStatus.fresh, EventStatus.stale]))
        .where(Event.latitude.between(min_lat, max_lat))
        .where(Event.longitude.between(min_lng, max_lng))
        .order_by(Event.start_time.asc())
        .limit(limit)
    )
    return list(db.scalars(stmt))
