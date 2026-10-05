"""Community contributions are published only after an audited moderation decision."""
from datetime import datetime, timezone, timedelta
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.encoders import jsonable_encoder
from sqlalchemy import or_, and_
from sqlalchemy.orm import Session
from PIL import Image, ImageOps, UnidentifiedImageError
from io import BytesIO
from pathlib import Path
from app.database import get_db
from app.config import get_settings
from app.api.deps import get_current_user
from app.core.community import (require_verified, require_moderator, require_admin, row,
    audit, notify, blocked, blocked_ids, rate_limit, reputation_level, owned_organization)
from app.core.utilities import nearby_query, utility_record, viewport_query
from app.core.entitlements import BACITY_PLUS, EntitlementService
from app.models.user import User
from app.models.privacy import PrivacyRequest
from app.models.oauth_identity import OAuthIdentity
from app.models.saved_event import SavedEvent
from app.models.event import Event, EventStatus, EventCategory
from app.models.venue import Venue
from app.models.community import (Submission, AuditLog, Follow, UserBlock, Report, Organization,
    OrganizationMember, Place, CityUtility, UtilityConfirmation, Review, ReviewRevision,
    HelpfulVote, Collection, Comment, Message, Notification)
from app.models.community import ActionToken, MailOutbox, RateBucket
from app.models.group import GroupSession, GroupParticipant, GroupVote
from app.models.area_watch import AreaWatch
from app.models.entitlement import ConsumerBillingCustomer, ConsumerSubscription
from app.schemas.community import (ProfileUpdate, EventSubmission, PlaceInput, UtilityInput,
    ModerationDecision, Reason, FollowInput, ReportInput, ReviewInput, BodyInput,
    OrganizationInput, ClaimInput, RoleInput, CollectionInput, CorrectionInput, Confirmation)

router = APIRouter(prefix='/community', tags=['community'])
settings = get_settings()
Image.MAX_IMAGE_PIXELS = 15_000_000
MODELS = {'event': Event, 'place': Place, 'utility': CityUtility, 'user': User,
          'review': Review, 'comment': Comment, 'message': Message}


def record(item):
    result = {column.name: getattr(item, column.name) for column in item.__table__.columns}
    if isinstance(item, Submission):
        result['payload'] = {k: v for k, v in item.payload.items() if k != '_source_learning'}
    return result


def records(query):
    return [record(item) for item in query.all()]


def public_profile(db, user):
    return dict(id=user.id, display_name=user.display_name, avatar_url=user.avatar_url,
                bio=user.bio, city=user.city, neighborhood=user.neighborhood, interests=user.interests,
                role=user.role, identity_verified=user.identity_verified,
                reputation=user.reputation,
                reputation_level=reputation_level(user.reputation),
                contributions_count=db.query(Submission).filter_by(user_id=user.id, state='approved').count(),
                reviews_count=db.query(Review).filter_by(user_id=user.id, state='visible').count(),
                followers=db.query(Follow).filter(Follow.target_type.in_(['user', 'guide']), Follow.target_id == str(user.id)).count(),
                following=db.query(Follow).filter_by(user_id=user.id).count())


def _avatar_path(user_id):
    return Path(settings.media_root) / 'avatars' / f'{user_id}.jpg'


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


