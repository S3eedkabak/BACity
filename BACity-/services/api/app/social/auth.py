"""Passkey-only authentication using py_webauthn. No consumer JWT fallback."""
import json
import secrets
import time
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from webauthn import (generate_registration_options, generate_authentication_options,
                      verify_registration_response, verify_authentication_response, options_to_json)
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria, UserVerificationRequirement,
                                     ResidentKeyRequirement, PublicKeyCredentialDescriptor)
from .config import settings
from .db import database
from .models import Staff, Credential, Invitation, Challenge, StaffSession
from .security import (COOKIE, CEREMONY, digest, encoded, decoded, audit, budget, client_ip,
                       authenticate, issue_session, require)

router = APIRouter(prefix='/api/auth')

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid')

class Enrollment(Input):
    invitation: str = Field('', max_length=100)

class Assertion(Input):
    credential: dict
    label: str = Field('Passkey', min_length=1, max_length=80)


def validate_client_context(credential):
    data=json.loads(decoded(credential['response']['clientDataJSON']))
    if data.get('crossOrigin') or data.get('topOrigin',settings().admin_origin)!=settings().admin_origin:
        raise ValueError('Cross-origin WebAuthn is not allowed')


def challenge(db, response, purpose, *, staff_id=None, invite=None, session=None, options):
    raw = secrets.token_urlsafe(32)
    db.add(Challenge(digest=digest(raw), purpose=purpose, challenge=encoded(options.challenge),
                     staff_id=staff_id, invitation_digest=invite, session_digest=session, expires=time.time()+120))
    response.set_cookie(CEREMONY, raw, max_age=120, secure=True, httponly=True, samesite='strict', path='/')
    db.commit()
    return json.loads(options_to_json(options))


def consume(request, db, purposes):
    raw = request.cookies.get(CEREMONY, '')
    row = db.execute(select(Challenge).where(Challenge.digest == digest(raw)).with_for_update()).scalar_one_or_none()
    if not row or row.consumed or row.expires <= time.time() or row.purpose not in purposes:
        audit(db,None,'passkey.challenge_rejected',result='denied',request=request); db.commit()
        raise HTTPException(400, 'Expired or already used passkey challenge')
    # Consume before verification; failed ceremonies cannot be replayed either.
    changed = db.execute(update(Challenge).where(Challenge.digest == row.digest, Challenge.consumed.is_(False))
                         .values(consumed=True)).rowcount
    db.commit()
    if changed != 1:
        raise HTTPException(400, 'Passkey challenge already used')
    return row


@router.post('/register/options')
def registration_options(payload: Enrollment, request: Request, response: Response, db=Depends(database)):
    budget(db, 'enrollment-ip', client_ip(request), 10, 600)
    invite, current = None, None
    if payload.invitation:
        invite = db.get(Invitation, digest(payload.invitation))
        if not invite or invite.consumed or invite.expires <= time.time():
            audit(db, None, 'passkey.enrollment', result='denied', request=request); db.commit()
            raise HTTPException(400, 'Invitation unavailable or expired')
        staff = db.get(Staff, invite.staff_id)
    else:
        current = authenticate(request, db)
        staff = current.staff
        if time.time()-current.session.verified > settings().recent_seconds:
            raise HTTPException(403, 'Recent passkey authentication required')
    if not staff or not staff.active:
        raise HTTPException(403, 'Staff access unavailable')
    credentials = db.query(Credential).filter_by(staff_id=staff.id, revoked=False).all()
    if len(credentials) >= 8:
        raise HTTPException(409, 'Authenticator limit reached')
    # Recovery invitations cannot add a credential to a still-enrolled account.
    if invite and credentials:
        raise HTTPException(409, 'Use an existing passkey or owner-assisted recovery')
    options = generate_registration_options(rp_id=settings().rp_id, rp_name='BACity staff',
        user_id=staff.id.encode(), user_name=staff.email, user_display_name=staff.name,
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.REQUIRED,
            require_resident_key=True, user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=decoded(c.id)) for c in credentials])
    return challenge(db, response, 'register', staff_id=staff.id,
                     invite=invite.digest if invite else None,
                     session=current.session.digest if current else None, options=options)


@router.post('/register/verify')
def registration_verify(payload: Assertion, request: Request, response: Response, db=Depends(database)):
    budget(db, 'register-verify', client_ip(request), 15, 600)
    row = consume(request, db, {'register'})
    staff = db.execute(select(Staff).where(Staff.id == row.staff_id).with_for_update()).scalar_one()
    if not staff.active:
        raise HTTPException(403, 'Staff access unavailable')
    invite = db.get(Invitation, row.invitation_digest) if row.invitation_digest else None
    current = None
    if invite:
        if invite.consumed or invite.expires <= time.time() or db.query(Credential).filter_by(staff_id=staff.id, revoked=False).count():
            raise HTTPException(400, 'Invitation unavailable')
    else:
        current = authenticate(request, db)
        if current.staff.id != staff.id or current.session.digest != row.session_digest or time.time()-current.session.verified > settings().recent_seconds:
            raise HTTPException(403, 'Enrollment session changed or expired')
    try:
        validate_client_context(payload.credential)
        verified = verify_registration_response(credential=payload.credential,
            expected_challenge=decoded(row.challenge), expected_rp_id=settings().rp_id,
            expected_origin=settings().admin_origin, require_user_presence=True, require_user_verification=True)
    except Exception:
        audit(db, staff.id, 'passkey.enrollment', result='denied', request=request); db.commit()
        raise HTTPException(400, 'Passkey verification failed') from None
    credential = Credential(id=encoded(verified.credential_id), staff_id=staff.id,
        public_key=encoded(verified.credential_public_key), sign_count=verified.sign_count, label=payload.label)
    db.add(credential); db.flush()
    if invite:
        invite.consumed = True
    raw = issue_session(db, staff, credential, response, current.session if current else None)
    audit(db, staff.id, 'passkey.enrolled', staff.id, request=request); db.commit()
    response.delete_cookie(CEREMONY, path='/', secure=True, httponly=True, samesite='strict')
    return {'authenticated': True, 'csrf': digest('csrf:' + raw)}


