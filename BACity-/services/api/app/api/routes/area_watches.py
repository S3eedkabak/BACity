"""Private BACity+ radius watches for newly discovered events."""
import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_plus
from app.core.community import rate_limit
from app.core.entitlements import BACITY_PLUS, EntitlementService
from app.core.planning import haversine_km
from app.core.recommendations import event_duplicate_key
from app.database import get_db
from app.models.area_watch import AreaWatch
from app.models.event import Event, EventStatus
from app.models.venue import Venue
from app.schemas.area_watch import AreaWatchCreate, AreaWatchFeedOut, AreaWatchOut, AreaWatchSummaryOut, AreaWatchUpdate, SeenRequest
from app.schemas.event import EventOut

router = APIRouter(prefix="/area-watches", tags=["private area watch"])

MAX_WATCHES = 5
LOOKBACK_DAYS = 30
MAX_PAGE_SIZE = 50
SQL_FETCH_MULTIPLIER = 5


def _owned(db: Session, identifier: UUID, user_id: UUID) -> AreaWatch:
    watch = db.query(AreaWatch).filter_by(id=identifier, user_id=user_id).first()
    if not watch:
        raise HTTPException(404, "Area watch not found")
    return watch


def _plus(db: Session, user_id: UUID) -> bool:
    return EntitlementService(db).has_entitlement(user_id, BACITY_PLUS)


def _require_active_plus(db: Session, user_id: UUID):
    if not _plus(db, user_id):
        raise HTTPException(403, "BACity+ required")


def _serialize(watch: AreaWatch, locked: bool, unseen_count: int = 0, detail: bool = False):
    data = {
        "id": watch.id, "name": watch.name, "radius_km": watch.radius_km,
        "categories": watch.categories or [], "active": watch.active,
        "locked": locked, "unseen_count": 0 if locked else unseen_count,
    }
    if detail:
        data.update({
            "center_latitude": watch.center_latitude, "center_longitude": watch.center_longitude,
            "last_viewed_at": watch.last_viewed_at, "created_at": watch.created_at, "updated_at": watch.updated_at,
        })
    return data


def _base_query(db: Session, watch: AreaWatch, now: datetime):
    lat = func.coalesce(Event.latitude, Venue.latitude)
    lng = func.coalesce(Event.longitude, Venue.longitude)
    pad_lat = watch.radius_km / 111.0
    pad_lng = watch.radius_km / 74.0
    query = db.query(Event).outerjoin(Venue, Venue.id == Event.venue_id).options(joinedload(Event.venue)).filter(
        Event.status.in_([EventStatus.fresh, EventStatus.stale]),
        Event.start_time >= now,
        Event.created_at.isnot(None), Event.created_at >= now - timedelta(days=LOOKBACK_DAYS),
        lat.isnot(None), lng.isnot(None),
        lat.between(watch.center_latitude - pad_lat, watch.center_latitude + pad_lat),
        lng.between(watch.center_longitude - pad_lng, watch.center_longitude + pad_lng),
    )
    if watch.categories:
        query = query.filter(Event.category.in_(watch.categories))
    if db.bind.dialect.name == "postgresql":
        distance = func.ST_DistanceSphere(
            func.ST_MakePoint(lng, lat),
            func.ST_MakePoint(watch.center_longitude, watch.center_latitude),
        )
        query = query.filter(distance <= watch.radius_km * 1000)
    return query


def _coordinates(event):
    if event.latitude is not None and event.longitude is not None:
        return float(event.latitude), float(event.longitude)
    if event.venue and event.venue.latitude is not None and event.venue.longitude is not None:
        return float(event.venue.latitude), float(event.venue.longitude)
    return None


def _inside(watch: AreaWatch, event) -> bool:
    coordinates = _coordinates(event)
    return bool(coordinates and haversine_km(watch.center_latitude, watch.center_longitude, *coordinates) <= watch.radius_km + 1e-9)


def _unseen_count(db: Session, watch: AreaWatch, now: datetime) -> int:
    query = _base_query(db, watch, now)
    if watch.last_viewed_at:
        query = query.filter(Event.created_at > watch.last_viewed_at)
    if db.bind.dialect.name == "postgresql":
        return query.count()
    return sum(1 for event in query.limit(2000).all() if _inside(watch, event))


