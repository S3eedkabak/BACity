import base64
import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.config import Settings, get_settings
from app.core.entitlements import BACITY_PLUS, EntitlementService
from app.core.google_play_billing import GOOGLE_PLAY_PROVIDER, obfuscated_account_id
from app.models.entitlement import ConsumerSubscription, ProviderEventReceipt
from app.models.user import User


SERVICE_ACCOUNT = json.dumps({
    "client_email": "play-api@example.iam.gserviceaccount.com",
    "private_key": "-----BEGIN PRIVATE KEY-----\nfake\n-----END PRIVATE KEY-----\n",
    "token_uri": "https://oauth2.googleapis.com/token",
})


def _account(client, db, email="play@example.com"):
    client.post("/auth/register", json={"email": email, "password": "password123"})
    token = client.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    return db.query(User).filter_by(email=email).one(), {"Authorization": "Bearer " + token}


def _provider(user, state="SUBSCRIPTION_STATE_ACTIVE", *, product="plus.monthly",
              expiry=None, acknowledged=False, account=True, base_plan="monthly"):
    expiry = expiry or datetime.now(timezone.utc) + timedelta(days=30)
    start = min(datetime.now(timezone.utc) - timedelta(days=1), expiry - timedelta(days=30))
    return {
        "startTime": start.isoformat(),
        "subscriptionState": state,
        "acknowledgementState": "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED" if acknowledged else "ACKNOWLEDGEMENT_STATE_PENDING",
        "externalAccountIdentifiers": {"obfuscatedExternalAccountId": obfuscated_account_id(user.id)} if account else {},
        "lineItems": [{
            "productId": product, "expiryTime": expiry.isoformat(),
            "autoRenewingPlan": {"autoRenewEnabled": state == "SUBSCRIPTION_STATE_ACTIVE"},
            "offerDetails": {"basePlanId": base_plan},
        }],
    }


class FakeGoogle:
    def __init__(self):
        self.purchases = {}
        self.acknowledged = []
        self.fail = False

    def subscription(self, token):
        if self.fail or token not in self.purchases:
            raise HTTPException(502, "Billing provider unavailable; please try again")
        return self.purchases[token]

    def acknowledge(self, token):
        self.acknowledged.append(token)
        self.purchases[token]["acknowledgementState"] = "ACKNOWLEDGEMENT_STATE_ACKNOWLEDGED"


@pytest.fixture
def play(monkeypatch):
    from app.api.routes import google_play_billing as route
    from app.core import google_play_billing as core
    settings = get_settings()
    values = {
        "google_play_billing_enabled": True,
        "google_play_package_name": "com.bratislavaevents.app",
        "google_play_subscription_product_id": "plus.monthly",
        "google_play_base_plan_id": "monthly",
        "google_play_service_account_json": SERVICE_ACCOUNT,
        "google_play_rtdn_audience": "https://api.example/billing/google-play/rtdn",
        "google_play_rtdn_service_account_email": "pubsub@example.iam.gserviceaccount.com",
    }
    for key, value in values.items():
        monkeypatch.setattr(settings, key, value)
    fake = FakeGoogle()
    monkeypatch.setattr(core, "GooglePlayClient", lambda ignored: fake)
    monkeypatch.setattr(route, "GooglePlayClient", lambda ignored: fake)
    monkeypatch.setattr(route, "verify_pubsub_oidc", lambda token, ignored: None if token == "valid-oidc" else (_ for _ in ()).throw(HTTPException(401)))
    return fake


def test_configuration_is_optional_and_fails_safely():
    assert Settings(google_play_billing_enabled=False, _env_file=None).google_play_billing_enabled is False
    with pytest.raises(ValidationError):
        Settings(google_play_billing_enabled=True, _env_file=None)
    configured = Settings(
        google_play_billing_enabled=True,
        google_play_package_name="com.bratislavaevents.app",
        google_play_subscription_product_id="plus.monthly",
        google_play_service_account_json=SERVICE_ACCOUNT, _env_file=None,
    )
    assert configured.google_play_billing_enabled


def test_verification_auth_product_spoofing_and_provider_failure(client, db_session, play):
    payload = {"purchase_token": "token-valid-0001", "product_id": "plus.monthly"}
    assert client.post("/billing/google-play/verify", json=payload).status_code == 401
    user, headers = _account(client, db_session)
    play.purchases[payload["purchase_token"]] = _provider(user)
    forged = {**payload, "product_id": "org.pro", "active": True, "expiry": "2099-01-01", "package_name": "evil.app"}
    assert client.post("/billing/google-play/verify", json=forged, headers=headers).status_code == 400
    play.fail = True
    assert client.post("/billing/google-play/verify", json=payload, headers=headers).status_code == 502
    assert not EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)


