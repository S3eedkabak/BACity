"""Compliance engineering properties, never legal-compliance assertions."""
from datetime import datetime
import json
import pytest
from sqlalchemy import text
from app.api.routes.privacy import calendar_months
from app.config import Settings, get_settings
from app.core.encryption import PREFIX
from app.models.privacy import PrivacyRequest
from app.models.community import AuditLog, Message, Notification, UserBlock
from tests.test_community import account


@pytest.mark.parametrize('kind', ['ACCESS', 'RECTIFICATION', 'ERASURE', 'RESTRICTION', 'PORTABILITY', 'OBJECTION', 'OTHER_PRIVACY_REQUEST'])
def test_private_request_categories_owner_and_encryption(client, db_session, kind):
    a, ha = account(client, db_session, 'privacy-a')
    b, hb = account(client, db_session, 'privacy-b')
    result = client.post('/privacy/requests', headers=ha, json={'kind': kind, 'details': 'Private rights request text'})
    assert result.status_code == 201, result.text
    identifier = result.json()['id']
    assert result.json()['identity_confirmed'] is False
    assert client.get('/privacy/requests/' + identifier, headers=hb).status_code == 404
    assert client.get('/privacy/requests', headers=hb).json() == []
    assert client.get('/privacy/requests/' + identifier).status_code == 401
    raw = db_session.execute(text('SELECT details FROM privacy_requests')).scalar()
    assert raw.startswith(PREFIX) and 'Private rights' not in raw
    history = [item.details for item in db_session.query(AuditLog).filter_by(target_type='privacy_request')]
    assert 'Private rights' not in json.dumps(history)


def test_admin_review_deadline_extension_and_audit(client, db_session):
    a, ha = account(client, db_session, 'requester')
    admin, hh = account(client, db_session, 'privacy-admin', role='ADMIN')
    mod, hm = account(client, db_session, 'privacy-mod', role='MODERATOR')
    item = client.post('/privacy/requests', headers=ha, json={'kind': 'OBJECTION'}).json()
    url = '/privacy/admin/requests/' + item['id']
    assert client.get('/privacy/admin/requests', headers=ha).status_code == 403
    assert client.get(url, headers=hm).status_code == 403
    assert client.patch(url, headers=hm, json={'status': 'in_review', 'decision_code': 'information_needed'}).status_code == 403
    queue = client.get('/privacy/admin/requests', headers=hh).json()
    assert 'details' not in queue[0] and 'user_id' not in queue[0]
    assert client.get(url, headers=hh).status_code == 200
    body = {'status': 'in_review', 'decision_code': 'other_assessed_reason', 'response': 'Complex request: extension assessed.', 'extend': True}
    extended = client.patch(url, headers=hh, json=body)
    assert extended.status_code == 200, extended.text
    created = datetime.fromisoformat(item['created_at'])
    assert datetime.fromisoformat(extended.json()['due_at']) == calendar_months(created, 3)
    assert client.patch(url, headers=hh, json=body).status_code == 409
    done = {'status': 'completed', 'decision_code': 'fulfilled', 'response': 'Reviewed and fulfilled.'}
    assert client.patch(url, headers=hh, json=done).status_code == 422
    done['identity_confirmed'] = True
    assert client.patch(url, headers=hh, json=done).status_code == 200
    assert client.patch(url, headers=hh, json=done).status_code == 409
    logs = db_session.query(AuditLog).filter_by(target_type='privacy_request').all()
    assert any(item.action == 'privacy_request_accessed' for item in logs)
    assert 'Complex request' not in json.dumps([item.details for item in logs])
    assert all('Complex request' not in item.body for item in db_session.query(Notification))


def test_privacy_export_portability_and_account_erasure(client, db_session):
    a, ha = account(client, db_session, 'export-owner')
    b, hb = account(client, db_session, 'export-other')
    db_session.add_all([Message(sender_id=a.id, recipient_id=b.id, body='own sent'), Message(sender_id=b.id, recipient_id=a.id, body='received'), Message(sender_id=b.id, recipient_id=b.id, body='unrelated')])
    db_session.commit()
    created = client.post('/privacy/requests', headers=ha, json={'kind': 'ERASURE', 'details': 'Erase private request'}).json()
    exported = client.get('/community/account/export', headers=ha).json()
    assert len(exported['privacy_requests']) == 1
    assert 'unrelated' not in json.dumps(exported)
    portable = client.get('/privacy/portability', headers=ha)
    assert portable.status_code == 200, portable.text
    assert [item['body'] for item in portable.json()['messages_sent']] == ['own sent']
    assert 'hashed_password' not in json.dumps(portable.json())
    assert 'consumer_billing' not in portable.json()
    assert client.request('DELETE', '/community/account', headers=ha, json={'reason': 'Erase account'}).status_code == 200
    db_session.expire_all()
    case = db_session.query(PrivacyRequest).one()
    assert case.user_id is None and case.details == '' and case.response == ''
    assert client.get('/privacy/requests/' + created['id'], headers=ha).status_code == 401


