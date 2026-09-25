from typing import Optional
from uuid import UUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi import Header
import os
import secrets
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import event as event_crud
from app.crud import saved_event as saved_event_crud
from app.schemas.event import EventOut, EventListResponse, SaveEventResponse, EventCreate
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter(prefix="/events", tags=["events"])


def require_ingestion_key(x_ingestion_key: str = Header(default="")):
    expected = os.getenv("INGESTION_API_KEY", "")
    if expected and not secrets.compare_digest(expected, x_ingestion_key):
        raise HTTPException(status_code=401, detail="Invalid ingestion key")


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_ingestion_key)])
def create_event(
    payload: EventCreate,
    db: Session = Depends(get_db),
):
    from app.crud.ingestion import ingest
    return ingest(db, payload)


@router.post("/maintenance", dependencies=[Depends(require_ingestion_key)])
def maintenance(db: Session = Depends(get_db)):
    from app.crud.ingestion import expire_events
    expire_events(db)
    return {"status": "ok"}


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
