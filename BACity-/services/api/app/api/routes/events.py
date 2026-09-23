from difflib import SequenceMatcher
from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import event as event_crud
from app.crud import saved_event as saved_event_crud
from app.schemas.event import EventOut, EventListResponse, SaveEventResponse, EventCreate
from app.api.deps import get_current_user
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.venue import Venue

router = APIRouter(prefix="/events", tags=["events"])


def _norm(value: Optional[str]) -> str:
    return " ".join((value or "").lower().split())


def _resolve_venue(db: Session, payload: EventCreate) -> Optional[Venue]:
    if payload.venue_id:
        return db.get(Venue, payload.venue_id)

    if not payload.venue_name and not payload.address:
        return None

    name = payload.venue_name or payload.address or "Unknown venue"
    address = payload.address

    venue = (
        db.query(Venue)
        .filter(
            Venue.name == name,
            Venue.address == address,
        )
        .first()
    )
    if venue:
        if payload.latitude is not None:
            venue.latitude = payload.latitude
        if payload.longitude is not None:
            venue.longitude = payload.longitude
        return venue

    venue = Venue(
        name=name,
        address=address,
        city="Bratislava",
        latitude=payload.latitude,
        longitude=payload.longitude,
    )
    db.add(venue)
    db.flush()
    return venue


def _find_fuzzy_duplicate(db: Session, payload: EventCreate) -> Optional[Event]:
    candidates = (
        db.query(Event)
        .filter(
            Event.start_time == payload.start_time,
            Event.status.in_([EventStatus.fresh, EventStatus.stale]),
        )
        .limit(200)
        .all()
    )

    target_title = _norm(payload.title)
    target_address = _norm(payload.address)

    for candidate in candidates:
        title_similarity = SequenceMatcher(
            None, target_title, _norm(candidate.title)
        ).ratio()
        if title_similarity < 0.90:
            continue

        candidate_address = _norm(candidate.address)
        target_venue = _norm(payload.venue_name)
        candidate_venue = _norm(candidate.venue.name if candidate.venue else "")
        same_venue = bool(
            target_address and candidate_address and target_address == candidate_address
        )
        if target_venue and candidate_venue and target_venue == candidate_venue:
            same_venue = True
        if payload.venue_id and candidate.venue_id == payload.venue_id:
            same_venue = True

        if same_venue:
            return candidate

    return None


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
):
    """Ingest a crawler event idempotently and with basic cross-source dedup."""
    exact = (
        db.query(Event)
        .filter(
            Event.source_url == payload.source_url,
            Event.title == payload.title,
            Event.start_time == payload.start_time,
        )
        .first()
    )
    existing = exact or _find_fuzzy_duplicate(db, payload)

    venue = _resolve_venue(db, payload)

    if existing:
        update_values = payload.model_dump(
            exclude={"venue_id", "venue_name", "source_name"}
        )
        for field, value in update_values.items():
            if hasattr(existing, field) and value is not None:
                setattr(existing, field, value)
        if venue:
            existing.venue_id = venue.id
            if existing.address is None:
                existing.address = venue.address
        db.commit()
        db.refresh(existing)
        return existing

    values = payload.model_dump(
        exclude={"venue_name", "source_name", "venue_id"}
    )
    event = Event(
        **values,
        venue_id=venue.id if venue else payload.venue_id,
        status=EventStatus.fresh,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.get("", response_model=EventListResponse)
def list_events(
    category: Optional[str] = None,
    tag: Optional[str] = None,
    free_only: bool = False,
    starts_after: Optional[datetime] = None,
    starts_before: Optional[datetime] = None,
    limit: int = Query(20, le=100),
    offset: int = 0,
    db: Session = Depends(get_db),
):
    total, items = event_crud.list_events(
        db,
        category=category,
        tag=tag,
        free_only=free_only,
        starts_after=starts_after,
        starts_before=starts_before,
        limit=limit,
        offset=offset,
    )
    return EventListResponse(total=total, items=items)


@router.get("/search", response_model=list[EventOut])
def search_events(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, le=100),
    db: Session = Depends(get_db),
):
    return event_crud.search_events(db, query=q, limit=limit)


@router.get("/viewport", response_model=list[EventOut])
def viewport_events(
    min_lat: float,
    max_lat: float,
    min_lng: float,
    max_lng: float,
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
):
    return event_crud.viewport_events(
        db,
        min_lat=min_lat,
        max_lat=max_lat,
        min_lng=min_lng,
        max_lng=max_lng,
        limit=limit,
    )


@router.get("/nearby", response_model=list[EventOut])
def nearby_events(
    lat: float,
    lng: float,
    radius_km: float = Query(5.0, gt=0, le=50),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    return event_crud.nearby_events(
        db, lat=lat, lng=lng, radius_km=radius_km, limit=limit
    )


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: UUID, db: Session = Depends(get_db)):
    event = event_crud.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post(
    "/{event_id}/save",
    response_model=SaveEventResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not event_crud.get_event(db, event_id):
        raise HTTPException(status_code=404, detail="Event not found")
    saved_event_crud.save_event(db, user_id=current_user.id, event_id=event_id)
    return SaveEventResponse(event_id=event_id, saved=True)


@router.delete("/{event_id}/save", response_model=SaveEventResponse)
def unsave_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    saved_event_crud.unsave_event(db, user_id=current_user.id, event_id=event_id)
    return SaveEventResponse(event_id=event_id, saved=False)
