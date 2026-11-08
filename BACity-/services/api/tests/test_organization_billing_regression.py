"""Organization Stripe remains separate from consumer provider integrations."""
import hashlib
import hmac
import json
import time

from app.config import get_settings
from app.core.entitlements import BACITY_PLUS, EntitlementService
from app.models.community import Organization, OrganizationMember
from tests.test_google_play_billing import _account


def test_organization_checkout_auth_and_consumer_isolation(client, db_session, monkeypatch):
    from app.api.routes import billing
    user, headers = _account(client, db_session, "org-billing@example.com")
    user.email_verified = True
    org = Organization(name="Organization", verified=True)
    db_session.add(org); db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=user.id))
    db_session.commit()
    s = get_settings()
    monkeypatch.setattr(s, "stripe_secret_key", "org-secret")
    monkeypatch.setattr(s, "stripe_webhook_secret", "org-webhook")
    monkeypatch.setattr(s, "stripe_pro_price_id", "price_org")
    calls = []
    def provider(method, path, data=None, key=None):
        calls.append((path, data))
        return {"id": "cus_org"} if path == "customers" else {"url": "https://checkout.stripe.com/organization"}
    monkeypatch.setattr(billing, "stripe", provider)
    payload = {"organization_id": str(org.id), "tier": "pro"}
    assert client.post("/billing/checkout", json=payload).status_code == 401
    assert client.post("/billing/checkout", json=payload, headers=headers).status_code == 200
    assert calls[1][1]["line_items[0][price]"] == "price_org"
    assert not EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)


def test_organization_webhook_does_not_grant_consumer_plus(client, db_session, monkeypatch):
    from app.api.routes import billing
    user, _ = _account(client, db_session, "org-webhook@example.com")
    org = Organization(name="Organization", verified=True, stripe_customer_id="cus_org")
    db_session.add(org); db_session.commit()
    s = get_settings()
    monkeypatch.setattr(s, "stripe_secret_key", "org-secret")
    monkeypatch.setattr(s, "stripe_webhook_secret", "org-webhook")
    monkeypatch.setattr(s, "stripe_pro_price_id", "price_org")
    monkeypatch.setattr(billing, "stripe", lambda *args: {"data": [{
        "id": "sub_org", "status": "active", "items": {"data": [{"price": {"id": "price_org"}}]},
    }]})
    body = json.dumps({"id": "org-event", "type": "customer.subscription.updated", "data": {"object": {"customer": "cus_org"}}}).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(b"org-webhook", stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    headers = {"Stripe-Signature": f"t={stamp},v1={signature}"}
    assert client.post("/billing/webhook", content=body).status_code == 400
    assert client.post("/billing/webhook", content=body, headers=headers).status_code == 200
    assert client.post("/billing/webhook", content=body, headers=headers).status_code == 200
    db_session.refresh(org)
    assert org.tier == "pro" and org.stripe_subscription_id == "sub_org"
    assert not EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)
