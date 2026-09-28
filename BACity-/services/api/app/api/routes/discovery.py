from datetime import date, datetime, time, timedelta, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import and_, or_
from sqlalchemy.orm import joinedload, Session
from app.database import get_db
from app.api.deps import get_current_user, require_plus
from app.config import get_settings
from app.core.community import blocked_ids, owned_organization, require_verified, audit, notify, row, rate_limit
from app.models.event import Event, EventCategory, EventStatus
from app.models.community import Follow, Promotion, Organization, OrganizationMember
from app.models.saved_event import SavedEvent
from app.schemas.event import EventOut
from app.schemas.community import RecurringEvents, EventSubmission
from app.api.routes.community import publish
from app.models.community import Submission
from app.core.recommendations import rank_events
from app.core.recommendation_context import build_recommendation_context
from app.core.tonight import MAX_CANDIDATES, MAX_RESULTS, rank_tonight_events, tonight_window
from app.core.event_chains import (
    CHAIN_HORIZON,
    MAX_CANDIDATES as MAX_CHAIN_CANDIDATES,
    ChainMode,
    build_event_chains,
    utc_naive,
)
from app.core.planning import local_planning_window
from app.core.evening_planner import (
    MAX_CANDIDATES as MAX_EVENING_CANDIDATES,
    MAX_WINDOW,
    PlanningStrategy,
    build_evening_plans,
)
from app.core.weekend_planner import (
    MAX_CANDIDATES as MAX_WEEKEND_CANDIDATES,
    MAX_PLANS as MAX_WEEKEND_PLANS,
    WeekendDayInput,
    WeekendMode,
    WeekendStrategy,
    build_weekend_plans,
    weekend_window,
)

router = APIRouter(tags=['personalization and organizers'])


