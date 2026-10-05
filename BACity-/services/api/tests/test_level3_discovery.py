"""Published human evidence uses the existing discovery queue, never private data."""
import json
import time
from uuid import UUID
from unittest.mock import Mock

import pytest
from app.core.security import create_access_token
from app.core import source_learning
from app.models.user import User
from app.models.event import Event, EventStatus
from app.models.event_source import EventSource
from app.models.candidate_source import CandidateSource
from app.models.community import Submission, Organization, OrganizationMember
from tests.test_community import event_payload


@pytest.fixture
def actors(db_session, monkeypatch):
    monkeypatch.setenv('INGESTION_API_KEY', 'learning-key')
    users = []
    for name, role in [('contributor', 'USER'), ('reviewer', 'MODERATOR')]:
        user = User(email=name+'@example.com', hashed_password='unused', email_verified=True, role=role)
        db_session.add(user)
        users.append(user)
    db_session.commit()
    return [(u, {'Authorization': 'Bearer '+create_access_token(u.email)}) for u in users]


def contribute(client, actors, data, decision='approve'):
    submitted = client.post('/community/submissions/events', json=data, headers=actors[0][1])
    assert submitted.status_code == 201, submitted.text
    identifier = submitted.json()['id']
    decided = client.post('/community/moderation/submissions/'+identifier,
        json={'decision': decision, 'reason': 'Reviewed public event evidence'}, headers=actors[1][1])
    assert decided.status_code == 200, decided.text
    assert '_source_learning' not in decided.json()['payload']
    return UUID(identifier), decided.json()


def drain(client):
    result = client.post('/crawler/learning/process', headers={'X-Ingestion-Key': 'learning-key'})
    assert result.status_code == 200, result.text
    return result.json()


def test_community_publication_queues_then_learns_without_private_identity(client, db_session, actors):
    identifier, result = contribute(client, actors, event_payload())
    db_session.expire_all()
    work = db_session.get(Submission, identifier).payload[source_learning.LEARNING_KEY]
    assert work['state'] == 'pending' and db_session.query(CandidateSource).count() == 0
    assert drain(client)['processed'] == 1
    assert drain(client)['processed'] == 0
    db_session.expire_all()
    candidate = db_session.query(CandidateSource).one()
    assert candidate.status == 'discovered' and candidate.attempts == 0
    serialized = json.dumps({c.name: getattr(candidate, c.name) for c in candidate.__table__.columns})
    assert actors[0][0].email not in serialized and str(actors[0][0].id) not in serialized
    event = db_session.get(Event, UUID(result['published_id']))
    assert event.is_manual_override and event.contributor_id == actors[0][0].id
    assert event.sources[0].facts['human_contribution'] is True
    assert client.get('/crawler/admin/learning', headers=actors[0][1]).status_code == 403
    history = client.get('/crawler/admin/learning', headers=actors[1][1]).json()
    assert history[0]['state'] == 'completed' and history[0]['sources'][0]['status'] == 'discovered'
    assert actors[0][0].email not in json.dumps(history)
    mine = client.get('/community/submissions', headers=actors[0][1]).json()
    assert '_source_learning' not in mine[0]['payload']
    assert client.post('/community/moderation/submissions/'+str(identifier),
        json={'decision': 'approve', 'reason': 'Repeated review'}, headers=actors[1][1]).status_code == 409
    assert db_session.query(CandidateSource).count() == 1


@pytest.mark.parametrize('state', ['pending', 'rejected', 'appealed', 'withdrawn'])
def test_unpublished_states_never_learn(client, db_session, actors, state):
    item = Submission(user_id=actors[0][0].id, kind='event', state=state, payload=event_payload())
    source_learning.queue_public_evidence(item, ['https://public.example/events'])
    db_session.add(item)
    db_session.commit()
    assert drain(client)['processed'] == 0
    assert db_session.query(CandidateSource).count() == 0


@pytest.mark.parametrize('source', ['', None, 'https://instagram.com/p/event', 'https://tiktok.com/@venue/video/123'])
def test_non_crawlable_event_still_publishes(client, db_session, actors, source):
    data = event_payload()
    data['source_url'] = source
    identifier, result = contribute(client, actors, data)
    assert result['published_id']
    assert drain(client)['processed'] == 0
    db_session.expire_all()
    assert db_session.query(Event).one().status == EventStatus.fresh
    assert db_session.get(Submission, identifier).payload[source_learning.LEARNING_KEY]['state'] == 'no_eligible_public_source'
    assert db_session.query(CandidateSource).count() == 0


