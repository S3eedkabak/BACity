from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    display_name: Optional[str] = None

    @field_validator('password')
    @classmethod
    def password_bytes(cls, value):
        if len(value.encode('utf-8')) > 72:
            raise ValueError('Password must fit within 72 UTF-8 bytes')
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


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
