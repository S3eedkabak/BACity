"""Adversarial boundary tests; all provider credentials and accounts are fixtures."""
import base64
import json
import logging
import re
import smtplib
import ssl
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from jose import jwt
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.config import Settings, get_settings
from app.core.http import RequestMiddleware
from app.core.security import decode_access_token, token_version
from app.models.community import Follow, MailOutbox
from app.models.oauth_identity import OAuthIdentity
from tests.test_community import account


@pytest.mark.parametrize('path,payload,secret', [
    ('/auth/register', {'email': 'invalid', 'password': 'pvt!'}, 'pvt!'),
    ('/auth/login', {'email': 'invalid', 'password': 'private-password'}, 'private-password'),
    ('/auth/reset-password', {'token': 'private-token', 'password': 'x'}, 'private-token'),
    ('/auth/oauth/native', {'provider': 'invalid', 'identity_token': 'private-jwt'}, 'private-jwt'),
])
def test_validation_does_not_echo_sensitive_input(client, path, payload, secret):
    response = client.post(path, json=payload)
    assert response.status_code == 422
    assert secret not in response.text
    assert all('input' not in error and 'ctx' not in error for error in response.json()['detail'])


@pytest.mark.parametrize('claims', [
    {'sub': 'owner@example.com'}, {'exp': datetime.utcnow() + timedelta(minutes=5)},
    {'sub': '', 'exp': datetime.utcnow() + timedelta(minutes=5)},
])
def test_access_token_requires_subject_and_expiry(claims):
    settings = get_settings()
    token = jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    assert decode_access_token(token) is None


