from datetime import datetime

from pydantic import BaseModel


class EntitlementStateOut(BaseModel):
    active: bool
    expires_at: datetime | None = None
    management_channel: str | None = None


class EntitlementsOut(BaseModel):
    bacity_plus: EntitlementStateOut
