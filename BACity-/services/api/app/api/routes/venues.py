from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.crud import venue as venue_crud
from app.schemas.venue import VenueOut
from app.schemas.event import EventOut

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(venue_id: UUID, db: Session = Depends(get_db)):
    venue = venue_crud.get_venue(db, venue_id)
    if not venue:
        raise HTTPException(status_code=404, detail="Venue not found")
    return venue


@router.get("/{venue_id}/events", response_model=list[EventOut])
def get_venue_events(venue_id: UUID, db: Session = Depends(get_db)):
    return venue_crud.get_venue_events(db, venue_id)