class RecommendationRequest(BaseModel):
    latitude: float | None = Field(None, ge=48, le=48.35)
    longitude: float | None = Field(None, ge=16.9, le=17.35)
    offset: int = Field(0, ge=0, le=1000)
    limit: int = Field(30, ge=1, le=100)

    @model_validator(mode='after')
    def coordinates_together(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Provide both coordinates')
        return self


class TonightRequest(BaseModel):
    latitude: float | None = Field(None, ge=48, le=48.35)
    longitude: float | None = Field(None, ge=16.9, le=17.35)

    @model_validator(mode='after')
    def coordinates_together(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Provide both coordinates')
        return self


class TonightRecommendationOut(BaseModel):
    event: EventOut
    classification: Literal['happening_now', 'starting_soon', 'later_tonight']
    reasons: list[str]
    saved: bool


class TonightResponse(BaseModel):
    timezone: str
    window_start: datetime
    window_end: datetime
    location_used: bool
    items: list[TonightRecommendationOut]


class EventChainRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    anchor_event_id: UUID
    mode: ChainMode = ChainMode.full


class EventChainItemOut(BaseModel):
    event: EventOut
    relation: Literal['before', 'anchor', 'after']
    is_anchor: bool
    reasons: list[str]
    location_confidence: Literal['nearby', 'distance_buffered', 'location_unknown'] | None = None


class EventChainAlternativeOut(BaseModel):
    id: str
    items: list[EventChainItemOut]


class EventChainResponse(BaseModel):
    anchor_event_id: UUID
    mode: ChainMode
    chains: list[EventChainAlternativeOut]


class EveningPlanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    date: date
    start_time: time
    end_time: time
    categories: list[EventCategory] = Field(default_factory=list, max_length=6)
    latitude: float | None = Field(None, ge=48, le=48.35)
    longitude: float | None = Field(None, ge=16.9, le=17.35)

    @model_validator(mode='after')
    def validate_request(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Provide both coordinates')
        if len(self.categories) != len(set(self.categories)):
            raise ValueError('Categories must be unique')
        if self.start_time.tzinfo is not None or self.end_time.tzinfo is not None:
            raise ValueError('Times must be local clock values without an offset')
        return self


class EveningPlanItemOut(BaseModel):
    event: EventOut
    reasons: list[str]
    location_confidence: Literal['nearby', 'distance_buffered', 'location_unknown'] | None = None


class EveningPlanAlternativeOut(BaseModel):
    id: str
    strategy: PlanningStrategy
    explanation: str
    limited: bool
    items: list[EveningPlanItemOut]


class EveningPlanResponse(BaseModel):
    timezone: str
    window_start: datetime
    window_end: datetime
    location_used: bool
    plans: list[EveningPlanAlternativeOut]


class WeekendPlanRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    weekend_start: date
    mode: WeekendMode = WeekendMode.weekend
    categories: list[EventCategory] = Field(default_factory=list, max_length=6)
    latitude: float | None = Field(None, ge=48, le=48.35)
    longitude: float | None = Field(None, ge=16.9, le=17.35)

    @model_validator(mode='after')
    def validate_request(self):
        if self.weekend_start.weekday() != 5:
            raise ValueError('weekend_start must be a Saturday')
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Provide both coordinates')
        if len(self.categories) != len(set(self.categories)):
            raise ValueError('Categories must be unique')
        return self


class WeekendPlanItemOut(BaseModel):
    event: EventOut
    reasons: list[str]
    location_confidence: Literal['nearby', 'distance_buffered', 'location_unknown'] | None = None


class WeekendDayPlanOut(BaseModel):
    date: date
    day: Literal['Saturday', 'Sunday']
    window_start: datetime
    window_end: datetime
    limited: bool
    items: list[WeekendPlanItemOut]


class WeekendPlanAlternativeOut(BaseModel):
    id: str
    strategy: WeekendStrategy
    explanation: str
    limited: bool
    days: list[WeekendDayPlanOut]


class WeekendPlanResponse(BaseModel):
    timezone: str
    weekend_start: date
    mode: WeekendMode
    location_used: bool
    plans: list[WeekendPlanAlternativeOut]


def _recommendations(user, db, latitude, longitude, offset, limit):
    if (latitude is None) != (longitude is None):
        raise HTTPException(422, 'Provide both coordinates')
    now = datetime.utcnow()
    excluded = blocked_ids(db, user.id)
    query = db.query(Event).options(joinedload(Event.venue)).filter(
        Event.start_time >= now,
        Event.start_time < now + timedelta(days=90),
        Event.status.in_([EventStatus.fresh, EventStatus.stale]),
    )
    if excluded:
        query = query.filter(or_(Event.contributor_id.is_(None), ~Event.contributor_id.in_(excluded)))
    candidates = query.order_by(Event.start_time).limit(1000).all()
    context = build_recommendation_context(db, user, candidates, latitude, longitude)
    ranked = rank_events(candidates, context, now=now)
    return [{
        'event': EventOut.model_validate(item.event),
        'reasons': list(item.reasons),
        'saved': item.event.id in context.saved_event_ids,
    } for item in ranked[offset:offset + limit]]


@router.get('/recommendations')
def recommendations(user=Depends(get_current_user), db: Session = Depends(get_db),
                    latitude: float | None = Query(None, ge=48, le=48.35),
                    longitude: float | None = Query(None, ge=16.9, le=17.35),
                    offset: int = Query(0, ge=0, le=1000),
                    limit: int = Query(30, ge=1, le=100)):
    """Backward-compatible recommendation endpoint for existing clients."""
    return _recommendations(user, db, latitude, longitude, offset, limit)


@router.post('/recommendations/query')
def recommendation_query(payload: RecommendationRequest, user=Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """Body-based query keeps approximate coordinates out of access-log URLs."""
    return _recommendations(user, db, payload.latitude, payload.longitude, payload.offset, payload.limit)


@router.post('/recommendations/tonight', response_model=TonightResponse)
def tonight_recommendations(
    payload: TonightRequest,
    user=Depends(require_plus),
    db: Session = Depends(get_db),
):
    """Small premium decision set; request-scoped approximate coordinates are never persisted."""
    rate_limit(db, f'plus-tonight:{user.id}', 120)
    now = datetime.utcnow()
    window = tonight_window(now, get_settings().default_timezone)
    excluded = blocked_ids(db, user.id)
    future_tonight = and_(
        Event.start_time > now,
        Event.start_time >= window.starts_at_utc,
        Event.start_time < window.ends_at_utc,
    )
    temporal_filter = future_tonight
    if window.starts_at_utc <= now < window.ends_at_utc:
        temporal_filter = or_(
            future_tonight,
            and_(Event.start_time <= now, Event.end_time.is_not(None), Event.end_time > now),
        )
    query = db.query(Event).options(joinedload(Event.venue)).filter(
        Event.status.in_([EventStatus.fresh, EventStatus.stale]),
        temporal_filter,
    )
    if excluded:
        query = query.filter(or_(Event.contributor_id.is_(None), ~Event.contributor_id.in_(excluded)))
    candidates = query.order_by(Event.start_time, Event.id).limit(MAX_CANDIDATES).all()
    context = build_recommendation_context(db, user, candidates, payload.latitude, payload.longitude)
    ranked = rank_tonight_events(candidates, context, window)
    return {
        'timezone': window.timezone,
        'window_start': window.starts_at_utc.replace(tzinfo=timezone.utc),
        'window_end': window.ends_at_utc.replace(tzinfo=timezone.utc),
        'location_used': payload.latitude is not None,
        'items': [{
            'event': EventOut.model_validate(item.event),
            'classification': item.classification.value,
            'reasons': list(item.reasons),
            'saved': item.event.id in context.saved_event_ids,
        } for item in ranked[:MAX_RESULTS]],
    }


@router.post('/recommendations/event-chain', response_model=EventChainResponse)
def event_chain_recommendations(
    payload: EventChainRequest,
    user=Depends(require_plus),
    db: Session = Depends(get_db),
):
    """Ephemeral premium chains around a server-loaded anchor event."""
    rate_limit(db, f'plus-event-chain:{user.id}', 60)
    anchor = db.query(Event).options(joinedload(Event.venue)).filter(Event.id == payload.anchor_event_id).first()
    if not anchor:
        raise HTTPException(404, 'Anchor event not found')
    if anchor.status not in {EventStatus.fresh, EventStatus.stale}:
        raise HTTPException(409, 'Anchor event is not available for planning')
    anchor_start = utc_naive(anchor.start_time)
    anchor_end = utc_naive(anchor.end_time) if anchor.end_time else None
    if anchor_end is not None and anchor_end <= anchor_start:
        raise HTTPException(409, 'Anchor event has invalid timing')
    now = datetime.utcnow()
    if (anchor_end is not None and anchor_end <= now) or (anchor_end is None and anchor_start <= now):
        raise HTTPException(409, 'Anchor event can no longer be planned safely')

    lower = anchor_start - CHAIN_HORIZON
    upper = (anchor_end or anchor_start) + CHAIN_HORIZON
    excluded = blocked_ids(db, user.id)
    query = db.query(Event).options(joinedload(Event.venue)).filter(
        Event.id != anchor.id,
        Event.status.in_([EventStatus.fresh, EventStatus.stale]),
        Event.start_time >= lower,
        Event.start_time <= upper,
    )
    if excluded:
        query = query.filter(or_(Event.contributor_id.is_(None), ~Event.contributor_id.in_(excluded)))
    candidates = query.order_by(Event.start_time, Event.id).limit(MAX_CHAIN_CANDIDATES).all()
    context = build_recommendation_context(db, user, candidates, None, None)
    chains = build_event_chains(anchor, candidates, context, payload.mode)
    return {
        'anchor_event_id': anchor.id,
        'mode': payload.mode,
        'chains': [{
            'id': f'chain-{index}',
            'items': [{
                'event': EventOut.model_validate(item.event),
                'relation': item.relation.value,
                'is_anchor': item.event.id == anchor.id,
                'reasons': list(item.reasons),
                'location_confidence': item.location_confidence,
            } for item in chain.items],
        } for index, chain in enumerate(chains, start=1)],
    }


@router.post('/recommendations/evening-plan', response_model=EveningPlanResponse)
def evening_plan_recommendations(
    payload: EveningPlanRequest,
    user=Depends(require_plus),
    db: Session = Depends(get_db),
):
    """Generate ephemeral plans from a validated local availability window."""
    rate_limit(db, f'plus-evening-plan:{user.id}', 30)
    settings = get_settings()
    try:
        window = local_planning_window(payload.date, payload.start_time, payload.end_time, settings.default_timezone)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    if window.duration <= timedelta(0) or window.duration > MAX_WINDOW:
        raise HTTPException(422, 'Availability window must be no longer than 10 hours')
    if window.starts_at_utc < datetime.utcnow():
        raise HTTPException(422, 'Availability window must start in the future')

    excluded = blocked_ids(db, user.id)
    query = db.query(Event).options(joinedload(Event.venue)).filter(
        Event.status.in_([EventStatus.fresh, EventStatus.stale]),
        Event.start_time >= window.starts_at_utc,
        Event.start_time < window.ends_at_utc,
    )
    if excluded:
        query = query.filter(or_(Event.contributor_id.is_(None), ~Event.contributor_id.in_(excluded)))
    candidates = query.order_by(Event.start_time, Event.id).limit(MAX_EVENING_CANDIDATES).all()
    context = build_recommendation_context(db, user, candidates, payload.latitude, payload.longitude)
    selected_categories = frozenset(category.value.casefold() for category in payload.categories)
    plans = build_evening_plans(candidates, context, window, selected_categories)
    return {
        'timezone': window.timezone,
        'window_start': window.starts_at_utc.replace(tzinfo=timezone.utc),
        'window_end': window.ends_at_utc.replace(tzinfo=timezone.utc),
        'location_used': payload.latitude is not None,
        'plans': [{
            'id': f'plan-{index}',
            'strategy': plan.strategy.value,
            'explanation': plan.explanation,
            'limited': plan.limited,
            'items': [{
                'event': EventOut.model_validate(item.event),
                'reasons': list(item.reasons),
                'location_confidence': item.location_confidence,
            } for item in plan.items],
        } for index, plan in enumerate(plans, start=1)],
    }


@router.post('/recommendations/weekend-plan', response_model=WeekendPlanResponse)
def weekend_plan_recommendations(
    payload: WeekendPlanRequest,
    user=Depends(require_plus),
    db: Session = Depends(get_db),
):
    """Generate bounded, ephemeral Saturday/Sunday plans from real BACity events."""
    rate_limit(db, f'plus-weekend-plan:{user.id}', 20)
    timezone_name = get_settings().default_timezone
    saturday = payload.weekend_start
    requested_dates = {
        WeekendMode.saturday: (saturday,),
        WeekendMode.sunday: (saturday + timedelta(days=1),),
        WeekendMode.weekend: (saturday, saturday + timedelta(days=1)),
    }[payload.mode]
    try:
        windows = tuple(weekend_window(day, timezone_name) for day in requested_dates)
    except (ValueError, KeyError) as exc:
        raise HTTPException(422, str(exc)) from exc
    now = datetime.utcnow()
    if all(window.ends_at_utc <= now for window in windows):
        raise HTTPException(422, 'Choose a weekend that has not ended')

    excluded = blocked_ids(db, user.id)
    query = db.query(Event).options(joinedload(Event.venue)).filter(
        Event.status.in_([EventStatus.fresh, EventStatus.stale]),
        Event.start_time >= max(min(window.starts_at_utc for window in windows), now),
        Event.start_time < max(window.ends_at_utc for window in windows),
    )
    if excluded:
        query = query.filter(or_(Event.contributor_id.is_(None), ~Event.contributor_id.in_(excluded)))
    candidates = query.order_by(Event.start_time, Event.id).limit(MAX_WEEKEND_CANDIDATES).all()
    context = build_recommendation_context(db, user, candidates, payload.latitude, payload.longitude)
    selected_categories = frozenset(category.value.casefold() for category in payload.categories)
    day_inputs = tuple(WeekendDayInput(day, window, tuple(candidates)) for day, window in zip(requested_dates, windows))
    plans = build_weekend_plans(day_inputs, context, selected_categories)
    return {
        'timezone': timezone_name,
        'weekend_start': saturday,
        'mode': payload.mode,
        'location_used': payload.latitude is not None,
        'plans': [{
            'id': f'weekend-plan-{index}',
            'strategy': plan.strategy.value,
            'explanation': plan.explanation,
            'limited': plan.limited,
            'days': [{
                'date': day.day,
                'day': 'Saturday' if day.day.weekday() == 5 else 'Sunday',
                'window_start': day.window.starts_at_utc.replace(tzinfo=timezone.utc),
                'window_end': day.window.ends_at_utc.replace(tzinfo=timezone.utc),
                'limited': day.limited,
                'items': [{
                    'event': EventOut.model_validate(item.event),
                    'reasons': list(item.reasons),
                    'location_confidence': item.location_confidence,
                } for item in day.items],
            } for day in plan.days],
        } for index, plan in enumerate(plans[:MAX_WEEKEND_PLANS], start=1)],
    }


@router.get('/promotions')
def promotions(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    rows = db.query(Promotion, Event).join(Event, Event.id == Promotion.event_id).filter(Promotion.starts_at <= now, Promotion.ends_at > now, Event.start_time >= now, Event.status == EventStatus.fresh).limit(20).all()
    return [{'label': 'Sponsored', 'event': EventOut.model_validate(event)} for p, event in rows]


@router.get('/organizer/organizations')
def my_organizations(user=Depends(require_verified), db: Session = Depends(get_db)):
    rows = db.query(Organization).join(OrganizationMember).filter(OrganizationMember.user_id == user.id).all()
    return [dict(id=o.id, name=o.name, verified=o.verified, tier=o.tier) for o in rows]


@router.post('/organizer/{identifier}/events')
def recurring_events(identifier: UUID, payload: RecurringEvents, user=Depends(require_verified), db: Session = Depends(get_db)):
    rate_limit(db, 'organizer-events:' + str(user.id), 10)
    org = owned_organization(db, user, identifier)
    if not org.verified:
        raise HTTPException(403, 'Organization verification required')
    if len(set(payload.dates)) != len(payload.dates):
        raise HTTPException(422, 'Recurring dates must be unique')
    duration = payload.event.end_time - payload.event.start_time if payload.event.end_time else None
    validated = []
    for start in payload.dates:
        data = payload.event.model_dump()
        data.update(start_time=start, end_time=start+duration if duration else None)
        validated.append(EventSubmission.model_validate(data))
    ids = []
    for event in validated:
        item = Submission(user_id=user.id, kind='event', payload=event.model_dump(mode='json'), state='approved', decision_reason='Published by verified organizer')
        db.add(item)
        db.flush()
        item.published_id = publish(db, item, 'Official')
        published = row(db, Event, item.published_id)
        published.organization_id = org.id
        ids.append(item.published_id)
        audit(db, user, 'organizer_published', 'event', published.id)
    # One notification per batch; follower addresses are never exposed to the organizer.
    for follower in db.query(Follow).filter_by(target_type='organizer', target_id=str(org.id)):
        notify(db, follower.user_id, 'organizer', f'{org.name} added {len(ids)} event(s)', org.id)
    db.commit()
    return {'event_ids': ids}


@router.get('/organizer/{identifier}/analytics')
def analytics(identifier: UUID, user=Depends(require_verified), db: Session = Depends(get_db)):
    org = owned_organization(db, user, identifier)
    return {'events': db.query(Event).filter_by(organization_id=org.id).count(),
            'followers': db.query(Follow).filter_by(target_type='organizer', target_id=str(org.id)).count(),
            'saves': db.query(SavedEvent).join(Event).filter(Event.organization_id == org.id).count()}
