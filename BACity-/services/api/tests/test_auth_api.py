def test_register_and_login(client):
    resp = client.post("/auth/register", json={
        "email": "student@example.com",
        "password": "hunter22",
        "display_name": "Test Student",
    })
    assert resp.status_code == 201
    assert resp.json()["email"] == "student@example.com"

    resp = client.post("/auth/login", json={
        "email": "student@example.com",
        "password": "hunter22",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    assert token

    resp = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "student@example.com"


def test_login_wrong_password(client):
    client.post("/auth/register", json={"email": "a@b.com", "password": "correct"})
    resp = client.post("/auth/login", json={"email": "a@b.com", "password": "wrong"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    resp = client.get("/users/me")
    assert resp.status_code == 401


def test_update_interests(client):
    client.post("/auth/register", json={"email": "c@d.com", "password": "pw123456"})
    token = client.post("/auth/login", json={"email": "c@d.com", "password": "pw123456"}).json()["access_token"]
    resp = client.patch(
        "/users/me",
        json={"interests": ["techno", "student", "free"]},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["interests"] == ["techno", "student", "free"]


def _oauth_state(location: str) -> str:
    from urllib.parse import parse_qs, urlparse
    return parse_qs(urlparse(location).query)["state"][0]


def _exchange_from_redirect(client, location: str):
    from urllib.parse import parse_qs, urlparse
    code = parse_qs(urlparse(location).query)["code"][0]
    response = client.post("/auth/oauth/exchange", json={"code": code})
    assert response.status_code == 200
    return response.json()["access_token"]


def test_google_oauth_creates_bacity_session(client, monkeypatch):
    from app.api.routes import auth

    monkeypatch.setattr(auth.settings, "google_oauth_client_id", "google-client")
    monkeypatch.setattr(auth.settings, "google_oauth_client_secret", "google-secret")
    start = client.get("/auth/oauth/google/start", follow_redirects=False)
    assert start.status_code in (302, 307)
    state = _oauth_state(start.headers["location"])

    monkeypatch.setattr(
        auth,
        "_google_identity",
        lambda code: ("google-subject", "google@example.com", "Google User", None),
    )
    callback = client.get(
        "/auth/oauth/google/callback",
        params={"code": "provider-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"].startswith("bratislava-events://oauth?code=")

    token = _exchange_from_redirect(client, callback.headers["location"])
    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "google@example.com"
    assert me.json()["email_verified"] is True


def test_apple_oauth_creates_bacity_session(client, monkeypatch):
    from app.api.routes import auth

    monkeypatch.setattr(auth.settings, "apple_oauth_client_id", "com.example.bacity.web")
    monkeypatch.setattr(auth.settings, "apple_team_id", "TEAM123")
    monkeypatch.setattr(auth.settings, "apple_key_id", "KEY123")
    monkeypatch.setattr(auth.settings, "apple_private_key", "fake-key")
    start = client.get("/auth/oauth/apple/start", follow_redirects=False)
    assert start.status_code in (302, 307)
    state = _oauth_state(start.headers["location"])

    monkeypatch.setattr(
        auth,
        "_apple_identity",
        lambda code: ("apple-subject", "apple@example.com", None),
    )
    callback = client.post(
        "/auth/oauth/apple/callback",
        data={"code": "provider-code", "state": state},
        follow_redirects=False,
    )
    assert callback.status_code == 303
    assert callback.headers["location"].startswith("bratislava-events://oauth?code=")

    token = _exchange_from_redirect(client, callback.headers["location"])
    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "apple@example.com"
    assert me.json()["email_verified"] is True
    assert client.post("/auth/oauth/exchange", json={"code": __import__('urllib.parse').parse.parse_qs(__import__('urllib.parse').parse.urlparse(callback.headers['location']).query)['code'][0]}).status_code == 400


def test_oauth_duplicate_email_links_one_account(client, db_session):
    from app.api.routes.auth import _find_or_create_social_user
    from app.models.oauth_identity import OAuthIdentity
    from app.models.user import User

    client.post('/auth/register', json={'email': 'same@example.com', 'password': 'password123'})
    existing = db_session.query(User).filter_by(email='same@example.com').one()
    google_user = _find_or_create_social_user(
        db_session, 'google', 'google-subject', ' SAME@example.com ', 'Provider Name'
    )
    apple_user = _find_or_create_social_user(
        db_session, 'apple', 'apple-subject', 'same@example.com'
    )
    assert google_user.id == existing.id == apple_user.id
    assert existing.email_verified is True
    assert db_session.query(User).filter_by(email='same@example.com').count() == 1
    assert db_session.query(OAuthIdentity).filter_by(user_id=existing.id).count() == 2


def test_oauth_identity_without_email_only_reuses_existing_link(client, db_session):
    from fastapi import HTTPException
    from app.api.routes.auth import _find_or_create_social_user

    with __import__('pytest').raises(HTTPException):
        _find_or_create_social_user(db_session, 'apple', 'private-relay-subject', None)
    linked = _find_or_create_social_user(
        db_session, 'apple', 'private-relay-subject', 'relay@privaterelay.appleid.com'
    )
    reused = _find_or_create_social_user(
        db_session, 'apple', 'private-relay-subject', None
    )
    assert reused.id == linked.id


def test_native_apple_validates_code_creates_session_and_blocks_replay(client, monkeypatch):
    from cryptography.fernet import Fernet
    from app.api.routes import auth
    monkeypatch.setattr(auth.settings, 'apple_ios_client_id', 'com.bratislavaevents.app')
    monkeypatch.setattr(auth.settings, 'apple_team_id', 'TEAM')
    monkeypatch.setattr(auth.settings, 'apple_key_id', 'KEY')
    monkeypatch.setattr(auth.settings, 'apple_private_key', 'PRIVATE')
    monkeypatch.setattr(auth.settings, 'oauth_token_encryption_key', Fernet.generate_key().decode())
    monkeypatch.setattr(auth, '_apple_token_claims', lambda token, audience: {
        'sub': 'native-apple-subject', 'email': 'relay@privaterelay.appleid.com'
    })
    monkeypatch.setattr(auth, '_apple_token_exchange', lambda code, client_id, redirect_uri=None: {
        'id_token': 'server-token', 'refresh_token': 'refresh-secret'
    })
    body = {'provider': 'apple', 'identity_token': 'native-identity-token-long-enough',
            'authorization_code': 'apple-code', 'display_name': 'Private User'}
    response = client.post('/auth/oauth/native', json=body)
    assert response.status_code == 200, response.text
    token = response.json()['access_token']
    me = client.get('/users/me', headers={'Authorization': 'Bearer ' + token}).json()
    assert me['email'] == 'relay@privaterelay.appleid.com'
    assert client.post('/auth/oauth/native', json=body).status_code == 409


def test_native_provider_collision_does_not_move_identity(client, db_session, monkeypatch):
    from app.api.routes import auth
    from app.models.oauth_identity import OAuthIdentity
    from app.models.user import User
    monkeypatch.setattr(auth.settings, 'google_oauth_client_id', 'web-client')
    monkeypatch.setattr(auth.settings, 'google_android_client_id', 'android-client')
    monkeypatch.setattr(auth, '_google_native_identity', lambda token: (
        'shared-google-subject', 'first@example.com', 'First', None
    ))
    client.post('/auth/register', json={'email': 'first@example.com', 'password': 'password123'})
    first = db_session.query(User).filter_by(email='first@example.com').one()
    db_session.add(OAuthIdentity(user_id=first.id, provider='google', subject='shared-google-subject'))
    db_session.commit()
    client.post('/auth/register', json={'email': 'second@example.com', 'password': 'password123'})
    token = client.post('/auth/login', json={'email': 'second@example.com', 'password': 'password123'}).json()['access_token']
    response = client.post('/auth/oauth/native', json={
        'provider': 'google', 'identity_token': 'google-token-long-enough-for-validation'
    }, headers={'Authorization': 'Bearer ' + token})
    assert response.status_code == 409
    db_session.expire_all()
    assert db_session.query(OAuthIdentity).filter_by(subject='shared-google-subject').one().user_id == first.id


def test_apple_revocation_uses_the_client_that_issued_the_token(monkeypatch):
    from cryptography.fernet import Fernet
    from app.api.routes import auth

    monkeypatch.setattr(auth.settings, 'oauth_token_encryption_key', Fernet.generate_key().decode())
    monkeypatch.setattr(auth, '_apple_client_secret', lambda client_id: 'signed-for:' + client_id)
    captured = {}

    class Response:
        status_code = 200

    def post(url, data, timeout):
        captured.update(data)
        return Response()

    monkeypatch.setattr(auth.httpx, 'post', post)
    credential = auth._encrypt_provider_token('refresh-token', 'com.example.web-service')
    assert auth.revoke_apple_token(credential, 'com.example.native') is True
    assert captured == {
        'client_id': 'com.example.web-service',
        'client_secret': 'signed-for:com.example.web-service',
        'token': 'refresh-token',
        'token_type_hint': 'refresh_token',
    }
