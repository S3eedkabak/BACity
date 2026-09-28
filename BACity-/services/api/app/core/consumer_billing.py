"""Server-authoritative Stripe consumer billing and reconciliation."""
import logging
from datetime import datetime
from urllib.parse import quote
from uuid import UUID

import httpx
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.entitlements import BACITY_PLUS
from app.models.entitlement import ConsumerBillingCustomer, ConsumerSubscription
from app.models.user import User

logger = logging.getLogger("bacity.consumer_billing")
STRIPE_PROVIDER = "stripe"
ELIGIBLE_STATUSES = frozenset({"active", "trialing"})
BLOCKING_STATUSES = frozenset({"active", "trialing", "past_due", "unpaid", "incomplete", "paused"})


def _timestamp(value) -> datetime | None:
    try:
        return datetime.utcfromtimestamp(int(value)) if value is not None else None
    except (TypeError, ValueError, OSError):
        return None


class StripeConsumerClient:
    """Small isolated v1 client; organization billing intentionally does not use it."""

    def __init__(self, settings: Settings):
        self.settings = settings

    def request(self, method: str, path: str, data=None, idempotency_key: str | None = None):
        headers = {
            "Authorization": "Bearer " + self.settings.stripe_consumer_secret_key,
            "Stripe-Version": self.settings.stripe_consumer_api_version,
        }
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        try:
            response = httpx.request(
                method, "https://api.stripe.com/v1/" + path,
                params=data if method == "GET" else None,
                data=None if method == "GET" else data,
                headers=headers, timeout=15,
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            logger.warning("Stripe consumer request failed operation=%s", path.split("/")[0])
            raise HTTPException(502, "Billing provider unavailable; please try again")

    def customer(self, identifier: str):
        return self.request("GET", "customers/" + quote(identifier, safe=""))

    def create_customer(self, user: User):
        return self.request("POST", "customers", {
            "email": user.email,
            "metadata[bacity_user_id]": str(user.id),
            "description": "BACity consumer account",
        }, f"consumer-customer-{user.id}")

    def price(self, identifier: str):
        return self.request("GET", "prices/" + quote(identifier, safe=""))

    def subscription(self, identifier: str):
        return self.request("GET", "subscriptions/" + quote(identifier, safe=""), {
            "expand[]": "items.data.price.product",
        })

    def subscriptions(self, customer_id: str):
        return self.request("GET", "subscriptions", {
            "customer": customer_id, "status": "all", "limit": 100,
            "expand[]": "data.items.data.price.product",
        })

    def checkout_session(self, identifier: str):
        return self.request("GET", "checkout/sessions/" + quote(identifier, safe=""))

    def create_checkout(self, customer_id: str, user_id: UUID, settings: Settings, key: str):
        return self.request("POST", "checkout/sessions", {
            "mode": "subscription", "customer": customer_id,
            "client_reference_id": str(user_id),
            "line_items[0][price]": settings.stripe_consumer_plus_price_id,
            "line_items[0][quantity]": "1",
            "metadata[bacity_user_id]": str(user_id),
            "subscription_data[metadata][bacity_user_id]": str(user_id),
            "success_url": settings.stripe_consumer_success_url,
            "cancel_url": settings.stripe_consumer_cancel_url,
        }, key)

    def portal(self, customer_id: str, settings: Settings):
        return self.request("POST", "billing_portal/sessions", {
            "customer": customer_id,
            "return_url": settings.stripe_consumer_portal_return_url,
        }, f"consumer-portal-{customer_id}-{int(datetime.utcnow().timestamp()) // 300}")

    def cancel_subscription(self, identifier: str):
        return self.request("DELETE", "subscriptions/" + quote(identifier, safe=""), {},
                            f"consumer-delete-cancel-{identifier}")


def _expected_livemode(settings: Settings) -> bool:
    return settings.stripe_consumer_livemode


def validate_price(price: dict, settings: Settings) -> None:
    product = price.get("product")
    if isinstance(product, dict):
        product = product.get("id")
    if (price.get("id") != settings.stripe_consumer_plus_price_id
            or bool(price.get("livemode")) != _expected_livemode(settings)
            or price.get("active") is not True
            or not price.get("recurring")
            or (settings.stripe_consumer_plus_product_id
                and product != settings.stripe_consumer_plus_product_id)):
        raise HTTPException(503, "BACity+ billing configuration is invalid")


def validate_customer(customer: dict, user_id: UUID, settings: Settings) -> None:
    if bool(customer.get("livemode")) != _expected_livemode(settings):
        raise HTTPException(409, "Billing environment mismatch")
    if customer.get("metadata", {}).get("bacity_user_id") != str(user_id):
        raise HTTPException(409, "Billing customer identity mismatch")


def get_or_create_customer(db: Session, user: User, client: StripeConsumerClient,
                           settings: Settings) -> ConsumerBillingCustomer:
    mapping = db.query(ConsumerBillingCustomer).filter_by(provider=STRIPE_PROVIDER, user_id=user.id).first()
    if mapping:
        validate_customer(client.customer(mapping.external_customer_id), user.id, settings)
        if mapping.livemode != _expected_livemode(settings):
            raise HTTPException(409, "Billing environment mismatch")
        return mapping
    provider = client.create_customer(user)
    validate_customer(provider, user.id, settings)
    mapping = ConsumerBillingCustomer(
        user_id=user.id, provider=STRIPE_PROVIDER, external_customer_id=provider["id"],
        livemode=_expected_livemode(settings),
    )
    db.add(mapping)
    db.flush()
    return mapping


def _subscription_product(subscription: dict, settings: Settings) -> tuple[bool, str | None]:
    prices = []
    products = []
    for item in subscription.get("items", {}).get("data", []):
        price = item.get("price") or {}
        prices.append(price.get("id"))
        product = price.get("product")
        products.append(product.get("id") if isinstance(product, dict) else product)
    matches = settings.stripe_consumer_plus_price_id in prices
    if settings.stripe_consumer_plus_product_id:
        matches = matches and settings.stripe_consumer_plus_product_id in products
    return matches, settings.stripe_consumer_plus_price_id if matches else None


def reconcile_subscription(db: Session, user_id: UUID, mapping: ConsumerBillingCustomer,
                           provider: dict, settings: Settings,
                           provider_event_created: datetime | None = None) -> ConsumerSubscription | None:
    if bool(provider.get("livemode")) != _expected_livemode(settings):
        raise HTTPException(409, "Billing environment mismatch")
    if provider.get("customer") != mapping.external_customer_id:
        raise HTTPException(409, "Subscription customer mismatch")
    metadata_user = provider.get("metadata", {}).get("bacity_user_id")
    if metadata_user and metadata_user != str(user_id):
        raise HTTPException(409, "Subscription account mismatch")
    external_id = provider.get("id")
    if not isinstance(external_id, str) or len(external_id) > 255:
        raise HTTPException(502, "Billing provider returned invalid subscription data")
    existing = db.query(ConsumerSubscription).filter_by(
        provider=STRIPE_PROVIDER, external_subscription_id=external_id,
    ).with_for_update().first()
    if existing and existing.user_id != user_id:
        raise HTTPException(409, "Subscription is already linked to another account")
    matches, product_id = _subscription_product(provider, settings)
    if not matches and not existing:
        return None
    now = datetime.utcnow()
    record = existing or ConsumerSubscription(
        user_id=user_id, entitlement=BACITY_PLUS, provider=STRIPE_PROVIDER,
        external_subscription_id=external_id,
        product_id=product_id or settings.stripe_consumer_plus_price_id,
        status="invalid_product",
    )
    record.external_customer_id = mapping.external_customer_id
    record.product_id = product_id or record.product_id
    record.status = str(provider.get("status")) if matches else "invalid_product"
    record.current_period_start = _timestamp(provider.get("current_period_start"))
    record.current_period_end = _timestamp(provider.get("current_period_end"))
    record.cancel_at_period_end = bool(provider.get("cancel_at_period_end"))
    record.cancelled_at = _timestamp(provider.get("canceled_at"))
    record.expires_at = record.current_period_end
    record.provider_updated_at = max(filter(None, [record.provider_updated_at, provider_event_created]), default=now)
    record.last_reconciled_at = now
    record.livemode = _expected_livemode(settings)
    db.add(record)
    return record


def reconcile_customer(db: Session, user: User, mapping: ConsumerBillingCustomer,
                       client: StripeConsumerClient, settings: Settings,
                       provider_event_created: datetime | None = None) -> list[ConsumerSubscription]:
    validate_customer(client.customer(mapping.external_customer_id), user.id, settings)
    payload = client.subscriptions(mapping.external_customer_id)
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list) or len(rows) > 100 or payload.get("has_more") is True:
        raise HTTPException(502, "Billing provider returned invalid subscription data")
    seen: set[str] = set()
    results = []
    for provider in rows:
        record = reconcile_subscription(db, user.id, mapping, provider, settings, provider_event_created)
        if record:
            seen.add(record.external_subscription_id)
            results.append(record)
    now = datetime.utcnow()
    local = db.query(ConsumerSubscription).filter_by(user_id=user.id, provider=STRIPE_PROVIDER).with_for_update().all()
    for record in local:
        if record.external_subscription_id not in seen:
            record.status = "canceled"
            record.cancelled_at = record.cancelled_at or now
            record.last_reconciled_at = now
    mapping.pending_checkout_session_id = None
    mapping.pending_checkout_expires_at = None
    return results


def stripe_status(db: Session, user_id: UUID) -> ConsumerSubscription | None:
    return db.query(ConsumerSubscription).filter_by(
        user_id=user_id, provider=STRIPE_PROVIDER,
    ).order_by(ConsumerSubscription.current_period_end.desc()).first()


def cancel_consumer_billing_for_deletion(db: Session, user: User, client: StripeConsumerClient,
                                         settings: Settings) -> bool:
    mapping = db.query(ConsumerBillingCustomer).filter_by(provider=STRIPE_PROVIDER, user_id=user.id).with_for_update().first()
    if not mapping:
        return False
    current = reconcile_customer(db, user, mapping, client, settings)
    for subscription in current:
        if subscription.status in BLOCKING_STATUSES:
            provider = client.cancel_subscription(subscription.external_subscription_id)
            reconcile_subscription(db, user.id, mapping, provider, settings)
    db.flush()
    return True
