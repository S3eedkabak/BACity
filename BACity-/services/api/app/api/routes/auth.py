import json
import secrets
import time
from urllib.parse import urlencode, quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form
from fastapi.responses import RedirectResponse
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.models.oauth_identity import OAuthIdentity
from app.schemas.auth import UserRegister, UserLogin, UserOut, Token
from app.api.deps import get_current_user
from app.core.community import rate_limit, audit
from app.core.mail import queue_action, consume_action

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
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
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    payload.email = payload.email.lower()
    rate_limit(db, "login-ip:" + request.client.host, 60, 900)
    rate_limit(db, "login-email:" + payload.email, 15, 900)
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not user.active or not verify_password(payload.password, user.hashed_password):
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
    password: str = Field(min_length=8, max_length=72)


class OAuthExchange(BaseModel):
    code: str = Field(min_length=20, max_length=4000)


@router.post("/request-reset")
def request_reset(payload: EmailInput, request: Request, db: Session = Depends(get_db)):
    rate_limit(db, "reset:" + request.client.host, 10)
    user = db.query(User).filter_by(email=payload.email.lower(), active=True).first()
    if user:
        queue_action(db, user, "reset")
        db.commit()
    return {"detail": "If the account exists, a reset email has been queued"}


@router.post("/request-verification")
def request_verification(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rate_limit(db, "verify:" + str(user.id), 3)
    if not user.email_verified:
        queue_action(db, user, "verify")
        db.commit()
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
def reset_password(payload: ResetInput, db: Session = Depends(get_db)):
    if len(payload.password.encode()) > 72:
        raise HTTPException(422, "Password exceeds 72 UTF-8 bytes")
    user = db.get(User, consume_action(db, payload.token, "reset"))
    if not user.active:
        raise HTTPException(400, "Account unavailable")
    user.hashed_password = hash_password(payload.password)
    user.token_version += 1
    audit(db, user, "password_reset", "user", user.id)
    db.commit()
    return {"detail": "Password changed; sign in again"}


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


def _find_or_create_social_user(
    db: Session,
    provider: str,
    subject: str,
    email: str | None,
    display_name: str | None = None,
    avatar_url: str | None = None,
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
        return user

    if not email:
        raise HTTPException(400, "The identity provider did not return an email address")

    normalized_email = email.strip().lower()
    user = db.query(User).filter(User.email == normalized_email).first()
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

    db.add(OAuthIdentity(user_id=user.id, provider=provider, subject=subject))
    audit(db, user, "oauth_linked", "user", user.id, {"provider": provider})
    db.commit()
    db.refresh(user)
    return user


def _exchange_code_for_user(user: User) -> str:
    return _signed(
        {
            "typ": "oauth_exchange",
            "sub": user.email,
            "ver": user.token_version,
            "nonce": secrets.token_urlsafe(12),
        },
        90,
    )


@router.get("/oauth/status")
def oauth_status():
    return {
        "google": settings.google_oauth_configured,
        "apple": settings.apple_oauth_configured,
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
    claims = _decoded(payload.code, "oauth_exchange")
    user = db.query(User).filter_by(email=claims.get("sub"), active=True).first()
    if not user or claims.get("ver") != user.token_version:
        raise HTTPException(401, "OAuth session no longer valid")
    return Token(access_token=create_access_token(user.email, version=user.token_version))


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


def _apple_client_secret() -> str:
    now = int(time.time())
    private_key = settings.apple_private_key.replace("\\n", "\n")
    return jwt.encode(
        {
            "iss": settings.apple_team_id,
            "iat": now,
            "exp": now + 300,
            "aud": "https://appleid.apple.com",
            "sub": settings.apple_oauth_client_id,
        },
        private_key,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


def _apple_identity(code: str) -> tuple[str, str | None]:
    with httpx.Client(timeout=10.0) as client:
        token_response = client.post(
            "https://appleid.apple.com/auth/token",
            data={
                "client_id": settings.apple_oauth_client_id,
                "client_secret": _apple_client_secret(),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": _callback_url("apple"),
            },
        )
        if token_response.status_code >= 400:
            raise HTTPException(400, "Apple rejected the authorization code")
        id_token = token_response.json().get("id_token")
        if not id_token:
            raise HTTPException(400, "Apple did not return an identity token")

        header = jwt.get_unverified_header(id_token)
        keys_response = client.get("https://appleid.apple.com/auth/keys")
        keys_response.raise_for_status()
        key = next(
            (item for item in keys_response.json().get("keys", []) if item.get("kid") == header.get("kid")),
            None,
        )
        if not key:
            raise HTTPException(400, "Apple signing key could not be found")

    try:
        claims = jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=settings.apple_oauth_client_id,
            issuer="https://appleid.apple.com",
        )
    except JWTError as exc:
        raise HTTPException(400, "Apple identity token could not be verified") from exc

    return str(claims["sub"]), claims.get("email")


@router.get("/oauth/google/callback")
def google_callback(code: str, state: str, db: Session = Depends(get_db)):
    try:
        claims = _decoded(state, "oauth_state")
        if claims.get("provider") != "google":
            raise HTTPException(400, "OAuth provider mismatch")
        subject, email, name, picture = _google_identity(code)
        user = _find_or_create_social_user(db, "google", subject, email, name, picture)
        return _app_redirect(code=_exchange_code_for_user(user))
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

        subject, email = _apple_identity(code)
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

        account = _find_or_create_social_user(db, "apple", subject, email, display_name)
        return _app_redirect(code=_exchange_code_for_user(account))
    except HTTPException as exc:
        return _app_redirect(error=str(exc.detail))
    except Exception:
        return _app_redirect(error="Apple sign in could not be completed")
