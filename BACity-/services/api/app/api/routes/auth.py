import hashlib
import json
import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Request, Form
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from cryptography.fernet import Fernet, InvalidToken
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.config import get_settings
from app.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.models.oauth_identity import OAuthIdentity
from app.schemas.auth import UserRegister, UserLogin, UserOut, Token, validate_new_password
from app.api.deps import get_current_user, get_optional_user
from app.core.community import rate_limit, audit
from app.core.mail import action_status, queue_action, consume_action, dispatch_pending_mail
from app.models.community import ActionToken

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()
_DUMMY_PASSWORD_HASH = hash_password("BACity timing equalization password")


def _schedule_mail_delivery(background_tasks: BackgroundTasks, db: Session) -> None:
    background_tasks.add_task(dispatch_pending_mail, db.get_bind())


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, request: Request, background_tasks: BackgroundTasks,
             db: Session = Depends(get_db)):
    rate_limit(db, "register:" + request.client.host, 20)
    payload.email = payload.email.lower()
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        display_name=payload.display_name,
        interests=[],
    )
    db.add(user)
    db.flush()
    queue_action(db, user, "verify")
    db.commit()
    db.refresh(user)
    _schedule_mail_delivery(background_tasks, db)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    payload.email = payload.email.lower()
    rate_limit(db, "login-ip:" + request.client.host, 60, 900)
    rate_limit(db, "login-email:" + payload.email, 15, 900)
    user = db.query(User).filter(User.email == payload.email).first()
    valid_password = verify_password(payload.password, user.hashed_password if user and user.active else _DUMMY_PASSWORD_HASH)
    if not user or not user.active or not valid_password:
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    token = create_access_token(subject=user.email, version=user.token_version)
    return Token(access_token=token)