def test_active_purchase_is_bound_acknowledged_and_idempotent(client, db_session, play):
    user, headers = _account(client, db_session, "active-play@example.com")
    token = "sensitive-purchase-token-active"
    play.purchases[token] = _provider(user)
    payload = {"purchase_token": token, "product_id": "plus.monthly"}
    first = client.post("/billing/google-play/verify", json=payload, headers=headers)
    second = client.post("/billing/google-play/verify", json=payload, headers=headers)
    assert first.status_code == second.status_code == 200
    assert first.json()["active"] is True and first.json()["management_channel"] == "play_store"
    assert token not in first.text
    assert db_session.query(ConsumerSubscription).filter_by(provider=GOOGLE_PLAY_PROVIDER).count() == 1
    assert play.acknowledged == [token]
    exported = client.get("/community/account/export", headers=headers)
    assert token not in exported.text and exported.json()["consumer_billing"][0]["provider"] == GOOGLE_PLAY_PROVIDER


def test_state_mapping_cancelled_valid_expired_grace_hold_paused_pending(client, db_session, play):
    user, headers = _account(client, db_session, "states-play@example.com")
    token = "state-purchase-token-0001"
    payload = {"purchase_token": token, "product_id": "plus.monthly"}
    future = datetime.now(timezone.utc) + timedelta(days=2)
    play.purchases[token] = _provider(user, "SUBSCRIPTION_STATE_CANCELED", expiry=future, acknowledged=True)
    response = client.post("/billing/google-play/verify", json=payload, headers=headers).json()
    assert response["active"] and response["cancel_at_period_end"]
    for state, expected in (
        ("SUBSCRIPTION_STATE_EXPIRED", "expired"),
        ("SUBSCRIPTION_STATE_IN_GRACE_PERIOD", "grace_period"),
        ("SUBSCRIPTION_STATE_ON_HOLD", "on_hold"),
        ("SUBSCRIPTION_STATE_PAUSED", "paused"),
        ("SUBSCRIPTION_STATE_PENDING", "pending"),
    ):
        play.purchases[token] = _provider(user, state, expiry=future, acknowledged=True)
        result = client.post("/billing/google-play/verify", json=payload, headers=headers)
        assert result.status_code == 200 and result.json()["active"] is False
        assert result.json()["subscription_status"] == expected
    play.purchases[token] = _provider(user, "SUBSCRIPTION_STATE_CANCELED", expiry=datetime.now(timezone.utc) - timedelta(seconds=1), acknowledged=True)
    result = client.post("/billing/google-play/verify", json=payload, headers=headers)
    assert result.json()["subscription_status"] == "expired" and not result.json()["active"]


def test_wrong_product_base_plan_and_account_binding_are_rejected(client, db_session, play):
    first, first_headers = _account(client, db_session, "owner-play@example.com")
    second, second_headers = _account(client, db_session, "thief-play@example.com")
    payload = {"purchase_token": "ownership-purchase-token", "product_id": "plus.monthly"}
    play.purchases[payload["purchase_token"]] = _provider(first, product="wrong.product")
    assert client.post("/billing/google-play/verify", json=payload, headers=first_headers).status_code == 400
    play.purchases[payload["purchase_token"]] = _provider(first, base_plan="annual")
    assert client.post("/billing/google-play/verify", json=payload, headers=first_headers).status_code == 400
    play.purchases[payload["purchase_token"]] = _provider(first)
    assert client.post("/billing/google-play/verify", json=payload, headers=first_headers).status_code == 200
    assert client.post("/billing/google-play/verify", json=payload, headers=second_headers).status_code == 409
    assert not EntitlementService(db_session).has_entitlement(second.id, BACITY_PLUS)


def _rtdn(token, message_id="message-1", event_time=None):
    notification = {
        "version": "1.0", "packageName": "com.bratislavaevents.app",
        "eventTimeMillis": str(event_time or int(datetime.now(timezone.utc).timestamp() * 1000)),
        "subscriptionNotification": {
            "version": "1.0", "notificationType": 3,
            "purchaseToken": token,
        },
    }
    return {"message": {"messageId": message_id, "data": base64.b64encode(json.dumps(notification).encode()).decode()}}


