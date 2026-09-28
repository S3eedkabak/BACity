"""Isolated Stripe web billing for consumer BACity+ subscriptions."""
import json
import logging
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.billing import verify_signature
from app.config import get_settings
from app.core.community import rate_limit
from app.core.consumer_billing import (
    BLOCKING_STATUSES, STRIPE_PROVIDER, StripeConsumerClient,
    get_or_create_customer, reconcile_customer, stripe_status, validate_price,
)
from app.core.entitlements import BACITY_PLUS, EntitlementService
from app.database import get_db
from app.models.entitlement import ConsumerBillingCustomer, ConsumerSubscription, ProviderEventReceipt
from app.models.user import User

router = APIRouter(prefix="/billing/consumer", tags=["consumer-billing"])
logger = logging.getLogger("bacity.consumer_billing")
MAX_WEBHOOK_BODY = 262_144
HANDLED_EVENTS = frozenset({
    "checkout.session.completed",
    "customer.subscription.created", "customer.subscription.updated",
    "customer.subscription.deleted", "customer.subscription.paused",
    "customer.subscription.resumed",
    "invoice.paid", "invoice.payment_failed",
})


def _settings():
    settings = get_settings()
    if not settings.consumer_billing_enabled:
        raise HTTPException(503, "Consumer billing is not enabled")
    return settings


def _safe_url(value, expected_host):
    parsed = urlsplit(value) if isinstance(value, str) else None
    if not parsed or parsed.scheme != "https" or parsed.hostname != expected_host:
        raise HTTPException(502, "Billing provider returned an invalid redirect")
    return value


