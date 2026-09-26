from datetime import datetime, timedelta, timezone


def payload(**changes):
    result = dict(title='Jazz Night', start_time='2027-01-02T20:00:00+01:00', venue_name='Club X',
                  address='Street 1, Bratislava', source_url='https://venue.example/events/jazz',
                  source_name='Venue', category='Music', source_reliability=.95, extraction_confidence=.95,
                  latitude=48.15, longitude=17.12, description='Venue description')
    result.update(changes)
    return result


def test_merge_preserves_better_source_and_both_references(client):
    first = client.post('/events', json=payload()).json()
    second = client.post('/events', json=payload(source_url='https://calendar.example/event/9?utm_campaign=test',
                                                source_name='Calendar', description='Worse description', source_reliability=.6)).json()
    assert first['id'] == second['id']
    assert second['description'] == 'Venue description'
    assert len(second['sources']) == 2
    assert all('utm_' not in s['source_url'] for s in second['sources'])


def test_utc_idempotency_and_cancellation(client):
    first = client.post('/events', json=payload()).json()
    cancelled = client.post('/events', json=payload(start_time='2027-01-02T19:00:00Z', status='cancelled')).json()
    assert first['id'] == cancelled['id']
    assert cancelled['status'] == 'cancelled'
    assert client.get('/events').json()['total'] == 0
    assert client.get('/events/viewport', params={'min_lat': 48, 'max_lat': 49, 'min_lng': 17, 'max_lng': 18}).json() == []


def test_same_listing_different_simultaneous_events_do_not_collapse(client):
    a = client.post('/events', json=payload(source_url='https://venue.example/program')).json()
    b = client.post('/events', json=payload(source_url='https://venue.example/program', title='Kids Workshop')).json()
    assert a['id'] != b['id']
    assert client.get('/events').json()['total'] == 2


def test_changed_url_slight_title_and_address_variation_deduplicate(client):
    first = client.post('/events', json=payload(title='Jazz Night Bratislava', address='Námestie SNP 25, Bratislava')).json()
    second = client.post('/events', json=payload(title='Jazz Night – Bratislava!', address='Nám. SNP 25',
                                                 source_url='https://calendar.example/new/jazz')).json()
    assert first['id'] == second['id']
    assert len(second['sources']) == 2


def test_recurring_occurrences_remain_distinct(client):
    first = client.post('/events', json=payload(source_url='https://venue.example/weekly')).json()
    second = client.post('/events', json=payload(source_url='https://venue.example/weekly',
                                                 start_time='2027-01-09T20:00:00+01:00')).json()
    assert first['id'] != second['id']


def test_ingestion_auth(client, monkeypatch):
    monkeypatch.setenv('INGESTION_API_KEY', 'secret')
    assert client.post('/events', json=payload()).status_code == 401
    assert client.post('/events', json=payload(), headers={'X-Ingestion-Key': 'secret'}).status_code == 201
    assert client.post('/events/maintenance').status_code == 401


def test_freshness_and_expiration(client, db_session):
    from app.models.event import Event
    item = client.post('/events', json=payload(start_time=(datetime.now(timezone.utc) + timedelta(days=30)).isoformat())).json()
    event = db_session.query(Event).first()
    event.last_verified_at = datetime.utcnow() - timedelta(days=15)
    db_session.commit()
    assert client.post('/events/maintenance').status_code == 200
    assert client.get('/events').json()['total'] == 0
    assert client.get('/events/' + item['id']).json()['status'] == 'removed'