def test_rtdn_auth_replay_unknown_and_current_state_refetch(client, db_session, play):
    user, headers = _account(client, db_session, "rtdn-play@example.com")
    token = "rtdn-purchase-token-0001"
    play.purchases[token] = _provider(user, acknowledged=True)
    client.post("/billing/google-play/verify", json={"purchase_token": token, "product_id": "plus.monthly"}, headers=headers)
    body = _rtdn(token)
    assert client.post("/billing/google-play/rtdn", json=body).status_code == 401
    assert client.post("/billing/google-play/rtdn", json=body, headers={"Authorization": "Bearer invalid"}).status_code == 401
    auth = {"Authorization": "Bearer valid-oidc"}
    play.purchases[token] = _provider(user, "SUBSCRIPTION_STATE_EXPIRED", expiry=datetime.now(timezone.utc) - timedelta(seconds=1), acknowledged=True)
    first = client.post("/billing/google-play/rtdn", json=body, headers=auth)
    replay = client.post("/billing/google-play/rtdn", json=body, headers=auth)
    assert first.json()["duplicate"] is False and replay.json()["duplicate"] is True
    assert not EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)
    voided = {"packageName": "com.bratislavaevents.app", "eventTimeMillis": "1000",
              "voidedPurchaseNotification": {"purchaseToken": token, "productType": 1, "refundType": 1}}
    voided_body = {"message": {"messageId": "voided-message", "data": base64.b64encode(json.dumps(voided).encode()).decode()}}
    assert client.post("/billing/google-play/rtdn", json=voided_body, headers=auth).status_code == 200
    unknown = client.post("/billing/google-play/rtdn", json=_rtdn("unknown-token-0000", "message-2"), headers=auth)
    assert unknown.status_code == 200
    assert db_session.query(ProviderEventReceipt).filter_by(external_event_id="message-2").one().outcome == "ignored"


def test_reconcile_restore_and_cross_provider_aggregation(client, db_session, play, monkeypatch):
    user, headers = _account(client, db_session, "multi-provider@example.com")
    token = "restore-purchase-token-0001"
    play.purchases[token] = _provider(user, acknowledged=True)
    assert client.post("/billing/google-play/verify", json={"purchase_token": token, "product_id": "plus.monthly"}, headers=headers).status_code == 200
    play.purchases[token] = _provider(user, "SUBSCRIPTION_STATE_EXPIRED", expiry=datetime.now(timezone.utc) - timedelta(days=1), acknowledged=True)
    db_session.add(ConsumerSubscription(
        user_id=user.id, entitlement=BACITY_PLUS, provider="stripe", product_id="price_plus",
        status="active", current_period_end=datetime.utcnow() + timedelta(days=10),
        external_subscription_id="stripe-active-id",
    )); db_session.commit()
    result = client.post("/billing/google-play/reconcile", headers=headers)
    assert result.status_code == 200 and result.json()["active"] is True
    assert EntitlementService(db_session).get_entitlement(user.id, BACITY_PLUS).management_channel == "web"
    monkeypatch.setenv("INGESTION_API_KEY", "internal-reconcile-key")
    assert client.post("/billing/google-play/reconcile-batch").status_code == 401
    batch = client.post("/billing/google-play/reconcile-batch?limit=1",
                        headers={"X-Ingestion-Key": "internal-reconcile-key"})
    assert batch.status_code == 200 and batch.json()["processed"] == 1


def test_duplicate_provider_protection_and_account_deletion(client, db_session, play):
    user, headers = _account(client, db_session, "delete-play@example.com")
    db_session.add(ConsumerSubscription(
        user_id=user.id, entitlement=BACITY_PLUS, provider="stripe", product_id="price_plus",
        status="active", current_period_end=datetime.utcnow() + timedelta(days=2),
        external_subscription_id="stripe-existing",
    )); db_session.commit()
    token = "duplicate-provider-token-0001"
    play.purchases[token] = _provider(user)
    assert client.get("/billing/google-play/config", headers=headers).json()["active_paid_other_provider"] is True
    assert client.post("/billing/google-play/verify", json={"purchase_token": token, "product_id": "plus.monthly"}, headers=headers).status_code == 409
    stripe = db_session.query(ConsumerSubscription).filter_by(provider="stripe").one()
    stripe.status = "expired"; stripe.current_period_end = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    assert client.post("/billing/google-play/verify", json={"purchase_token": token, "product_id": "plus.monthly"}, headers=headers).status_code == 200
    deleted = client.request("DELETE", "/community/account", json={"reason": "privacy"}, headers=headers)
    assert deleted.status_code == 409 and "Google Play" in deleted.json()["detail"]
    record = db_session.query(ConsumerSubscription).filter_by(provider=GOOGLE_PLAY_PROVIDER).one()
    record.status = "expired"; record.expires_at = datetime.utcnow() - timedelta(seconds=1)
    play.purchases[token] = _provider(user, "SUBSCRIPTION_STATE_EXPIRED", expiry=datetime.now(timezone.utc) - timedelta(seconds=1), acknowledged=True)
    db_session.commit()
    deleted = client.request("DELETE", "/community/account", json={"reason": "privacy"}, headers=headers)
    assert deleted.status_code == 200
    assert db_session.query(ConsumerSubscription).filter_by(provider=GOOGLE_PLAY_PROVIDER).count() == 0


