"""Single server-side authority for consumer entitlement evaluation."""
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.entitlement import ConsumerSubscription, EntitlementGrant

BACITY_PLUS = "bacity_plus"
PREMIUM_FEATURE_ENTITLEMENTS = {
    "tonight": BACITY_PLUS,
    "event_chains": BACITY_PLUS,
    "build_my_evening": BACITY_PLUS,
    "weekend_generator": BACITY_PLUS,
    "group_match": BACITY_PLUS,
    "group_voting": BACITY_PLUS,
    "area_watch": BACITY_PLUS,
}

ACTIVE_SUBSCRIPTION_STATUSES = frozenset({"active", "trialing"})


@dataclass(frozen=True)
class EntitlementState:
    active: bool
    expires_at: datetime | None = None
    management_channel: str | None = None


def _subscription_expiration(subscription: ConsumerSubscription) -> datetime | None:
    candidates = [value for value in (subscription.current_period_end, subscription.expires_at) if value]
    return min(candidates) if candidates else None


def _management_channel(provider: str) -> str:
    return {
        "stripe": "web",
        "apple": "app_store",
        "google_play": "play_store",
    }.get(provider, "support")


def _aggregate(active_sources: Iterable[tuple[datetime | None, str]]) -> EntitlementState:
    sources = list(active_sources)
    if not sources:
        return EntitlementState(active=False)
    # Prefer a provider management channel over a support-managed grant.
    channel = next((item[1] for item in sources if item[1] != "support"), sources[0][1])
    expirations = [item[0] for item in sources]
    expires_at = None if any(value is None for value in expirations) else max(expirations)
    return EntitlementState(active=True, expires_at=expires_at, management_channel=channel)


class EntitlementService:
    def __init__(self, db: Session):
        self.db = db

    def get_entitlement(self, user_id: UUID, entitlement: str, now: datetime | None = None) -> EntitlementState:
        now = now or datetime.utcnow()
        active_sources: list[tuple[datetime | None, str]] = []

        subscriptions = self.db.query(ConsumerSubscription).filter(
            ConsumerSubscription.user_id == user_id,
            ConsumerSubscription.entitlement == entitlement,
        ).all()
        for subscription in subscriptions:
            expiration = _subscription_expiration(subscription)
            if subscription.status not in ACTIVE_SUBSCRIPTION_STATUSES:
                continue
            if subscription.current_period_start and subscription.current_period_start > now:
                continue
            if expiration and expiration <= now:
                continue
            active_sources.append((expiration, _management_channel(subscription.provider)))

        grants = self.db.query(EntitlementGrant).filter(
            EntitlementGrant.user_id == user_id,
            EntitlementGrant.entitlement == entitlement,
        ).all()
        for grant in grants:
            if grant.revoked_at or grant.valid_from > now:
                continue
            if grant.valid_until and grant.valid_until <= now:
                continue
            active_sources.append((grant.valid_until, "support"))

        return _aggregate(active_sources)

    def get_entitlements(self, user_id: UUID, now: datetime | None = None) -> dict[str, EntitlementState]:
        return {BACITY_PLUS: self.get_entitlement(user_id, BACITY_PLUS, now=now)}

    def has_entitlement(self, user_id: UUID, entitlement: str, now: datetime | None = None) -> bool:
        return self.get_entitlement(user_id, entitlement, now=now).active
