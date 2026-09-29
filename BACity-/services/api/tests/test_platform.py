import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta
from unittest.mock import patch
import pytest
from pydantic import ValidationError
from app.config import Settings, get_settings
from app.api.routes.billing import verify_signature
from app.models.community import Organization, BillingReceipt, MailOutbox, Message
from app.models.user import User
from tests.test_community import account


def test_production_rejects_placeholder_secrets():
    from cryptography.fernet import Fernet
    with pytest.raises(ValidationError):
        Settings(environment='production', _env_file=None)
    settings = Settings(environment='production', jwt_secret='a'*40, ingestion_api_key='b'*40,
                        database_url='postgresql://localhost/bacity', public_app_url='https://bacity.example',
                        cors_origins='https://bacity.example', smtp_host='smtp.example.net',
                        mail_from='noreply@bacity.sk',
                        oauth_callback_base_url='https://api.bacity.example',
                        google_oauth_client_id='google-client', google_oauth_client_secret='google-secret',
                        google_android_client_id='google-android', google_ios_client_id='google-ios',
                        apple_oauth_client_id='com.bacity.web', apple_ios_client_id='com.bacity.ios', apple_team_id='TEAM',
                        apple_key_id='KEY', apple_private_key='private-key',
                        oauth_token_encryption_key=Fernet.generate_key().decode(), _env_file=None)
    assert settings.environment == 'production'


def test_limits_and_body_size(client):
    assert client.get('/events?limit=-1').status_code == 422
    assert client.get('/events?offset=-1').status_code == 422
    result = client.post('/auth/login', content=b'x' * 1048577)
    assert result.status_code == 413
    assert client.get('/health').headers['x-request-id']


def test_billing_unconfigured_and_signature_replay(client):
    assert client.get('/billing/status').json()['configured'] is False
    assert client.post('/billing/webhook', content='{}').status_code == 503
    now = str(int(time.time()))
    body = b'{"type":"test"}'
    signature = hmac.new(b'secret', now.encode()+b'.'+body, hashlib.sha256).hexdigest()
    assert verify_signature(body, f't={now},v1={signature}', 'secret')
    assert not verify_signature(body+b' ', f't={now},v1={signature}', 'secret')
    assert not verify_signature(body, f't={int(now)-600},v1={signature}', 'secret')
    assert not verify_signature(body, 'malformed', 'secret')


def test_webhooks_use_current_provider_state_and_deduplicate(client, db_session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'stripe_secret_key', 'sk_test_fake')
    monkeypatch.setattr(settings, 'stripe_webhook_secret', 'whsec_fake')
    monkeypatch.setattr(settings, 'stripe_business_price_id', 'price_business')
    org = Organization(name='Venue', stripe_customer_id='cus_123')
    db_session.add(org); db_session.commit()
    event = {'id': 'evt_123', 'type': 'customer.subscription.updated', 'data': {'object': {'customer': 'cus_123'}}}
    body = json.dumps(event).encode()
    now = str(int(time.time()))
    sig = hmac.new(b'whsec_fake', now.encode()+b'.'+body, hashlib.sha256).hexdigest()
    headers = {'stripe-signature': f't={now},v1={sig}'}
    current = {'data': [{'id': 'sub_123', 'status': 'active', 'items': {'data': [{'price': {'id': 'price_business'}}]}}]}
    with patch('app.api.routes.billing.stripe', return_value=current) as provider:
        assert client.post('/billing/webhook', content=body, headers=headers).status_code == 200
        assert client.post('/billing/webhook', content=body, headers=headers).status_code == 200
        assert provider.call_count == 1
    db_session.refresh(org)
    assert org.tier == 'business'
    assert db_session.query(BillingReceipt).count() == 1


