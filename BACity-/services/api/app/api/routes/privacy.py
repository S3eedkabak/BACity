"""Assessed privacy rights, not automatic legal adjudication or compliance claims."""
import calendar
from datetime import datetime
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.config import get_settings
from app.core.community import audit, notify, rate_limit, require_admin
from app.database import get_db
from app.models.privacy import PrivacyRequest
from app.models.user import User

router = APIRouter(prefix='/privacy', tags=['privacy'])
Kind = Literal['ACCESS', 'RECTIFICATION', 'ERASURE', 'RESTRICTION', 'PORTABILITY', 'OBJECTION', 'OTHER_PRIVACY_REQUEST']
State = Literal['received', 'in_review', 'awaiting_information', 'completed', 'refused']
Decision = Literal['identity_checked', 'information_needed', 'fulfilled', 'partly_fulfilled', 'not_applicable', 'rights_of_others', 'legal_retention', 'other_assessed_reason']


def calendar_months(value, months):
    index = value.year * 12 + value.month - 1 + months
    year, month = divmod(index, 12)
    month += 1
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


class RequestInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: Kind
    details: str = Field('', max_length=2000)


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    status: State
    decision_code: Decision
    response: str = Field('', max_length=2000)
    identity_confirmed: bool = False
    extend: bool = False

    @model_validator(mode='after')
    def meaningful_response(self):
        if (self.extend or self.status in ('completed', 'refused', 'awaiting_information')) and not self.response.strip():
            raise ValueError('Provide a concise user-facing explanation without third-party private data')
        if self.status == 'completed' and not self.identity_confirmed:
            raise ValueError('Assess identity before fulfilling a request')
        return self


def representation(item, *, content=True):
    result = {key: getattr(item, key) for key in ('id', 'kind', 'status', 'created_at', 'updated_at', 'due_at', 'extended', 'closed_at', 'decision_code', 'identity_confirmed')}
    if content:
        result.update(details=item.details, response=item.response)
    result['overdue'] = not item.closed_at and item.due_at < datetime.utcnow()
    return result


@router.get('/information')
def information():
    s = get_settings()
    return {
        'privacy_contact_email': s.privacy_contact_email or None,
        'controller_legal_name': s.controller_legal_name or None,
        'business_address': s.business_address or None,
        'support_contact_email': s.support_contact_email or None,
        'legal_contact_email': s.legal_contact_email or None,
        'privacy_notice_url': s.privacy_notice_url or None,
        'terms_url': s.terms_url or None,
        'privacy_notice_version': s.privacy_notice_version or None,
        'terms_version': s.terms_version or None,
        'documents_ready': bool(s.controller_legal_name and s.business_address and s.privacy_notice_url and s.terms_url and s.privacy_contact_email and s.privacy_notice_version and s.terms_version),
        'message_encryption': 'Server-side encrypted at rest; not end-to-end encrypted.',
        'location': 'Recommendation location is optional, coarsened and request-scoped. Area Watch centers are saved privately until you delete them.',
        'recommendations': 'Ranking considers interests, saved categories, follows, event timing, proximity when enabled, freshness, quality and bounded popularity, with diversity. Scores and private histories are not shared.',
    }


@router.post('/requests', status_code=201)
def submit(payload: RequestInput, user=Depends(get_current_user), db: Session = Depends(get_db)):
    version = user.token_version
    rate_limit(db, 'privacy-request:' + str(user.id), 5, 86400)
    # Serialize with deletion and recheck after rate_limit commits.
    db.query(User).filter_by(id=user.id).populate_existing().with_for_update(key_share=True).one()
    if not user.active or user.token_version != version:
        raise HTTPException(401, 'Account unavailable')
    if db.query(PrivacyRequest).filter(PrivacyRequest.user_id == user.id, PrivacyRequest.status.in_(['received', 'in_review', 'awaiting_information'])).count() >= 10:
        raise HTTPException(409, 'Please follow up on your existing privacy requests')
    now = datetime.utcnow()
    item = PrivacyRequest(user_id=user.id, kind=payload.kind, details=payload.details.strip(), due_at=calendar_months(now, 1), created_at=now)
    db.add(item)
    db.flush()
    audit(db, user, 'privacy_request_submitted', 'privacy_request', item.id, {'kind': item.kind})
    db.commit()
    return representation(item)


