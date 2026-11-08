from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.models.event import Event
from app.models.event_source import EventSource
from app.models.source import Source
from tests.test_ingestion import payload
from tests.test_crawler_admin import admin_headers, report


def test_registered_publisher_identity_and_linked_ticket_provenance(client,db_session):
    assert client.post('/crawler/runs',json=report(domain='visitbratislava.com',name='Visit Bratislava')).status_code==200
    event=client.post('/events',json=payload(source_url='https://www.visitbratislava.com/events/jazz/',
        original_source_url='https://www.visitbratislava.com/events/jazz/')).json()
    assert db_session.query(Source).count()==1
    source=db_session.query(Source).one()
    assert source.domain=='visitbratislava.com'
    evidence=db_session.query(EventSource).one()
    assert evidence.source_id==source.id
    assert evidence.original_source_url=='https://www.visitbratislava.com/events/jazz/'
    assert event['sources'][0]['source_url'].startswith('https://www.visitbratislava.com/')


def test_linked_external_calendar_observation_attributed_to_crawled_publisher(client,db_session):
    client.post('/events',json=payload(source_url='https://tickets.example/show/7',
        original_source_url='https://city.example/calendar',source_name='City Calendar'))
    assert db_session.query(Source).one().domain=='city.example'
    assert db_session.query(EventSource).one().original_source_url=='https://city.example/calendar'


def test_credible_unmapped_venue_visible_in_explore_excluded_from_map(client,db_session):
    start=(datetime.now(timezone.utc)+timedelta(days=5)).isoformat()
    event=client.post('/events',json=payload(start_time=start,venue_name='Public hall',
        latitude=None,longitude=None)).json()
    assert event['latitude'] is None and event['venue']['latitude'] is None
    assert client.get('/events').json()['total']==1
    assert client.get('/events/viewport',params={'min_lat':48,'max_lat':48.35,'min_lng':16.9,'max_lng':17.35}).json()==[]
    assert client.get('/crawler/admin/quality').status_code==401
    result=client.get('/crawler/admin/quality',headers=admin_headers(db_session)).json()['reconciliation']
    assert result['counts']['total']==result['counts']['future']==1
    assert result['counts']['explore_eligible']==result['counts']['home_candidate_eligible']==1
    assert result['counts']['map_eligible']==0 and result['counts']['unmapped_explore_eligible']==1


def test_same_publisher_nearby_performances_are_distinct(client):
    first=client.post('/events',json=payload(source_url='https://venue.example/slots')).json()
    second=client.post('/events',json=payload(source_url='https://venue.example/slots',
        start_time='2027-01-02T20:10:00+01:00')).json()
    assert first['id']!=second['id']


def test_malformed_original_publisher_url_is_rejected(client):
    assert client.post('/events',json=payload(original_source_url='file:///private/calendar')).status_code==422


def test_date_only_exhibition_survives_lifecycle_without_planner_end_clock(client,db_session):
    now=datetime.now(timezone.utc)
    end=(now+timedelta(days=5)).date().isoformat()
    created=client.post('/events',json=payload(start_time=(now-timedelta(days=30)).isoformat(),
        end_date=end,temporal_evidence='date_range')).json()
    assert created['end_date']==end and created['end_time'] is None
    assert client.post('/events/maintenance').status_code==200
    assert client.get('/events/'+created['id']).json()['status']=='fresh'
    event=db_session.get(Event,UUID(created['id']))
    event.end_date=(now-timedelta(days=3)).date();db_session.commit()
    client.post('/events/maintenance')
    assert client.get('/events/'+created['id']).json()['status']=='expired'


def test_same_source_date_precision_corrects_its_previous_midnight_placeholder(client):
    initial=client.post('/events',json=payload(end_time='2027-01-05T00:00:00+00:00',
        extraction_method='visit_microdata',temporal_evidence='explicit_end')).json()
    corrected=client.post('/events',json=payload(end_date='2027-01-05',
        extraction_method='visit_microdata',temporal_evidence='date_range')).json()
    assert initial['id']==corrected['id'] and corrected['end_time'] is None
    assert corrected['end_date']=='2027-01-05'


def test_postponement_withheld_but_saved_identity_survives_reschedule(client):
    first=client.post('/events',json=payload()).json()
    postponed=client.post('/events',json=payload(status='postponed')).json()
    assert postponed['id']==first['id'] and postponed['status']=='postponed'
    assert client.get('/events').json()['total']==0
    assert client.get('/events/'+first['id']).status_code==200
    resumed=client.post('/events',json=payload(start_time='2027-01-03T20:00:00+01:00',
        previous_start_time='2027-01-02T20:00:00+01:00')).json()
    assert resumed['id']==first['id'] and resumed['status']=='fresh'
    assert client.get('/events').json()['total']==1


def test_original_publisher_separate_slots_not_collapsed_through_ticket_links(client):
    first=client.post('/events',json=payload(source_url='https://tickets.example/show/one',
        original_source_url='https://city.example/calendar')).json()
    second=client.post('/events',json=payload(source_url='https://tickets.example/show/two',
        original_source_url='https://city.example/calendar',start_time='2027-01-02T20:10:00+01:00')).json()
    assert first['id']!=second['id']


def test_health_report_refreshes_extraction_metadata_for_ingestion_created_source(client,db_session):
    client.post('/events',json=payload(source_url='https://events.example/detail'))
    assert client.post('/crawler/runs',json=report(parser='structured')).status_code==200
    source=db_session.query(Source).one()
    assert source.parser=='structured' and source.event_url==report()['event_url']
