from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.api.deps import require_plus
from app.config import Settings
from app.core.entitlements import BACITY_PLUS, EntitlementService
from app.models.community import Organization
from app.models.entitlement import ConsumerSubscription, EntitlementGrant
from app.models.user import User
from app.plus_admin import set_development_plus


def _account(client, db, email="plus@example.com"):
    client.post("/auth/register", json={"email": email, "password": "password123"})
    token = client.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    user = db.query(User).filter_by(email=email).one()
    return user, {"Authorization": f"Bearer {token}"}


def _grant(user, **overrides):
    values = {
        "user_id": user.id,
        "entitlement": BACITY_PLUS,
        "source": "test",
        "reason_category": "fixture",
        "valid_from": datetime.utcnow() - timedelta(minutes=1),
        "valid_until": datetime.utcnow() + timedelta(days=1),
    }
    values.update(overrides)
    return EntitlementGrant(**values)


def test_free_active_expired_and_revoked_grants(client, db_session):
    user, _ = _account(client, db_session)
    service = EntitlementService(db_session)
    assert service.has_entitlement(user.id, BACITY_PLUS) is False

    active = _grant(user)
    db_session.add(active); db_session.commit()
    assert service.has_entitlement(user.id, BACITY_PLUS) is True

    active.revoked_at = datetime.utcnow()
    db_session.add(_grant(user, valid_until=datetime.utcnow() - timedelta(seconds=1)))
    db_session.commit()
    assert service.has_entitlement(user.id, BACITY_PLUS) is False


def test_subscription_status_and_multiple_sources_are_provider_neutral(client, db_session):
    user, _ = _account(client, db_session)
    now = datetime.utcnow()
    expired = ConsumerSubscription(
        user_id=user.id, entitlement=BACITY_PLUS, provider="apple", product_id="plus.monthly",
        status="active", current_period_end=now - timedelta(seconds=1),
        external_subscription_id="expired-provider-id",
    )
    active = _grant(user, valid_until=now + timedelta(days=2))
    db_session.add_all([expired, active]); db_session.commit()
    state = EntitlementService(db_session).get_entitlement(user.id, BACITY_PLUS, now=now)
    assert state.active is True
    assert state.management_channel == "support"
    assert state.expires_at == active.valid_until

    db_session.add(ConsumerSubscription(
        user_id=user.id, entitlement=BACITY_PLUS, provider="stripe", product_id="plus.web",
        status="active", current_period_end=now + timedelta(days=30),
        external_customer_id="customer-secret", external_subscription_id="subscription-secret",
    ))
    db_session.commit()
    state = EntitlementService(db_session).get_entitlement(user.id, BACITY_PLUS, now=now)
    assert state.active is True and state.management_channel == "web"
    assert state.expires_at > active.valid_until


def test_entitlement_endpoint_auth_spoofing_and_private_shape(client, db_session):
    user, headers = _account(client, db_session)
    assert client.get("/users/me/entitlements").status_code == 401
    assert client.get("/users/me/entitlements", params={"is_plus": "true"}, headers=headers).json() == {
        "bacity_plus": {"active": False, "expires_at": None, "management_channel": None}
    }
    assert client.request("GET", "/users/me/entitlements", json={"is_plus": True}, headers=headers).json()["bacity_plus"]["active"] is False

    db_session.add(ConsumerSubscription(
        user_id=user.id, entitlement=BACITY_PLUS, provider="stripe", product_id="plus.web",
        status="active", current_period_end=datetime.utcnow() + timedelta(days=1),
        external_customer_id="customer-secret", external_subscription_id="subscription-secret",
    ))
    db_session.commit()
    response = client.get("/users/me/entitlements", headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["bacity_plus"]["active"] is True
    assert payload["bacity_plus"]["management_channel"] == "web"
    serialized = response.text
    assert "customer-secret" not in serialized and "subscription-secret" not in serialized
    assert "provider" not in payload["bacity_plus"]


def test_reusable_plus_requirement_rejects_free_and_accepts_plus(client, db_session):
    user, _ = _account(client, db_session)
    with pytest.raises(HTTPException) as denied:
        require_plus(current_user=user, db=db_session)
    assert denied.value.status_code == 403
    db_session.add(_grant(user)); db_session.commit()
    assert require_plus(current_user=user, db=db_session).id == user.id


def test_organization_and_consumer_entitlements_are_isolated(client, db_session):
    user, _ = _account(client, db_session)
    organization = Organization(name="Pro venue", tier="pro")
    db_session.add(organization); db_session.commit()
    assert EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS) is False

    db_session.add(_grant(user)); db_session.commit()
    assert EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS) is True
    db_session.refresh(organization)
    assert organization.tier == "pro"


def test_development_fixture_is_explicit_deterministic_and_refuses_non_development(client, db_session):
    user, _ = _account(client, db_session)
    disabled = Settings(environment="development", enable_development_plus_grants=False, _env_file=None)
    with pytest.raises(RuntimeError):
        set_development_plus(db_session, user.email, "active", disabled)

    enabled = Settings(environment="development", enable_development_plus_grants=True, _env_file=None)
    set_development_plus(db_session, user.email, "active", enabled)
    assert EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS) is True
    set_development_plus(db_session, user.email, "expired", enabled)
    assert EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS) is False
    set_development_plus(db_session, user.email, "free", enabled)
    assert EntitlementService(db_session).has_entitlement(user.id, BACITY_PLUS) is False

    with pytest.raises(Exception, match="Development BACity.*disabled"):
        Settings(
            environment="staging", enable_development_plus_grants=True,
            jwt_secret="a" * 40, ingestion_api_key="b" * 40,
            database_url="postgresql://localhost/bacity", public_app_url="https://bacity.example",
            cors_origins="https://bacity.example", _env_file=None,
        )