@router.get('/requests')
def own_requests(user=Depends(get_current_user), db: Session = Depends(get_db), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50)):
    items = db.query(PrivacyRequest).filter_by(user_id=user.id).order_by(PrivacyRequest.created_at.desc(), PrivacyRequest.id).offset(offset).limit(limit).all()
    return [representation(item) for item in items]


@router.get('/portability')
def portability(user=Depends(get_current_user), db: Session = Depends(get_db)):
    # Reuse established complete export and its throttle. This is a technical
    # user-provided/observed subset, not a determination of Article 20 scope.
    from app.api.routes.community import export_account
    data = export_account(user, db)
    own = str(user.id)
    return {
        'schema_version': 1, 'exported_at': data['exported_at'],
        'scope': 'User-provided and observed data; legal portability scope requires review',
        'profile': {key: data['profile'].get(key) for key in ('email', 'display_name', 'bio', 'avatar_url', 'city', 'neighborhood', 'interests', 'public_profile', 'allow_general_messages')},
        **{key: data[key] for key in ('saved_events', 'collections', 'submissions', 'reviews', 'comments', 'utility_confirmations', 'helpful_votes', 'group_participation', 'group_votes', 'area_watches')},
        'follows': [item for item in data['follows'] if item['user_id'] == own],
        'messages_sent': [item for item in data['messages'] if item['sender_id'] == own],
    }


@router.get('/requests/{identifier}')
def own_request(identifier: UUID, user=Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.query(PrivacyRequest).filter_by(id=identifier, user_id=user.id).first()
    if not item:
        raise HTTPException(404, 'Request not found')
    return representation(item)


@router.get('/admin/requests')
def queue(user=Depends(require_admin), db: Session = Depends(get_db), offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=50), status: State | None = None):
    query = db.query(PrivacyRequest).filter(PrivacyRequest.user_id.isnot(None))
    if status:
        query = query.filter_by(status=status)
    return [representation(item, content=False) for item in query.order_by(PrivacyRequest.due_at, PrivacyRequest.id).offset(offset).limit(limit).all()]


@router.get('/admin/requests/{identifier}')
def inspect(identifier: UUID, user=Depends(require_admin), db: Session = Depends(get_db)):
    item = db.query(PrivacyRequest).filter_by(id=identifier).first()
    if not item or item.user_id is None:
        raise HTTPException(404, 'Request not found')
    audit(db, user, 'privacy_request_accessed', 'privacy_request', item.id)
    db.commit()
    return representation(item)


@router.patch('/admin/requests/{identifier}')
def review(identifier: UUID, payload: ReviewInput, user=Depends(require_admin), db: Session = Depends(get_db)):
    # Same owner -> request lock ordering as account deletion.
    owner = db.query(PrivacyRequest.user_id).filter_by(id=identifier).scalar()
    if owner is None:
        raise HTTPException(404, 'Request not found')
    db.query(User).filter_by(id=owner).with_for_update(key_share=True).one()
    item = db.query(PrivacyRequest).filter_by(id=identifier).populate_existing().with_for_update().first()
    if not item or item.user_id is None:
        raise HTTPException(404, 'Request not found')
    if item.closed_at:
        raise HTTPException(409, 'Closed requests are immutable')
    now = datetime.utcnow()
    if payload.extend:
        if item.extended or now > calendar_months(item.created_at, 1) or payload.status in ('completed', 'refused'):
            raise HTTPException(409, 'Extension must be assessed and communicated within the initial month, once')
        item.due_at = calendar_months(item.created_at, 3)
        item.extended = True
    item.status, item.response = payload.status, payload.response.strip()
    item.decision_code = payload.decision_code
    item.identity_confirmed = payload.identity_confirmed
    if item.status in ('completed', 'refused'):
        item.closed_at = now
    audit(db, user, 'privacy_request_reviewed', 'privacy_request', item.id, {'status': item.status, 'decision_code': item.decision_code, 'extended': item.extended})
    notify(db, item.user_id, 'privacy_request', 'Your privacy request has an update. Open Privacy & account rights to review it.', item.id)
    db.commit()
    return representation(item)
