from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.crud import saved_event as saved_event_crud
from app.models.user import User
from app.schemas.auth import UserOut, InterestsUpdate
from app.schemas.event import EventOut

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserOut)
def update_interests(
    payload: InterestsUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    current_user.interests = payload.interests
    db.commit()
    db.refresh(current_user)
    return current_user


@router.get("/me/saved-events", response_model=list[EventOut])
def read_saved_events(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return saved_event_crud.list_saved_events(db, user_id=current_user.id)