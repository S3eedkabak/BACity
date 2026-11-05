from datetime import datetime, timedelta
from app.models.community import Notification, Review, UserBlock, ReviewRevision, Organization
from tests.test_community import account


def test_notification_summary_all_owned_rows_and_pagination(client, db_session):
    owner, headers = account(client, db_session, 'inbox-owner')
    other, other_headers = account(client, db_session, 'inbox-other')
    db_session.add_all([Notification(user_id=owner.id, kind='message' if i % 2 else 'moderation', body=f'Update {i}') for i in range(125)] + [Notification(user_id=other.id, kind='message', body='Private')]); db_session.commit()
    assert client.get('/community/notification-summary').status_code == 401
    assert client.get('/community/notification-summary', headers=headers).json() == {'unread': 125, 'messages': 62}
    first = client.get('/community/notifications', params={'limit': 30}, headers=headers).json()
    second = client.get('/community/notifications', params={'offset': 30, 'limit': 100}, headers=headers).json()
    assert len(first) == 30 and len(second) == 95
    assert len({r['id'] for r in first + second}) == 125
    identifier = first[0]['id']
    assert client.post(f'/community/notifications/{identifier}/read', headers=other_headers).status_code == 404
    assert client.post(f'/community/notifications/{identifier}/read', headers=headers).status_code == 200
    assert client.post(f'/community/notifications/{identifier}/read', headers=headers).status_code == 200
    assert client.get('/community/notification-summary', headers=headers).json()['unread'] == 124
    assert client.get('/community/notification-summary', headers=other_headers).json()['unread'] == 1
    for params in ({'offset': -1}, {'limit': 101}, {'limit': 0}):
        assert client.get('/community/notifications', params=params, headers=headers).status_code == 422


def test_review_summary_real_visible_dimension_averages(client, db_session, sample_event):
    owner, headers = account(client, db_session, 'review-owner')
    other, _ = account(client, db_session, 'review-other')
    muted, _ = account(client, db_session, 'review-muted')
    db_session.add_all([
        Review(user_id=owner.id, target_type='event', target_id=str(sample_event.id), body='Great local concert.', dimensions={'worth_attending': 5, 'value': 3}),
        Review(user_id=other.id, target_type='event', target_id=str(sample_event.id), body='Enjoyed the evening.', dimensions={'worth_attending': 3}),
        Review(user_id=muted.id, target_type='event', target_id=str(sample_event.id), body='Hidden by moderation.', dimensions={'worth_attending': 1}, state='hidden'),
    ]); db_session.commit()
    path = f'/community/review-summary/event/{sample_event.id}'
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers).json() == {'count': 2, 'dimensions': {'worth_attending': {'average': 4, 'count': 2}, 'value': {'average': 3, 'count': 1}}}
    db_session.add(UserBlock(user_id=owner.id, blocked_id=other.id)); db_session.commit()
    assert client.get(path, headers=headers).json()['count'] == 1
    assert client.get(path, headers=headers).json()['dimensions']['worth_attending']['average'] == 5
    assert client.get(f'/community/review-summary/user/{sample_event.id}', headers=headers).status_code == 422


def test_review_update_keeps_author_identity_and_moderation(client, db_session, sample_event):
    owner, headers = account(client, db_session, 'review-writer')
    other, other_headers = account(client, db_session, 'review-second')
    sample_event.start_time = datetime.utcnow() - timedelta(days=1); db_session.commit()
    payload = {'target_type': 'event', 'target_id': str(sample_event.id), 'body': 'A very good experience.', 'dimensions': {'worth_attending': 4}}
    first = client.post('/community/reviews', json=payload, headers=headers)
    assert first.status_code == 200
    updated = client.post('/community/reviews', json={**payload, 'dimensions': {'worth_attending': 5}}, headers=headers)
    assert updated.json()['id'] == first.json()['id']
    assert db_session.query(Review).count() == 1 and db_session.query(ReviewRevision).count() == 1
    assert client.post('/community/reviews', json={**payload, 'user_id': str(owner.id)}, headers=other_headers).status_code == 422
    assert client.post('/community/reviews', json={**payload, 'dimensions': {'worth_attending': 6}}, headers=headers).status_code == 422
    assert client.post('/community/reviews', json={**payload, 'body': 'short'}, headers=headers).status_code == 422
    persisted = db_session.query(Review).one(); persisted.state = 'hidden'; db_session.commit()
    assert client.post('/community/reviews', json=payload, headers=headers).status_code == 403


def test_follow_state_owner_scoped_and_idempotent(client, db_session):
    owner, headers = account(client, db_session, 'follow-owner')
    other, other_headers = account(client, db_session, 'follow-other')
    org = Organization(name='Local arts'); db_session.add(org); db_session.commit()
    params = {'target_type': 'organizer', 'target_id': str(org.id)}; path = '/community/follow-state'
    assert client.get(path, params=params).status_code == 401
    assert client.get(path, params=params, headers=headers).json() == {'id': None, 'following': False}
    first = client.post('/community/follows', json=params, headers=headers).json()
    assert client.post('/community/follows', json=params, headers=headers).json()['id'] == first['id']
    assert client.get(path, params=params, headers=headers).json() == {'id': first['id'], 'following': True}
    assert client.get(path, params=params, headers=other_headers).json()['following'] is False
    assert client.delete('/community/follows/' + first['id'], headers=other_headers).status_code == 404
    assert client.delete('/community/follows/' + first['id'], headers=headers).status_code == 200
    assert client.get(path, params=params, headers=headers).json()['following'] is False
    assert client.get(path, params={**params, 'target_type': 'unsupported'}, headers=headers).status_code == 422


def test_ui_read_budget_is_shared_per_authenticated_owner(client, db_session, monkeypatch):
    from app.api.routes import community
    owner, headers = account(client, db_session, 'budget-owner')
    other, other_headers = account(client, db_session, 'budget-other')
    original = community.rate_limit
    def limited(db, key, limit, seconds=3600):
        return original(db, key, 2 if key.startswith('ui-read:') else limit, seconds)
    monkeypatch.setattr(community, 'rate_limit', limited)
    assert client.get('/community/notification-summary', headers=headers).status_code == 200
    assert client.get('/community/follow-state', params={'target_type': 'category', 'target_id': 'Music'}, headers=headers).status_code == 200
    assert client.get('/community/notification-summary', headers=headers).status_code == 429
    assert client.get('/community/notification-summary', headers=other_headers).status_code == 200
