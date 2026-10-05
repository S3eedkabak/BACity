"""Local endpoint attacks and storage-compromise properties; no live providers."""
import base64
import json
import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from jose import jwt
from pydantic import ValidationError
from sqlalchemy import text

from app.config import Settings, get_settings
from app.core.encryption import PREFIX, EncryptionError, encrypt, decrypt
from app.core.security import create_access_token
from app.models.community import Message, Notification, MailOutbox, Collection, Organization, OrganizationMember
from app.models.entitlement import ConsumerSubscription
from app.private_data import process_private_data
from tests.test_community import account
from tests.test_ingestion import payload as event_payload
from tests.test_area_watches import _grant, _payload


def crypto_config(**changes):
    values = dict(private_data_keys=json.dumps({'one': base64.b64encode(os.urandom(32)).decode()}),
                  private_data_active_key='one', environment='production')
    values.update(changes)
    return SimpleNamespace(**values)


def test_aead_nonce_rotation_tampering_and_field_binding():
    config = crypto_config()
    first = encrypt('private message', 'messages.body', config)
    assert first != encrypt('private message', 'messages.body', config)
    assert 'private message' not in first
    assert decrypt(first, 'messages.body', config) == 'private message'
    with pytest.raises(EncryptionError):
        decrypt(first, 'mail_outbox.body', config)
    altered = first[:-4] + 'AAAA'
    with pytest.raises(EncryptionError):
        decrypt(altered, 'messages.body', config)
    keys = json.loads(config.private_data_keys)
    keys['two'] = base64.b64encode(os.urandom(32)).decode()
    config.private_data_keys, config.private_data_active_key = json.dumps(keys), 'two'
    assert decrypt(first, 'messages.body', config) == 'private message'
    assert encrypt('private message', 'messages.body', config).startswith(PREFIX + 'two:')
    del keys['one']
    config.private_data_keys = json.dumps(keys)
    with pytest.raises(EncryptionError):
        decrypt(first, 'messages.body', config)


@pytest.mark.parametrize('stored', ['plaintext', PREFIX + 'unknown:AAAA', 'bacity:aead:v2:future'])
def test_encrypted_mode_never_falls_back_to_plaintext(stored):
    with pytest.raises(EncryptionError):
        decrypt(stored, 'messages.body', crypto_config())


@pytest.mark.parametrize('keys,active', [('', ''), ('{}', 'one'), ('not json', 'one'),
                                     ('{"one":"invalid"}', 'one'), ('[]', 'one')])
def test_staging_missing_or_malformed_keys_fails_closed(keys, active):
    with pytest.raises(ValidationError) as error:
        Settings(environment='staging', private_data_keys=keys, private_data_active_key=active, _env_file=None)
    assert 'input_value' not in str(error.value)


def test_private_storage_snapshot_and_legacy_backfill(client, db_session):
    a, ha = account(client, db_session, 'storage-a')
    b, hb = account(client, db_session, 'storage-b')
    b.allow_general_messages = True
    db_session.commit()
    sent = client.post(f'/community/messages/{b.id}', headers=ha, json={'body': 'private snapshot text'})
    assert sent.status_code == 200
    db_session.add(ConsumerSubscription(user_id=a.id, provider='google_play', product_id='test',
        external_subscription_id='fixture-hash', status='expired', provider_purchase_token='private purchase token'))
    db_session.commit()
    for table, column, sensitive in [('messages', 'body', 'private snapshot text'),
                                    ('mail_outbox', 'body', 'token='),
                                    ('consumer_subscriptions', 'provider_purchase_token', 'private purchase token')]:
        stored = db_session.execute(text(f'SELECT {column} FROM {table}')).scalar()
        assert stored.startswith(PREFIX) and sensitive not in stored
    assert client.get(f'/community/messages/{a.id}', headers=hb).json()[0]['body'] == 'private snapshot text'
    # Legacy backfill uses raw bounded SQL, not the strict production decoder.
    db_session.execute(text("UPDATE messages SET body = 'legacy private text'"))
    db_session.commit()
    assert client.get(f'/community/messages/{b.id}', headers=ha).status_code == 503
    config = get_settings()
    with db_session.bind.connect() as connection:
        dry = process_private_data(connection, config)
        assert dry['legacy'] == 1 and dry['changed'] == 0
        applied = process_private_data(connection, config, apply=True)
        assert applied['changed'] == 1
        assert process_private_data(connection, config, apply=True)['changed'] == 0
    db_session.expire_all()
    assert client.get(f'/community/messages/{b.id}', headers=ha).json()[0]['body'] == 'legacy private text'


