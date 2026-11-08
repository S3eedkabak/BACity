"""Additive public map API; legacy viewport clients remain supported."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.routes.events import public_read_budget
from app.database import get_db
from app.crud import map_events
from app.models.event import EventCategory
from app.schemas.event import EventOut

router = APIRouter(prefix='/events/map', tags=['events'], dependencies=[Depends(public_read_budget)])


def filters(category: EventCategory | None = None, q: str | None = Query(None,max_length=200),
            free_only: bool = False, starts_after: datetime | None = None, starts_before: datetime | None = None,
            status: Literal['fresh','stale'] | None = None,
            near_lat: float | None=Query(None,ge=-90,le=90),near_lng:float | None=Query(None,ge=-180,le=180),
            radius_km:float=Query(3,gt=0,le=50),district:str|None=Query(None,max_length=16)):
    if district:
        from app.crud.districts import collection
        if district not in {f['properties']['id'] for f in collection()['features']}:
            raise HTTPException(422,'Unknown official district')
    if (near_lat is None)!=(near_lng is None):
        raise HTTPException(422,'Nearby requires both coordinates')
    if starts_after and starts_before and (starts_after.replace(tzinfo=timezone.utc) if starts_after.tzinfo is None else starts_after) > (starts_before.replace(tzinfo=timezone.utc) if starts_before.tzinfo is None else starts_before):
        raise HTTPException(422,'Dates must be ordered')
    def utc(value):
        return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.astimezone(timezone.utc).isoformat()
    return {k:v for k,v in {'category':category.value if category else None,'q':q.strip() if q else None,'free_only':free_only,
        'starts_after':utc(starts_after) if starts_after else None,'starts_before':utc(starts_before) if starts_before else None,'status':status,'district':district,**({'near_lat':near_lat,'near_lng':near_lng,'radius_km':radius_km} if near_lat is not None else {})}.items() if v is not None and v is not False and v!=''}


@router.get('/clusters')
def clusters(min_lat: float = Query(ge=-90,le=90), max_lat: float = Query(ge=-90,le=90),
             min_lng: float = Query(ge=-180,le=180), max_lng: float = Query(ge=-180,le=180),
             zoom: int = Query(12,ge=0,le=22), selected=Depends(filters), db: Session=Depends(get_db)):
    if min_lat>max_lat or min_lng>max_lng:
        raise HTTPException(422,'Bounds must be ordered; dateline wrapping is unsupported for Bratislava')
    return map_events.clusters(db,dict(min_lat=min_lat,max_lat=max_lat,min_lng=min_lng,max_lng=max_lng),zoom,selected)


class AreaPage(BaseModel):
    count_semantics: str = "distinct_discoverable_events"
    name: str
    total: int
    items: list[EventOut]
    has_more: bool
    next_cursor: str | None
    refreshed: bool


@router.get('/area',response_model=AreaPage)
def area(area_token: str = Query(max_length=4096), cursor: str | None = Query(None,max_length=4096),
         limit: int = Query(30,ge=1,le=100), override_filters: bool=False,
         selected=Depends(filters), db: Session=Depends(get_db)):
    # The rate budget dependency commits before entering this route.
    if db.bind.dialect.name=='postgresql':
        from sqlalchemy import text
        db.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ'))
    return map_events.area_events(db,area_token,cursor,limit,selected if override_filters else None)


@router.get('/districts')
def district_events(selected=Depends(filters),db:Session=Depends(get_db)):
    return map_events.districts(db,selected)
