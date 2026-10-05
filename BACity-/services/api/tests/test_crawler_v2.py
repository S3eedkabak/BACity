from datetime import datetime, timedelta

from app.models.event import Event, EventStatus
from app.models.event_source import EventSource
from app.models.source import Source, SourceStatus
from tests.test_ingestion import payload
from tests.test_crawler_admin import admin_headers, report


def test_temporal_evidence_wins_and_weak_refresh_cannot_erase_it(client,db_session):
    first=client.post('/events',json=payload(end_time='2027-01-02T22:00:00+01:00',temporal_evidence='text_range')).json()
    stronger=client.post('/events',json=payload(source_url='https://organizer.example/jazz',source_reliability=.8,
        end_time='2027-01-02T23:00:00+01:00',temporal_evidence='explicit_end',organizer_name='Music Hall')).json()
    assert stronger['id'] == first['id'] and '22:00:00' in stronger['end_time']
    weaker=client.post('/events',json=payload(end_time='2027-01-02T21:00:00+01:00',temporal_evidence='text_range',source_reliability=.6,description='Weak refresh')).json()
    assert weaker['end_time'] == stronger['end_time']
    assert weaker['description'] == 'Venue description'
    missing=client.post('/events',json=payload()).json()
    assert missing['end_time'] == stronger['end_time']
    facts=db_session.query(EventSource).filter(EventSource.source_url=='https://organizer.example/jazz').one().facts
    assert facts['best_end']['rank'] == 3 and facts['organizer'] == 'Music Hall' and facts['observed_at']
    admin=admin_headers(db_session)
    quality=client.get('/crawler/admin/quality',headers=admin).json()
    assert quality['coverage']['organizer']['count'] == 1
    assert quality['ingestion_outcomes']['organizer.example']['ingestion_merged'] == 1
    assert client.get('/crawler/admin/events/'+first['id']+'/quality').status_code == 401
    audit=client.get('/crawler/admin/events/'+first['id']+'/quality',headers=admin).json()
    assert len(audit['sources']) == 2 and 'end_time' not in audit['missing']


def test_same_artist_repeat_show_and_different_venue_not_merged(client):
    a=client.post('/events',json=payload()).json()
    b=client.post('/events',json=payload(start_time='2027-01-02T22:00:00+01:00',source_url='https://venue.example/events/late')).json()
    c=client.post('/events',json=payload(venue_name='Completely Different Hall',source_url='https://other.example/e')).json()
    assert len({a['id'],b['id'],c['id']}) == 3


def test_explicit_reschedule_preserves_canonical_id_not_recurring_occurrence(client):
    a=client.post('/events',json=payload()).json()
    b=client.post('/events',json=payload(start_time='2027-01-03T20:00:00+01:00',previous_start_time='2027-01-02T20:00:00+01:00')).json()
    assert a['id'] == b['id'] and b['start_time'].startswith('2027-01-03')


def test_multisource_survives_one_source_failure(client,db_session):
    client.post('/events',json=payload())
    client.post('/events',json=payload(source_url='https://calendar.example/jazz'))
    event=db_session.query(Event).one()
    event.last_verified_at=datetime.utcnow()-timedelta(days=20)
    for source in db_session.query(Source):
        source.crawl_status='healthy'; source.last_success_at=datetime.utcnow()
    db_session.query(Source).filter(Source.domain=='calendar.example').one().status=SourceStatus.failing
    db_session.commit()
    client.post('/events/maintenance')
    db_session.expire_all()
    assert db_session.query(Event).one().status == EventStatus.stale


def test_quota_limited_crawl_cannot_prove_event_removal(client,db_session):
    client.post('/events',json=payload(source_url='https://events.example/jazz'))
    event=db_session.query(Event).one(); event.last_verified_at=datetime.utcnow()-timedelta(days=20)
    db_session.commit()
    assert client.post('/crawler/runs',json=report(status='partial')).status_code == 200
    client.post('/events/maintenance')
    db_session.expire_all()
    assert db_session.query(Event).one().status == EventStatus.stale


def test_learning_requires_key_and_only_public_canonical_evidence(client,db_session,monkeypatch):
    created=client.post('/events',json=payload()).json()
    assert client.post('/crawler/evidence',json={'event_id':created['id']}).status_code == 503
    monkeypatch.setenv('INGESTION_API_KEY','test-key')
    headers={'X-Ingestion-Key':'test-key'}
    assert client.post('/crawler/evidence',json={'event_id':created['id']}).status_code == 401
    assert client.post('/crawler/evidence',json={'event_id':created['id'],'private_message':'secret'},headers=headers).status_code == 422
    assert client.post('/crawler/evidence',json={'event_id':created['id']},headers=headers).status_code == 200
    assert client.post('/crawler/evidence',json={'event_id':created['id']},headers=headers).status_code == 200
    event=db_session.query(Event).one(); event.source_url='http://169.254.169.254/latest/meta-data'; db_session.commit()
    assert client.post('/crawler/evidence',json={'event_id':created['id']},headers=headers).status_code == 422
    event.status=EventStatus.removed; db_session.commit()
    assert client.post('/crawler/evidence',json={'event_id':created['id']},headers=headers).status_code == 422


def test_candidate_admin_disable_wins_over_snapshot_and_quality_visible(client,db_session,monkeypatch):
    monkeypatch.setenv('INGESTION_API_KEY','test-key')
    worker={'X-Ingestion-Key':'test-key'}
    item={'domain':'hall.example','url':'https://hall.example/events','origin':'https://city.example/events',
          'status':'probation','discovered':1,'attempts':1,'good_runs':1,'failures':0,
          'metrics':{'quality/events':4,'quality/with_end':3}}
    assert client.post('/crawler/candidates/report',json={'items':[item]},headers=worker).status_code == 200
    assert client.get('/crawler/admin/candidates').status_code == 401
    admin=admin_headers(db_session)
    assert client.patch('/crawler/admin/candidates/hall.example',json={'enabled':False},headers=admin).status_code == 200
    assert client.post('/crawler/candidates/report',json={'items':[item]},headers=worker).status_code == 200
    row=client.get('/crawler/candidates/runtime',headers=worker).json()[0]
    assert row['enabled'] is False and row['status'] == 'disabled'
    assert client.patch('/crawler/admin/candidates/hall.example',json={'enabled':True,'url':'http://postgres'},headers=admin).status_code == 422
    item['url']='http://127.0.0.1/events'
    assert client.post('/crawler/candidates/report',json={'items':[item]},headers=worker).status_code == 422
    quality=client.get('/crawler/admin/quality',headers=admin)
    assert quality.status_code == 200 and quality.json()['coverage']['end_datetime']['count'] == 0
    source=client.post('/crawler/runs',json=report(domain='hall.example'),headers=worker).json()['source_id']
    assert client.patch('/crawler/admin/candidates/hall.example',json={'enabled':True},headers=admin).status_code == 200
    assert client.patch('/crawler/admin/sources/'+source,json={'enabled':False},headers=admin).status_code == 200
    assert client.get('/crawler/candidates/runtime',headers=worker).json()[0]['enabled'] is False
