"""Google Play consumer subscriptions; Google remains the state authority."""
import base64
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes.events import require_ingestion_key
from app.config import get_settings
from app.core.community import rate_limit
from app.core.entitlements import BACITY_PLUS, EntitlementService
from app.core.google_play_billing import (
    GOOGLE_PLAY_PROVIDER, GooglePlayClient, reconcile_google_batch,
    reconcile_google_subscription, obfuscated_account_id, should_acknowledge,
    verify_and_reconcile, verify_pubsub_oidc, purchase_identity,
)
from app.database import get_db
from app.models.entitlement import ConsumerSubscription, ProviderEventReceipt
from app.models.user import User

class PrivateBillingRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request):
            try:
                return await handler(request)
            except RequestValidationError:
                # FastAPI's default validation response includes the submitted
                # input. Never echo purchase credentials, including malformed ones.
                raise HTTPException(422, "Invalid billing request")
        return safe_handler


router = APIRouter(prefix="/billing/google-play", tags=["consumer-billing"], route_class=PrivateBillingRoute)
logger = logging.getLogger("bacity.google_play_billing")
MAX_NOTIFICATION_BODY = 262_144


class PurchaseVerification(BaseModel):
    purchase_token: str = Field(min_length=10, max_length=4096)
    product_id: str = Field(min_length=1, max_length=255)


def _settings():
    settings = get_settings()
    if not settings.google_play_billing_enabled:
        raise HTTPException(503, "Google Play billing is not enabled")
    return settings


def _safe_result(db: Session, user_id, record: ConsumerSubscription):
    entitlement = EntitlementService(db).get_entitlement(user_id, BACITY_PLUS)
    return {
        "active": entitlement.active,
        "expires_at": entitlement.expires_at,
        "management_channel": entitlement.management_channel,
        "subscription_status": record.status,
        "cancel_at_period_end": record.cancel_at_period_end,
    }


def _other_paid(db: Session, user_id):
    now = datetime.utcnow()
    return db.query(ConsumerSubscription.id).filter(
        ConsumerSubscription.user_id == user_id,
        ConsumerSubscription.entitlement == BACITY_PLUS,
        ConsumerSubscription.provider != GOOGLE_PLAY_PROVIDER,
        ConsumerSubscription.status.in_(("active", "trialing")),
        (ConsumerSubscription.current_period_start.is_(None) | (ConsumerSubscription.current_period_start <= now)),
        (ConsumerSubscription.current_period_end.is_(None) | (ConsumerSubscription.current_period_end > now)),
        (ConsumerSubscription.expires_at.is_(None) | (ConsumerSubscription.expires_at > now)),
    ).first() is not None


@router.get("/config")
def config(user=Depends(get_current_user), db: Session = Depends(get_db)):
    settings = get_settings()
    entitlement = EntitlementService(db).get_entitlement(user.id, BACITY_PLUS)
    google = db.query(ConsumerSubscription).filter_by(
        provider=GOOGLE_PLAY_PROVIDER, user_id=user.id,
    ).filter(ConsumerSubscription.status != "replaced").order_by(
        ConsumerSubscription.last_reconciled_at.desc(), ConsumerSubscription.created_at.desc(),
    ).first()
    paid_other = _other_paid(db, user.id)
    return {
        "configured": settings.google_play_billing_enabled,
        "package_name": settings.google_play_package_name if settings.google_play_billing_enabled else None,
        "product_id": settings.google_play_subscription_product_id if settings.google_play_billing_enabled else None,
        "base_plan_id": settings.google_play_base_plan_id or None,
        "obfuscated_account_id": obfuscated_account_id(user.id) if settings.google_play_billing_enabled else None,
        "plus_active": entitlement.active,
        "management_channel": entitlement.management_channel,
        "active_paid_other_provider": paid_other,
        "subscription_status": google.status if google else None,
        "current_period_end": google.current_period_end if google else None,
        "cancel_at_period_end": google.cancel_at_period_end if google else False,
    }


@router.post("/verify")
def verify(payload: PurchaseVerification, user=Depends(get_current_user), db: Session = Depends(get_db)):
    settings = _settings()
    rate_limit(db, f"google-play-verify:{user.id}", 20)
    if payload.product_id != settings.google_play_subscription_product_id:
        raise HTTPException(400, "Purchase does not match the BACity+ subscription")
    db.query(User).filter_by(id=user.id).with_for_update().one()
    existing = db.query(ConsumerSubscription).filter_by(
        provider=GOOGLE_PLAY_PROVIDER, external_subscription_id=purchase_identity(payload.purchase_token),
    ).first()
    if existing and existing.user_id != user.id:
        raise HTTPException(409, "Purchase cannot be linked to this account")
    if not existing:
        other = _other_paid(db, user.id)
        if other:
            raise HTTPException(409, "BACity+ is already active through another billing provider")
    record = verify_and_reconcile(db, user.id, payload.purchase_token, settings)
    return _safe_result(db, user.id, record)


