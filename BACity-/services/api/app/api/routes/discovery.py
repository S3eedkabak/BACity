from datetime import datetime, timedelta
from math import cos, radians, sqrt
from uuid import UUID
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session
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

router = APIRouter(tags=['personalization and organizers'])


@router.get('/recommendations')
def recommendations(user=Depends(get_current_user), db: Session = Depends(get_db),
                    latitude: float | None = Query(None, ge=48, le=48.35),
                    longitude: float | None = Query(None, ge=16.9, le=17.35),
                    limit: int = Query(30, ge=1, le=100)):
    if (latitude is None) != (longitude is None):
        raise HTTPException(422, 'Provide both coordinates')
    now = datetime.utcnow()
    excluded = blocked_ids(db, user.id)
    query = db.query(Event).filter(Event.start_time >= now, Event.start_time < now + timedelta(days=90), Event.status.in_([EventStatus.fresh, EventStatus.stale]))
    if excluded:
        from sqlalchemy import or_
        query = query.filter(or_(Event.contributor_id.is_(None), ~Event.contributor_id.in_(excluded)))
    candidates = query.order_by(Event.start_time).limit(1000).all()
    interests = {i.casefold() for i in user.interests}
    following = {(f.target_type, f.target_id) for f in db.query(Follow).filter_by(user_id=user.id)}
    saved_categories = {str(c.value).casefold() for (c,) in db.query(Event.category).join(SavedEvent, SavedEvent.event_id == Event.id).filter(SavedEvent.user_id == user.id).distinct()}
    counts = dict(db.query(SavedEvent.event_id, func.count(SavedEvent.id)).group_by(SavedEvent.event_id).all())
    ranked = []
    for event in candidates:
        score, reasons = 0.0, []
        category = event.category.value.casefold()
        if category in interests or interests.intersection(t.casefold() for t in event.tags):
            score += 5
            reasons.append('Matches your interests')
        if category in saved_categories:
            score += 2
            reasons.append('Similar to events you saved')
        for kind, value in [('venue', event.venue_id), ('organizer', event.organization_id), ('neighborhood', event.neighborhood), ('category', event.category.value), ('guide', event.contributor_id), ('user', event.contributor_id)]:
            if value and (kind, str(value)) in following:
                score += 4
                reasons.append(f'From a {kind} you follow')
        if latitude is not None and event.latitude is not None and event.longitude is not None:
            distance = 111 * sqrt((latitude-event.latitude)**2 + (cos(radians(latitude))*(longitude-event.longitude))**2)
            score += max(0, 3-distance/2)
            if distance < 5:
                reasons.append(f'{distance:.1f} km away')
        if event.start_time < now + timedelta(days=7):
            score += 1
            reasons.append('Happening this week')
        if event.last_verified_at and event.last_verified_at > now-timedelta(days=2):
            score += 1
            reasons.append('Recently checked')
        count = counts.get(event.id, 0)
        score += min(count, 20) / 10
        if count:
            reasons.append(f'Saved by {count} people')
        ranked.append((score, event.start_time, {'event': EventOut.model_validate(event), 'reasons': reasons or ['Upcoming in Bratislava']}))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    return [r[2] for r in ranked[:limit]]


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