@pytest.mark.parametrize('payload', [{'kind': 'UNKNOWN'}, {'kind': 'ACCESS', 'user_id': 'spoof'}, {'kind': 'ACCESS', 'details': 'x' * 2001}])
def test_privacy_request_validation(client, db_session, payload):
    a, ha = account(client, db_session, 'privacy-validation')
    assert client.post('/privacy/requests', headers=ha, json=payload).status_code == 422


def test_privacy_request_throttling_and_calendar_deadlines(client, db_session):
    a, ha = account(client, db_session, 'privacy-throttle')
    for index in range(5):
        assert client.post('/privacy/requests', headers=ha, json={'kind': 'ACCESS'}).status_code == 201
    assert client.post('/privacy/requests', headers=ha, json={'kind': 'ACCESS'}).status_code == 429
    assert calendar_months(datetime(2028, 1, 31, 12), 1) == datetime(2028, 2, 29, 12)
    assert calendar_months(datetime(2027, 1, 31, 12), 1) == datetime(2027, 2, 28, 12)


def test_privacy_information_not_fake_policy_and_safe_config(client):
    info = client.get('/privacy/information').json()
    assert info['documents_ready'] is False
    assert info['privacy_notice_url'] is None and info['privacy_contact_email'] is None
    assert 'not end-to-end' in info['message_encryption']
    assert 'interests' in info['recommendations']
    with pytest.raises(ValueError):
        Settings(privacy_contact_email='contact@example.com\nBCC:bad', _env_file=None)
    with pytest.raises(ValueError):
        Settings(privacy_notice_url='javascript:bad', _env_file=None)


def test_late_extension_not_permitted(client, db_session):
    a, ha = account(client, db_session, 'late-user')
    admin, hh = account(client, db_session, 'late-admin', role='ADMIN')
    case = PrivacyRequest(user_id=a.id, kind='ACCESS', created_at=datetime(2020, 1, 1), due_at=datetime(2020, 2, 1))
    db_session.add(case); db_session.commit()
    assert client.patch(f'/privacy/admin/requests/{case.id}', headers=hh, json={'status': 'in_review', 'decision_code': 'other_assessed_reason', 'extend': True, 'response': 'Late extension'}).status_code == 409


def test_export_does_not_reveal_someone_elses_block_decision(client, db_session):
    a, ha = account(client, db_session, 'blocked-export')
    b, hb = account(client, db_session, 'blocker-export')
    db_session.add(UserBlock(user_id=b.id, blocked_id=a.id)); db_session.commit()
    assert client.get('/community/account/export', headers=ha).json()['blocks'] == []
    assert len(client.get('/community/account/export', headers=hb).json()['blocks']) == 1


def test_moderation_audit_does_not_duplicate_freeform_evidence(client, db_session):
    a, ha = account(client, db_session, 'moderation-content')
    admin, hh = account(client, db_session, 'moderation-staff', role='ADMIN')
    from tests.test_community import event_payload
    submission = client.post('/community/submissions/events', headers=ha, json=event_payload()).json()
    decision = client.post('/community/moderation/submissions/' + submission['id'], headers=hh,
        json={'decision': 'reject', 'reason': 'Unique private moderation evidence'})
    assert decision.status_code == 200, decision.text
    logs = db_session.query(AuditLog).filter_by(target_type='submission').all()
    assert 'Unique private moderation evidence' not in json.dumps([row.details for row in logs])


def test_access_export_does_not_silently_truncate_messages(client, db_session):
    a, ha = account(client, db_session, 'complete-export')
    b, hb = account(client, db_session, 'complete-other')
    db_session.add_all([Message(sender_id=a.id, recipient_id=b.id, body=f'own {index}') for index in range(125)])
    db_session.add(Message(sender_id=b.id, recipient_id=b.id, body='Not owned by requester'))
    db_session.commit()
    response = client.get('/community/account/export', headers=ha)
    assert response.status_code == 200
    assert len(response.json()['messages']) == 125
    assert 'Not owned by requester' not in response.text


def test_privacy_details_not_logged_and_no_location_or_identity_fields(client, db_session, caplog):
    a, ha = account(client, db_session, 'private-case-log')
    response = client.post('/privacy/requests', headers=ha, json={'kind': 'RESTRICTION', 'details': 'Private case contents not for logs'})
    assert response.status_code == 201
    assert 'Private case contents' not in caplog.text
    for key in ('latitude', 'identity_document', 'email', 'user_id'):
        assert client.post('/privacy/requests', headers=ha, json={'kind': 'ACCESS', key: 'forbidden'}).status_code == 422