@router.post('/login/options')
def login_options(request: Request, response: Response, db=Depends(database)):
    budget(db, 'login-ip', client_ip(request), 20, 300)
    options = generate_authentication_options(rp_id=settings().rp_id,
        user_verification=UserVerificationRequirement.REQUIRED)
    return challenge(db, response, 'login', options=options)


@router.post('/reauth/options')
def reauth_options(request: Request, response: Response, current=Depends(authenticate), db=Depends(database)):
    budget(db, 'reauth', current.staff.id, 10, 300)
    credentials = db.query(Credential).filter_by(staff_id=current.staff.id, revoked=False).all()
    options = generate_authentication_options(rp_id=settings().rp_id,
        allow_credentials=[PublicKeyCredentialDescriptor(id=decoded(c.id)) for c in credentials],
        user_verification=UserVerificationRequirement.REQUIRED)
    return challenge(db, response, 'reauth', staff_id=current.staff.id, session=current.session.digest, options=options)


@router.post('/login/verify')
def login_verify(payload: Assertion, request: Request, response: Response, db=Depends(database)):
    budget(db, 'login-verify', client_ip(request), 20, 300)
    row = consume(request, db, {'login', 'reauth'})
    credential = db.execute(select(Credential).where(Credential.id == str(payload.credential.get('id', ''))[:1400]).with_for_update()).scalar_one_or_none()
    staff = db.get(Staff, credential.staff_id) if credential else None
    old = None
    if row.purpose == 'reauth':
        current = authenticate(request, db)
        if row.staff_id != current.staff.id or row.session_digest != current.session.digest:
            raise HTTPException(403, 'Reauthentication session changed')
        old = current.session
    elif request.cookies.get(COOKIE):
        old = db.get(StaffSession, digest(request.cookies[COOKIE]))
    try:
        if not credential or credential.revoked or not staff or not staff.active:
            raise ValueError('Unavailable credential')
        if row.staff_id and row.staff_id != staff.id:
            raise ValueError('Wrong staff identity')
        handle = (payload.credential.get('response') or {}).get('userHandle')
        if handle and decoded(handle) != staff.id.encode():
            raise ValueError('Wrong user handle')
        validate_client_context(payload.credential)
        verified = verify_authentication_response(credential=payload.credential,
            expected_challenge=decoded(row.challenge), expected_rp_id=settings().rp_id,
            expected_origin=settings().admin_origin, credential_public_key=decoded(credential.public_key),
            credential_current_sign_count=credential.sign_count, require_user_verification=True)
    except Exception:
        audit(db, staff.id if staff else None, 'staff.login', result='denied', request=request); db.commit()
        raise HTTPException(400, 'Passkey verification failed') from None
    credential.sign_count = verified.new_sign_count
    raw = issue_session(db, staff, credential, response, old)
    audit(db, staff.id, 'staff.reauthenticated' if row.purpose == 'reauth' else 'staff.login', staff.id, request=request)
    db.commit()
    response.delete_cookie(CEREMONY, path='/', secure=True, httponly=True, samesite='strict')
    return {'authenticated': True, 'csrf': digest('csrf:' + raw)}


@router.get('/session')
def session_info(request: Request, current=Depends(authenticate)):
    return {'id': current.staff.id, 'name': current.staff.name, 'role': current.staff.role,
            'csrf': digest('csrf:' + request.cookies[COOKIE]),
            'recent': time.time()-current.session.verified < settings().recent_seconds}


@router.post('/logout')
def logout(request: Request, response: Response, current=Depends(authenticate), db=Depends(database)):
    current.session.revoked = True
    audit(db, current.staff.id, 'session.logout', request=request); db.commit()
    response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='strict')
    return {'ok': True}


@router.post('/logout-all')
def logout_all(request: Request, response: Response, current=Depends(authenticate), db=Depends(database)):
    db.query(StaffSession).filter_by(staff_id=current.staff.id).update({'revoked': True})
    audit(db, current.staff.id, 'session.revoke_all', current.staff.id, request=request); db.commit()
    response.delete_cookie(COOKIE, path='/', secure=True, httponly=True, samesite='strict')
    return {'ok': True}


@router.get('/credentials')
def credentials(current=Depends(authenticate), db=Depends(database)):
    return [{'id': c.id, 'label': c.label, 'created': c.created} for c in
            db.query(Credential).filter_by(staff_id=current.staff.id, revoked=False).all()]


@router.delete('/credentials/{credential_id}')
def revoke_credential(credential_id: str, request: Request, current=Depends(require('read', recent=True)), db=Depends(database)):
    credentials = db.query(Credential).filter_by(staff_id=current.staff.id, revoked=False).with_for_update().all()
    target = next((c for c in credentials if c.id == credential_id), None)
    if not target:
        raise HTTPException(404, 'Authenticator not found')
    if len(credentials) < 2:
        raise HTTPException(409, 'Register a backup authenticator first')
    target.revoked = True
    db.query(StaffSession).filter_by(credential_id=target.id).update({'revoked': True})
    audit(db, current.staff.id, 'passkey.revoked', current.staff.id, request=request); db.commit()
    return {'ok': True}