@pytest.mark.parametrize('url', ['http://localhost', 'http://127.0.0.1', 'http://169.254.169.254/latest/meta-data',
    'http://postgres', 'https://10.0.0.1', 'https://safe.example:8443', 'https://safe.example/?token=secret',
    'https://user:password@safe.example', 'https://safe.internal'])
def test_private_evidence_is_not_a_crawl_target_or_publication_dependency(client, db_session, actors, url):
    data = event_payload()
    data.update(source_url='', public_source_url=url)
    contribute(client, actors, data)
    assert drain(client)['processed'] == 0
    assert db_session.query(Event).count() == 1 and db_session.query(CandidateSource).count() == 0


def test_social_provenance_can_learn_separate_public_calendar(client, db_session, actors):
    data = event_payload()
    data.update(source_url='https://facebook.com/events/123', public_source_url='https://venue.example/calendar')
    contribute(client, actors, data)
    drain(client)
    db_session.expire_all()
    assert db_session.query(EventSource).one().source_url == data['source_url']
    assert db_session.query(CandidateSource).one().domain == 'venue.example'


def test_verified_organizer_website_is_evidence_not_automatic_trust(client, db_session, actors):
    org = Organization(name='Neighborhood organizer', website='https://organizer.example/calendar', verified=True)
    db_session.add(org)
    db_session.flush()
    db_session.add(OrganizationMember(user_id=actors[0][0].id, organization_id=org.id))
    db_session.commit()
    data = event_payload()
    data['source_url'] = ''
    result = client.post('/organizer/'+str(org.id)+'/events',
        json={'event': data, 'dates': [data['start_time']]}, headers=actors[0][1])
    assert result.status_code == 200, result.text
    drain(client)
    db_session.expire_all()
    assert db_session.query(Event).one().organization_id == org.id
    assert db_session.query(CandidateSource).one().status == 'discovered'


def test_equivalent_sources_and_multiple_contributions_are_idempotent(client, db_session, actors):
    data = event_payload()
    data.update(source_url='https://www.venue.example/events?utm_source=community#poster', public_source_url='https://venue.example/calendar')
    contribute(client, actors, data)
    contribute(client, actors, {**data, 'source_url': 'https://venue.example/events'})
    drain(client)
    assert db_session.query(CandidateSource).count() == 1
    assert db_session.query(Event).count() == 1


def test_learning_failure_retries_without_rolling_back_publication(client, db_session, actors, monkeypatch, caplog):
    identifier, result = contribute(client, actors, event_payload())
    original = source_learning.learn_public_url
    broken = Mock(side_effect=RuntimeError('private-content-never-log'))
    monkeypatch.setattr(source_learning, 'learn_public_url', broken)
    drain(client)
    db_session.expire_all()
    item = db_session.get(Submission, identifier)
    assert item.state == 'approved' and db_session.get(Event, UUID(result['published_id']))
    assert item.payload[source_learning.LEARNING_KEY]['state'] == 'retry'
    assert 'private-content-never-log' not in caplog.text
    assert drain(client)['processed'] == 0
    item.payload = {**item.payload, source_learning.LEARNING_KEY: {**item.payload[source_learning.LEARNING_KEY], 'next_attempt': 0}}
    db_session.commit()
    monkeypatch.setattr(source_learning, 'learn_public_url', original)
    drain(client)
    assert db_session.query(CandidateSource).count() == 1


@pytest.mark.parametrize('human_first', [True, False])
def test_crawler_and_human_share_canonical_dedup_and_provenance(client, db_session, actors, human_first):
    data = event_payload()
    crawler = {**data, 'source_url': 'https://crawler.example/concert', 'extraction_method': 'jsonld'}
    if human_first:
        _, human = contribute(client, actors, data)
        crawled = client.post('/events', json=crawler, headers={'X-Ingestion-Key': 'learning-key'})
    else:
        crawled = client.post('/events', json=crawler, headers={'X-Ingestion-Key': 'learning-key'})
        _, human = contribute(client, actors, data)
    assert crawled.status_code == 201, crawled.text
    assert crawled.json()['id'] == human['published_id']
    assert db_session.query(Event).count() == 1
    db_session.expire_all()
    assert db_session.query(EventSource).count() == 2
    assert any(s.facts.get('human_contribution') for s in db_session.query(EventSource))


def test_removal_before_processing_skips_learning_not_existing_candidate(client, db_session, actors):
    contribute(client, actors, event_payload())
    db_session.query(Event).one().status = EventStatus.removed
    db_session.commit()
    drain(client)
    db_session.expire_all()
    assert db_session.query(Submission).one().payload[source_learning.LEARNING_KEY]['state'] == 'skipped'
    assert db_session.query(CandidateSource).count() == 0


