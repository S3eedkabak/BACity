"""Four controlled scheduler cycles, including identity, expiry and retention."""
from datetime import datetime, timedelta
from sqlalchemy import select
from app.crud.event_identity import discoverable
from app.models.event import Event, EventStatus
from app.models.event_identity import EventOccurrence
from app.models.event_maintenance import EventMaintenanceArchive, EventMaintenanceRun
from app.models.saved_event import SavedEvent
from app.models.user import User
from app.operations.event_maintenance import run_maintenance
from tests.test_ingestion import payload


def test_four_cycles_preserve_identity_bookmark_and_audit(client,db_session):
    first=client.post('/events',json=payload()).json()
    event_id=first['id']
    user=User(email='maintenance@example.test',hashed_password='test')
    db_session.add(user);db_session.flush()
    db_session.add(SavedEvent(user_id=user.id,event_id=event_id));db_session.commit()

    one=run_maintenance(db_session,datetime(2027,1,1,12))
    assert one['status']=='ok'
    assert db_session.query(Event).count()==1
    assert db_session.scalar(select(Event.id).where(discoverable(datetime(2027,1,1,12)))) is not None

    second=client.post('/events',json=payload(description='Publisher corrected description')).json()
    assert second['id']==event_id
    two=run_maintenance(db_session,datetime(2027,1,1,13))
    assert two['reconciled_aliases']==0
    assert db_session.query(Event).count()==1
    assert db_session.get(Event,event_id).description=='Publisher corrected description'

    three=run_maintenance(db_session,datetime(2027,1,3,1))
    assert three['expired_events']==1
    assert db_session.scalar(select(Event.id).where(discoverable(datetime(2027,1,3,1)))) is None
    assert db_session.get(Event,event_id).status==EventStatus.expired
    assert db_session.query(EventOccurrence).count()==1

    four=run_maintenance(db_session,datetime(2027,4,5,1))
    assert four['archived_occurrences']==1
    archive=db_session.query(EventMaintenanceArchive).one()
    assert archive.snapshot['source_url']=='https://venue.example/events/jazz'
    assert db_session.query(EventOccurrence).count()==0
    assert db_session.get(Event,event_id) is not None
    assert db_session.query(SavedEvent).filter_by(event_id=event_id).count()==1
    assert db_session.query(EventMaintenanceRun).count()>=4
    again=run_maintenance(db_session,datetime(2027,4,5,1,1))
    assert again['archived_occurrences']==0
    assert db_session.query(EventMaintenanceArchive).count()==1


def test_recurring_only_expires_after_final_verified_session(client,db_session):
    common=dict(title='Weekly Workshop',source_url='https://venue.example/weekly',
        identity_kind='recurring',publisher_event_id='series-17')
    first=client.post('/events',json=payload(**common,start_time='2027-03-21T10:00:00+01:00')).json()
    second=client.post('/events',json=payload(**common,start_time='2027-03-28T10:00:00+02:00')).json()
    assert first['id']==second['id']
    before=run_maintenance(db_session,datetime(2027,3,21,10))
    assert before['expired_occurrences']==1
    assert db_session.scalar(select(Event.id).where(discoverable(datetime(2027,3,21,10)))) is not None
    assert db_session.query(EventOccurrence).filter_by(status='fresh').count()==1
    after=run_maintenance(db_session,datetime(2027,3,28,9))
    assert after['expired_events']==1
    assert db_session.scalar(select(Event.id).where(discoverable(datetime(2027,3,28,9)))) is None


def test_multiday_end_date_uses_bratislava_calendar_day(client,db_session):
    item=client.post('/events',json=payload(start_time='2027-10-24T10:00:00+02:00',
        end_date='2027-10-31',temporal_evidence='date_range')).json()
    assert item['end_date']=='2027-10-31'
    run_maintenance(db_session,datetime(2027,10,31,22,59))
    assert db_session.get(Event,item['id']).status in (EventStatus.fresh,EventStatus.stale)
    assert db_session.scalar(select(Event.id).where(discoverable(datetime(2027,10,31,22,59)))) is not None
    run_maintenance(db_session,datetime(2027,10,31,23,1))
    assert db_session.get(Event,item['id']).status==EventStatus.expired


def test_catalog_date_range_cannot_become_a_decades_long_event(client,db_session):
    item=client.post('/events',json=payload(title='Permanent catalogue listing',
        start_time='2016-04-01T00:00:00+02:00',end_date='2038-04-01',
        temporal_evidence='date_range')).json()
    assert item['end_date'] is None
    assert item['end_time'] is None
    assert client.get('/events').json()['total']==0
    evidence=db_session.get(Event,item['id']).sources[0].facts
    assert evidence['observed_schedule']['end_date']=='2038-04-01'
    assert client.post('/events',json=payload(title='Permanent catalogue listing',
        start_time='2016-04-01T00:00:00+02:00',end_date='2038-04-01',
        temporal_evidence='date_range')).json()['id']==item['id']
    assert db_session.query(Event).count()==1
