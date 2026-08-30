from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.crud import event as event_crud
from app.crud import saved_event as saved_event_crud
from app.schemas.event import EventOut, EventListResponse, SaveEventResponse, EventCreate
from app.api.deps import get_current_user
from app.models.user import User
from app.models.event import Event, EventStatus

router = APIRouter(prefix="/events", tags=["events"])


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
):
    """
    Ingest endpoint for the crawler. Idempotent on source URL + title + start time
    so repeated crawls do not flood the database with duplicate rows.
    """
    existing = db.scalar(
        select(Event).where(
            event_crud.Event.source_url == payload.source_url,
            event_crud.Event.title == payload.title,
            event_crud.Event.start_time == payload.start_time,
        )
    )
    if existing:
        for field, value in payload.model_dump(exclude={"venue_id", "source_id"}).items():
            if hasattr(existing, field) and value is not None:
                setattr(existing, field, value)
        db.commit()
        db.refresh(existing)
        return existing

    event = event_crud.Event(
        **payload.model_dump(),
        status=EventStatus.fresh,
        source_reliability=payload.source_reliability,
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
def search_events(q: str = Query(..., min_length=1), limit: int = Query(20, le=100),
                   db: Session = Depends(get_db)):
    return event_crud.search_events(db, query=q, limit=limit)


@router.get("/nearby", response_model=list[EventOut])
def nearby_events(
    lat: float,
    lng: float,
    radius_km: float = Query(5.0, gt=0, le=50),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    return event_crud.nearby_events(db, lat=lat, lng=lng, radius_km=radius_km, limit=limit)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: UUID, db: Session = Depends(get_db)):
    event = event_crud.get_event(db, event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/{event_id}/save", response_model=SaveEventResponse, status_code=status.HTTP_201_CREATED)
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