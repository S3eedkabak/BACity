from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_BYTES = 4096


def validate_new_password(value: str) -> str:
    if len(value) < MIN_PASSWORD_LENGTH:
        raise ValueError(f'Password must be at least {MIN_PASSWORD_LENGTH} characters')
    if not value.strip():
        raise ValueError('Password cannot contain only whitespace')
    if len(value.encode('utf-8')) > MAX_PASSWORD_BYTES:
        raise ValueError(f'Password must not exceed {MAX_PASSWORD_BYTES} UTF-8 bytes')
    return value


def validate_password_bound(value: str) -> str:
    if len(value.encode('utf-8')) > MAX_PASSWORD_BYTES:
        raise ValueError(f'Password must not exceed {MAX_PASSWORD_BYTES} UTF-8 bytes')
    return value


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH)
    display_name: Optional[str] = None

    @field_validator('password')
    @classmethod
    def password_bytes(cls, value):
        return validate_new_password(value)


class UserLogin(BaseModel):
    email: EmailStr
    password: str

    @field_validator('password')
    @classmethod
    def password_bytes(cls, value):
        return validate_password_bound(value)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: EmailStr
    display_name: Optional[str] = None
    interests: list[str] = []
    role: str = 'USER'
    email_verified: bool = False
    identity_verified: bool = False
    reputation: int = 0
    bio: Optional[str] = None
    city: str = 'Bratislava'
    neighborhood: Optional[str] = None
    avatar_url: Optional[str] = None
    public_profile: bool = True
    allow_general_messages: bool = False


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class InterestsUpdate(BaseModel):
    interests: list[str]
