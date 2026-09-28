from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import decode_access_token, token_version
from app.models.user import User
from app.core.entitlements import BACITY_PLUS, EntitlementService, EntitlementState

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    email = decode_access_token(token)
    if not email:
        raise credentials_exception
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.active or user.token_version != token_version(token):
        raise credentials_exception
    return user


def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    email = decode_access_token(token)
    user = db.query(User).filter(User.email == email).first() if email else None
    if not user or not user.active or user.token_version != token_version(token):
        raise HTTPException(status_code=401, detail="Could not validate credentials")
    return user


def get_entitlements(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, EntitlementState]:
    return EntitlementService(db).get_entitlements(current_user.id)


def require_entitlement(entitlement: str):
    def dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        if not EntitlementService(db).has_entitlement(current_user.id, entitlement):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="BACity+ required")
        return current_user

    return dependency


require_plus = require_entitlement(BACITY_PLUS)
