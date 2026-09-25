from datetime import datetime
from typing import Literal, Optional
from urllib.parse import urlsplit
from uuid import UUID
import ipaddress
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from app.schemas.event import EventCreate

Role = Literal['USER', 'GUIDE', 'ORGANIZER', 'MODERATOR', 'ADMIN']
UtilityKind = Literal['toilet', 'water_fountain', 'bike_repair', 'charging', 'wifi', 'bench', 'playground', 'dog_park', 'recycling', 'accessible_entrance', 'parking', 'locker']
OperationalStatus = Literal['open', 'closed', 'out_of_order', 'unknown']
FollowType = Literal['user', 'guide', 'venue', 'organizer', 'neighborhood', 'category']


def public_url(value):
    if not value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Use a public HTTPS URL without credentials')
    if parsed.hostname == 'localhost' or parsed.hostname.endswith(('.local', '.internal')):
        raise ValueError('Private URLs are not supported')
    try:
        if not ipaddress.ip_address(parsed.hostname).is_global:
            raise ValueError('Private addresses are not supported')
    except ValueError as exc:
        if 'Private' in str(exc):
            raise
    return value


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ProfileUpdate(StrictModel):
    display_name: Optional[str] = Field(None, min_length=2, max_length=80)
    avatar_url: Optional[str] = Field(None, max_length=2048)
    bio: Optional[str] = Field(None, max_length=1000)
    city: str = Field('Bratislava', max_length=80)
    neighborhood: Optional[str] = Field(None, max_length=80)
    interests: list[str] = Field(default_factory=list, max_length=30)
    public_profile: bool = True
    allow_general_messages: bool = False
    _url = field_validator('avatar_url')(public_url)


class EventSubmission(EventCreate):
    source_url: str = Field(max_length=2048)
    description: str = Field(min_length=20, max_length=15000)
    organizer_name: Optional[str] = Field(None, max_length=200)
    ticket_url: Optional[str] = Field(None, max_length=2048)
    neighborhood: Optional[str] = Field(None, max_length=80)
    _links = field_validator('source_url', 'ticket_url', 'image_url')(public_url)

    @model_validator(mode='after')
    def user_event(self):
        from datetime import timezone, timedelta
        if self.start_time.tzinfo is None or (self.end_time and self.end_time.tzinfo is None):
            raise ValueError('Dates must include their timezone offset')
        if not datetime.now(timezone.utc) - timedelta(days=1) <= self.start_time <= datetime.now(timezone.utc) + timedelta(days=730):
            raise ValueError('Event must be current or within the next two years')
        if not (self.address or self.venue_name):
            raise ValueError('A venue or address is required')
        return self


class PlaceInput(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    category: str = Field('Other', max_length=80)
    address: str = Field(min_length=3, max_length=500)
    latitude: float = Field(ge=48, le=48.35)
    longitude: float = Field(ge=16.9, le=17.35)
    neighborhood: Optional[str] = Field(None, max_length=80)
    website: Optional[str] = None
    accessibility: dict[str, bool] = Field(default_factory=dict, max_length=20)
    operational_status: OperationalStatus = 'unknown'
    _url = field_validator('website')(public_url)


class UtilityInput(StrictModel):
    kind: UtilityKind = 'toilet'
    name: str = Field(min_length=2, max_length=200)
    latitude: float = Field(ge=48, le=48.35)
    longitude: float = Field(ge=16.9, le=17.35)
    address: Optional[str] = Field(None, max_length=500)
    opening_hours: Optional[str] = Field(None, max_length=500)
    free: Optional[bool] = None
    fee: Optional[float] = Field(None, ge=0, le=1000)
    wheelchair_accessible: Optional[bool] = None
    changing_table: Optional[bool] = None
    cleanliness: Optional[int] = Field(None, ge=1, le=5)
    operational_status: OperationalStatus = 'unknown'
    source_url: Optional[str] = None
    _url = field_validator('source_url')(public_url)


class Confirmation(StrictModel):
    operational_status: OperationalStatus
    cleanliness: Optional[int] = Field(None, ge=1, le=5)


class ModerationDecision(StrictModel):
    decision: Literal['approve', 'reject']
    reason: str = Field(min_length=5, max_length=2000)
    trust_level: Literal['Official', 'Verified', 'Community', 'Unverified'] = 'Community'


class Reason(StrictModel):
    reason: str = Field(min_length=5, max_length=2000)


class FollowInput(StrictModel):
    target_type: FollowType
    target_id: str = Field(min_length=1, max_length=100)


class ReportInput(Reason):
    target_type: Literal['event', 'user', 'review', 'comment', 'message', 'place', 'utility']
    target_id: UUID


class ReviewInput(StrictModel):
    target_type: Literal['event', 'place']
    target_id: UUID
    body: str = Field(min_length=10, max_length=3000)
    dimensions: dict[str, int] = Field(min_length=1, max_length=10)

    @model_validator(mode='after')
    def dimensions_match(self):
        allowed = {'worth_attending', 'crowd', 'value', 'accessibility', 'would_attend_again'} if self.target_type == 'event' else {'atmosphere', 'price', 'accessibility', 'cleanliness', 'crowdedness', 'family_friendliness', 'solo_friendliness'}
        if not set(self.dimensions) <= allowed or any(not 1 <= v <= 5 for v in self.dimensions.values()):
            raise ValueError('Choose supported dimensions with ratings from 1 to 5')
        return self


class BodyInput(StrictModel):
    body: str = Field(min_length=1, max_length=3000)


class OrganizationInput(StrictModel):
    name: str = Field(min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=5000)
    website: str = Field(max_length=2048)
    venue_id: Optional[UUID] = None
    _url = field_validator('website')(public_url)


class ClaimInput(Reason):
    evidence_url: str = Field(max_length=2048)
    _url = field_validator('evidence_url')(public_url)


class RoleInput(Reason):
    role: Role


class CollectionInput(StrictModel):
    title: str = Field(min_length=2, max_length=150)
    description: Optional[str] = Field(None, max_length=3000)
    neighborhood: Optional[str] = Field(None, max_length=80)
    items: list[dict[str, str]] = Field(default_factory=list, max_length=100)
    public: bool = False


class CorrectionInput(Reason):
    target_type: Literal['place', 'utility', 'event']
    target_id: UUID
    changes: dict = Field(min_length=1, max_length=20)


class RecurringEvents(StrictModel):
    event: EventSubmission
    dates: list[datetime] = Field(min_length=1, max_length=52)