def test_message_endpoint_sender_identity_pagination_export_and_notifications(client, db_session, caplog):
    a, ha = account(client, db_session, 'chat-a')
    b, hb = account(client, db_session, 'chat-b')
    c, hc = account(client, db_session, 'chat-c', role='MODERATOR')
    b.allow_general_messages = True
    db_session.commit()
    path = f'/community/messages/{b.id}'
    assert client.post(path, headers=ha, json={'body': 'secret chat', 'sender_id': str(c.id)}).status_code == 422
    assert client.post(path, json={'body': 'secret chat'}).status_code == 401
    message = client.post(path, headers=ha, json={'body': 'secret chat'}).json()
    assert message['sender_id'] == str(a.id)
    for identifier in (a.id, b.id):
        assert client.get(f'/community/messages/{identifier}', headers=hc).json() == []
        assert client.get(f'/community/messages/{identifier}?offset=1', headers=hc).json() == []
    assert client.post('/community/reports', headers=hc, json={
        'target_type': 'message', 'target_id': message['id'], 'reason': 'Guessing private message'}).status_code == 404
    notifications = client.get('/community/notifications', headers=hb).json()
    assert notifications and all('secret chat' not in n['body'] for n in notifications)
    assert client.post(f"/community/notifications/{notifications[0]['id']}/read", headers=ha).status_code == 404
    assert client.get('/community/account/export', headers=hc).json()['messages'] == []
    assert client.get('/community/account/export', headers=ha).json()['messages'][0]['body'] == 'secret chat'
    assert 'secret chat' not in caplog.text
    assert client.post('/community/blocks/' + str(a.id), headers=hb).status_code == 200
    assert client.get(path, headers=ha).status_code == 403
    assert client.post(path, headers=ha, json={'body': 'bypass block'}).status_code == 403


def test_message_flood_bound_and_deleted_account(client, db_session):
    a, ha = account(client, db_session, 'flood-a')
    b, hb = account(client, db_session, 'flood-b')
    b.allow_general_messages = True
    db_session.commit()
    path = f'/community/messages/{b.id}'
    assert client.post(path, headers=ha, json={'body': 'x' * 20001}).status_code == 422
    for _ in range(30):
        assert client.post(path, headers=ha, json={'body': 'bounded message'}).status_code == 200
    assert client.post(path, headers=ha, json={'body': 'one too many'}).status_code == 429
    assert client.request('DELETE', '/community/account', headers=hb, json={'reason': 'Delete test account'}).status_code == 200
    assert client.get(f'/community/messages/{a.id}', headers=hb).status_code == 401
    assert db_session.query(Message).count() == 0


@pytest.mark.parametrize('changes', [ {'exp': datetime.utcnow() - timedelta(seconds=1)}, {'sub': ''},
    {'ver': 100}, {'ver': True}, {'role': 'ADMIN', 'ver': 1} ])