@router.post("/logout")
def logout(user=Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1
    db.commit()
    return {"detail": "Logged out"}


class EmailInput(BaseModel):
    email: EmailStr


class ActionInput(BaseModel):
    token: str = Field(min_length=20, max_length=2000)


class ResetInput(ActionInput):
    password: str = Field(min_length=8)

    @field_validator('password')
    @classmethod
    def password_security(cls, value):
        return validate_new_password(value)


class OAuthExchange(BaseModel):
    code: str = Field(min_length=20, max_length=4000)


class NativeOAuthInput(BaseModel):
    provider: str = Field(pattern="^(google|apple)$")
    identity_token: str = Field(min_length=20, max_length=10000)
    authorization_code: str | None = Field(default=None, min_length=5, max_length=4000)
    display_name: str | None = Field(default=None, max_length=200)


@router.post("/request-reset")
def request_reset(payload: EmailInput, request: Request, background_tasks: BackgroundTasks,
                  db: Session = Depends(get_db)):
    normalized_email = payload.email.lower()
    rate_limit(db, "reset:" + request.client.host, 10)
    rate_limit(db, "reset-email:" + normalized_email, 3)
    user = db.query(User).filter_by(email=normalized_email, active=True).first()
    if user:
        queue_action(db, user, "reset")
        db.commit()
    # Schedule this for both outcomes so transport work cannot reveal whether
    # the supplied address belongs to an account.
    _schedule_mail_delivery(background_tasks, db)
    return {"detail": "If the account exists, a reset email has been queued"}


@router.post("/request-verification")
def request_verification(background_tasks: BackgroundTasks, user=Depends(get_current_user),
                         db: Session = Depends(get_db)):
    rate_limit(db, "verify:" + str(user.id), 3)
    if not user.email_verified:
        queue_action(db, user, "verify")
        db.commit()
    _schedule_mail_delivery(background_tasks, db)
    return {"detail": "Verification email queued if needed"}


@router.post("/verify-email")
def verify_email(payload: ActionInput, db: Session = Depends(get_db)):
    user = db.get(User, consume_action(db, payload.token, "verify"))
    if not user.active:
        raise HTTPException(400, "Account unavailable")
    user.email_verified = True
    db.commit()
    return {"detail": "Email verified"}


@router.post("/reset-password")
def reset_password(payload: ResetInput, request: Request, db: Session = Depends(get_db)):
    token_ref = hashlib.sha256(payload.token.encode()).hexdigest()
    rate_limit(db, "reset-attempt:" + request.client.host, 20, 900)
    rate_limit(db, "reset-token:" + token_ref, 5, 900)
    user = db.get(User, consume_action(db, payload.token, "reset"))
    if not user.active:
        raise HTTPException(400, "Account unavailable")
    user.hashed_password = hash_password(payload.password)
    user.token_version += 1
    audit(db, user, "password_reset", "user", user.id)
    db.commit()
    return {"detail": "Password changed; sign in again"}


@router.post("/reset-password/status")
def reset_password_status(payload: ActionInput, request: Request, db: Session = Depends(get_db)):
    token_ref = hashlib.sha256(payload.token.encode()).hexdigest()
    rate_limit(db, "reset-status:" + request.client.host, 30, 900)
    rate_limit(db, "reset-status-token:" + token_ref, 10, 900)
    return {"status": action_status(db, payload.token, "reset")}


# ---- Google / Apple OAuth -------------------------------------------------

def _provider_configured(provider: str) -> bool:
    if provider == "google":
        return settings.google_oauth_configured
    if provider == "apple":
        return settings.apple_oauth_configured
    return False


def _callback_url(provider: str) -> str:
    return settings.oauth_callback_base_url.rstrip("/") + f"/auth/oauth/{provider}/callback"


def _signed(payload: dict, ttl_seconds: int) -> str:
    now = int(time.time())
    return jwt.encode(
        {**payload, "iat": now, "exp": now + ttl_seconds},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def _decoded(token: str, purpose: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(400, "OAuth session expired or invalid") from exc
    if payload.get("typ") != purpose:
        raise HTTPException(400, "OAuth session invalid")
    return payload


def _app_redirect(code: str | None = None, error: str | None = None):
    base = settings.oauth_app_redirect_uri
    if code:
        return RedirectResponse(base + "?code=" + quote(code, safe=""), status_code=303)
    return RedirectResponse(base + "?error=" + quote(error or "Sign in failed", safe=""), status_code=303)


def _credential_cipher() -> Fernet:
    if not settings.oauth_token_encryption_key:
        raise HTTPException(503, "Provider credential encryption is not configured")
    try:
        return Fernet(settings.oauth_token_encryption_key.encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(503, "Provider credential encryption is invalid") from exc


def _encrypt_provider_token(value: str | None, client_id: str | None = None) -> str | None:
    if not value:
        return None
    credential = json.dumps({"token": value, "client_id": client_id}, separators=(",", ":"))
    return _credential_cipher().encrypt(credential.encode()).decode()


def decrypt_provider_token(value: str) -> dict:
    try:
        decrypted = _credential_cipher().decrypt(value.encode()).decode()
        credential = json.loads(decrypted)
        if not isinstance(credential, dict) or not isinstance(credential.get("token"), str):
            raise ValueError
        return credential
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(503, "Stored provider credential could not be decrypted") from exc


def revoke_apple_token(value: str, fallback_client_id: str) -> bool:
    try:
        credential = decrypt_provider_token(value)
        client_id = credential.get("client_id") or fallback_client_id
        response = httpx.post("https://appleid.apple.com/auth/revoke", data={
            "client_id": client_id,
            "client_secret": _apple_client_secret(client_id),
            "token": credential["token"],
            "token_type_hint": "refresh_token",
        }, timeout=10.0)
        return response.status_code == 200
    except (httpx.HTTPError, HTTPException):
        return False


def _find_or_create_social_user(
    db: Session,
    provider: str,
    subject: str,
    email: str | None,
    display_name: str | None = None,
    avatar_url: str | None = None,
    linking_user: User | None = None,
    provider_refresh_token: str | None = None,
    provider_client_id: str | None = None,
) -> User:
    identity = (
        db.query(OAuthIdentity)
        .filter_by(provider=provider, subject=subject)
        .first()
    )
    if identity:
        user = db.get(User, identity.user_id)
        if not user or not user.active:
            raise HTTPException(403, "Account unavailable")
        if linking_user and user.id != linking_user.id:
            raise HTTPException(409, "This provider identity is already linked to another account")
        if provider_refresh_token:
            identity.refresh_token_encrypted = _encrypt_provider_token(provider_refresh_token, provider_client_id)
            db.commit()
        return user

    if not email:
        raise HTTPException(400, "The identity provider did not return an email address")

    normalized_email = email.strip().lower()
    email_owner = db.query(User).filter(User.email == normalized_email).first()
    user = linking_user or email_owner
    if linking_user and email_owner and email_owner.id != linking_user.id:
        raise HTTPException(409, "That verified provider email belongs to another BACity account")
    if user and not user.active:
        raise HTTPException(403, "Account unavailable")

    if not user:
        user = User(
            email=normalized_email,
            hashed_password=hash_password(secrets.token_urlsafe(48)),
            display_name=display_name,
            interests=[],
            email_verified=True,
            avatar_url=avatar_url,
        )
        db.add(user)
        db.flush()
    else:
        # A verified provider may safely verify ownership of the matching email.
        user.email_verified = True
        if not user.display_name and display_name:
            user.display_name = display_name
        if not user.avatar_url and avatar_url:
            user.avatar_url = avatar_url

    identity = OAuthIdentity(user_id=user.id, provider=provider, subject=subject,
                             refresh_token_encrypted=_encrypt_provider_token(provider_refresh_token, provider_client_id))
    db.add(identity)
    audit(db, user, "oauth_linked", "user", user.id, {"provider": provider})
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This provider is already linked") from exc
    db.refresh(user)
    return user


def _exchange_code_for_user(db: Session, user: User) -> str:
    now = datetime.utcnow()
    db.query(ActionToken).filter_by(user_id=user.id, purpose="oauth_exchange", used_at=None).update({"used_at": now})
    code = secrets.token_urlsafe(32)
    db.add(ActionToken(user_id=user.id, token_hash=hashlib.sha256(code.encode()).hexdigest(),
                       purpose="oauth_exchange", expires_at=now + timedelta(seconds=90)))
    db.commit()
    return code


@router.get("/oauth/status")
def oauth_status():
    return {
        "google": settings.google_oauth_configured,
        "google_native": settings.google_native_configured,
        "apple": settings.apple_oauth_configured,
        "apple_native": settings.apple_native_configured,
    }


@router.get("/oauth/{provider}/start")
def oauth_start(provider: str, request: Request, db: Session = Depends(get_db)):
    if provider not in {"google", "apple"}:
        raise HTTPException(404, "Unknown identity provider")
    if not _provider_configured(provider):
        raise HTTPException(503, f"{provider.title()} sign in is not configured")

    rate_limit(db, f"oauth-start:{request.client.host}", 40, 900)
    state = _signed({"typ": "oauth_state", "provider": provider}, 600)

    if provider == "google":
        query = urlencode(
            {
                "client_id": settings.google_oauth_client_id,
                "redirect_uri": _callback_url("google"),
                "response_type": "code",
                "scope": "openid email profile",
                "state": state,
                "prompt": "select_account",
            }
        )
        return RedirectResponse("https://accounts.google.com/o/oauth2/v2/auth?" + query)

    query = urlencode(
        {
            "client_id": settings.apple_oauth_client_id,
            "redirect_uri": _callback_url("apple"),
            "response_type": "code",
            "response_mode": "form_post",
            "scope": "name email",
            "state": state,
        }
    )
    return RedirectResponse("https://appleid.apple.com/auth/authorize?" + query)


@router.post("/oauth/exchange", response_model=Token)
def oauth_exchange(payload: OAuthExchange, request: Request, db: Session = Depends(get_db)):
    rate_limit(db, f"oauth-exchange:{request.client.host}", 40, 900)
    user_id = consume_action(db, payload.code, "oauth_exchange")
    user = db.get(User, user_id)
    if not user or not user.active:
        raise HTTPException(401, "OAuth session no longer valid")
    token = Token(access_token=create_access_token(user.email, version=user.token_version))
    db.commit()
    return token


def _google_identity(code: str) -> tuple[str, str, str | None, str | None]:
    with httpx.Client(timeout=10.0) as client:
        token_response = client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": settings.google_oauth_client_id,
                "client_secret": settings.google_oauth_client_secret,
                "redirect_uri": _callback_url("google"),
                "grant_type": "authorization_code",
            },
        )
        if token_response.status_code >= 400:
            raise HTTPException(400, "Google rejected the authorization code")
        id_token = token_response.json().get("id_token")
        if not id_token:
            raise HTTPException(400, "Google did not return an identity token")

        profile_response = client.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={"id_token": id_token},
        )
        if profile_response.status_code >= 400:
            raise HTTPException(400, "Google identity token could not be verified")
        profile = profile_response.json()

    if profile.get("aud") != settings.google_oauth_client_id:
        raise HTTPException(400, "Google identity token audience mismatch")
    if str(profile.get("email_verified", "")).lower() != "true":
        raise HTTPException(400, "Google email is not verified")

    return (
        str(profile["sub"]),
        str(profile["email"]),
        profile.get("name"),
        profile.get("picture"),
    )


def _google_native_identity(id_token: str) -> tuple[str, str, str | None, str | None]:
    try:
        response = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": id_token}, timeout=10.0)
        response.raise_for_status()
        profile = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(400, "Google identity token could not be verified") from exc
    allowed = {value for value in (settings.google_oauth_client_id, settings.google_android_client_id,
                                   settings.google_ios_client_id) if value}
    if profile.get("aud") not in allowed or str(profile.get("email_verified", "")).lower() != "true":
        raise HTTPException(400, "Google identity token claims are invalid")
    return str(profile["sub"]), str(profile["email"]), profile.get("name"), profile.get("picture")


def _apple_client_secret(client_id: str | None = None) -> str:
    now = int(time.time())
    private_key = settings.apple_private_key.replace("\\n", "\n")
    return jwt.encode(
        {
            "iss": settings.apple_team_id,
            "iat": now,
            "exp": now + 300,
            "aud": "https://appleid.apple.com",
            "sub": client_id or settings.apple_oauth_client_id,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


def _apple_token_exchange(code: str, client_id: str, redirect_uri: str | None = None) -> dict:
    data = {
        "client_id": client_id,
        "client_secret": _apple_client_secret(client_id),
        "code": code,
        "grant_type": "authorization_code",
    }
    if redirect_uri:
        data["redirect_uri"] = redirect_uri
    try:
        with httpx.Client(timeout=10.0) as client:
            token_response = client.post("https://appleid.apple.com/auth/token", data=data)
            if token_response.status_code >= 400:
                raise HTTPException(400, "Apple rejected the authorization code")
            return token_response.json()
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "Apple sign in is temporarily unavailable") from exc


def _apple_token_claims(id_token: str, client_id: str) -> dict:
    try:
        header = jwt.get_unverified_header(id_token)
        with httpx.Client(timeout=10.0) as client:
            keys_response = client.get("https://appleid.apple.com/auth/keys")
            keys_response.raise_for_status()
            key = next(
                (item for item in keys_response.json().get("keys", []) if item.get("kid") == header.get("kid")),
                None,
            )
    except (httpx.HTTPError, ValueError, JWTError) as exc:
        raise HTTPException(502, "Apple sign in is temporarily unavailable") from exc
    if not key:
        raise HTTPException(400, "Apple signing key could not be found")

    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=client_id,
            issuer="https://appleid.apple.com",
        )
    except JWTError as exc:
        raise HTTPException(400, "Apple identity token could not be verified") from exc

    return claims


def _apple_identity(code: str) -> tuple[str, str | None, str | None]:
    tokens = _apple_token_exchange(code, settings.apple_oauth_client_id, _callback_url("apple"))
    id_token = tokens.get("id_token")
    if not id_token:
        raise HTTPException(400, "Apple did not return an identity token")
    claims = _apple_token_claims(id_token, settings.apple_oauth_client_id)
    return str(claims["sub"]), claims.get("email"), tokens.get("refresh_token")


@router.get("/oauth/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    try:
        claims = _decoded(state, "oauth_state")
        if claims.get("provider") != "google":
            raise HTTPException(400, "OAuth provider mismatch")
        subject, email, name, picture = _google_identity(code)
        user = _find_or_create_social_user(db, "google", subject, email, name, picture)
        return _app_redirect(code=_exchange_code_for_user(db, user))
    except HTTPException as exc:
        return _app_redirect(error=str(exc.detail))
    except Exception:
        return _app_redirect(error="Google sign in could not be completed")


@router.post("/oauth/apple/callback")
def apple_callback(
    code: str = Form(...),
    state: str = Form(...),
    user: str | None = Form(None),
    db: Session = Depends(get_db),
):
    try:
        claims = _decoded(state, "oauth_state")
        if claims.get("provider") != "apple":
            raise HTTPException(400, "OAuth provider mismatch")

        subject, email, refresh_token = _apple_identity(code)
        display_name = None
        if user:
            try:
                supplied = json.loads(user)
                name = supplied.get("name") or {}
                display_name = " ".join(
                    part for part in [name.get("firstName"), name.get("lastName")] if part
                ) or None
                email = email or supplied.get("email")
            except (ValueError, TypeError):
                pass

        account = _find_or_create_social_user(db, "apple", subject, email, display_name,
                                              provider_refresh_token=refresh_token,
                                              provider_client_id=settings.apple_oauth_client_id)
        return _app_redirect(code=_exchange_code_for_user(db, account))
    except HTTPException as exc:
        return _app_redirect(error=str(exc.detail))
    except Exception:
        return _app_redirect(error="Apple sign in could not be completed")


def _mark_native_token_used(db: Session, user: User, identity_token: str):
    digest = hashlib.sha256(("native:" + identity_token).encode()).hexdigest()
    if db.query(ActionToken).filter_by(token_hash=digest).first():
        raise HTTPException(409, "This provider response was already used")
    db.add(ActionToken(user_id=user.id, token_hash=digest, purpose="oauth_native_replay",
                       expires_at=datetime.utcnow() + timedelta(hours=1), used_at=datetime.utcnow()))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "This provider response was already used") from exc


@router.post("/oauth/native", response_model=Token)
def native_oauth(payload: NativeOAuthInput, request: Request, current_user=Depends(get_optional_user),
                 db: Session = Depends(get_db)):
    """Accept provider-issued native credentials; BACity still owns the session."""
    rate_limit(db, f"oauth-native:{request.client.host}", 40, 900)
    if payload.provider == "google":
        if not settings.google_native_configured:
            raise HTTPException(503, "Google native sign in is not configured")
        subject, email, name, avatar = _google_native_identity(payload.identity_token)
        refresh_token = None
    else:
        if not settings.apple_native_configured:
            raise HTTPException(503, "Apple native sign in is not configured")
        if not payload.authorization_code:
            raise HTTPException(400, "Apple authorization code is required")
        submitted = _apple_token_claims(payload.identity_token, settings.apple_ios_client_id)
        tokens = _apple_token_exchange(payload.authorization_code, settings.apple_ios_client_id)
        server_token = tokens.get("id_token")
        if not server_token:
            raise HTTPException(400, "Apple did not return an identity token")
        verified = _apple_token_claims(server_token, settings.apple_ios_client_id)
        if submitted.get("sub") != verified.get("sub"):
            raise HTTPException(400, "Apple credentials do not identify the same account")
        subject, email = str(verified["sub"]), verified.get("email") or submitted.get("email")
        name, avatar, refresh_token = payload.display_name, None, tokens.get("refresh_token")

    user = _find_or_create_social_user(db, payload.provider, subject, email, name, avatar,
                                       linking_user=current_user, provider_refresh_token=refresh_token,
                                       provider_client_id=settings.apple_ios_client_id if payload.provider == "apple" else None)
    _mark_native_token_used(db, user, payload.identity_token)
    return Token(access_token=create_access_token(user.email, version=user.token_version))
