"""Server-authoritative Google Play subscription verification and reconciliation."""
import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import HTTPException
from jose import jwt
from jose.exceptions import JOSEError
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.entitlements import BACITY_PLUS
from app.models.entitlement import ConsumerSubscription

logger = logging.getLogger("bacity.google_play_billing")
GOOGLE_PLAY_PROVIDER = "google_play"
ANDROID_PUBLISHER_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v1/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")
ELIGIBLE_PROVIDER_STATES = frozenset({"SUBSCRIPTION_STATE_ACTIVE", "SUBSCRIPTION_STATE_CANCELED"})


class _ProviderURLRedaction(logging.Filter):
    def filter(self, record):
        if "androidpublisher.googleapis.com" in record.getMessage():
            record.msg = "Google Play HTTP request (provider URL redacted)"
            record.args = ()
        return True


# httpx logs full request URLs at INFO, and Play puts credentials in URL paths.
logging.getLogger("httpx").addFilter(_ProviderURLRedaction())


def _utc_naive(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    except (TypeError, ValueError, OverflowError):
        return None


def obfuscated_account_id(user_id: UUID) -> str:
    return hashlib.sha256(str(user_id).encode()).hexdigest()


def purchase_identity(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class GooglePlayClient:
    """Minimal Android Publisher adapter. Purchase tokens are never logged."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._token: str | None = None
        self._token_expires = datetime.min

    def _credentials(self) -> dict:
        try:
            return json.loads(self.settings.google_play_service_account_json)
        except (TypeError, ValueError):
            raise HTTPException(503, "Google Play billing is not configured")

    def _access_token(self) -> str:
        now = datetime.utcnow()
        if self._token and self._token_expires > now + timedelta(seconds=30):
            return self._token
        credentials = self._credentials()
        issued = int(now.replace(tzinfo=timezone.utc).timestamp())
        try:
            assertion = jwt.encode({
                "iss": credentials["client_email"], "scope": ANDROID_PUBLISHER_SCOPE,
                "aud": credentials["token_uri"], "iat": issued, "exp": issued + 3600,
            }, credentials["private_key"], algorithm="RS256")
            response = httpx.post(credentials["token_uri"], data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            }, timeout=15)
            response.raise_for_status()
            payload = response.json()
            self._token = payload["access_token"]
            self._token_expires = now + timedelta(seconds=min(int(payload.get("expires_in", 3600)), 3600))
            return self._token
        except (httpx.HTTPError, KeyError, TypeError, ValueError, JOSEError):
            logger.warning("Google Play OAuth request failed")
            raise HTTPException(502, "Billing provider unavailable; please try again")

    def _request(self, method: str, url: str, json_body: dict | None = None) -> dict:
        try:
            response = httpx.request(method, url, json=json_body,
                                     headers={"Authorization": "Bearer " + self._access_token()}, timeout=15)
            response.raise_for_status()
            return response.json() if response.content else {}
        except (httpx.HTTPError, ValueError):
            logger.warning("Google Play request failed operation=%s", method)
            raise HTTPException(502, "Billing provider unavailable; please try again")

    def subscription(self, purchase_token: str) -> dict:
        package = quote(self.settings.google_play_package_name, safe="")
        token = quote(purchase_token, safe="")
        return self._request("GET", f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{package}/purchases/subscriptionsv2/tokens/{token}")

    def acknowledge(self, purchase_token: str) -> None:
        package = quote(self.settings.google_play_package_name, safe="")
        product = quote(self.settings.google_play_subscription_product_id, safe="")
        token = quote(purchase_token, safe="")
        self._request("POST", f"https://androidpublisher.googleapis.com/androidpublisher/v3/applications/{package}/purchases/subscriptions/{product}/tokens/{token}:acknowledge", {})


def _matching_line(provider: dict, settings: Settings) -> dict | None:
    for item in provider.get("lineItems") or []:
        if item.get("productId") != settings.google_play_subscription_product_id:
            continue
        base_plan = ((item.get("offerDetails") or {}).get("basePlanId"))
        if settings.google_play_base_plan_id and base_plan != settings.google_play_base_plan_id:
            continue
        return item
    return None


def _normalized_state(provider: dict, expiry: datetime | None, now: datetime) -> tuple[str, bool]:
    state = provider.get("subscriptionState")
    if state == "SUBSCRIPTION_STATE_ACTIVE" and expiry and expiry > now:
        return "active", False
    if state == "SUBSCRIPTION_STATE_CANCELED" and expiry and expiry > now:
        return "active", True
    if state in ELIGIBLE_PROVIDER_STATES and expiry and expiry <= now:
        return "expired", state == "SUBSCRIPTION_STATE_CANCELED"
    return {
        "SUBSCRIPTION_STATE_PENDING": "pending",
        "SUBSCRIPTION_STATE_IN_GRACE_PERIOD": "grace_period",
        "SUBSCRIPTION_STATE_ON_HOLD": "on_hold",
        "SUBSCRIPTION_STATE_PAUSED": "paused",
        "SUBSCRIPTION_STATE_EXPIRED": "expired",
        "SUBSCRIPTION_STATE_PENDING_PURCHASE_CANCELED": "expired",
    }.get(state, "unknown"), state == "SUBSCRIPTION_STATE_CANCELED"


def should_acknowledge(provider: dict, record: ConsumerSubscription) -> bool:
    return (provider.get("acknowledgementState") == "ACKNOWLEDGEMENT_STATE_PENDING"
            and provider.get("subscriptionState") in ELIGIBLE_PROVIDER_STATES
            and record.expires_at is not None and record.expires_at > datetime.utcnow())


def reconcile_google_subscription(db: Session, user_id: UUID, purchase_token: str, provider: dict,
                                  settings: Settings, client: GooglePlayClient,
                                  provider_event_created: datetime | None = None) -> ConsumerSubscription:
    line = _matching_line(provider, settings)
    if not line:
        raise HTTPException(400, "Purchase does not match the BACity+ subscription")
    external = provider.get("externalAccountIdentifiers") or {}
    account_id = external.get("obfuscatedExternalAccountId")
    if account_id and account_id != obfuscated_account_id(user_id):
        raise HTTPException(409, "Purchase cannot be linked to this account")
    existing = db.query(ConsumerSubscription).filter_by(
        provider=GOOGLE_PLAY_PROVIDER, external_subscription_id=purchase_identity(purchase_token),
    ).with_for_update().first()
    if existing and existing.user_id != user_id:
        raise HTTPException(409, "Purchase cannot be linked to this account")
    if existing and existing.status == "replaced":
        raise HTTPException(409, "Purchase has been replaced; restore the current subscription")
    if not existing and account_id != obfuscated_account_id(user_id):
        raise HTTPException(409, "Purchase cannot be linked to this account")

    linked_token = provider.get("linkedPurchaseToken")
    linked = None
    if linked_token and linked_token != purchase_token:
        linked = db.query(ConsumerSubscription).filter_by(
            provider=GOOGLE_PLAY_PROVIDER, external_subscription_id=purchase_identity(linked_token),
        ).with_for_update().first()
        if linked and linked.user_id != user_id:
            raise HTTPException(409, "Purchase cannot be linked to this account")

    now = datetime.utcnow()
    expiry = _utc_naive(line.get("expiryTime"))
    start = _utc_naive(provider.get("startTime"))
    if start and expiry and expiry <= start:
        raise HTTPException(502, "Billing provider returned an invalid subscription period")
    status, cancel_at_end = _normalized_state(provider, expiry, now)
    record = existing or ConsumerSubscription(
        user_id=user_id, entitlement=BACITY_PLUS, provider=GOOGLE_PLAY_PROVIDER,
        external_subscription_id=purchase_identity(purchase_token),
        product_id=settings.google_play_subscription_product_id, status="pending",
    )
    record.product_id = settings.google_play_subscription_product_id
    record.provider_purchase_token = purchase_token
    record.status = status
    record.current_period_start = start
    record.current_period_end = expiry
    record.expires_at = expiry
    record.cancel_at_period_end = cancel_at_end
    record.cancelled_at = now if cancel_at_end and not record.cancelled_at else record.cancelled_at
    if not cancel_at_end:
        record.cancelled_at = None
    record.livemode = provider.get("testPurchase") is None
    record.provider_updated_at = max(filter(None, [record.provider_updated_at, provider_event_created]), default=now)
    record.last_reconciled_at = now
    if linked:
        linked.status = "replaced"
        linked.last_reconciled_at = now
    db.add(record)
    db.flush()
    return record


def verify_and_reconcile(db: Session, user_id: UUID, purchase_token: str, settings: Settings,
                         client: GooglePlayClient | None = None,
                         provider_event_created: datetime | None = None) -> ConsumerSubscription:
    client = client or GooglePlayClient(settings)
    from app.models.user import User
    db.query(User).filter_by(id=user_id).with_for_update().one()
    provider = client.subscription(purchase_token)
    record = reconcile_google_subscription(db, user_id, purchase_token, provider, settings, client,
                                            provider_event_created)
    # Persist verified provider state before acknowledging delivery. A failed
    # acknowledgement is safely retried by the same idempotent verification.
    db.commit()
    if should_acknowledge(provider, record):
        client.acknowledge(purchase_token)
    return record


def verify_pubsub_oidc(token: str, settings: Settings) -> None:
    try:
        header = jwt.get_unverified_header(token)
        unverified = jwt.get_unverified_claims(token)
        issuer = unverified.get("iss")
        if issuer not in GOOGLE_ISSUERS:
            raise ValueError()
        certs = httpx.get(GOOGLE_CERTS_URL, timeout=10).json()
        certificate = certs[header["kid"]]
        claims = jwt.decode(token, certificate, algorithms=["RS256"],
                            audience=settings.google_play_rtdn_audience,
                            issuer=issuer, options={"require_exp": True, "require_iat": True})
        if claims.get("email") != settings.google_play_rtdn_service_account_email or claims.get("email_verified") is not True:
            raise ValueError()
    except Exception as exc:
        # jose exception classes vary by installed backend; never expose token diagnostics.
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(401, "Invalid notification authentication")


def reconcile_google_batch(db: Session, settings: Settings, limit: int = 100,
                           client: GooglePlayClient | None = None) -> tuple[int, int]:
    client = client or GooglePlayClient(settings)
    rows = db.query(ConsumerSubscription).filter(
        ConsumerSubscription.provider == GOOGLE_PLAY_PROVIDER,
        ConsumerSubscription.status != "replaced",
        ConsumerSubscription.provider_purchase_token.isnot(None),
    ).order_by(
        ConsumerSubscription.last_reconciled_at.asc().nullsfirst(), ConsumerSubscription.id,
    ).limit(min(max(limit, 1), 100)).all()
    reconciled = failed = 0
    for row in rows:
        try:
            verify_and_reconcile(db, row.user_id, row.provider_purchase_token, settings, client)
            reconciled += 1
        except HTTPException:
            db.rollback()
            row.last_reconciled_at = datetime.utcnow()
            db.commit()
            failed += 1
    return reconciled, failed