def test_missing_binding_token_length_privacy_and_replacement(client, db_session, play):
    user, headers = _account(client, db_session, "new-binding@example.com")
    token = "secret-" + "x" * 500
    payload = {"purchase_token": token, "product_id": "plus.monthly"}
    play.purchases[token] = _provider(user, account=False)
    assert client.post("/billing/google-play/verify", json=payload, headers=headers).status_code == 409
    play.purchases[token] = _provider(user)
    assert client.post("/billing/google-play/verify", json=payload, headers=headers).status_code == 200
    row = db_session.query(ConsumerSubscription).filter_by(provider=GOOGLE_PLAY_PROVIDER).one()
    assert len(row.external_subscription_id) == 64 and row.provider_purchase_token == token
    assert token not in client.get("/community/account/export", headers=headers).text
    bad = "sensitive-" + "y" * 4100
    response = client.post("/billing/google-play/verify", json={**payload, "purchase_token": bad}, headers=headers)
    assert response.status_code == 422 and bad not in response.text
    replacement = "replacement-token-0001"
    play.purchases[replacement] = {**_provider(user), "linkedPurchaseToken": token}
    assert client.post("/billing/google-play/verify", json={**payload, "purchase_token": replacement}, headers=headers).status_code == 200
    db_session.refresh(row)
    assert row.status == "replaced"
    assert client.post("/billing/google-play/verify", json=payload, headers=headers).status_code == 409


def test_first_claim_wrong_account_and_foreign_linked_token(client, db_session, play):
    owner, owner_headers = _account(client, db_session, "first-owner@example.com")
    thief, thief_headers = _account(client, db_session, "first-thief@example.com")
    token = "first-claim-token-0001"
    payload = {"purchase_token": token, "product_id": "plus.monthly"}
    play.purchases[token] = _provider(owner)
    assert client.post("/billing/google-play/verify", json=payload, headers=thief_headers).status_code == 409
    assert client.post("/billing/google-play/verify", json=payload, headers=owner_headers).status_code == 200
    play.purchases["foreign-linked-token"] = {**_provider(thief), "linkedPurchaseToken": token}
    assert client.post("/billing/google-play/verify", json={**payload, "purchase_token": "foreign-linked-token"}, headers=thief_headers).status_code == 409


def test_hold_grace_and_provider_failure_block_deletion(client, db_session, play):
    user, headers = _account(client, db_session, "hold-delete@example.com")
    token = "hold-delete-token-0001"
    play.purchases[token] = _provider(user, "SUBSCRIPTION_STATE_ON_HOLD", acknowledged=True)
    client.post("/billing/google-play/verify", json={"purchase_token": token, "product_id": "plus.monthly"}, headers=headers)
    for state in ("SUBSCRIPTION_STATE_ON_HOLD", "SUBSCRIPTION_STATE_IN_GRACE_PERIOD", "SUBSCRIPTION_STATE_PAUSED"):
        play.purchases[token] = _provider(user, state, acknowledged=True)
        assert client.request("DELETE", "/community/account", json={"reason": "privacy"}, headers=headers).status_code == 409
    play.fail = True
    assert client.request("DELETE", "/community/account", json={"reason": "privacy"}, headers=headers).status_code == 502