def test_mail_delivery_retry_and_retention(client, db_session, monkeypatch):
    from app import worker
    from tests.conftest import TestingSessionLocal
    monkeypatch.setattr(worker, 'SessionLocal', TestingSessionLocal)
    settings = get_settings()
    user, _ = account(client, db_session, 'mailer')
    monkeypatch.setattr(settings, 'smtp_host', 'mailpit')
    monkeypatch.setattr(settings, 'smtp_starttls', False)
    with patch('app.core.mail.smtplib.SMTP', side_effect=OSError('unavailable')):
        worker.tick()
    mail = db_session.query(MailOutbox).one()
    assert mail.attempts == 1 and mail.sent_at is None
    mail.next_attempt_at = datetime.utcnow()-timedelta(seconds=1)
    db_session.commit()
    with patch('app.core.mail.smtplib.SMTP') as smtp:
        smtp.return_value.send_message.return_value = {}
        worker.tick()
        assert smtp.return_value.send_message.call_count == 1
    db_session.refresh(mail)
    assert mail.sent_at and mail.body == '[Delivered]'
    mail.sent_at = None
    mail.attempts = 10
    mail.next_attempt_at = datetime.utcnow()-timedelta(seconds=1)
    db_session.commit()
    with patch('app.core.mail.smtplib.SMTP') as smtp:
        smtp.return_value.send_message.return_value = {}
        worker.tick()
        smtp.assert_not_called()


def test_auth_routes_attempt_the_shared_smtp_transport(client, db_session, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, 'smtp_host', 'smtp.example.test')
    monkeypatch.setattr(settings, 'smtp_port', 587)
    monkeypatch.setattr(settings, 'smtp_starttls', True)
    monkeypatch.setattr(settings, 'smtp_ssl', False)
    monkeypatch.setattr(settings, 'smtp_username', 'smtp-login')
    monkeypatch.setattr(settings, 'smtp_password', 'smtp-secret')

    with patch('app.core.mail.smtplib.SMTP') as smtp:
        smtp.return_value.send_message.return_value = {}
        registered = client.post('/auth/register', json={
            'email': 'transport@example.com', 'password': 'password123'
        })
        assert registered.status_code == 201
        assert smtp.return_value.starttls.call_count == 1
        assert smtp.return_value.login.call_count == 1
        assert smtp.return_value.send_message.call_count == 1

        token = client.post('/auth/login', json={
            'email': 'transport@example.com', 'password': 'password123'
        }).json()['access_token']
        verification = client.post('/auth/request-verification', headers={
            'Authorization': 'Bearer ' + token
        })
        assert verification.status_code == 200
        assert smtp.return_value.send_message.call_count == 2

        reset = client.post('/auth/request-reset', json={'email': 'transport@example.com'})
        assert reset.status_code == 200
        assert smtp.return_value.send_message.call_count == 3

        user = db_session.query(User).filter_by(email='transport@example.com').one()
        user.email_verified = True
        db_session.commit()
        verified = client.post('/auth/request-verification', headers={
            'Authorization': 'Bearer ' + token
        })
        assert verified.status_code == 200
        assert smtp.return_value.send_message.call_count == 3


def test_smtp_failure_keeps_reset_response_private_and_retry_bounded(client, db_session, monkeypatch, caplog):
    import smtplib
    settings = get_settings()
    client.post('/auth/register', json={'email': 'private@example.com', 'password': 'password123'})
    monkeypatch.setattr(settings, 'smtp_host', 'smtp.example.test')
    monkeypatch.setattr(settings, 'smtp_username', 'smtp-login')
    monkeypatch.setattr(settings, 'smtp_password', 'smtp-secret')

    with patch('app.core.mail.smtplib.SMTP') as smtp:
        smtp.return_value.login.side_effect = smtplib.SMTPAuthenticationError(
            535, b'5.7.8 Authentication rejected'
        )
        existing = client.post('/auth/request-reset', json={'email': 'private@example.com'})
        missing = client.post('/auth/request-reset', json={'email': 'missing@example.com'})

    assert existing.status_code == missing.status_code == 200
    assert existing.json() == missing.json()
    mail = db_session.query(MailOutbox).filter_by(
        recipient='private@example.com', subject='Reset your BACity password'
    ).one()
    assert mail.attempts == 1 and mail.sent_at is None
    assert mail.error == 'SMTPAuthenticationError'
    assert 'smtp_code=535' in caplog.text
    assert 'smtp_response=5.7.8 Authentication rejected' in caplog.text
    assert 'smtp_host=smtp.example.test' in caplog.text
    assert 'smtp_port=587' in caplog.text
    assert 'smtp_mode=starttls' in caplog.text
    assert 'smtp-login' not in caplog.text
    assert 'smtp-secret' not in caplog.text
    assert 'private@example.com' not in caplog.text
