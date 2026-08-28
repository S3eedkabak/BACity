from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict


class UserRegister(BaseModel):
    email: EmailStr
    password: str
    display_name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    display_name: Optional[str] = None
    interests: list[str] = []


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class InterestsUpdate(BaseModel):
    interests: list[str]