def test_test_notification_out_of_order_failure_retry_and_batch_isolation(client, db_session, play, monkeypatch):
    user, headers = _account(client, db_session, "retry-play@example.com")
    token = "retry-play-token-0001"
    play.purchases[token] = _provider(user, acknowledged=True)
    client.post("/billing/google-play/verify", json={"purchase_token": token, "product_id": "plus.monthly"}, headers=headers)
    auth = {"Authorization": "Bearer valid-oidc"}
    body = _rtdn(token, "retry-message")
    play.fail = True
    assert client.post("/billing/google-play/rtdn", json=body, headers=auth).status_code == 502
    assert db_session.query(ProviderEventReceipt).count() == 0
    play.fail = False
    assert client.post("/billing/google-play/rtdn", json=body, headers=auth).status_code == 200
    play.purchases[token] = _provider(user, "SUBSCRIPTION_STATE_EXPIRED", expiry=datetime.now(timezone.utc) - timedelta(days=1), acknowledged=True)
    # An older delivered event still refetches today's authoritative state.
    assert client.post("/billing/google-play/rtdn", json=_rtdn(token, "old-message", 1000), headers=auth).status_code == 200
    assert not EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS)
    notification = {"packageName": "com.bratislavaevents.app", "testNotification": {"version": "1.0"}}
    body = {"message": {"messageId": "console-test", "data": base64.b64encode(json.dumps(notification).encode()).decode()}}
    assert client.post("/billing/google-play/rtdn", json=body, headers=auth).json()["test"]
    monkeypatch.setenv("INGESTION_API_KEY", "internal-reconcile-key")
    play.fail = True
    result = client.post("/billing/google-play/reconcile-batch", headers={"X-Ingestion-Key": "internal-reconcile-key"})
    assert result.status_code == 200 and result.json()["failed"] == 1


def test_ack_failure_is_retryable_and_expired_other_provider_does_not_block(client, db_session, play, monkeypatch):
    user, headers = _account(client, db_session, "ack-retry@example.com")
    db_session.add(ConsumerSubscription(
        user_id=user.id, entitlement=BACITY_PLUS, provider="stripe", product_id="price_plus",
        status="active", current_period_end=datetime.utcnow() - timedelta(days=1),
        external_subscription_id="stale-stripe-status",
    )); db_session.commit()
    token = "ack-retry-token-0001"
    play.purchases[token] = _provider(user)
    original = play.acknowledge
    def fail_ack(ignored):
        raise HTTPException(502, "Billing provider unavailable")
    monkeypatch.setattr(play, "acknowledge", fail_ack)
    payload = {"purchase_token": token, "product_id": "plus.monthly"}
    assert client.post("/billing/google-play/verify", json=payload, headers=headers).status_code == 502
    assert db_session.query(ConsumerSubscription).filter_by(provider=GOOGLE_PLAY_PROVIDER).count() == 1
    monkeypatch.setattr(play, "acknowledge", original)
    assert client.post("/billing/google-play/verify", json=payload, headers=headers).json()["active"]
    assert play.acknowledged == [token]


def test_transport_uses_server_package_and_redacts_httpx_urls(monkeypatch, caplog):
    import logging
    import httpx
    from app.core.google_play_billing import GooglePlayClient
    settings = get_settings()
    monkeypatch.setattr(settings, "google_play_package_name", "server.package")
    adapter = GooglePlayClient(settings)
    monkeypatch.setattr(adapter, "_access_token", lambda: "access-secret")
    token = "sensitive-transport-token"
    urls = []
    def request(method, url, **kwargs):
        urls.append(url)
        logging.getLogger("httpx").info("HTTP Request: %s %s", method, url)
        return httpx.Response(404, request=httpx.Request(method, url))
    monkeypatch.setattr(httpx, "request", request)
    with caplog.at_level(logging.INFO):
        with pytest.raises(HTTPException) as error:
            adapter.subscription(token)
    assert error.value.status_code == 502
    assert "/applications/server.package/" in urls[0]
    assert token not in caplog.text and "access-secret" not in caplog.text


def test_oidc_signature_audience_email_and_expiry(monkeypatch):
    import httpx
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    from jose import jwt
    from app.core.google_play_billing import verify_pubsub_oidc
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    public = key.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    monkeypatch.setattr(httpx, "get", lambda *args, **kwargs: httpx.Response(200, json={"test-key": public.decode()}))
    settings = get_settings()
    monkeypatch.setattr(settings, "google_play_rtdn_audience", "https://api.example/rtdn")
    monkeypatch.setattr(settings, "google_play_rtdn_service_account_email", "pubsub@example.com")
    now = int(datetime.now(timezone.utc).timestamp())
    claims = {"iss": "https://accounts.google.com", "aud": settings.google_play_rtdn_audience,
              "email": settings.google_play_rtdn_service_account_email, "email_verified": True,
              "iat": now, "exp": now + 60}
    def encoded(data):
        return jwt.encode(data, private, algorithm="RS256", headers={"kid": "test-key"})
    verify_pubsub_oidc(encoded(claims), settings)
    for invalid in ({"aud": "wrong"}, {"email": "wrong@example.com"}, {"email_verified": False}, {"exp": now - 60}, {"iss": "https://evil.example"}):
        with pytest.raises(HTTPException) as error:
            verify_pubsub_oidc(encoded({**claims, **invalid}), settings)
        assert error.value.status_code == 401