@router.post("/reconcile")
def reconcile(user=Depends(get_current_user), db: Session = Depends(get_db)):
    settings = _settings()
    rate_limit(db, f"google-play-reconcile:{user.id}", 20)
    rows = db.query(ConsumerSubscription).filter_by(
        provider=GOOGLE_PLAY_PROVIDER, user_id=user.id,
    ).filter(ConsumerSubscription.status != "replaced").order_by(ConsumerSubscription.last_reconciled_at.asc().nullsfirst()).limit(10).all()
    client = GooglePlayClient(settings)
    for row in rows:
        verify_and_reconcile(db, user.id, row.provider_purchase_token, settings, client)
    entitlement = EntitlementService(db).get_entitlement(user.id, BACITY_PLUS)
    return {"active": entitlement.active, "expires_at": entitlement.expires_at,
            "management_channel": entitlement.management_channel, "reconciled": len(rows)}


async def _bounded_body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_NOTIFICATION_BODY:
            raise HTTPException(413, "Notification payload too large")
    return bytes(body)


@router.post("/rtdn")
async def rtdn(request: Request, authorization: str | None = Header(None),
               db: Session = Depends(get_db)):
    settings = _settings()
    if not settings.google_play_rtdn_audience or not settings.google_play_rtdn_service_account_email:
        raise HTTPException(503, "Google Play notifications are not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Invalid notification authentication")
    verify_pubsub_oidc(authorization[7:], settings)
    try:
        envelope = json.loads(await _bounded_body(request))
        message = envelope["message"]
        message_id = str(message["messageId"])
        if not message_id or len(message_id) > 255:
            raise ValueError()
        decoded = base64.b64decode(message["data"], validate=True)
        if len(decoded) > 65_536:
            raise ValueError()
        notification = json.loads(decoded)
        if notification["packageName"] != settings.google_play_package_name:
            raise ValueError()
        subscription = notification.get("subscriptionNotification")
        if subscription is None and "testNotification" in notification:
            return {"received": True, "test": True}
        if subscription is None:
            voided = notification.get("voidedPurchaseNotification")
            if voided and voided.get("productType") == 1:
                subscription = voided
            else:
                return {"received": True, "ignored": True}
        purchase_token = str(subscription["purchaseToken"])
        # Current RTDN format omits subscriptionId. Product/base-plan identity
        # comes from the authoritative subscriptionsv2 response, not this hint.
        product_id = subscription.get("subscriptionId")
        if (notification["packageName"] != settings.google_play_package_name
                or (product_id is not None and product_id != settings.google_play_subscription_product_id)
                or len(purchase_token) < 10 or len(purchase_token) > 4096):
            raise ValueError()
        event_created = datetime.utcfromtimestamp(int(notification["eventTimeMillis"]) / 1000)
        event_type = ("voided:" + str(subscription.get("refundType", "unknown"))
                      if "voidedPurchaseNotification" in notification
                      else "subscription:" + str(subscription.get("notificationType", "unknown")))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, OverflowError):
        raise HTTPException(400, "Invalid notification payload")
    if db.bind.dialect.name == "postgresql":
        db.execute(text("SELECT pg_advisory_xact_lock(82619425)"))
    if db.query(ProviderEventReceipt).filter_by(
        provider=GOOGLE_PLAY_PROVIDER, external_event_id=message_id,
    ).first():
        return {"received": True, "duplicate": True}
    record = db.query(ConsumerSubscription).filter_by(
        provider=GOOGLE_PLAY_PROVIDER, external_subscription_id=purchase_identity(purchase_token),
    ).first()
    outcome = "ignored"
    if record and record.status != "replaced":
        db.query(User).filter_by(id=record.user_id).with_for_update().one()
        provider_client = GooglePlayClient(settings)
        provider = provider_client.subscription(purchase_token)
        record = reconcile_google_subscription(
            db, record.user_id, purchase_token, provider, settings, provider_client, event_created,
        )
        # RTDN processing stays under one transaction/advisory lock. Renewals
        # are normally already acknowledged; a completed pending purchase is
        # acknowledged only after the authoritative state was refetched.
        if should_acknowledge(provider, record):
            provider_client.acknowledge(purchase_token)
        outcome = "reconciled"
    db.add(ProviderEventReceipt(
        provider=GOOGLE_PLAY_PROVIDER, external_event_id=message_id,
        event_type=event_type[:128], provider_created_at=event_created, outcome=outcome,
    ))
    db.commit()
    logger.info("Google Play notification processed message_id=%s outcome=%s", message_id, outcome)
    return {"received": True, "duplicate": False}


@router.post("/reconcile-batch", dependencies=[Depends(require_ingestion_key)])
def reconcile_batch(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db)):
    settings = _settings()
    # The general ingestion dependency permits development without a key.
    # Billing reconciliation must never inherit that development bypass.
    import os
    if not os.getenv("INGESTION_API_KEY", settings.ingestion_api_key):
        raise HTTPException(503, "Internal reconciliation authentication is not configured")
    reconciled, failed = reconcile_google_batch(db, settings, limit)
    db.commit()
    return {"processed": reconciled + failed, "reconciled": reconciled, "failed": failed}
