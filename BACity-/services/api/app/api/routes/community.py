"""Community contributions are published only after an audited moderation decision."""
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.core.community import (require_verified, require_moderator, require_admin, row,
    audit, notify, blocked, blocked_ids, rate_limit, reputation_level, owned_organization)
from app.core.utilities import nearby_query, utility_record, viewport_query
from app.models.user import User
from app.models.oauth_identity import OAuthIdentity
from app.models.saved_event import SavedEvent
from app.models.event import Event, EventStatus
from app.models.venue import Venue
from app.models.community import (Submission, AuditLog, Follow, UserBlock, Report, Organization,
    OrganizationMember, Place, CityUtility, UtilityConfirmation, Review, ReviewRevision,
    HelpfulVote, Collection, Comment, Message, Notification)
from app.models.community import ActionToken, MailOutbox, RateBucket
from app.schemas.community import (ProfileUpdate, EventSubmission, PlaceInput, UtilityInput,
    ModerationDecision, Reason, FollowInput, ReportInput, ReviewInput, BodyInput,
    OrganizationInput, ClaimInput, RoleInput, CollectionInput, CorrectionInput, Confirmation)

router = APIRouter(prefix='/community', tags=['community'])
MODELS = {'event': Event, 'place': Place, 'utility': CityUtility, 'user': User,
          'review': Review, 'comment': Comment, 'message': Message}


def record(item):
    return {column.name: getattr(item, column.name) for column in item.__table__.columns}


def records(query):
    return [record(item) for item in query.all()]


def public_profile(db, user):
    return dict(id=user.id, display_name=user.display_name, avatar_url=user.avatar_url,
                bio=user.bio, city=user.city, neighborhood=user.neighborhood, interests=user.interests,
                role=user.role, identity_verified=user.identity_verified,
                reputation_level=reputation_level(user.reputation),
                followers=db.query(Follow).filter(Follow.target_type.in_(['user', 'guide']), Follow.target_id == str(user.id)).count(),
                following=db.query(Follow).filter_by(user_id=user.id).count())


def submit(db, user, kind, payload):
    rate_limit(db, 'submit:' + str(user.id), 20)
    flags = []
    if user.reputation < 10:
        flags.append('new_contributor')
    if kind == 'event':
        start = datetime.fromisoformat(payload['start_time']).astimezone(timezone.utc).replace(tzinfo=None)
        if db.query(Event).filter(Event.title.ilike(payload['title']), Event.start_time == start).first():
            flags.append('possible_duplicate')
    item = Submission(user_id=user.id, kind=kind, payload=payload, risk_flags=flags)
    db.add(item)
    db.flush()
    audit(db, user, 'submitted', kind, item.id)
    db.commit()
    return record(item)


@router.patch('/profile')
def edit_profile(payload: ProfileUpdate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, key, value)
    db.commit()
    return public_profile(db, user)