@router.get("/status")
def consumer_status(user=Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    entitlement = EntitlementService(db).get_entitlement(user.id, BACITY_PLUS)
    subscription = stripe_status(db, user.id)
    mapping = db.query(ConsumerBillingCustomer).filter_by(provider=STRIPE_PROVIDER, user_id=user.id).first()
    has_blocking_subscription = db.query(ConsumerSubscription.id).filter(
        ConsumerSubscription.provider == STRIPE_PROVIDER,
        ConsumerSubscription.user_id == user.id,
        ConsumerSubscription.status.in_(BLOCKING_STATUSES),
    ).first() is not None
    return {
        "billing_enabled": settings.consumer_billing_enabled,
        "plus_active": entitlement.active,
        "management_channel": entitlement.management_channel,
        "provider": STRIPE_PROVIDER if subscription else None,
        "subscription_status": subscription.status if subscription else None,
        "current_period_end": subscription.current_period_end if subscription else None,
        "cancel_at_period_end": subscription.cancel_at_period_end if subscription else False,
        "portal_available": bool(settings.consumer_billing_enabled and mapping),
        "checkout_available": bool(settings.consumer_billing_enabled and not has_blocking_subscription),
    }


@router.post("/checkout")
def checkout(user=Depends(get_current_user), db: Session = Depends(get_db)):
    settings = _settings()
    rate_limit(db, f"consumer-checkout:{user.id}", 5)
    locked_user = db.query(User).filter_by(id=user.id).with_for_update().one()
    client = StripeConsumerClient(settings)
    validate_price(client.price(settings.stripe_consumer_plus_price_id), settings)
    mapping = get_or_create_customer(db, locked_user, client, settings)
    now = datetime.utcnow()
    if mapping.pending_checkout_session_id and mapping.pending_checkout_expires_at and mapping.pending_checkout_expires_at > now:
        pending = client.checkout_session(mapping.pending_checkout_session_id)
        if pending.get("status") == "open" and pending.get("customer") == mapping.external_customer_id:
            return {"url": _safe_url(pending.get("url"), "checkout.stripe.com")}
    subscriptions = reconcile_customer(db, locked_user, mapping, client, settings)
    if any(item.status in BLOCKING_STATUSES for item in subscriptions):
        db.commit()
        raise HTTPException(409, "Use billing management for your existing Stripe subscription")
    key = f"consumer-checkout-{user.id}-{int(now.timestamp()) // 1800}"
    session = client.create_checkout(mapping.external_customer_id, user.id, settings, key)
    if (session.get("customer") != mapping.external_customer_id
            or bool(session.get("livemode")) != settings.stripe_consumer_livemode):
        raise HTTPException(502, "Billing provider returned invalid Checkout data")
    mapping.pending_checkout_session_id = session.get("id")
    mapping.pending_checkout_expires_at = datetime.utcfromtimestamp(session["expires_at"]) if session.get("expires_at") else now + timedelta(minutes=30)
    db.commit()
    return {"url": _safe_url(session.get("url"), "checkout.stripe.com")}


@router.post("/portal")
def portal(user=Depends(get_current_user), db: Session = Depends(get_db)):
    settings = _settings()
    rate_limit(db, f"consumer-portal:{user.id}", 10)
    mapping = db.query(ConsumerBillingCustomer).filter_by(provider=STRIPE_PROVIDER, user_id=user.id).first()
    if not mapping:
        raise HTTPException(404, "No Stripe consumer billing account")
    session = StripeConsumerClient(settings).portal(mapping.external_customer_id, settings)
    return {"url": _safe_url(session.get("url"), "billing.stripe.com")}


@router.post("/reconcile")
def reconcile(user=Depends(get_current_user), db: Session = Depends(get_db)):
    settings = _settings()
    rate_limit(db, f"consumer-reconcile:{user.id}", 30)
    locked_user = db.query(User).filter_by(id=user.id).with_for_update().one()
    mapping = db.query(ConsumerBillingCustomer).filter_by(provider=STRIPE_PROVIDER, user_id=user.id).with_for_update().first()
    if mapping:
        reconcile_customer(db, locked_user, mapping, StripeConsumerClient(settings), settings)
        db.commit()
    entitlement = EntitlementService(db).get_entitlement(user.id, BACITY_PLUS)
    return {"active": entitlement.active, "expires_at": entitlement.expires_at,
            "management_channel": entitlement.management_channel}


async def _bounded_body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_WEBHOOK_BODY:
            raise HTTPException(413, "Webhook payload too large")
    return bytes(body)


@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    settings = _settings()
    body = await _bounded_body(request)
    if not verify_signature(body, request.headers.get("stripe-signature", ""),
                            settings.stripe_consumer_webhook_secret):
        raise HTTPException(400, "Invalid webhook signature")
    try:
        event = json.loads(body)
        event_id, kind, obj = event["id"], event["type"], event["data"]["object"]
        created = datetime.utcfromtimestamp(int(event["created"]))
        if (not isinstance(event_id, str) or len(event_id) > 255
                or not isinstance(kind, str) or len(kind) > 128 or not isinstance(obj, dict)):
            raise ValueError()
        if bool(event["livemode"]) != settings.stripe_consumer_livemode:
            raise HTTPException(400, "Webhook environment mismatch")
    except HTTPException:
        raise
    except (KeyError, TypeError, ValueError, OSError):
        raise HTTPException(400, "Invalid webhook payload")
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(82619424)"))
    if db.query(ProviderEventReceipt).filter_by(provider=STRIPE_PROVIDER, external_event_id=event_id).first():
        return {"received": True, "duplicate": True}
    outcome = "ignored"
    if kind in HANDLED_EVENTS:
        customer_id = obj.get("customer")
        mapping = db.query(ConsumerBillingCustomer).filter_by(
            provider=STRIPE_PROVIDER, external_customer_id=customer_id,
        ).with_for_update().first() if customer_id else None
        if mapping:
            user = db.get(User, mapping.user_id)
            if user:
                reconcile_customer(db, user, mapping, StripeConsumerClient(settings), settings, created)
                outcome = "reconciled"
    db.add(ProviderEventReceipt(
        provider=STRIPE_PROVIDER, external_event_id=event_id, event_type=kind,
        provider_created_at=created, outcome=outcome,
    ))
    db.commit()
    logger.info("Consumer webhook processed event_id=%s event_type=%s outcome=%s", event_id, kind, outcome)
    return {"received": True, "duplicate": False}