def test_malicious_jwt_claims_rejected_by_endpoint(client, db_session, changes):
    user, _ = account(client, db_session, 'jwt-boundary')
    claims = {'sub': user.email, 'exp': datetime.utcnow() + timedelta(minutes=5), 'ver': user.token_version}
    claims.update(changes)
    config = get_settings()
    token = jwt.encode(claims, config.jwt_secret, algorithm=config.jwt_algorithm)
    assert client.get('/users/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401


def test_stale_admin_role_claim_cannot_elevate_current_user(client, db_session):
    user, _ = account(client, db_session, 'role-spoof')
    config = get_settings()
    token = jwt.encode({'sub': user.email, 'exp': datetime.utcnow() + timedelta(minutes=5),
        'ver': user.token_version, 'role': 'ADMIN', 'is_plus': True}, config.jwt_secret, algorithm=config.jwt_algorithm)
    headers = {'Authorization': 'Bearer ' + token}
    assert client.get('/community/moderation/submissions', headers=headers).status_code == 403
    assert client.post('/recommendations/tonight', json={}, headers=headers).status_code == 403


@pytest.mark.parametrize('attack', ['missing-exp', 'missing-sub', 'wrong-algorithm', 'wrong-signature', 'malformed'])
def test_token_structure_and_signature_at_actual_endpoint(client, db_session, attack):
    user, _ = account(client, db_session, 'token-structure')
    config = get_settings()
    claims = {'sub': user.email, 'exp': datetime.utcnow() + timedelta(minutes=5), 'ver': user.token_version}
    if attack == 'missing-exp':
        del claims['exp']
    if attack == 'missing-sub':
        del claims['sub']
    token = 'not.a.valid.token' if attack == 'malformed' else jwt.encode(
        claims, 'not-the-signing-secret' if attack == 'wrong-signature' else config.jwt_secret,
        algorithm='HS512' if attack == 'wrong-algorithm' else config.jwt_algorithm)
    assert client.get('/users/me', headers={'Authorization': 'Bearer ' + token}).status_code == 401


@pytest.mark.parametrize('field', ['name', 'categories', 'radius_km', 'active', 'center_latitude'])
def test_null_area_watch_update_is_validation_error_not_server_error(client, db_session, field):
    owner, headers = account(client, db_session, 'null-watch')
    _grant(db_session, owner)
    watch = client.post('/area-watches', headers=headers, json=_payload()).json()
    assert client.patch('/area-watches/' + watch['id'], headers=headers, json={field: None}).status_code == 422
    assert client.get('/area-watches/' + watch['id'], headers=headers).json()['name'] == 'City Centre'


def test_organizer_cross_account_update_and_moderator_admin_boundary(client, db_session):
    a, ha = account(client, db_session, 'org-a')
    b, hb = account(client, db_session, 'org-b', role='MODERATOR')
    org = Organization(name='Owner venue', website='https://venue.example')
    db_session.add(org)
    db_session.flush()
    db_session.add(OrganizationMember(organization_id=org.id, user_id=a.id))
    db_session.commit()
    assert client.patch(f'/community/organizations/{org.id}', headers=hb,
                        json={'name': 'Hijacked', 'website': org.website}).status_code == 403
    assert client.patch(f'/community/moderation/users/{a.id}/role', headers=hb,
                        json={'role': 'ADMIN', 'reason': 'Escalation'}).status_code == 403


def test_weaker_source_cannot_poison_shared_venue_coordinates(client, db_session):
    from app.models.venue import Venue
    trusted = client.post('/events', json=event_payload()).json()
    assert client.post('/events', json=event_payload(source_url='https://weak.example/repost',
        source_reliability=.1, latitude=48.30, longitude=17.30)).status_code == 201
    venue = db_session.query(Venue).one()
    assert (venue.latitude, venue.longitude) == (48.15, 17.12)
    assert client.get('/events/' + trusted['id']).json()['latitude'] == 48.15


def test_private_neighborhood_cannot_leak_via_discovery_targets(client, db_session):
    _, headers = account(client, db_session, 'neighborhood-viewer')
    private, _ = account(client, db_session, 'neighborhood-private')
    private.public_profile, private.neighborhood = False, 'Private-only location'
    db_session.commit()
    results = client.get('/community/follow-targets?target_type=neighborhood', headers=headers)
    assert results.status_code == 200
    assert 'Private-only location' not in results.text


@pytest.mark.parametrize('role', ['USER', 'GUIDE', 'MODERATOR', 'ADMIN'])
def test_private_object_matrix_does_not_grant_staff_owner_bypass(client, db_session, role):
    owner, own = account(client, db_session, 'object-owner')
    attacker, other = account(client, db_session, 'object-attacker', role=role)
    _grant(db_session, owner)
    _grant(db_session, attacker)
    watch = client.post('/area-watches', headers=own, json=_payload()).json()
    path = '/area-watches/' + watch['id']
    assert client.get(path, headers=other).status_code == 404
    assert client.patch(path, headers=other, json={'name': 'Stolen watch'}).status_code == 404
    assert client.delete(path, headers=other).status_code == 404
    assert client.get(path + '/events', headers=other).status_code == 404
    collection = Collection(user_id=owner.id, title='Private library', public=False, items=[])
    db_session.add(collection)
    db_session.commit()
    assert 'Private library' not in client.get('/community/collections', headers=other).text
    assert client.get('/community/account/export', headers=other).json()['collections'] == []


def test_free_group_participant_cannot_become_host_or_plus(client, db_session):
    from datetime import date
    from app.models.group import GroupSession, GroupParticipant
    host, host_headers = account(client, db_session, 'group-host')
    participant, headers = account(client, db_session, 'group-participant')
    outsider, outsider_headers = account(client, db_session, 'group-outsider')
    now = datetime.utcnow()
    group = GroupSession(host_id=host.id, name='Private group', target_date=date.today(),
        starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=4),
        expires_at=now + timedelta(days=2), purge_after=now + timedelta(days=90), categories=[])
    db_session.add(group)
    db_session.flush()
    db_session.add_all([GroupParticipant(group_id=group.id, user_id=host.id),
        GroupParticipant(group_id=group.id, user_id=participant.id, liked_categories=['Music'])])
    db_session.commit()
    path = f'/groups/{group.id}'
    assert client.get(path, headers=outsider_headers).status_code == 404
    assert client.get(path, headers=headers).status_code == 200
    assert 'liked_categories' not in client.get(path, headers=host_headers).text
    assert client.patch(path, headers=headers, json={'name': 'Host takeover'}).status_code == 403
    assert client.post(path + '/invite', headers=headers).status_code == 403
    assert client.post(path + '/matches', headers=headers, json={}).status_code == 403
    assert client.patch(path + '/preferences', headers=headers,
        json={'user_id': str(host.id), 'liked_categories': ['Music']}).status_code == 422
    assert client.post('/recommendations/tonight', headers=headers, json={}).status_code == 403
    assert client.get('/users/me/entitlements', headers=headers).status_code == 200


