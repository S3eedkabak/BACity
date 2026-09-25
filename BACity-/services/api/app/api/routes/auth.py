from fastapi import APIRouter, Depends, HTTPException, status, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import hash_password, verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import UserRegister, UserLogin, UserOut, Token
from app.api.deps import get_current_user
from app.core.community import rate_limit, audit
from app.core.mail import queue_action, consume_action

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    rate_limit(db, 'register:' + request.client.host, 20)
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
    queue_action(db, user, 'verify')
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    payload.email = payload.email.lower()
    rate_limit(db, 'login-ip:' + request.client.host, 60, 900)
    rate_limit(db, 'login-email:' + payload.email, 15, 900)
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
    token: str = Field(min_length=20, max_length=200)


class ResetInput(ActionInput):
    password: str = Field(min_length=8, max_length=72)


@router.post('/request-reset')
def request_reset(payload: EmailInput, request: Request, db: Session = Depends(get_db)):
    rate_limit(db, 'reset:' + request.client.host, 10)
    user = db.query(User).filter_by(email=payload.email.lower(), active=True).first()
    if user:
        queue_action(db, user, 'reset')
        db.commit()
    return {'detail': 'If the account exists, a reset email has been queued'}


@router.post('/request-verification')
def request_verification(user=Depends(get_current_user), db: Session = Depends(get_db)):
    rate_limit(db, 'verify:' + str(user.id), 3)
    if not user.email_verified:
        queue_action(db, user, 'verify')
        db.commit()
    return {'detail': 'Verification email queued if needed'}


@router.post('/verify-email')
def verify_email(payload: ActionInput, db: Session = Depends(get_db)):
    user = db.get(User, consume_action(db, payload.token, 'verify'))
    if not user.active:
        raise HTTPException(400, 'Account unavailable')
    user.email_verified = True
    db.commit()
    return {'detail': 'Email verified'}


@router.post('/reset-password')
def reset_password(payload: ResetInput, db: Session = Depends(get_db)):
    if len(payload.password.encode()) > 72:
        raise HTTPException(422, 'Password exceeds 72 UTF-8 bytes')
    user = db.get(User, consume_action(db, payload.token, 'reset'))
    if not user.active:
        raise HTTPException(400, 'Account unavailable')
    user.hashed_password = hash_password(payload.password)
    user.token_version += 1
    audit(db, user, 'password_reset', 'user', user.id)
    db.commit()
    return {'detail': 'Password changed; sign in again'}
