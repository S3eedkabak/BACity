from datetime import datetime, timedelta, timezone
from io import BytesIO
import re
from PIL import Image
from app.models.user import User
from app.models.community import MailOutbox, Submission, Organization, OrganizationMember, Message, CityUtility, Review
from app.models.oauth_identity import OAuthIdentity
from app.models.event import Event


def account(client, db, name, role='USER', verified=True):
    email = name + '@example.com'
    result = client.post('/auth/register', json={'email': email, 'password': 'password123'})
    assert result.status_code == 201, result.text
    user = db.query(User).filter_by(email=email).one()
    user.role, user.email_verified = role, verified
    db.commit()
    login = client.post('/auth/login', json={'email': email, 'password': 'password123'})
    assert login.status_code == 200, login.text
    return user, {'Authorization': 'Bearer ' + login.json()['access_token']}


def event_payload():
    return {'title': 'Neighborhood concert', 'description': 'A concert organized by the local neighborhood community.',
            'start_time': (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
            'address': 'Bratislava, Main Square', 'source_url': 'https://example.com/concert',
            'category': 'Music', 'latitude': 48.145, 'longitude': 17.109}


def test_verified_account_and_single_use_reset(client, db_session):
    user, headers = account(client, db_session, 'first', verified=False)
    assert client.post('/community/submissions/events', json=event_payload(), headers=headers).status_code == 403
    mail = db_session.query(MailOutbox).one()
    token = re.search(r'token=([^\s]+)', mail.body).group(1)
    assert client.post('/auth/verify-email', json={'token': token}).status_code == 200
    assert client.post('/auth/verify-email', json={'token': token}).status_code == 400
    assert client.post('/auth/request-reset', json={'email': user.email}).status_code == 200
    db_session.expire_all()
    mail = db_session.query(MailOutbox).order_by(MailOutbox.created_at.desc()).first()
    token = re.search(r'token=([^\s]+)', mail.body).group(1)
    assert client.post('/auth/reset-password', json={'token': token, 'password': 'newpassword123'}).status_code == 200
    assert client.get('/users/me', headers=headers).status_code == 401
    assert client.post('/auth/reset-password', json={'token': token, 'password': 'newpassword123'}).status_code == 400


def test_pending_moderation_and_guide_permissions(client, db_session):
    user, headers = account(client, db_session, 'guide', role='GUIDE')
    moderator, mod = account(client, db_session, 'moderator', role='MODERATOR')
    result = client.post('/community/submissions/events', json=event_payload(), headers=headers)
    assert result.status_code == 201, result.text
    identifier = result.json()['id']
    assert db_session.query(Event).count() == 0
    assert client.get('/community/moderation/submissions', headers=headers).status_code == 403
    decision = {'decision': 'approve', 'reason': 'Confirmed on organizer website'}
    result = client.post('/community/moderation/submissions/' + identifier, json=decision, headers=mod)
    assert result.status_code == 200, result.text
    assert result.json()['state'] == 'approved'
    published = db_session.query(Event).one()
    assert published.is_manual_override
    assert published.trust_level == 'Community'
    assert client.post('/community/moderation/submissions/' + identifier, json=decision, headers=mod).status_code == 409
    assert client.patch('/community/moderation/users/' + str(user.id) + '/role', json={'role': 'ADMIN', 'reason': 'Attempt upgrade'}, headers=headers).status_code == 403


def test_appeals_require_different_moderator(client, db_session):
    _, user = account(client, db_session, 'author')
    _, mod = account(client, db_session, 'mod', role='MODERATOR')
    _, other = account(client, db_session, 'other', role='MODERATOR')
    submission = client.post('/community/submissions/events', json=event_payload(), headers=user).json()['id']
    decision = {'decision': 'reject', 'reason': 'Missing independently verifiable evidence'}
    assert client.post(f'/community/moderation/submissions/{submission}', json=decision, headers=mod).status_code == 200
    assert client.post(f'/community/submissions/{submission}/appeal', json={'reason': 'New evidence now available'}, headers=user).status_code == 200
    assert client.post(f'/community/moderation/submissions/{submission}', json=decision, headers=mod).status_code == 403
    assert client.post(f'/community/moderation/submissions/{submission}', json=decision, headers=other).status_code == 200


def test_mutual_follow_messages_blocking_and_private_profiles(client, db_session):
    a, ha = account(client, db_session, 'alice')
    b, hb = account(client, db_session, 'bob')
    _, hc = account(client, db_session, 'charlie')
    path = '/community/messages/' + str(b.id)
    assert client.post(path, json={'body': 'Hello'}, headers=ha).status_code == 403
    for h, other in [(ha, b), (hb, a)]:
        assert client.post('/community/follows', json={'target_type': 'user', 'target_id': str(other.id)}, headers=h).status_code == 200
    assert client.post(path, json={'body': 'Hello Bob'}, headers=ha).status_code == 200
    assert client.get(path, headers=hc).json() == []
    assert client.post('/community/blocks/' + str(a.id), headers=hb).status_code == 200
    assert client.post(path, json={'body': 'Blocked'}, headers=ha).status_code == 403
    assert client.get(path, headers=ha).status_code == 403
    assert client.get('/community/profiles/' + str(b.id), headers=ha).status_code == 404


def test_utility_approval_confirmation_and_reviews(client, db_session, sample_event):
    _, h = account(client, db_session, 'resident')
    _, mod = account(client, db_session, 'reviewer', role='MODERATOR')
    result = client.post('/community/submissions/utilities', json={'name': 'Town hall toilet', 'latitude': 48.145, 'longitude': 17.109, 'free': True}, headers=h)
    assert result.status_code == 201, result.text
    assert client.get('/community/utilities').json() == []
    result = client.post('/community/moderation/submissions/' + result.json()['id'], json={'decision': 'approve', 'reason': 'Location independently checked'}, headers=mod)
    assert result.status_code == 200, result.text
    utility = client.get('/community/utilities', params={'free': True}).json()[0]
    assert utility['last_confirmed_at'] is None
    path = '/community/utilities/' + utility['id'] + '/confirm'
    assert client.post(path, json={'operational_status': 'open', 'cleanliness': 4}, headers=h).status_code == 200
    assert client.post(path, json={'operational_status': 'open'}, headers=h).status_code == 429
    review = {'target_type': 'event', 'target_id': str(sample_event.id), 'body': 'A lovely local event', 'dimensions': {'value': 4}}
    assert client.post('/community/reviews', json=review, headers=h).status_code == 422
    sample_event.start_time = datetime.utcnow() - timedelta(days=1)
    db_session.commit()
    result = client.post('/community/reviews', json=review, headers=h)
    assert result.status_code == 200, result.text
    assert result.json()['attendance_verified'] is False


def test_utility_viewport_nearby_freshness_and_conflicts(client, db_session):
    first, h1 = account(client, db_session, 'utility-one')
    _, h2 = account(client, db_session, 'utility-two')
    utility = CityUtility(
        kind='toilet', name='Official WC', latitude=48.145, longitude=17.109,
        free=True, operational_status='unknown',
        source_url='https://geoportal.bratislava.sk/hSite/rest/services/Hosted/verejne_toalety_data_/FeatureServer/1?objectid=99',
    )
    db_session.add(utility); db_session.commit()

    viewport = client.get('/community/utilities/viewport', params={
        'min_lat': 48.14, 'max_lat': 48.15, 'min_lng': 17.10, 'max_lng': 17.12,
    })
    assert viewport.status_code == 200 and len(viewport.json()) == 1
    assert viewport.json()[0]['freshness_status'] == 'current'
    nearby = client.get('/community/utilities/nearby', params={'lat': 48.145, 'lng': 17.109, 'radius_km': 1})
    assert nearby.status_code == 200 and nearby.json()[0]['id'] == str(utility.id)

    path = f'/community/utilities/{utility.id}/confirm'
    assert client.post(path, json={'operational_status': 'open'}, headers=h1).json()['operational_status'] == 'open'
    conflicted = client.post(path, json={'operational_status': 'closed'}, headers=h2).json()
    assert conflicted['operational_status'] == 'unknown'
    assert conflicted['status_conflict'] is True
    assert conflicted['confirmation_summary'] == {'open': 1, 'closed': 1}
    detail = client.get(f'/community/utilities/{utility.id}').json()
    assert detail['confirmation_count'] == 2 and detail['confidence_score'] < 1


def test_organizer_claim_isolation_and_recommendations(client, db_session, sample_event):
    a, ha = account(client, db_session, 'owner')
    _, hb = account(client, db_session, 'outsider')
    _, mod = account(client, db_session, 'adminreview', role='MODERATOR')
    org = client.post('/community/organizations', json={'name': 'Town venue', 'website': 'https://example.com'}, headers=ha).json()['id']
    assert client.get(f'/organizer/{org}/analytics', headers=ha).status_code == 403
    claim = client.post(f'/community/organizations/{org}/claim', json={'reason': 'I operate this venue', 'evidence_url': 'https://example.com/about'}, headers=ha).json()['id']
    assert client.post(f'/community/moderation/submissions/{claim}', json={'decision': 'approve', 'reason': 'Ownership independently checked'}, headers=mod).status_code == 200
    assert client.get(f'/organizer/{org}/analytics', headers=ha).status_code == 200
    assert client.get(f'/organizer/{org}/analytics', headers=hb).status_code == 403
    a.interests = ['Nightlife']
    db_session.commit()
    results = client.get('/recommendations', headers=ha).json()
    assert 'Matches your interests' in results[0]['reasons']


def test_logout_and_delete_revoke_access(client, db_session):
    a, ha = account(client, db_session, 'logout')
    assert client.post('/auth/logout', headers=ha).status_code == 200
    assert client.get('/users/me', headers=ha).status_code == 401
    b, hb = account(client, db_session, 'delete')
    assert client.request('DELETE', '/community/account', json={'reason': 'No longer using this account'}, headers=hb).status_code == 200
    assert client.get('/users/me', headers=hb).status_code == 401


def test_account_export_and_complete_private_data_erasure(client, db_session):
    user, headers = account(client, db_session, 'privacy')
    other, _ = account(client, db_session, 'privacy-other')
    db_session.add(OAuthIdentity(user_id=user.id, provider='google', subject='provider-subject'))
    db_session.add(Message(sender_id=user.id, recipient_id=other.id, body='private text'))
    db_session.commit()

    exported = client.get('/community/account/export', headers=headers)
    assert exported.status_code == 200, exported.text
    payload = exported.json()
    assert payload['profile']['email'] == 'privacy@example.com'
    assert 'hashed_password' not in payload['profile']
    assert payload['oauth_identities'][0]['subject'] == 'provider-subject'
    assert payload['messages'][0]['body'] == 'private text'

    deleted = client.request('DELETE', '/community/account', json={'reason': 'Privacy request'}, headers=headers)
    assert deleted.status_code == 200
    db_session.expire_all()
    anonymized = db_session.get(User, user.id)
    assert anonymized.email.endswith('@example.invalid') and not anonymized.active
    assert db_session.query(OAuthIdentity).filter_by(user_id=user.id).count() == 0
    assert db_session.query(Message).filter(Message.sender_id == user.id).count() == 0
    assert db_session.query(MailOutbox).filter_by(recipient='privacy@example.com').count() == 0


def test_rich_profile_social_pagination_and_avatar(client, db_session, sample_event, tmp_path, monkeypatch):
    from app.api.routes import community

    alice, ha = account(client, db_session, 'profile-alice', role='GUIDE')
    bob, hb = account(client, db_session, 'profile-bob')
    alice.display_name, alice.neighborhood, alice.reputation = 'Alice Guide', 'Staré Mesto', 240
    bob.display_name = 'Bob Resident'
    sample_event.neighborhood = 'Staré Mesto'
    contribution = Submission(user_id=alice.id, kind='event', payload={}, state='approved', published_id=str(sample_event.id))
    review = Review(user_id=alice.id, target_type='event', target_id=str(sample_event.id),
                    body='A detailed and useful review', dimensions={'value': 5})
    db_session.add_all([contribution, review]); db_session.commit()

    assert client.post('/community/follows', json={'target_type': 'user', 'target_id': str(alice.id)}, headers=hb).status_code == 200
    assert client.post('/community/follows', json={'target_type': 'category', 'target_id': 'music'}, headers=ha).status_code == 200
    assert client.post('/community/follows', json={'target_type': 'neighborhood', 'target_id': 'staré mesto'}, headers=ha).status_code == 200

    profile = client.get(f'/community/profiles/{alice.id}', headers=hb).json()
    assert profile['reputation_level'] == 'Local Guide'
    assert profile['followers'] == 1 and profile['contributions_count'] == 1 and profile['reviews_count'] == 1
    assert client.get(f'/community/profiles/{alice.id}/contributions', params={'limit': 1}, headers=hb).json()[0]['title'] == sample_event.title
    assert client.get(f'/community/profiles/{alice.id}/reviews', params={'limit': 1}, headers=hb).json()[0]['target_name'] == sample_event.title
    assert client.get(f'/community/profiles/{alice.id}/followers', params={'limit': 1}, headers=hb).json()[0]['display_name'] == 'Bob Resident'
    following = client.get(f'/community/profiles/{alice.id}/following', params={'limit': 1}, headers=hb).json()
    assert len(following) == 1 and following[0]['target_label'] == 'Staré Mesto'
    targets = client.get('/community/follow-targets', params={'target_type': 'guide', 'q': 'Alice'}, headers=hb).json()
    assert targets[0]['target_id'] == str(alice.id)
    people = client.get('/community/people', params={'q': 'Alice', 'limit': 1}, headers=hb).json()
    assert people[0]['display_name'] == 'Alice Guide'

    monkeypatch.setattr(community.settings, 'media_root', str(tmp_path))
    image = BytesIO(); Image.new('RGB', (300, 200), '#ff7f86').save(image, format='PNG')
    uploaded = client.post('/community/profile/avatar', files={'avatar': ('avatar.png', image.getvalue(), 'image/png')}, headers=ha)
    assert uploaded.status_code == 200, uploaded.text
    assert f'/media/avatars/{alice.id}.jpg?v=' in uploaded.json()['avatar_url']
    saved = Image.open(tmp_path / 'avatars' / f'{alice.id}.jpg')
    assert saved.size == (512, 512)