def _cursor_encode(event: Event) -> str:
    raw = json.dumps([event.created_at.isoformat(), str(event.id)], separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _cursor_decode(value: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
        created, identifier = json.loads(raw)
        parsed = datetime.fromisoformat(created)
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed, UUID(identifier)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, "Invalid cursor") from exc


@router.get("", response_model=list[AreaWatchSummaryOut])
def list_watches(user=Depends(get_current_user), db: Session = Depends(get_db)):
    watches = db.query(AreaWatch).filter_by(user_id=user.id).order_by(AreaWatch.created_at, AreaWatch.id).limit(MAX_WATCHES).all()
    locked = not _plus(db, user.id)
    now = datetime.utcnow()
    return [_serialize(watch, locked, 0 if locked or not watch.active else _unseen_count(db, watch, now)) for watch in watches]


@router.post("", response_model=AreaWatchOut)
def create_watch(payload: AreaWatchCreate, user=Depends(require_plus), db: Session = Depends(get_db)):
    rate_limit(db, f"area-watch-create:{user.id}", 10, 86400)
    if db.query(AreaWatch).filter_by(user_id=user.id).count() >= MAX_WATCHES:
        raise HTTPException(409, "Area Watch limit reached")
    watch = AreaWatch(
        user_id=user.id, name=payload.name, center_latitude=payload.center_latitude,
        center_longitude=payload.center_longitude, radius_km=float(payload.radius_km),
        categories=[category.value for category in payload.categories],
    )
    db.add(watch)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An Area Watch with this name already exists") from exc
    db.refresh(watch)
    return _serialize(watch, False, _unseen_count(db, watch, datetime.utcnow()), True)


@router.get("/{identifier}", response_model=AreaWatchOut)
def get_watch(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    watch = _owned(db, identifier, user.id)
    locked = not _plus(db, user.id)
    return _serialize(watch, locked, 0 if locked or not watch.active else _unseen_count(db, watch, datetime.utcnow()), True)


@router.patch("/{identifier}", response_model=AreaWatchOut)
def update_watch(identifier: UUID, payload: AreaWatchUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"area-watch-update:{user.id}", 30)
    watch = _owned(db, identifier, user.id)
    _require_active_plus(db, user.id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "categories":
            value = [category.value for category in value]
        setattr(watch, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "An Area Watch with this name already exists") from exc
    return _serialize(watch, False, _unseen_count(db, watch, datetime.utcnow()) if watch.active else 0, True)


@router.delete("/{identifier}")
def delete_watch(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    watch = _owned(db, identifier, user.id)
    db.delete(watch)
    db.commit()
    return {"deleted": True}


@router.get("/{identifier}/events", response_model=AreaWatchFeedOut)
def watch_events(
    identifier: UUID, cursor: str | None = None,
    limit: int = Query(20, ge=1, le=MAX_PAGE_SIZE),
    user=Depends(get_current_user), db: Session = Depends(get_db),
):
    rate_limit(db, f"area-watch-feed:{user.id}", 120)
    watch = _owned(db, identifier, user.id)
    _require_active_plus(db, user.id)
    if not watch.active:
        raise HTTPException(409, "Area Watch is inactive")
    response_watermark = datetime.utcnow()
    query = _base_query(db, watch, response_watermark).filter(Event.created_at <= response_watermark)
    if cursor:
        created, event_id = _cursor_decode(cursor)
        query = query.filter(or_(Event.created_at < created, and_(Event.created_at == created, Event.id < event_id)))
    fetch_limit = min(MAX_PAGE_SIZE * SQL_FETCH_MULTIPLIER, limit * SQL_FETCH_MULTIPLIER)
    rows = query.order_by(Event.created_at.desc(), Event.id.desc()).limit(fetch_limit).all()
    filtered = []
    seen_keys = set()
    for event in rows:
        if not _inside(watch, event):
            continue
        key = event_duplicate_key(event)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        filtered.append(event)
    page = filtered[:limit]
    has_more = len(filtered) > limit or (len(rows) == fetch_limit and bool(page))
    items = [{
        "event": EventOut.model_validate(event), "discovered_at": event.created_at,
        "unseen": watch.last_viewed_at is None or event.created_at > watch.last_viewed_at,
        "explanations": ["Newly discovered in your watched area"] + ([f"Matches {event.category.value}"] if watch.categories else []),
    } for event in page]
    return {
        "items": items, "next_cursor": _cursor_encode(page[-1]) if has_more else None,
        "response_watermark": response_watermark.replace(tzinfo=timezone.utc),
        "unseen_count": _unseen_count(db, watch, response_watermark), "lookback_days": LOOKBACK_DAYS,
    }


@router.post("/{identifier}/seen", response_model=AreaWatchOut)
def mark_seen(identifier: UUID, payload: SeenRequest, user=Depends(get_current_user), db: Session = Depends(get_db)):
    rate_limit(db, f"area-watch-seen:{user.id}", 120)
    watch = _owned(db, identifier, user.id)
    _require_active_plus(db, user.id)
    watermark = payload.watermark.astimezone(timezone.utc).replace(tzinfo=None) if payload.watermark.tzinfo else payload.watermark
    now = datetime.utcnow()
    if watermark > now + timedelta(seconds=5):
        raise HTTPException(422, "Watermark is in the future")
    if watch.last_viewed_at is None or watermark > watch.last_viewed_at:
        watch.last_viewed_at = min(watermark, now)
        db.commit()
    return _serialize(watch, False, _unseen_count(db, watch, now) if watch.active else 0, True)
