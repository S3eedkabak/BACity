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
from tests.test_community import account


def test_production_rejects_placeholder_secrets():
    with pytest.raises(ValidationError):
        Settings(environment='production', _env_file=None)
    settings = Settings(environment='production', jwt_secret='a'*40, ingestion_api_key='b'*40,
                        database_url='postgresql://localhost/bacity', public_app_url='https://bacity.example',
                        cors_origins='https://bacity.example', _env_file=None)
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
    monkeypatch.setattr(settings, 'smtp_host', 'mailpit')
    monkeypatch.setattr(settings, 'smtp_starttls', False)
    user, _ = account(client, db_session, 'mailer')
    with patch('app.worker.smtplib.SMTP', side_effect=OSError('unavailable')):
        worker.tick()
    mail = db_session.query(MailOutbox).one()
    assert mail.attempts == 1 and mail.sent_at is None
    mail.next_attempt_at = datetime.utcnow()-timedelta(seconds=1)
    db_session.commit()
    with patch('app.worker.smtplib.SMTP') as smtp:
        worker.tick()
        assert smtp.return_value.__enter__.return_value.send_message.call_count == 1
    db_session.refresh(mail)
    assert mail.sent_at and mail.body == '[Delivered]'