@router.post('/profile/avatar')
async def upload_avatar(
    avatar: UploadFile = File(...), user=Depends(get_current_user), db: Session = Depends(get_db),
):
    if avatar.content_type not in {'image/jpeg', 'image/png', 'image/webp'}:
        raise HTTPException(415, 'Use a JPEG, PNG, or WebP image')
    payload = await avatar.read(5 * 1024 * 1024 + 1)
    if len(payload) > 5 * 1024 * 1024:
        raise HTTPException(413, 'Avatar must be 5 MB or smaller')
    try:
        source = Image.open(BytesIO(payload))
        source.load()
        if source.width < 128 or source.height < 128 or source.width * source.height > 30_000_000:
            raise HTTPException(422, 'Avatar must be at least 128×128 and at most 30 megapixels')
        rendered = ImageOps.fit(source.convert('RGB'), (512, 512), method=Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise HTTPException(422, 'Avatar image could not be decoded') from exc
    destination = _avatar_path(user.id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix('.tmp')
    rendered.save(temporary, format='JPEG', quality=88, optimize=True)
    temporary.replace(destination)
    version = int(datetime.utcnow().timestamp())
    user.avatar_url = settings.oauth_callback_base_url.rstrip('/') + f'/media/avatars/{user.id}.jpg?v={version}'
    audit(db, user, 'avatar_updated', 'user', user.id)
    db.commit()
    return public_profile(db, user)


@router.get('/profiles/{identifier}')
def profile(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    target = row(db, User, identifier)
    if not target.active or blocked(db, user.id, target.id) or (not target.public_profile and user.id != target.id):
        raise HTTPException(404, 'Profile unavailable')
    result = public_profile(db, target)
    follow_link = db.query(Follow).filter(
        Follow.user_id == user.id, Follow.target_type.in_(['user', 'guide']), Follow.target_id == str(target.id)
    ).first()
    result['is_following'] = bool(follow_link)
    result['follow_id'] = follow_link.id if follow_link else None
    contributions = db.query(Submission).filter_by(user_id=target.id, state='approved')
    if user.id != target.id:
        contributions = contributions.filter(Submission.kind != 'event')
    result['contributions'] = contributions.order_by(Submission.created_at.desc()).limit(5).all()
    # Only publication metadata is public, never claims, reasons or correction evidence.
    result['contributions'] = [dict(id=s.id, kind=s.kind, published_id=s.published_id, created_at=s.created_at) for s in result['contributions']]
    return result


def _profile_access(db, viewer, identifier):
    target = row(db, User, identifier)
    if not target.active or blocked(db, viewer.id, target.id) or (not target.public_profile and viewer.id != target.id):
        raise HTTPException(404, 'Profile unavailable')
    return target


def _contribution_record(db, submission):
    title = None
    if submission.published_id and submission.kind in ('event', 'place', 'utility'):
        try:
            published = db.get(MODELS[submission.kind], UUID(str(submission.published_id)))
            title = getattr(published, 'title', None) or getattr(published, 'name', None) if published else None
        except ValueError:
            pass
    return dict(id=submission.id, kind=submission.kind, published_id=submission.published_id,
                title=title or submission.kind.title(), created_at=submission.created_at)


@router.get('/profiles/{identifier}/contributions')
def profile_contributions(identifier: UUID, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
                          user=Depends(get_current_user), db: Session = Depends(get_db)):
    target = _profile_access(db, user, identifier)
    query = db.query(Submission).filter_by(user_id=target.id, state='approved')
    if user.id != target.id:
        query = query.filter(Submission.kind != 'event')
    items = query.order_by(Submission.created_at.desc()).offset(offset).limit(limit).all()
    return [_contribution_record(db, item) for item in items]


@router.get('/profiles/{identifier}/reviews')
def profile_reviews(identifier: UUID, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
                    user=Depends(get_current_user), db: Session = Depends(get_db)):
    target = _profile_access(db, user, identifier)
    items = db.query(Review).filter_by(user_id=target.id, state='visible').order_by(
        Review.updated_at.desc()).offset(offset).limit(limit).all()
    result = []
    for item in items:
        target_item = db.get(MODELS[item.target_type], UUID(item.target_id)) if item.target_type in ('event', 'place') else None
        result.append(dict(id=item.id, target_type=item.target_type, target_id=item.target_id,
                           target_name=getattr(target_item, 'title', None) or getattr(target_item, 'name', None),
                           body=item.body, dimensions=item.dimensions, updated_at=item.updated_at,
                           helpful=db.query(HelpfulVote).filter_by(review_id=item.id).count()))
    return result


def _follow_record(db, item, viewer):
    label, subtitle = item.target_id, item.target_type.title()
    model = {'user': User, 'guide': User, 'venue': Venue, 'organizer': Organization}.get(item.target_type)
    if model:
        try:
            target = db.get(model, UUID(item.target_id))
        except ValueError:
            target = None
        if model is User and (not target or not target.active or
            (target.id != viewer.id and (not target.public_profile or blocked(db, viewer.id, target.id)))):
            if item.user_id == viewer.id:
                # Keep the owner's existing edge removable without exposing
                # now-private profile metadata to them or to public visitors.
                return {**record(item), 'target_label': 'Unavailable profile', 'target_subtitle': 'Profile unavailable'}
            return None
        if target:
            label = getattr(target, 'display_name', None) or getattr(target, 'name', None) or label
            subtitle = getattr(target, 'neighborhood', None) or getattr(target, 'address', None) or subtitle
    return {**record(item), 'target_label': label, 'target_subtitle': subtitle}


@router.get('/profiles/{identifier}/followers')
def profile_followers(identifier: UUID, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    target = _profile_access(db, user, identifier)
    follower_ids = db.query(Follow.user_id).filter(
        Follow.target_type.in_(['user', 'guide']), Follow.target_id == str(target.id)
    ).order_by(Follow.created_at.desc()).offset(offset).limit(limit).all()
    blocked_set = set(blocked_ids(db, user.id))
    return [public_profile(db, person) for (person_id,) in follower_ids
            if person_id not in blocked_set and (person := db.get(User, person_id)) and person.active and person.public_profile]


@router.get('/profiles/{identifier}/following')
def profile_following(identifier: UUID, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
                      user=Depends(get_current_user), db: Session = Depends(get_db)):
    target = _profile_access(db, user, identifier)
    items = db.query(Follow).filter_by(user_id=target.id).order_by(Follow.created_at.desc()).offset(offset).limit(limit).all()
    return [value for item in items if (value := _follow_record(db, item, user)) is not None]


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
    elif payload.target_type == 'category':
        category = next((item.value for item in EventCategory if item.value.casefold() == target_id.casefold()), None)
        if not category:
            raise HTTPException(422, 'Unknown event category')
        target_id = category
    elif payload.target_type == 'neighborhood':
        known = {value for (value,) in db.query(Event.neighborhood).filter(Event.neighborhood.isnot(None)).distinct()}
        known.update(value for (value,) in db.query(Place.neighborhood).filter(Place.neighborhood.isnot(None)).distinct())
        known.update(value for (value,) in db.query(User.neighborhood).filter(User.neighborhood.isnot(None)).distinct())
        match = next((value for value in known if value.casefold() == target_id.casefold()), None)
        if not match:
            raise HTTPException(422, 'Unknown neighborhood')
        target_id = match
    item = db.query(Follow).filter_by(user_id=user.id, target_type=payload.target_type, target_id=target_id).first()
    if not item:
        item = Follow(user_id=user.id, target_type=payload.target_type, target_id=target_id)
        db.add(item)
        db.commit()
    return record(item)


@router.get('/follows')
def follows(target_type: str | None = Query(None, max_length=20), offset: int = Query(0, ge=0),
            limit: int = Query(50, ge=1, le=100), user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(Follow).filter_by(user_id=user.id)
    if target_type:
        query = query.filter_by(target_type=target_type)
    return [value for item in query.order_by(Follow.created_at.desc()).offset(offset).limit(limit).all()
            if (value := _follow_record(db, item, user)) is not None]


@router.get('/follow-targets')
def follow_targets(target_type: str = Query(max_length=20), q: str = Query('', max_length=100),
                   offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
                   user=Depends(get_current_user), db: Session = Depends(get_db)):
    search = f'%{q}%'
    if target_type in ('user', 'guide'):
        query = db.query(User).filter(User.active.is_(True), User.public_profile.is_(True),
            User.id != user.id, User.display_name.ilike(search), ~User.id.in_(blocked_ids(db, user.id)))
        if target_type == 'guide':
            query = query.filter(User.role == 'GUIDE')
        return [dict(target_type=target_type, target_id=str(item.id), name=item.display_name or 'BACity member',
                     subtitle=f'{item.neighborhood or item.city} · {reputation_level(item.reputation)}', avatar_url=item.avatar_url)
                for item in query.order_by(User.display_name).offset(offset).limit(limit)]
    if target_type in ('venue', 'organizer'):
        model = Venue if target_type == 'venue' else Organization
        query = db.query(model).filter(model.name.ilike(search)).order_by(model.name).offset(offset).limit(limit)
        return [dict(target_type=target_type, target_id=str(item.id), name=item.name,
                     subtitle=getattr(item, 'address', None) or ('Verified organizer' if getattr(item, 'verified', False) else 'Organizer'))
                for item in query]
    if target_type == 'category':
        values = [item.value for item in EventCategory if q.casefold() in item.value.casefold()]
    elif target_type == 'neighborhood':
        values = {value for (value,) in db.query(Event.neighborhood).filter(Event.neighborhood.isnot(None)).distinct()}
        values.update(value for (value,) in db.query(Place.neighborhood).filter(Place.neighborhood.isnot(None)).distinct())
        values.update(value for (value,) in db.query(User.neighborhood).filter(
            User.neighborhood.isnot(None), User.active.is_(True), User.public_profile.is_(True),
            ~User.id.in_(blocked_ids(db, user.id)),
        ).distinct())
        values = sorted(value for value in values if q.casefold() in value.casefold())
    else:
        raise HTTPException(422, 'Unsupported follow target type')
    return [dict(target_type=target_type, target_id=value, name=value, subtitle=target_type.title())
            for value in list(values)[offset:offset + limit]]


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
    _lock_message_users(db, user.id, identifier)
    if not user.active:
        raise HTTPException(401, 'Account unavailable')
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
    return records(db.query(Submission).filter_by(user_id=user.id).order_by(Submission.created_at.desc()).offset(offset).limit(100))


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
        from app.crud.ingestion import find_canonical_event, utc, canonical_url, normalize
        from app.models.event_source import EventSource
        from app.core.source_learning import queue_public_evidence
        payload = EventSubmission.model_validate(item.payload)
        payload = payload.model_copy(update={'start_time': utc(payload.start_time), 'end_time': utc(payload.end_time),
            'source_url': canonical_url(payload.source_url) if payload.source_url else '', 'previous_start_time': None})
        obj, evidence, _ = find_canonical_event(db, payload)
        data = payload.model_dump(exclude={'public_source_url', 'organizer_name', 'venue_name', 'source_name', 'original_source_url', 'source_id', 'venue_id', 'status', 'extraction_confidence', 'source_reliability', 'temporal_evidence', 'extraction_method', 'previous_start_time'})
        if obj is None:
            obj = Event(**data, contributor_id=item.user_id, trust_level=trust, is_manual_override=True,
                        extraction_confidence=1, source_reliability=0.7, status=EventStatus.fresh)
            db.add(obj)
            db.flush()
        if payload.source_url:
            if evidence is None:
                evidence = EventSource(event_id=obj.id, source_url=payload.source_url,
                    original_source_url=payload.source_url, start_time=payload.start_time,
                    title_key=normalize(payload.title), reliability=.7, dedup_confidence=1)
                db.add(evidence)
            evidence.facts = {**(evidence.facts or {}), 'human_contribution': True}
        # Snapshot only explicit public fields; no contributor identity or raw text.
        queue_public_evidence(item, [payload.public_source_url, payload.source_url, obj.venue.website if obj.venue else None])
    elif item.kind in ('place', 'utility'):
        schema, model = (PlaceInput, Place) if item.kind == 'place' else (UtilityInput, CityUtility)
        obj = model(**schema.model_validate(item.payload).model_dump(), contributor_id=item.user_id)
        if item.kind == 'place':
            obj.trust_level = trust
    elif item.kind == 'claim':
        obj = row(db, Organization, item.payload['organization_id'])
        # Different submissions may approve concurrently: lock the shared target,
        # not just each submission, before checking whether ownership is available.
        obj = db.query(Organization).filter_by(id=obj.id).with_for_update().one()
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
    audit(db, user, item.state, 'submission', item.id, {'decision': payload.decision, 'trust_level': payload.trust_level})
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
    audit(db, user, 'report_resolved', 'report', item.id, {'decision': payload.decision})
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
def people(q: str = Query('', max_length=100), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50),
           user=Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(User).filter(User.active.is_(True), User.public_profile.is_(True), User.display_name.ilike('%' + q + '%'), ~User.id.in_(blocked_ids(db, user.id)))
    return [public_profile(db, person) for person in query.order_by(User.display_name).offset(offset).limit(limit)]


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


def _lock_message_users(db, *identifiers):
    """Shared locks for send/block/deletion; stable order prevents pair deadlocks."""
    # PostgreSQL NO KEY UPDATE serializes these mutations without conflicting
    # with unrelated FK key-share checks (IDs are never changed by deletion).
    return db.query(User).filter(User.id.in_(identifiers)).order_by(User.id).populate_existing().with_for_update(key_share=True).all()


@router.post('/messages/{identifier}')
def send_message(identifier: UUID, payload: BodyInput, user=Depends(require_verified), db: Session = Depends(get_db)):
    version = user.token_version
    rate_limit(db, 'message:' + str(user.id), 30)
    _lock_message_users(db, user.id, identifier)
    if not user.active or not user.email_verified or user.token_version != version:
        raise HTTPException(401, 'Session changed; sign in again')
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
    rate_limit(db, 'account-export:' + str(user.id), 10, 3600)
    user_id, user_id_text = user.id, str(user.id)
    review_ids = [item.id for item in db.query(Review.id).filter_by(user_id=user_id)]
    profile = record(user)
    profile.pop('hashed_password', None)
    profile.pop('token_version', None)
    submissions = [{key: value for key, value in record(item).items()
                    if key not in {'risk_flags', 'reviewer_id'}}
                   for item in db.query(Submission).filter(Submission.user_id == user_id).all()]
    plus = EntitlementService(db).get_entitlement(user_id, BACITY_PLUS)
    consumer_billing = [
        {
            'provider': item.provider,
            'product': BACITY_PLUS,
            'status': item.status,
            'current_period_start': item.current_period_start,
            'current_period_end': item.current_period_end,
            'cancel_at_period_end': item.cancel_at_period_end,
            'cancelled_at': item.cancelled_at,
        }
        for item in db.query(ConsumerSubscription).filter_by(user_id=user_id).all()
    ]
    export = {
        'schema_version': 1,
        'exported_at': datetime.utcnow(),
        'profile': profile,
        'linked_sign_in_providers': [
            {'provider': item.provider, 'linked_at': item.created_at}
            for item in db.query(OAuthIdentity).filter_by(user_id=user_id).all()
        ],
        'consumer_entitlements': {
            BACITY_PLUS: {
                'active': plus.active,
                'expires_at': plus.expires_at,
                'management_channel': plus.management_channel,
            }
        },
        'consumer_billing': consumer_billing,
        'saved_events': records(db.query(SavedEvent).filter_by(user_id=user_id)),
        'submissions': submissions,
        'follows': records(db.query(Follow).filter(or_(Follow.user_id == user_id, and_(Follow.target_type.in_(['user', 'guide']), Follow.target_id == user_id_text)))),
        'blocks': records(db.query(UserBlock).filter_by(user_id=user_id)),
        'reports': records(db.query(Report).filter_by(user_id=user_id)),
        'organization_memberships': records(db.query(OrganizationMember).filter_by(user_id=user_id)),
        'places_contributed': records(db.query(Place).filter_by(contributor_id=user_id)),
        'utilities_contributed': records(db.query(CityUtility).filter_by(contributor_id=user_id)),
        'events_contributed': records(db.query(Event).filter_by(contributor_id=user_id)),
        'utility_confirmations': records(db.query(UtilityConfirmation).filter_by(user_id=user_id)),
        'reviews': records(db.query(Review).filter_by(user_id=user_id)),
        'review_revisions': records(db.query(ReviewRevision).filter(ReviewRevision.review_id.in_(review_ids))) if review_ids else [],
        'helpful_votes': records(db.query(HelpfulVote).filter_by(user_id=user_id)),
        'collections': records(db.query(Collection).filter_by(user_id=user_id)),
        'comments': records(db.query(Comment).filter_by(user_id=user_id)),
        'messages': records(db.query(Message).filter(or_(Message.sender_id == user_id, Message.recipient_id == user_id))),
        'notifications': records(db.query(Notification).filter_by(user_id=user_id)),
        'groups_hosted': [
            {key: value for key, value in record(item).items() if key != 'invite_token_hash'}
            for item in db.query(GroupSession).filter_by(host_id=user_id)
        ],
        'group_participation': records(db.query(GroupParticipant).filter_by(user_id=user_id)),
        'group_votes': records(db.query(GroupVote).filter_by(user_id=user_id)),
        'area_watches': records(db.query(AreaWatch).filter_by(user_id=user_id)),
        'privacy_requests': [
            {key: value for key, value in record(item).items() if key != 'user_id'}
            for item in db.query(PrivacyRequest).filter_by(user_id=user_id)
        ],
    }
    audit(db, user, 'account_exported', 'user', user.id)
    db.commit()
    return jsonable_encoder(export)


@router.delete('/account')
def delete_account(payload: Reason, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """Erase private/activity data and anonymize retained public or compliance records."""
    user_id, old_email, version = user.id, user.email, user.token_version
    google_subscriptions = db.query(ConsumerSubscription).filter_by(
        provider='google_play', user_id=user_id,
    ).all()
    if google_subscriptions:
        from app.core.google_play_billing import verify_and_reconcile
        if not settings.google_play_billing_enabled:
            raise HTTPException(409, 'Google Play billing must be reconciled before account deletion')
        for item in google_subscriptions:
            if item.status != 'replaced':
                verify_and_reconcile(db, user_id, item.provider_purchase_token, settings)
    if any(item.status not in {'expired', 'replaced'} for item in google_subscriptions):
        raise HTTPException(409, 'Cancel BACity+ in Google Play and wait until the paid period ends before deleting this account')
    billing_customer = db.query(ConsumerBillingCustomer).filter_by(provider='stripe', user_id=user_id).first()
    if billing_customer:
        if not settings.stripe_consumer_secret_key:
            raise HTTPException(409, 'Cancel consumer billing before deleting this account')
        from app.core.consumer_billing import StripeConsumerClient, cancel_consumer_billing_for_deletion
        cancel_consumer_billing_for_deletion(db, user, StripeConsumerClient(settings), settings)
    # Provider reconciliation can commit; acquire this lock afterwards and hold
    # it through erasure. Message send/block share it and recheck live state.
    _lock_message_users(db, user_id)
    if not user.active or user.token_version != version:
        raise HTTPException(401, 'Account unavailable')
    _avatar_path(user_id).unlink(missing_ok=True)
    provider_revocation = {'stripe': 'cancelled'} if billing_customer else {}
    if google_subscriptions:
        # Google Play subscriptions are user-managed. At this point none are
        # active; erase sensitive purchase tokens before anonymizing the account.
        db.query(ConsumerSubscription).filter_by(provider='google_play', user_id=user_id).delete(
            synchronize_session=False,
        )
        provider_revocation['google_play'] = 'inactive_purchase_links_erased'
    for identity in db.query(OAuthIdentity).filter_by(user_id=user_id).all():
        if identity.provider == 'apple' and identity.refresh_token_encrypted:
            from app.api.routes.auth import revoke_apple_token
            client_id = settings.apple_ios_client_id or settings.apple_oauth_client_id
            provider_revocation['apple'] = 'revoked' if revoke_apple_token(identity.refresh_token_encrypted, client_id) else 'manual_revoke_required'
        else:
            provider_revocation.setdefault(identity.provider, 'local_link_removed')

    # Provider subjects and all private/security records are erased immediately.
    db.query(OAuthIdentity).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(ActionToken).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(MailOutbox).filter_by(recipient=old_email).delete(synchronize_session=False)
    db.query(SavedEvent).filter_by(user_id=user_id).delete(synchronize_session=False)
    # Delivered conversations belong to the surviving participant too. Keep
    # encrypted content under existing bounded message expiry, never reactivate
    # the deleted sender. Erase when neither participant remains active.
    inactive = db.query(User.id).filter(User.active.is_(False))
    db.query(Message).filter(or_(
        and_(Message.sender_id == user_id, or_(Message.recipient_id == user_id, Message.recipient_id.in_(inactive))),
        and_(Message.recipient_id == user_id, Message.sender_id.in_(inactive)),
    )).delete(synchronize_session=False)
    db.query(Follow).filter(or_(Follow.user_id == user_id, and_(Follow.target_type.in_(['user', 'guide']), Follow.target_id == str(user_id)))).delete(synchronize_session=False)
    db.query(UserBlock).filter(or_(UserBlock.user_id == user_id, UserBlock.blocked_id == user_id)).delete(synchronize_session=False)
    # Generic message notifications retain the surviving user's inbox link,
    # not the deleted profile. Other target notifications are removed.
    db.query(Notification).filter(or_(Notification.user_id == user_id,
        and_(Notification.target_id == str(user_id), Notification.kind != 'message'))).delete(synchronize_session=False)
    db.query(OrganizationMember).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(HelpfulVote).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(UtilityConfirmation).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(Report).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(Collection).filter(Collection.user_id == user_id, Collection.public.is_(False)).delete(synchronize_session=False)
    hosted_group_ids = [group_id for (group_id,) in db.query(GroupSession.id).filter_by(host_id=user_id)]
    if hosted_group_ids:
        db.query(GroupSession).filter(GroupSession.id.in_(hosted_group_ids)).update({
            'status': 'cancelled', 'invite_token_hash': None, 'invite_expires_at': None,
        }, synchronize_session=False)
    db.query(GroupVote).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(GroupParticipant).filter_by(user_id=user_id).delete(synchronize_session=False)
    db.query(AreaWatch).filter_by(user_id=user_id).delete(synchronize_session=False)
    # Remove request content and account linkage; retain only workflow metadata
    # until the owner approves a retention rule. Do not imply legal fulfilment.
    db.query(PrivacyRequest).filter_by(user_id=user_id).update({
        'user_id': None, 'details': '', 'response': '', 'identity_confirmed': False,
    }, synchronize_session=False)
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
    db.add(MailOutbox(recipient=old_email, subject='Your BACity account was deleted',
                      body='Your BACity account has been disabled and personal profile data was anonymized. '
                           'If you used a social provider, review that provider’s connected-app settings as well.'))
    db.commit()
    return {'deleted': True, 'provider_revocation': provider_revocation}