def test_tampered_private_data_fails_closed_without_disclosing_storage(client, db_session):
    a, ha = account(client, db_session, 'tamper-a')
    b, _ = account(client, db_session, 'tamper-b')
    db_session.add(Message(sender_id=a.id, recipient_id=b.id, body='Do not leak this body'))
    db_session.commit()
    db_session.execute(text('UPDATE messages SET body = :body'), {'body': PREFIX + 'test:AAAA'})
    db_session.commit()
    response = client.get(f'/community/messages/{b.id}', headers=ha)
    assert response.status_code == 503
    assert 'AAAA' not in response.text and 'Do not leak this body' not in response.text


def test_backfill_rotation_is_bounded_resumable_and_verified(db_session):
    from app.models.user import User
    a, b = User(email='backfill-a@example.com', hashed_password='unused'), User(email='backfill-b@example.com', hashed_password='unused')
    db_session.add_all([a, b])
    db_session.flush()
    db_session.add_all([Message(sender_id=a.id, recipient_id=b.id, body=f'body {i}') for i in range(205)])
    db_session.commit()
    config = get_settings()
    keys = json.loads(config.private_data_keys)
    keys['next'] = base64.b64encode(os.urandom(32)).decode()
    config.private_data_keys, config.private_data_active_key = json.dumps(keys), 'next'
    with db_session.bind.connect() as connection:
        result = process_private_data(connection, config, apply=True, rotate=True)
        assert result == {'checked': 205, 'legacy': 0, 'changed': 205}
        assert process_private_data(connection, config, apply=True, rotate=True)['changed'] == 0
    db_session.expire_all()
    assert db_session.query(Message).count() == 205
    assert {message.body for message in db_session.query(Message)} == {f'body {i}' for i in range(205)}
