from datetime import datetime, timedelta, timezone

from app.core.security import create_access_token, hash_password
from app.models.source import CrawlerRun, Source, SourceStatus
from app.models.user import User


def report(**changes):
    now = datetime.now(timezone.utc)
    result = {
        'name': 'Test Venue', 'domain': 'events.example', 'base_url': 'https://events.example',
        'event_url': 'https://events.example/program', 'source_type': 'venue', 'language': 'sk',
        'parser': 'jsonld', 'reliability_score': .9, 'requires_js': False,
        'crawl_frequency_minutes': 360, 'started_at': (now - timedelta(seconds=10)).isoformat(),
        'finished_at': now.isoformat(), 'success': True, 'status': 'healthy',
        'pages_processed': 3, 'items_processed': 5, 'accepted_events': 4,
        'rejected_events': 1, 'extraction_errors': 0, 'skip_reasons': {'missing_date': 1}, 'error': None,
    }
    result.update(changes)
    return result


def admin_headers(db_session):
    user = User(email='admin@example.com', hashed_password=hash_password('password123'), role='ADMIN', email_verified=True)
    db_session.add(user); db_session.commit()
    return {'Authorization': 'Bearer ' + create_access_token(user.email)}


def test_run_reporting_tracks_health_and_bounded_diagnostics(client, db_session):
    assert client.post('/crawler/runs', json=report()).status_code == 200
    source = db_session.query(Source).one()
    assert source.accepted_events == 4 and source.last_skip_reasons == {'missing_date': 1}
    assert db_session.query(CrawlerRun).count() == 1
    assert client.post('/crawler/runs', json=report(success=False, status='failed', error='selector changed')).status_code == 200
    db_session.expire_all(); source = db_session.query(Source).one()
    assert source.status == SourceStatus.failing and source.consecutive_failures == 1
    assert source.last_error == 'selector changed'


def test_source_admin_is_admin_only_and_runtime_is_ingestion_protected(client, db_session, monkeypatch):
    client.post('/crawler/runs', json=report())
    assert client.get('/crawler/admin/sources').status_code == 401
    headers = admin_headers(db_session)
    rows = client.get('/crawler/admin/sources', headers=headers).json()
    assert rows[0]['accepted_events'] == 4
    changed = client.patch('/crawler/admin/sources/' + rows[0]['id'], headers=headers, json={'enabled': False}).json()
    assert changed['enabled'] is False
    monkeypatch.setenv('INGESTION_API_KEY', 'secret')
    assert client.get('/crawler/runtime').status_code == 401
    runtime = client.get('/crawler/runtime', headers={'X-Ingestion-Key': 'secret'}).json()
    assert runtime == [{'domain': 'events.example', 'enabled': False, 'crawl_frequency_minutes': 360}]


def test_source_failure_prevents_false_removed_status(client, db_session):
    from app.models.event import Event, EventStatus
    payload = dict(title='Future event', start_time=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
                   venue_name='Hall', address='Street 1, Bratislava', source_url='https://events.example/e/1',
                   category='Community', source_reliability=.9, extraction_confidence=.9)
    event_id = client.post('/events', json=payload).json()['id']
    event = db_session.query(Event).first(); event.last_verified_at = datetime.utcnow() - timedelta(days=20)
    source = db_session.query(Source).first(); source.status = SourceStatus.failing
    db_session.commit()
    client.post('/events/maintenance')
    db_session.expire_all()
    assert db_session.get(Event, event_id).status == EventStatus.stale
