from datetime import datetime, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload, Session
from app.database import get_db
from app.api.deps import get_current_user
from app.core.community import blocked_ids, owned_organization, require_verified, audit, notify, row, rate_limit
from app.models.event import Event, EventStatus
from app.models.saved_event import SavedEvent
from app.models.community import Follow, Promotion, Organization, OrganizationMember
from app.schemas.event import EventOut
from app.schemas.community import RecurringEvents, EventSubmission
from app.api.routes.community import publish
from app.models.community import Submission
from app.core.recommendations import RecommendationContext, rank_events

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
    interests = {i.casefold() for i in user.interests}
    following = {(f.target_type.casefold(), f.target_id.casefold())
                 for f in db.query(Follow).filter_by(user_id=user.id)}
    saved_categories = {str(c.value).casefold() for (c,) in db.query(Event.category).join(SavedEvent, SavedEvent.event_id == Event.id).filter(SavedEvent.user_id == user.id).distinct()}
    candidate_ids = [event.id for event in candidates]
    saved_event_ids = frozenset(event_id for (event_id,) in db.query(SavedEvent.event_id).filter(
        SavedEvent.user_id == user.id,
        SavedEvent.event_id.in_(candidate_ids),
    )) if candidate_ids else frozenset()
    counts = {}
    if candidate_ids:
        counts = dict(
            db.query(SavedEvent.event_id, func.count(func.distinct(SavedEvent.user_id)))
            .join(Event, Event.id == SavedEvent.event_id)
            .outerjoin(OrganizationMember, and_(
                OrganizationMember.organization_id == Event.organization_id,
                OrganizationMember.user_id == SavedEvent.user_id,
            ))
            .filter(
                SavedEvent.event_id.in_(candidate_ids),
                OrganizationMember.id.is_(None),
                or_(Event.contributor_id.is_(None), Event.contributor_id != SavedEvent.user_id),
            )
            .group_by(SavedEvent.event_id)
            .all()
        )
    context = RecommendationContext(
        interests=frozenset(interests),
        saved_categories=frozenset(saved_categories),
        following=frozenset(following),
        save_counts=counts,
        saved_event_ids=saved_event_ids,
        latitude=latitude,
        longitude=longitude,
    )
    ranked = rank_events(candidates, context, now=now)
    return [{
        'event': EventOut.model_validate(item.event),
        'reasons': list(item.reasons),
        'saved': item.event.id in saved_event_ids,
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