def test_blocked_candidate_does_not_invalidate_event_or_reset_trust(client, db_session, actors):
    db_session.add(CandidateSource(domain='example.com', url='https://example.com/', origin='https://example.com/', discovered=time.time(), status='blocked', reason='unsafe_address'))
    db_session.commit()
    contribute(client, actors, event_payload())
    drain(client)
    db_session.expire_all()
    assert db_session.query(CandidateSource).one().status == 'blocked'
    assert db_session.query(Event).one().status == EventStatus.fresh


def test_account_deletion_leaves_only_public_candidate_evidence(client, db_session, actors):
    contribute(client, actors, event_payload())
    deleted = client.request('DELETE', '/community/account', headers=actors[0][1], json={'reason': 'Remove my private account'})
    assert deleted.status_code == 200, deleted.text
    drain(client)
    candidate = db_session.query(CandidateSource).one()
    assert candidate.domain == 'example.com'
    assert not any('user' in c.name or 'contributor' in c.name for c in candidate.__table__.columns)


def test_learning_endpoint_requires_configured_worker_key(client, actors):
    assert client.post('/crawler/learning/process').status_code == 401
    assert client.post('/crawler/learning/process', headers=actors[0][1]).status_code == 401


def test_duplicate_evidence_provenance_survives_crawler_refresh(client, db_session, actors):
    data = event_payload()
    contribute(client, actors, data)
    result = client.post('/events', json=data, headers={'X-Ingestion-Key': 'learning-key'})
    assert result.status_code == 201
    db_session.expire_all()
    assert db_session.query(EventSource).one().facts['human_contribution'] is True
    assert db_session.query(EventSource).one().source_id is not None


def test_private_text_media_and_spoofed_work_are_not_learning_evidence(client, db_session, actors):
    data = event_payload()
    data.update(source_url='', description='A poster mentions https://secret.example/calendar in private text.',
        image_url='https://uploads.example/private-screenshot.png',
        _source_learning={'state': 'pending', 'urls': ['http://localhost']})
    contribute(client, actors, data)
    assert drain(client)['processed'] == 0
    assert db_session.query(CandidateSource).count() == 0


def test_learning_retries_are_bounded(client, db_session, actors, monkeypatch):
    identifier, _ = contribute(client, actors, event_payload())
    monkeypatch.setattr(source_learning, 'learn_public_url', Mock(side_effect=RuntimeError()))
    for attempt in range(5):
        db_session.expire_all()
        item = db_session.get(Submission, identifier)
        item.payload = {**item.payload, source_learning.LEARNING_KEY: {**item.payload[source_learning.LEARNING_KEY], 'next_attempt': 0}}
        db_session.commit()
        assert drain(client)['processed'] == 1
    db_session.expire_all()
    work = db_session.get(Submission, identifier).payload[source_learning.LEARNING_KEY]
    assert work['attempts'] == 5 and work['state'] == 'failed'
    assert drain(client)['processed'] == 0
    assert db_session.query(Event).count() == 1


def test_learning_batch_and_evidence_bounds(db_session, actors):
    from app.api.routes.community import publish
    for index in range(30):
        data = event_payload()
        data.update(title='Public event '+str(index), source_url='https://venue'+str(index)+'.example/events')
        item = Submission(user_id=actors[0][0].id, kind='event', state='approved', payload=data)
        db_session.add(item)
        item.published_id = publish(db_session, item, 'Community')
        source_learning.queue_public_evidence(item, ['https://one.example/', 'https://two.example/', 'https://three.example/', 'https://four.example/'])
        assert len(item.payload[source_learning.LEARNING_KEY]['urls']) <= 3
    db_session.commit()
    assert source_learning.process_public_evidence(db_session, limit=1000)['processed'] == 25
    assert source_learning.process_public_evidence(db_session)['processed'] == 5


def test_human_provenance_cannot_prove_upstream_removal(client, db_session, actors):
    from datetime import datetime, timedelta
    from app.crud.ingestion import expire_events
    data = event_payload()
    # Future event remains valid even when its public evidence was never crawled.
    data['start_time'] = (datetime.now().astimezone() + timedelta(days=30)).isoformat()
    contribute(client, actors, data)
    event = db_session.query(Event).one()
    event.last_verified_at = datetime.utcnow() - timedelta(days=20)
    db_session.commit()
    expire_events(db_session)
    assert db_session.query(Event).one().status == EventStatus.stale
