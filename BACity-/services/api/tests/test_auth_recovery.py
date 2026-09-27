import hashlib
import re
from datetime import datetime, timedelta

from passlib.context import CryptContext

from app.api.routes.auth import _find_or_create_social_user
from app.core.security import hash_password, verify_password
from app.models.community import ActionToken, MailOutbox
from app.models.oauth_identity import OAuthIdentity
from app.models.user import User


def _register(client, email="recovery@example.com", password="original password"):
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return email, password


def _request_reset(client, db, email):
    response = client.post("/auth/request-reset", json={"email": email})
    assert response.status_code == 200, response.text
    db.expire_all()
    message = db.query(MailOutbox).filter_by(
        recipient=email, subject="Reset your BACity password"
    ).one()
    token = re.search(r"token=([^\s]+)", message.body).group(1)
    return response, message, token


def test_password_reset_end_to_end_and_session_invalidation(client, db_session):
    email, old_password = _register(client)
    old_session = client.post("/auth/login", json={
        "email": email, "password": old_password
    }).json()["access_token"]

    response, message, token = _request_reset(client, db_session, email)
    assert response.json() == {"detail": "If the account exists, a reset email has been queued"}
    assert "BACity" in message.body and "30 minutes" in message.body
    action = db_session.query(ActionToken).filter_by(purpose="reset").one()
    assert action.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert token != action.token_hash
    assert client.post("/auth/reset-password/status", json={"token": token}).json() == {
        "status": "valid"
    }

    new_password = "mestské heslo 🔐 with a long memorable phrase " * 4
    reset = client.post("/auth/reset-password", json={
        "token": token, "password": new_password
    })
    assert reset.status_code == 200, reset.text
    assert client.post("/auth/reset-password/status", json={"token": token}).json() == {
        "status": "used"
    }
    assert client.post("/auth/reset-password", json={
        "token": token, "password": new_password
    }).status_code == 400
    assert client.post("/auth/login", json={
        "email": email, "password": old_password
    }).status_code == 401
    assert client.post("/auth/login", json={
        "email": email, "password": new_password
    }).status_code == 200
    assert client.get("/users/me", headers={
        "Authorization": "Bearer " + old_session
    }).status_code == 401


def test_reset_request_does_not_enumerate_accounts(client, db_session):
    email, _ = _register(client)
    existing = client.post("/auth/request-reset", json={"email": email})
    missing = client.post("/auth/request-reset", json={"email": "missing@example.com"})
    assert existing.status_code == missing.status_code == 200
    assert existing.json() == missing.json()


def test_expired_invalid_and_used_reset_states(client, db_session):
    email, _ = _register(client)
    _, _, token = _request_reset(client, db_session, email)
    action = db_session.query(ActionToken).filter_by(purpose="reset").one()
    action.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()

    assert client.post("/auth/reset-password/status", json={"token": token}).json() == {
        "status": "expired"
    }
    assert client.post("/auth/reset-password", json={
        "token": token, "password": "another secure password"
    }).status_code == 400
    invalid = "invalid-reset-token-value-long-enough"
    assert client.post("/auth/reset-password/status", json={"token": invalid}).json() == {
        "status": "invalid"
    }
    assert client.post("/auth/reset-password", json={
        "token": invalid, "password": "another secure password"
    }).status_code == 400


def test_reset_request_and_attempt_rate_limits(client):
    for _ in range(3):
        assert client.post("/auth/request-reset", json={
            "email": "same-missing@example.com"
        }).status_code == 200
    limited = client.post("/auth/request-reset", json={"email": "same-missing@example.com"})
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "3600"


def test_invalid_reset_attempts_are_bounded(client):
    password = "safe password for rate-limit test"
    for attempt in range(20):
        token = f"invalid-reset-token-{attempt:02d}-long-enough"
        assert client.post("/auth/reset-password", json={
            "token": token, "password": password
        }).status_code == 400
    limited = client.post("/auth/reset-password", json={
        "token": "invalid-reset-token-final-long-enough", "password": password
    })
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "900"


def test_password_validation_and_existing_bcrypt_compatibility(client):
    assert client.post("/auth/register", json={
        "email": "short@example.com", "password": "short"
    }).status_code == 422
    assert client.post("/auth/register", json={
        "email": "spaces@example.com", "password": "        "
    }).status_code == 422
    assert client.post("/auth/register", json={
        "email": "huge@example.com", "password": "x" * 4097
    }).status_code == 422

    long_password = "unicode 🔐 passphrase " * 20
    encoded = hash_password(long_password)
    assert verify_password(long_password, encoded)
    old_context = CryptContext(schemes=["bcrypt"])
    old_hash = old_context.hash("legacy-password")
    assert verify_password("legacy-password", old_hash)


def test_reset_does_not_log_token_password_or_email(client, db_session, caplog):
    email, _ = _register(client, email="sensitive-reset@example.com")
    _, _, token = _request_reset(client, db_session, email)
    password = "unique secret passphrase 🔐"
    caplog.clear()
    assert client.post("/auth/reset-password", json={
        "token": token, "password": password
    }).status_code == 200
    assert token not in caplog.text
    assert password not in caplog.text
    assert email not in caplog.text


def test_email_verification_still_uses_single_use_action_token(client, db_session):
    email, _ = _register(client, email="verify-recovery@example.com")
    message = db_session.query(MailOutbox).filter_by(
        recipient=email, subject="Verify your BACity email"
    ).one()
    token = re.search(r"token=([^\s]+)", message.body).group(1)
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 200
    assert client.post("/auth/verify-email", json={"token": token}).status_code == 400


def test_oauth_link_survives_password_recovery(client, db_session):
    user = _find_or_create_social_user(
        db_session, "google", "recovery-google-subject", "oauth-recovery@example.com"
    )
    identity_id = db_session.query(OAuthIdentity).filter_by(user_id=user.id).one().id
    _, _, token = _request_reset(client, db_session, user.email)
    assert client.post("/auth/reset-password", json={
        "token": token, "password": "new local passphrase"
    }).status_code == 200
    assert client.post("/auth/login", json={
        "email": user.email, "password": "new local passphrase"
    }).status_code == 200
    db_session.expire_all()
    assert db_session.query(OAuthIdentity).filter_by(id=identity_id, user_id=user.id).one()
    assert db_session.query(User).filter_by(email=user.email).count() == 1
