import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError
from fastapi import HTTPException

from app.config import Settings, get_settings
from app.core.entitlements import BACITY_PLUS, EntitlementService
from app.models.entitlement import (
    ConsumerBillingCustomer, ConsumerSubscription, EntitlementGrant, ProviderEventReceipt,
)
from app.models.user import User
from app.api.routes.consumer_billing import _safe_url


class FakeStripe:
    def __init__(self):
        self.customer_data = {}
        self.subscription_data = []
        self.sessions = {}
        self.created_customers = 0
        self.created_checkouts = 0
        self.cancelled = []

    def customer(self, identifier):
        return self.customer_data[identifier]

    def create_customer(self, user):
        self.created_customers += 1
        value = {"id": f"cus_{user.id}", "livemode": False,
                 "metadata": {"bacity_user_id": str(user.id)}}
        self.customer_data[value["id"]] = value
        return value

    def price(self, identifier):
        return {"id": identifier, "livemode": False, "active": True,
                "recurring": {"interval": "month"}, "product": "prod_plus"}

    def subscriptions(self, customer_id):
        return {"data": [item for item in self.subscription_data if item["customer"] == customer_id]}

    def create_checkout(self, customer_id, user_id, settings, key):
        self.created_checkouts += 1
        value = {"id": "cs_test_one", "customer": customer_id, "livemode": False,
                 "status": "open", "url": "https://checkout.stripe.com/test/session",
                 "expires_at": int(time.time()) + 1800}
        self.sessions[value["id"]] = value
        return value

    def checkout_session(self, identifier):
        return self.sessions[identifier]

    def portal(self, customer_id, settings):
        return {"url": "https://billing.stripe.com/test/session"}

    def cancel_subscription(self, identifier):
        self.cancelled.append(identifier)
        item = next(value for value in self.subscription_data if value["id"] == identifier)
        item.update(status="canceled", canceled_at=int(time.time()))
        return item


def _account(client, db, email="billing@example.com"):
    assert client.post("/auth/register", json={"email": email, "password": "password123"}).status_code == 201
    token = client.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    return db.query(User).filter_by(email=email).one(), {"Authorization": "Bearer " + token}


def _subscription(user, customer_id, status="active", *, identifier="sub_plus", price="price_plus",
                  livemode=False, cancel_at_period_end=False, period_end=None):
    now = int(time.time())
    return {
        "id": identifier, "customer": customer_id, "livemode": livemode,
        "metadata": {"bacity_user_id": str(user.id)}, "status": status,
        "current_period_start": now - 3600,
        "current_period_end": period_end or now + 86400,
        "cancel_at_period_end": cancel_at_period_end, "canceled_at": None,
        "items": {"data": [{"price": {"id": price, "product": "prod_plus"}}]},
    }