@pytest.mark.parametrize('version', ['0', True, -1, {}, None])
def test_session_version_must_be_nonnegative_integer(version):
    settings = get_settings()
    token = jwt.encode({'sub': 'owner@example.com', 'exp': datetime.utcnow() + timedelta(minutes=5),
                        'ver': version}, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    assert token_version(token) is None


@pytest.mark.parametrize('url', [
    '/events/viewport?min_lat=48&max_lat=49&min_lng=17&max_lng=18&limit=-1',
    '/events/viewport?min_lat=49&max_lat=48&min_lng=17&max_lng=18',
    '/events/viewport?min_lat=nan&max_lat=49&min_lng=17&max_lng=18',
    '/events/nearby?lat=48&lng=17&limit=0', '/events/nearby?lat=inf&lng=17',
    '/events/nearby?lat=48&lng=181',
])
def test_map_queries_cannot_remove_limits_or_supply_invalid_coordinates(client, url):
    assert client.get(url).status_code == 422


def test_browser_oauth_state_cannot_be_transferred_or_replayed(client, monkeypatch):
    from app.api.routes import auth
    monkeypatch.setattr(auth.settings, 'google_oauth_client_id', 'test-client')
    monkeypatch.setattr(auth.settings, 'google_oauth_client_secret', 'test-secret')
    first = client.get('/auth/oauth/google/start', follow_redirects=False)
    state = parse_qs(urlsplit(first.headers['location']).query)['state'][0]
    second = client.get('/auth/oauth/google/start', follow_redirects=False)
    assert state != parse_qs(urlsplit(second.headers['location']).query)['state'][0]
    with patch.object(auth, '_google_identity') as provider:
        # A different browser nonce is not the one bound to the signed state.
        rejected = client.get('/auth/oauth/google/callback', params={'state': state, 'code': 'test-code'},
                              follow_redirects=False)
        assert 'error=' in rejected.headers['location']
        provider.assert_not_called()
        client.cookies.clear()
        assert 'error=' in client.get('/auth/oauth/google/callback', params={'state': state, 'code': 'test-code'},
                                     follow_redirects=False).headers['location']
        provider.assert_not_called()


def test_unsigned_apple_form_cannot_link_a_victim_email(client, db_session, monkeypatch):
    from app.api.routes import auth
    victim, _ = account(client, db_session, 'apple-victim')
    for key, value in {'apple_oauth_client_id': 'test-client', 'apple_team_id': 'team',
                       'apple_key_id': 'key', 'apple_private_key': 'test-key'}.items():
        monkeypatch.setattr(auth.settings, key, value)
    start = client.get('/auth/oauth/apple/start', follow_redirects=False)
    state = parse_qs(urlsplit(start.headers['location']).query)['state'][0]
    monkeypatch.setattr(auth, '_apple_identity', lambda code: ('attacker-subject', None, None))
    response = client.post('/auth/oauth/apple/callback', data={'code': 'provider-code', 'state': state,
        'user': json.dumps({'email': victim.email, 'name': {'firstName': 'Attacker'}})}, follow_redirects=False)
    assert 'error=' in response.headers['location']
    assert db_session.query(OAuthIdentity).count() == 0


def test_apple_email_must_be_verified(monkeypatch):
    from app.api.routes import auth
    with patch.object(auth.jwt, 'get_unverified_header', return_value={'kid': 'key'}), \
         patch.object(auth.httpx, 'Client') as client, \
         patch.object(auth.jwt, 'decode', return_value={'sub': 'subject', 'email': 'victim@example.com',
                                                       'email_verified': False}):
        client.return_value.__enter__.return_value.get.return_value.json.return_value = {'keys': [{'kid': 'key'}]}
        with pytest.raises(HTTPException) as exc:
            auth._apple_token_claims('test-token', 'test-client')
        assert exc.value.status_code == 400


@pytest.mark.parametrize('implicit_tls', [False, True])
def test_smtp_tls_verifies_certificate_and_hostname(client, db_session, monkeypatch, implicit_tls):
    from app.core.mail import deliver_pending_mail
    account(client, db_session, 'tls')
    settings = get_settings()
    monkeypatch.setattr(settings, 'smtp_host', 'smtp.example.test')
    monkeypatch.setattr(settings, 'smtp_ssl', implicit_tls)
    monkeypatch.setattr(settings, 'smtp_starttls', not implicit_tls)
    transport = 'SMTP_SSL' if implicit_tls else 'SMTP'
    with patch('app.core.mail.smtplib.' + transport) as smtp:
        smtp.return_value.send_message.return_value = {}
        assert deliver_pending_mail(db_session) == 1
        context = smtp.call_args.kwargs['context'] if implicit_tls else smtp.return_value.starttls.call_args.kwargs['context']
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED


def test_smtp_auth_diagnostics_redact_echoed_secrets(client, db_session, monkeypatch, caplog):
    from app.core.mail import deliver_pending_mail
    user, _ = account(client, db_session, 'smtp-private')
    mail = db_session.query(MailOutbox).one()
    token = re.search(r'token=([^\s]+)', mail.body).group(1)
    settings = get_settings()
    monkeypatch.setattr(settings, 'smtp_host', 'smtp.example.test')
    monkeypatch.setattr(settings, 'smtp_username', 'test-smtp-login')
    monkeypatch.setattr(settings, 'smtp_password', 'test-smtp-password')
    secrets = [user.email, token, settings.smtp_username, settings.smtp_password,
               base64.b64encode(settings.smtp_password.encode()).decode()]
    with patch('app.core.mail.smtplib.SMTP') as smtp:
        smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(535, '\r\n'.join(secrets).encode())
        assert deliver_pending_mail(db_session) == 0
    assert 'smtp_code=535' in caplog.text
    assert all(secret not in caplog.text for secret in secrets)


def test_httpx_does_not_log_google_identity_tokens(caplog):
    with caplog.at_level(logging.INFO, logger='httpx'):
        logging.getLogger('httpx').info('HTTP Request: GET %s "HTTP/1.1 200 OK"',
            'https://oauth2.googleapis.com/tokeninfo?id_token=private-google-jwt')
    assert 'private-google-jwt' not in caplog.text and 'URL redacted' in caplog.text


def test_public_following_respects_private_inactive_and_blocked_profiles(client, db_session):
    owner, owner_headers = account(client, db_session, 'graph-owner')
    hidden, _ = account(client, db_session, 'graph-private')
    viewer, headers = account(client, db_session, 'graph-viewer')
    db_session.add(Follow(user_id=owner.id, target_type='user', target_id=str(hidden.id)))
    hidden.public_profile = False
    db_session.commit()
    result = client.get(f'/community/profiles/{owner.id}/following', headers=headers)
    assert result.status_code == 200 and result.json() == []
    own = client.get('/community/follows', headers=owner_headers).json()
    assert len(own) == 1 and own[0]['target_label'] == 'Unavailable profile'
    assert hidden.display_name is None or hidden.display_name not in json.dumps(own)
    hidden.public_profile, hidden.active = True, False
    db_session.commit()
    assert client.get(f'/community/profiles/{owner.id}/following', headers=headers).json() == []
    from app.models.community import UserBlock
    hidden.active = True
    db_session.add(UserBlock(user_id=hidden.id, blocked_id=viewer.id))
    db_session.commit()
    assert client.get(f'/community/profiles/{owner.id}/following', headers=headers).json() == []


@pytest.mark.parametrize('end', [None, -1, 10 ** 100])
def test_active_stripe_subscription_cannot_grant_unbounded_entitlement(client, db_session, end):
    from app.core.consumer_billing import reconcile_subscription
    from app.models.entitlement import ConsumerBillingCustomer, ConsumerSubscription
    from tests.test_consumer_billing import _subscription
    user, _ = account(client, db_session, 'billing-bound')
    settings = Settings(stripe_consumer_plus_price_id='price_plus', _env_file=None)
    mapping = ConsumerBillingCustomer(user_id=user.id, provider='stripe', external_customer_id='cus_fixture', livemode=False)
    provider = _subscription(user, 'cus_fixture')
    provider['current_period_end'] = end
    with pytest.raises(HTTPException) as exc:
        reconcile_subscription(db_session, user.id, mapping, provider, settings)
    assert exc.value.status_code == 502
    assert db_session.query(ConsumerSubscription).count() == 0


@pytest.mark.parametrize('origin', ['*', 'https://*', 'https://user:pass@example.com', 'https://example.com/path'])
def test_cors_wildcards_and_non_origins_rejected(origin):
    with pytest.raises(ValidationError):
        Settings(cors_origins=origin, _env_file=None)


def test_host_allowlist_rejects_untrusted_hosts():
    app = Starlette(routes=[Route('/health', lambda request: JSONResponse({'status': 'ok'}))])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=Settings(_env_file=None).trusted_host_list)
    client = TestClient(app)
    assert client.get('/health', headers={'host': 'attacker.example'}).status_code == 400
    assert client.get('/health', headers={'host': 'localhost'}).status_code == 200


