from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class VenueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    address: Optional[str] = None
    city: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    website: Optional[str] = None
    category: Optional[str] = None
    verified: bool
    created_at: datetime