def _signature(body, secret="whsec_consumer"):
    stamp = str(int(time.time()))
    digest = hmac.new(secret.encode(), stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"t={stamp},v1={digest}"


@pytest.fixture
def billing(client, monkeypatch):
    from app.api.routes import consumer_billing
    from app.core import consumer_billing as consumer_core
    settings = get_settings()
    values = {
        "consumer_billing_enabled": True,
        "stripe_consumer_secret_key": "sk_test_consumer",
        "stripe_consumer_webhook_secret": "whsec_consumer",
        "stripe_consumer_plus_price_id": "price_plus",
        "stripe_consumer_plus_product_id": "prod_plus",
        "stripe_consumer_livemode": False,
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    fake = FakeStripe()
    monkeypatch.setattr(consumer_billing, "StripeConsumerClient", lambda ignored: fake)
    monkeypatch.setattr(consumer_core, "StripeConsumerClient", lambda ignored: fake)
    return fake


def test_configuration_is_optional_but_strict_when_enabled():
    assert Settings(consumer_billing_enabled=False, _env_file=None).consumer_billing_enabled is False
    with pytest.raises(ValidationError):
        Settings(consumer_billing_enabled=True, _env_file=None)
    with pytest.raises(ValidationError):
        Settings(
            consumer_billing_enabled=True, stripe_consumer_secret_key="sk_test_x",
            stripe_consumer_webhook_secret="whsec_x", stripe_consumer_plus_price_id="price_x",
            stripe_consumer_success_url="https://evil.example/success",
            stripe_consumer_cancel_url="http://localhost:8081/plus?billing=cancelled",
            stripe_consumer_portal_return_url="http://localhost:8081/plus", _env_file=None,
        )
    assert _safe_url("https://checkout.stripe.com/test", "checkout.stripe.com").startswith("https://")
    with pytest.raises(HTTPException):
        _safe_url("https://checkout.stripe.com.evil.example/test", "checkout.stripe.com")


def test_checkout_is_authenticated_disabled_and_server_configured(client, db_session, billing, monkeypatch):
    assert client.post("/billing/consumer/checkout").status_code == 401
    _, headers = _account(client, db_session)
    settings = get_settings()
    monkeypatch.setattr(settings, "consumer_billing_enabled", False)
    assert client.post("/billing/consumer/checkout", headers=headers).status_code == 503
    monkeypatch.setattr(settings, "consumer_billing_enabled", True)
    response = client.post("/billing/consumer/checkout?price_id=price_org", json={"customer_id": "cus_other"}, headers=headers)
    assert response.status_code == 200 and response.json()["url"].startswith("https://checkout.stripe.com/")
    assert billing.created_customers == billing.created_checkouts == 1
    assert EntitlementService(db_session).has_entitlement(db_session.query(User).filter_by(email="billing@example.com").one().id, BACITY_PLUS) is False


def test_checkout_retry_reuses_customer_and_pending_session(client, db_session, billing):
    _, headers = _account(client, db_session, "retry@example.com")
    first = client.post("/billing/consumer/checkout", headers=headers)
    second = client.post("/billing/consumer/checkout", headers=headers)
    assert first.json() == second.json()
    assert billing.created_customers == billing.created_checkouts == 1
    assert db_session.query(ConsumerBillingCustomer).count() == 1
    for _ in range(3):
        assert client.post("/billing/consumer/checkout", headers=headers).status_code == 200
    assert client.post("/billing/consumer/checkout", headers=headers).status_code == 429
    assert billing.created_customers == billing.created_checkouts == 1


def test_reconciliation_status_mapping_renewal_cancellation_and_grant(client, db_session, billing):
    user, headers = _account(client, db_session, "lifecycle@example.com")
    client.post("/billing/consumer/checkout", headers=headers)
    mapping = db_session.query(ConsumerBillingCustomer).filter_by(user_id=user.id).one()
    billing.subscription_data = [_subscription(user, mapping.external_customer_id, "active")]
    assert client.post("/billing/consumer/reconcile", headers=headers).json()["active"] is True
    assert client.post("/billing/consumer/reconcile", headers=headers).json()["active"] is True
    assert db_session.query(ConsumerSubscription).count() == 1
    first_end = db_session.query(ConsumerSubscription).one().current_period_end
    billing.subscription_data[0]["current_period_end"] += 86400
    billing.subscription_data[0]["cancel_at_period_end"] = True
    client.post("/billing/consumer/reconcile", headers=headers)
    db_session.expire_all()
    record = db_session.query(ConsumerSubscription).one()
    assert record.current_period_end > first_end and record.cancel_at_period_end is True
    for state in ("past_due", "unpaid", "canceled", "incomplete", "incomplete_expired", "paused"):
        billing.subscription_data[0]["status"] = state
        client.post("/billing/consumer/reconcile", headers=headers)
        db_session.expire_all()
        assert EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS) is False
    db_session.add(EntitlementGrant(
        user_id=user.id, entitlement=BACITY_PLUS, source="promotion", reason_category="test",
        valid_from=datetime.utcnow() - timedelta(days=1), valid_until=datetime.utcnow() + timedelta(days=1),
    )); db_session.commit()
    assert EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS) is True


def test_trialing_and_expiration_are_fail_closed(client, db_session, billing):
    user, headers = _account(client, db_session, "trial@example.com")
    client.post("/billing/consumer/checkout", headers=headers)
    mapping = db_session.query(ConsumerBillingCustomer).filter_by(user_id=user.id).one()
    billing.subscription_data = [_subscription(user, mapping.external_customer_id, "trialing")]
    client.post("/billing/consumer/reconcile", headers=headers)
    assert EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)
    record = db_session.query(ConsumerSubscription).one()
    record.current_period_end = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    assert not EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)


def test_wrong_product_customer_account_and_environment_never_grant(client, db_session, billing):
    user, headers = _account(client, db_session, "wrong@example.com")
    client.post("/billing/consumer/checkout", headers=headers)
    mapping = db_session.query(ConsumerBillingCustomer).filter_by(user_id=user.id).one()
    billing.subscription_data = [_subscription(user, mapping.external_customer_id, price="price_org")]
    client.post("/billing/consumer/reconcile", headers=headers)
    assert not EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)
    billing.subscription_data = [_subscription(user, mapping.external_customer_id, livemode=True)]
    assert client.post("/billing/consumer/reconcile", headers=headers).status_code == 409
    wrong_account = _subscription(user, mapping.external_customer_id)
    wrong_account["metadata"]["bacity_user_id"] = "00000000-0000-0000-0000-000000000000"
    billing.subscription_data = [wrong_account]
    assert client.post("/billing/consumer/reconcile", headers=headers).status_code == 409
    billing.subscription_data = [_subscription(user, "cus_wrong")]
    assert client.post("/billing/consumer/reconcile", headers=headers).status_code == 200


