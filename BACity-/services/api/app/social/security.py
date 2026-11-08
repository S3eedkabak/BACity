"""Opaque sessions, transactional audit chaining and default-deny staff permissions."""
import hashlib
import json
import secrets
import time
from dataclasses import dataclass
from sqlalchemy import case, select
from fastapi import Depends, HTTPException, Request
from .config import settings
from .db import database
from .models import Staff, StaffSession, Credential, RateBucket, AuditHead, AuditEvent

COOKIE = '__Host-bacity-staff'
CEREMONY = '__Host-bacity-ceremony'
PERMISSIONS = {
    'OWNER': {'read', 'propose', 'approve', 'review', 'publish', 'staff', 'audit', 'access', 'emergency'},
    'SOCIAL_ADMIN': {'read', 'propose', 'approve', 'review', 'publish', 'audit'},
    'SOCIAL_EDITOR': {'read', 'propose', 'review'},
    'SOCIAL_REVIEWER': {'read', 'review'},
    'SOCIAL_VIEWER': {'read'},
}

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def encoded(value):
    import base64
    return base64.urlsafe_b64encode(value).decode().rstrip('=')

def decoded(value):
    import base64
    return base64.urlsafe_b64decode(value + '=' * (-len(value) % 4))

def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True)

def client_ip(request):
    # Uvicorn must run with --no-proxy-headers. Never consume forwarded headers.
    return getattr(request.state,'source_ip',None) or (request.client.host if request.client else 'unknown')

def insert_for(db, model):
    if db.bind.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    return insert(model)

def budget(db, action, identity, limit=30, period=60):
    now = time.time()
    window = int(now // period)
    key = digest(action + ':' + identity)
    stmt = insert_for(db, RateBucket).values(key=key, window=window, count=1, expires=now + period * 2)
    count = db.execute(stmt.on_conflict_do_update(index_elements=['key'], set_={
        'window': window, 'count': case((RateBucket.window == window, RateBucket.count + 1), else_=1),
        'expires': now + period * 2,
    }).returning(RateBucket.count)).scalar_one()
    # Persist failed attempts as well as successful ones. Call before mutations.
    db.commit()
    if count > limit:
        raise HTTPException(429, 'Please wait before trying again', headers={'Retry-After': str(period)})

def audit(db, actor, action, resource='', result='success', request=None, details=None):
    db.execute(insert_for(db, AuditHead).values(id=1, sequence=0, digest='0' * 64)
               .on_conflict_do_nothing(index_elements=['id']))
    head = db.execute(select(AuditHead).where(AuditHead.id == 1).with_for_update()).scalar_one()
    safe_details = {key:value for key,value in (details or {}).items() if key in {'role','active','method','eligibility','enabled','outcome','observations','stopped','event_id'}}
    if details and details.get('note'):
        safe_details['note_hash'] = digest(details['note'])
    if head.sequence>=settings().max_audit_events:
        raise HTTPException(503,'Private audit storage is at capacity; contact the host owner')
    record = {'actor': actor, 'action': action, 'resource': str(resource), 'result': result,
              'timestamp': time.time(), 'request_id': getattr(request.state, 'request_id', None) if request else None,
              'source_ip': client_ip(request) if request else 'local-operator', 'details': safe_details}
    sequence = head.sequence + 1
    hashed = digest(head.digest + canonical({'sequence': sequence, 'record': record}))
    db.add(AuditEvent(sequence=sequence, previous=head.digest, digest=hashed, record=record, timestamp=record['timestamp']))
    head.sequence, head.digest = sequence, hashed
    db.flush()

def verify_audit(events,head=None):
    previous, sequence = '0' * 64, 0
    for item in events:
        sequence += 1
        if item.sequence != sequence or item.previous != previous:
            return False
        if item.digest != digest(previous + canonical({'sequence': sequence, 'record': item.record})):
            return False
        previous = item.digest
    return head is None or (head.sequence==sequence and head.digest==previous)

@dataclass
class StaffContext:
    staff: Staff
    session: StaffSession


def authenticate(request: Request, db=Depends(database)):
    raw = request.cookies.get(COOKIE, '')
    if len(raw) != 43:
        raise HTTPException(401, 'Passkey authentication required')
    session = db.get(StaffSession, digest(raw))
    staff = db.get(Staff, session.staff_id) if session else None
    credential = db.get(Credential, session.credential_id) if session else None
    now, cfg = time.time(), settings()
    if (not session or session.revoked or not staff or not staff.active or not credential or credential.revoked
            or session.staff_version != staff.version or now-session.last_seen >= cfg.session_idle_seconds
            or now-session.created >= cfg.session_absolute_seconds):
        raise HTTPException(401, 'Session expired or revoked')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        csrf = request.headers.get('x-csrf-token', '')
        if not secrets.compare_digest(csrf, digest('csrf:' + raw)):
            raise HTTPException(403, 'Invalid request verification')
        budget(db, 'mutation-ip', client_ip(request), 90)
        budget(db, 'mutation-staff', staff.id, 60)
    session.last_seen = now
    db.commit()
    return StaffContext(staff, session)


def require(permission, recent=False):
    def check(context=Depends(authenticate)):
        if permission not in PERMISSIONS.get(context.staff.role, set()):
            raise HTTPException(403, 'Staff permission denied')
        if recent and time.time() - context.session.verified > settings().recent_seconds:
            raise HTTPException(403, 'Reauthenticate with your passkey to continue')
        return context
    return check


def issue_session(db, staff, credential, response, old=None):
    now, cfg = time.time(), settings()
    if old:
        old.revoked = True
    raw = secrets.token_urlsafe(32)
    db.add(StaffSession(digest=digest(raw), staff_id=staff.id, staff_version=staff.version,
                        credential_id=credential.id, created=now, last_seen=now, verified=now))
    response.set_cookie(COOKIE, raw, max_age=cfg.session_absolute_seconds, path='/',
                        secure=True, httponly=True, samesite='strict')
    return raw