def test_delivered_conversation_survives_sender_deletion_without_private_identity(client, db_session):
    from sqlalchemy import text
    from app.core.encryption import PREFIX
    alice, ha = account(client, db_session, 'shared-alice')
    bob, hb = account(client, db_session, 'shared-bob')
    outsider, hc = account(client, db_session, 'shared-outsider')
    alice.allow_general_messages = bob.allow_general_messages = True
    alice.bio, alice.avatar_url = 'Private deleted bio', 'https://example.com/private-avatar'
    db_session.commit()
    assert client.post(f'/community/messages/{bob.id}', headers=ha, json={'body': 'Delivered to Bob'}).status_code == 200
    assert client.post(f'/community/messages/{alice.id}', headers=hb, json={'body': 'Bob reply'}).status_code == 200
    assert len(client.get(f'/community/messages/{alice.id}', headers=hb).json()) == 2
    assert client.request('DELETE', '/community/account', headers=ha, json={'reason': 'Delete'}).status_code == 200
    assert client.get(f'/community/messages/{bob.id}', headers=ha).status_code == 401
    assert client.get(f'/community/profiles/{alice.id}', headers=hb).status_code == 404
    assert client.post(f'/community/messages/{alice.id}', headers=hb, json={'body': 'Cannot send'}).status_code == 403
    assert {m['body'] for m in client.get(f'/community/messages/{alice.id}', headers=hb).json()} == {'Delivered to Bob', 'Bob reply'}
    assert client.get(f'/community/messages/{alice.id}', headers=hc).json() == []
    notifications = client.get('/community/notifications', headers=hb).json()
    assert any(n['kind'] == 'message' and n['target_id'] == str(alice.id) for n in notifications)
    export = client.get('/community/account/export', headers=hb)
    assert 'Private deleted bio' not in export.text and 'private-avatar' not in export.text
    assert len(export.json()['messages']) == 2
    assert all(body.startswith(PREFIX) for (body,) in db_session.execute(text('SELECT body FROM messages')))
    assert client.request('DELETE', '/community/account', headers=hb, json={'reason': 'Delete'}).status_code == 200
    assert db_session.query(Message).count() == 0


def test_public_event_and_profile_history_do_not_attribute_community_contributor(client, db_session):
    from app.models.event import Event
    from app.schemas.event import EventOut
    from tests.test_community import event_payload
    author, ha = account(client, db_session, 'anonymous-contributor')
    viewer, hv = account(client, db_session, 'anonymous-viewer')
    admin, hh = account(client, db_session, 'anonymous-admin', role='ADMIN')
    submitted = client.post('/community/submissions/events', headers=ha, json=event_payload()).json()
    approved = client.post('/community/moderation/submissions/' + submitted['id'], headers=hh,
        json={'decision': 'approve', 'reason': 'Valid real event'})
    assert approved.status_code == 200, approved.text
    event = db_session.query(Event).filter_by(contributor_id=author.id).one()
    public = client.get(f'/events/{event.id}')
    assert public.status_code == 200, public.text
    assert public.json()['contributor_id'] is None
    assert str(author.id) not in public.text and author.email not in public.text
    assert EventOut.model_validate(event).model_dump()['contributor_id'] is None
    assert client.get(f'/community/profiles/{author.id}', headers=hv).json()['contributions'] == []
    assert client.get(f'/community/profiles/{author.id}/contributions', headers=hv).json() == []
    assert client.get(f'/community/profiles/{author.id}/contributions', headers=ha).json()[0]['published_id'] == str(event.id)
    assert client.get('/community/account/export', headers=ha).json()['events_contributed'][0]['contributor_id'] == str(author.id)
    author.public_profile = False; db_session.commit()
    assert client.get(f'/community/profiles/{author.id}', headers=hv).status_code == 404


def test_public_contacts_configurable_without_exposing_internal_operations(client, monkeypatch):
    from app.api.routes import privacy
    config = Settings(controller_legal_name='Test controller', business_address='Test public address',
        support_contact_email='support@example.com', legal_contact_email='legal@example.com',
        operations_contact_email='internal@example.com', _env_file=None)
    monkeypatch.setattr(privacy, 'get_settings', lambda: config)
    result = client.get('/privacy/information')
    assert result.json()['controller_legal_name'] == 'Test controller'
    assert result.json()['business_address'] == 'Test public address'
    assert 'internal@example.com' not in result.text and result.json()['documents_ready'] is False
    for field in ('support_contact_email', 'legal_contact_email', 'operations_contact_email'):
        with pytest.raises(ValueError):
            Settings(**{field: 'bad@example.com\nBCC: secret'}, _env_file=None)