def test_webhook_signature_body_limit_dedup_and_current_state(client, db_session, billing):
    user, headers = _account(client, db_session, "webhook@example.com")
    client.post("/billing/consumer/checkout", headers=headers)
    mapping = db_session.query(ConsumerBillingCustomer).filter_by(user_id=user.id).one()
    billing.subscription_data = [_subscription(user, mapping.external_customer_id, "active")]
    event = {"id": "evt_consumer", "type": "customer.subscription.updated", "created": int(time.time()),
             "livemode": False, "data": {"object": {"customer": mapping.external_customer_id}}}
    body = json.dumps(event).encode()
    assert client.post("/billing/consumer/webhook", content=body).status_code == 400
    assert client.post("/billing/consumer/webhook", content=body, headers={"stripe-signature": "bad"}).status_code == 400
    good = {"stripe-signature": _signature(body)}
    assert client.post("/billing/consumer/webhook", content=body, headers=good).json()["duplicate"] is False
    assert client.post("/billing/consumer/webhook", content=body, headers=good).json()["duplicate"] is True
    assert db_session.query(ProviderEventReceipt).count() == 1
    assert EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)
    assert client.post("/billing/consumer/webhook", content=b"x" * 262145,
                       headers={"stripe-signature": "bad"}).status_code == 413
    malformed = b"{"
    assert client.post("/billing/consumer/webhook", content=malformed,
                       headers={"stripe-signature": _signature(malformed)}).status_code == 400
    unsupported = {"id": "evt_ignored", "type": "charge.succeeded", "created": int(time.time()),
                   "livemode": False, "data": {"object": {"customer": mapping.external_customer_id}}}
    unsupported_body = json.dumps(unsupported).encode()
    response = client.post("/billing/consumer/webhook", content=unsupported_body,
                           headers={"stripe-signature": _signature(unsupported_body)})
    assert response.status_code == 200 and response.json()["duplicate"] is False
    assert db_session.query(ProviderEventReceipt).filter_by(external_event_id="evt_ignored").one().outcome == "ignored"


def test_out_of_order_webhook_cannot_resurrect_cancelled_provider_state(client, db_session, billing):
    user, headers = _account(client, db_session, "ordering@example.com")
    client.post("/billing/consumer/checkout", headers=headers)
    mapping = db_session.query(ConsumerBillingCustomer).filter_by(user_id=user.id).one()
    billing.subscription_data = [_subscription(user, mapping.external_customer_id, "canceled")]
    event = {"id": "evt_old_active", "type": "customer.subscription.updated", "created": 1,
             "livemode": False, "data": {"object": {"customer": mapping.external_customer_id, "status": "active"}}}
    body = json.dumps(event).encode()
    assert client.post("/billing/consumer/webhook", content=body,
                       headers={"stripe-signature": _signature(body)}).status_code == 200
    assert not EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)


def test_portal_status_and_export_hide_provider_identifiers(client, db_session, billing):
    user, headers = _account(client, db_session, "portal@example.com")
    assert client.post("/billing/consumer/portal", headers=headers).status_code == 404
    client.post("/billing/consumer/checkout", headers=headers)
    mapping = db_session.query(ConsumerBillingCustomer).filter_by(user_id=user.id).one()
    billing.subscription_data = [_subscription(user, mapping.external_customer_id, "active", cancel_at_period_end=True)]
    client.post("/billing/consumer/reconcile", headers=headers)
    assert client.post("/billing/consumer/portal", json={"customer_id": "cus_other"}, headers=headers).json()["url"].startswith("https://billing.stripe.com/")
    status = client.get("/billing/consumer/status", headers=headers).json()
    assert status["plus_active"] and status["portal_available"] and status["cancel_at_period_end"]
    exported = client.get("/community/account/export", headers=headers)
    assert exported.status_code == 200 and exported.json()["consumer_billing"][0]["provider"] == "stripe"
    assert mapping.external_customer_id not in exported.text and "sub_plus" not in exported.text
    for _ in range(8):
        assert client.post("/billing/consumer/portal", headers=headers).status_code == 200
    assert client.post("/billing/consumer/portal", headers=headers).status_code == 429


def test_email_change_keeps_identity_and_delete_recreate_does_not_inherit(client, db_session, billing):
    user, headers = _account(client, db_session, "identity@example.com")
    client.post("/billing/consumer/checkout", headers=headers)
    mapping = db_session.query(ConsumerBillingCustomer).filter_by(user_id=user.id).one()
    billing.subscription_data = [_subscription(user, mapping.external_customer_id, "active")]
    client.post("/billing/consumer/reconcile", headers=headers)
    user.email = "changed@example.com"; db_session.commit()
    changed_token = client.post("/auth/login", json={"email": "changed@example.com", "password": "password123"}).json()["access_token"]
    headers = {"Authorization": "Bearer " + changed_token}
    assert client.get("/billing/consumer/status", headers=headers).json()["plus_active"] is True
    deleted = client.request("DELETE", "/community/account", json={"reason": "privacy"}, headers=headers)
    assert deleted.status_code == 200 and billing.cancelled == ["sub_plus"]
    assert client.post("/billing/consumer/checkout", headers=headers).status_code == 401
    new_user, new_headers = _account(client, db_session, "identity@example.com")
    assert new_user.id != user.id
    assert client.get("/billing/consumer/status", headers=new_headers).json()["plus_active"] is False