def test_urlencoded_form_limits_apply_before_starlette_parser(client):
    response = client.post('/auth/oauth/apple/callback', content='&'.join('field=value' for _ in range(129)),
                           headers={'content-type': 'application/x-www-form-urlencoded'})
    assert response.status_code == 413


def test_windows_static_unc_path_rejected_before_resolution(client):
    assert client.get('/media/%5C%5Cattacker.example%5Cshare').status_code == 400


def test_ingestion_fails_closed_when_production_key_disappears(client, monkeypatch):
    monkeypatch.setattr(get_settings(), 'environment', 'production')
    monkeypatch.setenv('INGESTION_API_KEY', '')
    assert client.post('/events', json={}).status_code == 503


def test_registration_cannot_assign_privilege(client):
    response = client.post('/auth/register', json={'email': 'mass-assignment@example.com', 'password': 'password123',
        'role': 'ADMIN', 'email_verified': True, 'is_plus': True, 'reputation': 999999})
    assert response.status_code == 201
    assert response.json()['role'] == 'USER' and response.json()['email_verified'] is False


@pytest.mark.parametrize('url', ['https://user:secret@checkout.stripe.com/session',
    'https://checkout.stripe.com:8443/session', 'https://checkout.stripe.com:bad/session',
    'https://[broken', 'https://checkout.stripe.com/session\n'])
def test_stripe_redirects_reject_credentials_invalid_ports_and_malformed_urls(url):
    from app.api.routes.consumer_billing import _safe_url
    with pytest.raises(HTTPException) as exc:
        _safe_url(url, 'checkout.stripe.com')
    assert exc.value.status_code == 502


def test_configuration_errors_do_not_print_credentials():
    secret = 'private-configuration-secret'
    with pytest.raises(ValidationError) as exc:
        Settings(jwt_secret=secret, cors_origins='*', _env_file=None)
    assert secret not in str(exc.value)


def test_resource_budgets_are_shared_and_enforced(client, db_session, monkeypatch):
    from app.api.routes import events
    calls = []
    def limited(db, key, maximum, window):
        calls.append((key, maximum, window))
        raise HTTPException(429, 'Please try again later')
    monkeypatch.setattr('app.core.community.rate_limit', limited)
    for path in ['/events', '/events/search?q=concert',
        '/events/viewport?min_lat=48&max_lat=49&min_lng=17&max_lng=18', '/events/nearby?lat=48&lng=17']:
        assert client.get(path).status_code == 429
    assert all(maximum == 600 and window == 60 for _, maximum, window in calls)
    assert len({key for key, _, _ in calls}) == 1