@router.get('/profiles/{identifier}')
def profile(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    target = row(db, User, identifier)
    if not target.active or blocked(db, user.id, target.id) or (not target.public_profile and user.id != target.id):
        raise HTTPException(404, 'Profile unavailable')
    result = public_profile(db, target)
    result['contributions'] = db.query(Submission).filter_by(user_id=target.id, state='approved').order_by(Submission.created_at.desc()).limit(100).all()
    # Only publication metadata is public, never claims, reasons or correction evidence.
    result['contributions'] = [dict(id=s.id, kind=s.kind, published_id=s.published_id, created_at=s.created_at) for s in result['contributions']]
    return result


@router.post('/follows')
def follow(payload: FollowInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    rate_limit(db, 'follow:' + str(user.id), 100)
    target_id = payload.target_id
    if payload.target_type in ('user', 'guide'):
        target = row(db, User, target_id)
        if target.id == user.id or not target.active or not target.public_profile or blocked(db, user.id, target.id):
            raise HTTPException(403, 'Cannot follow this profile')
        if payload.target_type == 'guide' and target.role != 'GUIDE':
            raise HTTPException(422, 'Profile is not a guide')
        target_id = str(target.id)
    elif payload.target_type in ('venue', 'organizer'):
        target_id = str(row(db, Venue if payload.target_type == 'venue' else Organization, target_id).id)
    item = db.query(Follow).filter_by(user_id=user.id, target_type=payload.target_type, target_id=target_id).first()
    if not item:
        item = Follow(user_id=user.id, target_type=payload.target_type, target_id=target_id)
        db.add(item)
        db.commit()
    return record(item)


@router.get('/follows')
def follows(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Follow).filter_by(user_id=user.id).order_by(Follow.created_at.desc()).limit(500).all()


@router.delete('/follows/{identifier}')
def unfollow(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    item = row(db, Follow, identifier)
    if item.user_id != user.id:
        raise HTTPException(404, 'Not found')
    db.delete(item)
    db.commit()
    return {'deleted': True}


@router.post('/blocks/{identifier}')
def block(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    target = row(db, User, identifier)
    if target.id == user.id:
        raise HTTPException(422, 'Cannot block yourself')
    if not db.query(UserBlock).filter_by(user_id=user.id, blocked_id=target.id).first():
        db.add(UserBlock(user_id=user.id, blocked_id=target.id))
    db.query(Follow).filter(Follow.target_type.in_(['user', 'guide']), or_(and_(Follow.user_id == user.id, Follow.target_id == str(target.id)), and_(Follow.user_id == target.id, Follow.target_id == str(user.id)))).delete(synchronize_session=False)
    db.commit()
    return {'blocked': True}


@router.delete('/blocks/{identifier}')
def unblock(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(UserBlock).filter_by(user_id=user.id, blocked_id=identifier).delete()
    db.commit()
    return {'blocked': False}


@router.get('/blocks')
def blocks(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(UserBlock).filter_by(user_id=user.id).limit(500).all()


@router.post('/submissions/events', status_code=201)
def submit_event(payload: EventSubmission, user=Depends(require_verified), db: Session = Depends(get_db)):
    return submit(db, user, 'event', payload.model_dump(mode='json'))


@router.post('/submissions/places', status_code=201)
def submit_place(payload: PlaceInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    return submit(db, user, 'place', payload.model_dump(mode='json'))


@router.post('/submissions/utilities', status_code=201)
def submit_utility(payload: UtilityInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    return submit(db, user, 'utility', payload.model_dump(mode='json'))


@router.post('/submissions/corrections', status_code=201)
def submit_correction(payload: CorrectionInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    row(db, MODELS[payload.target_type], payload.target_id)
    allowed = {'place': set(PlaceInput.model_fields), 'utility': set(UtilityInput.model_fields),
               'event': {'title', 'description', 'address', 'latitude', 'longitude', 'image_url', 'ticket_url', 'neighborhood'}}
    if not set(payload.changes) <= allowed[payload.target_type]:
        raise HTTPException(422, 'Unsupported correction fields')
    return submit(db, user, 'correction', payload.model_dump(mode='json'))


@router.get('/submissions')
def my_submissions(user=Depends(get_current_user), db: Session = Depends(get_db), offset: int = Query(0, ge=0)):
    return db.query(Submission).filter_by(user_id=user.id).order_by(Submission.created_at.desc()).offset(offset).limit(100).all()


@router.post('/submissions/{identifier}/appeal')
def appeal(identifier: UUID, payload: Reason, user=Depends(require_verified), db: Session = Depends(get_db)):
    item = row(db, Submission, identifier)
    if item.user_id != user.id:
        raise HTTPException(404, 'Not found')
    if item.state != 'rejected' or item.appeal:
        raise HTTPException(409, 'Only one appeal of a rejected contribution is allowed')
    item.appeal = payload.reason
    item.state = 'appealed'
    audit(db, user, 'appealed', 'submission', item.id)
    db.commit()
    return record(item)


@router.get('/moderation/submissions')
def queue(user=Depends(require_moderator), db: Session = Depends(get_db), offset: int = Query(0, ge=0)):
    return db.query(Submission).filter(Submission.state.in_(['pending', 'appealed'])).order_by(Submission.created_at).offset(offset).limit(100).all()


def publish(db, item, trust):
    owner = row(db, User, item.user_id)
    if not owner.active:
        raise HTTPException(409, 'Contributor account is no longer active')
    if item.kind == 'event':
        payload = EventSubmission.model_validate(item.payload)
        data = payload.model_dump(exclude={'organizer_name', 'venue_name', 'source_name', 'original_source_url', 'source_id', 'venue_id', 'status', 'extraction_confidence', 'source_reliability'})
        for key in ('start_time', 'end_time'):
            if data[key]:
                data[key] = data[key].astimezone(timezone.utc).replace(tzinfo=None)
        obj = Event(**data, contributor_id=item.user_id, trust_level=trust, is_manual_override=True,
                    extraction_confidence=1, source_reliability=0.7, status=EventStatus.fresh)
    elif item.kind in ('place', 'utility'):
        schema, model = (PlaceInput, Place) if item.kind == 'place' else (UtilityInput, CityUtility)
        obj = model(**schema.model_validate(item.payload).model_dump(), contributor_id=item.user_id)
        if item.kind == 'place':
            obj.trust_level = trust
    elif item.kind == 'claim':
        obj = row(db, Organization, item.payload['organization_id'])
        if db.query(OrganizationMember).filter_by(organization_id=obj.id).first():
            raise HTTPException(409, 'Organization already has an owner; ownership transfers require administrator review')
        db.add(OrganizationMember(organization_id=obj.id, user_id=item.user_id))
        obj.verified = True
    elif item.kind == 'correction':
        data = item.payload
        obj = row(db, MODELS[data['target_type']], data['target_id'])
        schema = {'place': PlaceInput, 'utility': UtilityInput, 'event': EventSubmission}[data['target_type']]
        existing = {key: getattr(obj, key) for key in schema.model_fields if hasattr(obj, key)}
        if data['target_type'] == 'event':
            for key in ('start_time', 'end_time'):
                if existing.get(key):
                    existing[key] = existing[key].replace(tzinfo=timezone.utc)
        schema.model_validate({**existing, **data['changes']})
        for key, value in data['changes'].items():
            setattr(obj, key, value)
        if data['target_type'] == 'event':
            obj.is_manual_override = True
    else:
        raise HTTPException(422, 'Unsupported submission kind')
    db.add(obj)
    db.flush()
    owner.reputation += 10
    return str(obj.id)


@router.post('/moderation/submissions/{identifier}')
def decide(identifier: UUID, payload: ModerationDecision, user=Depends(require_moderator), db: Session = Depends(get_db)):
    item = db.query(Submission).filter_by(id=identifier).with_for_update().first()
    if not item:
        raise HTTPException(404, 'Not found')
    if item.user_id == user.id:
        raise HTTPException(403, 'Another moderator must review your contribution')
    if item.state not in ('pending', 'appealed'):
        raise HTTPException(409, 'Already decided')
    if item.state == 'appealed' and item.reviewer_id == user.id:
        raise HTTPException(403, 'An appeal requires a different moderator')
    if payload.decision == 'approve':
        item.published_id = publish(db, item, payload.trust_level)
    item.state = 'approved' if payload.decision == 'approve' else 'rejected'
    item.decision_reason = payload.reason
    item.reviewer_id = user.id
    audit(db, user, item.state, 'submission', item.id, payload.model_dump())
    notify(db, item.user_id, 'moderation', f'Your {item.kind} contribution was {item.state}: {payload.reason}', item.id)
    db.commit()
    return record(item)


@router.post('/reports', status_code=201)
def report(payload: ReportInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    rate_limit(db, 'report:' + str(user.id), 20)
    target = row(db, MODELS[payload.target_type], payload.target_id)
    if payload.target_type == 'message' and user.id not in (target.sender_id, target.recipient_id):
        raise HTTPException(404, 'Not found')
    item = Report(user_id=user.id, **payload.model_dump(exclude={'target_id'}), target_id=str(payload.target_id))
    db.add(item)
    db.commit()
    return record(item)


@router.get('/moderation/reports')
def reports(user=Depends(require_moderator), db: Session = Depends(get_db)):
    return db.query(Report).filter_by(state='pending').order_by(Report.created_at).limit(100).all()


@router.post('/moderation/reports/{identifier}')
def resolve_report(identifier: UUID, payload: ModerationDecision, user=Depends(require_moderator), db: Session = Depends(get_db)):
    item = row(db, Report, identifier)
    if item.state != 'pending':
        raise HTTPException(409, 'Already resolved')
    target = row(db, MODELS[item.target_type], item.target_id)
    if payload.decision == 'approve':
        if item.target_type == 'user':
            if target.role in ('ADMIN', 'MODERATOR') and user.role != 'ADMIN':
                raise HTTPException(403, 'Administrator permission required')
            if target.id == user.id:
                raise HTTPException(403, 'Cannot suspend yourself')
            target.active = False
            target.token_version += 1
        elif item.target_type == 'event':
            target.status = EventStatus.cancelled
            target.is_manual_override = True
        elif item.target_type in ('review', 'comment'):
            target.state = 'hidden'
        elif item.target_type == 'message':
            target.body = '[Removed by moderation]'
        else:
            target.operational_status = 'closed'
    item.state = 'resolved'
    item.decision = payload.reason
    audit(db, user, 'report_resolved', 'report', item.id, payload.model_dump())
    db.commit()
    return record(item)


@router.patch('/moderation/users/{identifier}/role')
def assign_role(identifier: UUID, payload: RoleInput, user=Depends(require_admin), db: Session = Depends(get_db)):
    target = row(db, User, identifier)
    if target.id == user.id:
        raise HTTPException(403, 'Cannot change your own role')
    old = target.role
    target.role = payload.role
    target.token_version += 1
    audit(db, user, 'role_changed', 'user', target.id, {'from': old, **payload.model_dump()})
    db.commit()
    return public_profile(db, target)


@router.get('/moderation/audit')
def audit_history(user=Depends(require_moderator), db: Session = Depends(get_db), offset: int = Query(0, ge=0)):
    return db.query(AuditLog).order_by(AuditLog.created_at.desc()).offset(offset).limit(100).all()


@router.get('/places')
def places(db: Session = Depends(get_db), q: str = Query('', max_length=100), offset: int = Query(0, ge=0)):
    return db.query(Place).filter(Place.name.ilike('%' + q + '%')).order_by(Place.name).offset(offset).limit(100).all()


@router.get('/places/{identifier}')
def place_detail(identifier: UUID, db: Session = Depends(get_db)):
    return record(row(db, Place, identifier))


@router.get('/people')
def people(q: str = Query('', max_length=100), user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(User).filter(User.active.is_(True), User.public_profile.is_(True), User.display_name.ilike('%' + q + '%'), ~User.id.in_(blocked_ids(db, user.id)))
    return [public_profile(db, person) for person in query.order_by(User.display_name).limit(50)]


@router.get('/utilities')
def utilities(db: Session = Depends(get_db), kind: str = Query('toilet', max_length=40), accessible: bool | None = None, free: bool | None = None, offset: int = Query(0, ge=0)):
    query = db.query(CityUtility).filter_by(kind=kind)
    if accessible is not None:
        query = query.filter_by(wheelchair_accessible=accessible)
    if free is not None:
        query = query.filter_by(free=free)
    return [utility_record(db, item) for item in query.order_by(CityUtility.name).offset(offset).limit(100).all()]


@router.get('/utilities/viewport')
def utilities_viewport(
    min_lat: float = Query(ge=-90, le=90), max_lat: float = Query(ge=-90, le=90),
    min_lng: float = Query(ge=-180, le=180), max_lng: float = Query(ge=-180, le=180),
    kind: str = Query('toilet', max_length=40), limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
):
    if min_lat > max_lat or min_lng > max_lng:
        raise HTTPException(422, 'Viewport minimums must not exceed maximums')
    return [utility_record(db, item) for item in viewport_query(
        db, min_lat=min_lat, max_lat=max_lat, min_lng=min_lng, max_lng=max_lng, kind=kind, limit=limit,
    )]


@router.get('/utilities/nearby')
def utilities_nearby(
    lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
    radius_km: float = Query(3, gt=0, le=25), kind: str = Query('toilet', max_length=40),
    limit: int = Query(100, ge=1, le=200), db: Session = Depends(get_db),
):
    return [utility_record(db, item) for item in nearby_query(
        db, lat=lat, lng=lng, radius_km=radius_km, kind=kind, limit=limit,
    )]


@router.get('/utilities/{identifier}')
def utility_detail(identifier: UUID, db: Session = Depends(get_db)):
    return utility_record(db, row(db, CityUtility, identifier))


@router.post('/utilities/{identifier}/confirm')
def confirm_utility(identifier: UUID, payload: Confirmation, user=Depends(require_verified), db: Session = Depends(get_db)):
    rate_limit(db, f'confirm:{user.id}:{identifier}', 1, 86400)
    item = row(db, CityUtility, identifier)
    db.add(UtilityConfirmation(utility_id=item.id, user_id=user.id, **payload.model_dump()))
    if payload.cleanliness is not None:
        item.cleanliness = payload.cleanliness
    item.last_confirmed_at = datetime.utcnow()
    audit(db, user, 'utility_confirmed', 'utility', item.id, payload.model_dump())
    db.commit()
    db.refresh(item)
    aggregated = utility_record(db, item)
    item.operational_status = aggregated['operational_status']
    db.commit()
    return aggregated


@router.post('/reviews')
def review(payload: ReviewInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    rate_limit(db, 'review:' + str(user.id), 20)
    target = row(db, MODELS[payload.target_type], payload.target_id)
    if payload.target_type == 'event' and (target.end_time or target.start_time) > datetime.utcnow():
        raise HTTPException(422, 'Review an event after it has taken place')
    if getattr(target, 'contributor_id', None) == user.id:
        raise HTTPException(403, 'Cannot review your own contribution')
    item = db.query(Review).filter_by(user_id=user.id, target_type=payload.target_type, target_id=str(payload.target_id)).first()
    if item:
        if item.state != 'visible':
            raise HTTPException(403, 'A moderated review cannot be republished')
        db.add(ReviewRevision(review_id=item.id, body=item.body, dimensions=item.dimensions))
        item.body, item.dimensions = payload.body, payload.dimensions
    else:
        item = Review(user_id=user.id, **payload.model_dump(exclude={'target_id'}), target_id=str(payload.target_id))
        db.add(item)
    db.commit()
    return record(item)


@router.get('/reviews/{target_type}/{identifier}')
def reviews(target_type: str, identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    if target_type not in ('event', 'place'):
        raise HTTPException(422, 'Unsupported review target')
    items = db.query(Review).filter_by(target_type=target_type, target_id=str(identifier), state='visible').filter(~Review.user_id.in_(blocked_ids(db, user.id))).order_by(Review.created_at.desc()).limit(100).all()
    return [{'id': i.id, 'user_id': i.user_id, 'body': i.body, 'dimensions': i.dimensions,
             'attendance_verified': i.attendance_verified, 'updated_at': i.updated_at,
             'helpful': db.query(HelpfulVote).filter_by(review_id=i.id).count()} for i in items]


@router.post('/reviews/{identifier}/helpful')
def helpful(identifier: UUID, user=Depends(require_verified), db: Session = Depends(get_db)):
    item = row(db, Review, identifier)
    if item.user_id == user.id or item.state != 'visible' or blocked(db, user.id, item.user_id):
        raise HTTPException(403, 'Cannot vote on this review')
    if not db.query(HelpfulVote).filter_by(review_id=item.id, user_id=user.id).first():
        db.add(HelpfulVote(review_id=item.id, user_id=user.id))
        db.commit()
    return {'helpful': True}


@router.post('/collections', status_code=201)
def create_collection(payload: CollectionInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    rate_limit(db, 'collection:' + str(user.id), 20)
    for item in payload.items:
        if set(item) != {'type', 'id'} or item['type'] not in ('event', 'place', 'utility'):
            raise HTTPException(422, 'Collection items need a type and id')
        row(db, MODELS[item['type']], item['id'])
    item = Collection(user_id=user.id, **payload.model_dump())
    db.add(item)
    db.commit()
    return record(item)


@router.get('/collections')
def collections(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Collection).filter(or_(Collection.public.is_(True), Collection.user_id == user.id), ~Collection.user_id.in_(blocked_ids(db, user.id))).order_by(Collection.created_at.desc()).limit(100).all()


@router.post('/events/{identifier}/comments')
def add_comment(identifier: UUID, payload: BodyInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    rate_limit(db, 'comment:' + str(user.id), 30)
    row(db, Event, identifier)
    item = Comment(event_id=identifier, user_id=user.id, body=payload.body)
    db.add(item)
    db.commit()
    return record(item)


@router.get('/events/{identifier}/comments')
def comments(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db), offset: int = Query(0, ge=0)):
    return db.query(Comment).filter_by(event_id=identifier, state='visible').filter(~Comment.user_id.in_(blocked_ids(db, user.id))).order_by(Comment.created_at.desc()).offset(offset).limit(100).all()


def can_message(db, user, target):
    if not target.active or target.id == user.id or blocked(db, user.id, target.id):
        return False
    if target.allow_general_messages:
        return True
    def follows(a, b):
        return db.query(Follow).filter(Follow.user_id == a, Follow.target_type.in_(['user', 'guide']), Follow.target_id == str(b)).first()
    return bool(follows(user.id, target.id) and follows(target.id, user.id))


@router.post('/messages/{identifier}')
def send_message(identifier: UUID, payload: BodyInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    rate_limit(db, 'message:' + str(user.id), 30)
    target = row(db, User, identifier)
    if not can_message(db, user, target):
        raise HTTPException(403, 'Messaging requires mutual follows or recipient opt-in')
    item = Message(sender_id=user.id, recipient_id=target.id, body=payload.body)
    db.add(item)
    notify(db, target.id, 'message', 'You received a new message', user.id)
    db.commit()
    return record(item)


@router.get('/messages/{identifier}')
def conversation(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db), offset: int = Query(0, ge=0)):
    if blocked(db, user.id, identifier):
        raise HTTPException(403, 'Conversation unavailable')
    return db.query(Message).filter(or_(and_(Message.sender_id == user.id, Message.recipient_id == identifier), and_(Message.sender_id == identifier, Message.recipient_id == user.id))).order_by(Message.created_at.desc()).offset(offset).limit(100).all()


@router.get('/notifications')
def notifications(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Notification).filter_by(user_id=user.id).order_by(Notification.created_at.desc()).limit(100).all()


@router.post('/notifications/{identifier}/read')
def read_notification(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    item = row(db, Notification, identifier)
    if item.user_id != user.id:
        raise HTTPException(404, 'Not found')
    item.read_at = datetime.utcnow()
    db.commit()
    return {'read': True}


@router.post('/organizations', status_code=201)
def organization(payload: OrganizationInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    rate_limit(db, 'organization:' + str(user.id), 5)
    if payload.venue_id:
        row(db, Venue, payload.venue_id)
    item = Organization(**payload.model_dump())
    db.add(item)
    db.commit()
    return {'id': item.id, 'name': item.name, 'verified': item.verified}


@router.get('/organizations')
def organizations(db: Session = Depends(get_db), q: str = Query('', max_length=100)):
    return [dict(id=i.id, name=i.name, description=i.description, website=i.website, venue_id=i.venue_id, verified=i.verified)
            for i in db.query(Organization).filter(Organization.name.ilike('%' + q + '%')).order_by(Organization.name).limit(100)]


@router.post('/organizations/{identifier}/claim')
def claim(identifier: UUID, payload: ClaimInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    row(db, Organization, identifier)
    return submit(db, user, 'claim', {'organization_id': str(identifier), **payload.model_dump()})


@router.patch('/organizations/{identifier}')
def update_org(identifier: UUID, payload: OrganizationInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    item = owned_organization(db, user, identifier)
    # Changing the claimed website or venue invalidates the verified ownership evidence.
    if payload.website != item.website or payload.venue_id != item.venue_id:
        raise HTTPException(409, 'Ownership changes require moderator review')
    item.name, item.description = payload.name, payload.description
    audit(db, user, 'organization_updated', 'organization', item.id)
    db.commit()
    return {'id': item.id, 'name': item.name, 'description': item.description, 'verified': item.verified}


@router.get('/account/export')
def export_account(user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Return a portable snapshot of all records associated with the account."""
    user_id, user_id_text = user.id, str(user.id)
    review_ids = [item.id for item in db.query(Review.id).filter_by(user_id=user_id)]
    profile = record(user)
    profile.pop('hashed_password', None)
    export = {
        'schema_version': 1,
        'exported_at': datetime.utcnow(),
        'profile': profile,
        'oauth_identities': records(db.query(OAuthIdentity).filter_by(user_id=user_id)),
        'saved_events': records(db.query(SavedEvent).filter_by(user_id=user_id)),
        'submissions': records(db.query(Submission).filter(or_(Submission.user_id == user_id, Submission.reviewer_id == user_id))),
        'audit_logs': records(db.query(AuditLog).filter(or_(AuditLog.actor_id == user_id, and_(AuditLog.target_type == 'user', AuditLog.target_id == user_id_text)))),
        'follows': records(db.query(Follow).filter(or_(Follow.user_id == user_id, and_(Follow.target_type.in_(['user', 'guide']), Follow.target_id == user_id_text)))),
        'blocks': records(db.query(UserBlock).filter(or_(UserBlock.user_id == user_id, UserBlock.blocked_id == user_id))),
        'reports': records(db.query(Report).filter_by(user_id=user_id)),
        'organization_memberships': records(db.query(OrganizationMember).filter_by(user_id=user_id)),
        'places_contributed': records(db.query(Place).filter_by(contributor_id=user_id)),
        'utilities_contributed': records(db.query(CityUtility).filter_by(contributor_id=user_id)),
        'utility_confirmations': records(db.query(UtilityConfirmation).filter_by(user_id=user_id)),
        'reviews': records(db.query(Review).filter_by(user_id=user_id)),
        'review_revisions': records(db.query(ReviewRevision).filter(ReviewRevision.review_id.in_(review_ids))) if review_ids else [],
        'helpful_votes': records(db.query(HelpfulVote).filter_by(user_id=user_id)),
        'collections': records(db.query(Collection).filter_by(user_id=user_id)),
        'comments': records(db.query(Comment).filter_by(user_id=user_id)),
        'messages': records(db.query(Message).filter(or_(Message.sender_id == user_id, Message.recipient_id == user_id))),
        'notifications': records(db.query(Notification).filter_by(user_id=user_id)),
    }
    audit(db, user, 'account_exported', 'user', user.id)
    db.commit()
    return jsonable_encoder(export)


@router.delete('/account')
def delete_account(payload: Reason, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Erase private/activity data and anonymize retained public or compliance records."""
    user_id, old_email = user.id, user.email
    # Provider subjects and all private/security records are erased immediately.
    db.query(OAuthIdentity).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(ActionToken).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(MailOutbox).filter_by(recipient=old_email).delete(synchronize_session=False)
    db.query(SavedEvent).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(Message).filter(or_(Message.sender_id == user_id, Message.recipient_id == user_id)).delete(synchronize_session=False)
    db.query(Follow).filter(or_(Follow.user_id == user_id, and_(Follow.target_type.in_(['user', 'guide']), Follow.target_id == str(user_id)))).delete(synchronize_session=False)
    db.query(UserBlock).filter(or_(UserBlock.user_id == user_id, UserBlock.blocked_id == user_id)).delete(synchronize_session=False)
    db.query(Notification).filter(or_(Notification.user_id == user_id, Notification.target_id == str(user_id))).delete(synchronize_session=False)
    db.query(OrganizationMember).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(HelpfulVote).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(UtilityConfirmation).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(Report).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(Collection).filter(Collection.user_id == user_id, Collection.public.is_(False)).delete(synchronize_session=False)
    db.query(RateBucket).filter(or_(RateBucket.key.contains(str(user_id)), RateBucket.key.contains(old_email))).delete(synchronize_session=False)

    # Unpublished submissions are retained only as empty workflow tombstones.
    db.query(Submission).filter(
        Submission.user_id == user_id,
        Submission.state.notin_(['approved', 'rejected']),
    ).update({'state': 'withdrawn', 'payload': {}, 'appeal': None, 'decision_reason': None}, synchronize_session=False)

    # Published contributions and compliance logs retain the anonymous user ID.
    user.active = False
    user.token_version += 1
    user.email = f'deleted-{user.id}@example.invalid'
    user.hashed_password = '!deleted'
    user.display_name = 'Deleted account'
    user.bio = user.avatar_url = user.neighborhood = None
    user.interests = []
    user.city = 'Bratislava'
    user.role = 'USER'
    user.email_verified = user.identity_verified = False
    user.allow_general_messages = False
    user.public_profile = False
    audit(db, user, 'account_deleted', 'user', user.id)
    db.commit()
    return {'deleted': True}
