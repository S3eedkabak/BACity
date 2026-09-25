import hashlib
import time
from datetime import datetime
from uuid import UUID
from fastapi import Depends, HTTPException
from sqlalchemy import or_, and_
from app.api.deps import get_current_user
from app.models.community import AuditLog, Notification, RateBucket, UserBlock, OrganizationMember, Organization


def require_verified(user=Depends(get_current_user)):
    if not user.email_verified:
        raise HTTPException(403, 'Verify your email before contributing')
    return user


def require_moderator(user=Depends(require_verified)):
    if user.role not in ('MODERATOR', 'ADMIN'):
        raise HTTPException(403, 'Moderator permission required')
    return user


def require_admin(user=Depends(require_moderator)):
    if user.role != 'ADMIN':
        raise HTTPException(403, 'Administrator permission required')
    return user


def row(db, model, identifier):
    try:
        item = db.get(model, UUID(str(identifier)))
    except (ValueError, TypeError):
        item = None
    if item is None:
        raise HTTPException(404, 'Not found')
    return item


def audit(db, actor, action, kind, identifier, details=None):
    db.add(AuditLog(actor_id=actor.id if actor else None, action=action, target_type=kind, target_id=str(identifier), details=details or {}))


def notify(db, user_id, kind, body, target_id=None):
    db.add(Notification(user_id=user_id, kind=kind, body=body, target_id=str(target_id) if target_id else None))


def blocked(db, left, right):
    return bool(db.query(UserBlock).filter(or_(and_(UserBlock.user_id == left, UserBlock.blocked_id == right), and_(UserBlock.user_id == right, UserBlock.blocked_id == left))).first())


def blocked_ids(db, user_id):
    rows = db.query(UserBlock).filter(or_(UserBlock.user_id == user_id, UserBlock.blocked_id == user_id)).all()
    return [r.blocked_id if r.user_id == user_id else r.user_id for r in rows]


def owned_organization(db, user, identifier):
    org = row(db, Organization, identifier)
    membership = db.query(OrganizationMember).filter_by(organization_id=org.id, user_id=user.id).first()
    if user.role != 'ADMIN' and not membership:
        raise HTTPException(403, 'Approved organization membership required')
    return org


def rate_limit(db, key, limit, seconds=3600):
    """Atomic counters shared across API replicas; store hashes, not emails/IPs."""
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    insert = pg_insert if db.bind.dialect.name == 'postgresql' else sqlite_insert
    values = {'key': hashlib.sha256(key.encode()).hexdigest(), 'window': int(time.time()) // seconds * seconds}
    statement = insert(RateBucket).values(**values, count=1).on_conflict_do_update(index_elements=['key', 'window'], set_={'count': RateBucket.count + 1}).returning(RateBucket.count)
    count = db.execute(statement).scalar_one()
    db.commit()
    if count > limit:
        raise HTTPException(429, 'Too many requests; please try later', headers={'Retry-After': str(seconds)})


def reputation_level(score):
    return 'Senior Guide' if score >= 500 else 'Local Guide' if score >= 200 else 'Trusted Contributor' if score >= 100 else 'Contributor' if score >= 10 else 'New User'
