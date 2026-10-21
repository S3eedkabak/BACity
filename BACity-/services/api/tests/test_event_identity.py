from datetime import datetime, timedelta
from app.models.event import Event, EventStatus
from app.models.event_source import EventSource
from app.models.event_identity import EventOccurrence, EventOffer, EventReconciliation
from app.crud.event_identity import refresh_identity
from app.operations.reconcile_events import reconcile
from tests.test_ingestion import payload

DESCRIPTION='An immersive exhibition with projections and paintings. Visitors select an admission time slot; once inside their visit is not time limited. ' * 4

def listing(**changes):
    return payload(**{'title':'An Artist','category':'Exhibitions','description':DESCRIPTION,**changes})


def test_exhibition_sessions_and_ticket_offers_share_identity(client,db_session):
    a=client.post('/events',json=listing(end_time='2027-01-02T22:00:00+01:00')).json()
    b=client.post('/events',json=listing(start_time='2027-01-03T12:00:00+01:00',end_time='2027-01-03T22:00:00+01:00',source_url='https://venue.example/session/2')).json()
    c=client.post('/events',json={**listing(start_time='2027-01-01T10:00:00+01:00',end_time='2027-02-01T22:00:00+01:00',source_url='https://calendar.example/vip',price=20),'title':'An Artist – VIP fast track'}).json()
    assert a['id']==b['id']==c['id']
    assert c['title']=='An Artist'
    assert len(c['offers'])==1 and c['offers'][0]['price']==20
    assert db_session.query(Event).count()==1
    assert db_session.query(EventOccurrence).count()==2
    assert db_session.query(EventSource).count()==3
    assert client.post('/events',json=listing(end_time='2027-01-02T22:00:00+01:00')).json()['id']==a['id']
    assert db_session.query(EventOccurrence).count()==2
    assert client.get('/events/'+a['id']+'/occurrences').json()['total']==2


def test_publisher_exhibition_range_contains_sessions_without_duplicate_card(client,db_session):
    timed=client.post('/events',json=listing(title='Painter exhibition',identity_kind='recurring',
        start_time='2027-01-15T10:00:00+01:00',end_time='2027-01-15T20:00:00+01:00',
        source_url='https://visit.example/exhibitions/painter/slot-1')).json()
    broad=client.post('/events',json=listing(title='Painter exhibition',identity_kind='single',
        start_time='2027-01-01T00:00:00+01:00',end_time=None,end_date='2027-02-01',
        temporal_evidence='date_range',source_url='https://visit.example/exhibitions/painter/calendar')).json()
    assert broad['id']==timed['id']
    later=client.post('/events',json=listing(title='Painter exhibition',identity_kind='recurring',
        start_time='2027-01-22T10:00:00+01:00',end_time='2027-01-22T20:00:00+01:00',
        source_url='https://visit.example/exhibitions/painter/slot-2')).json()
    assert later['id']==timed['id']
    assert later['identity_kind']=='single'
    assert later['end_date']=='2027-02-01'
    assert later['start_time'].startswith('2026-12-31T23:00')
    assert db_session.query(Event).count()==1
    assert db_session.query(EventSource).count()==3
    assert client.get('/events').json()['total']==1


def test_offline_exhibition_reconcile_uses_newly_moved_source_span(client,db_session):
    first=client.post('/events',json=listing(title='Painter exhibition',identity_kind='recurring',
        start_time='2027-01-15T10:00:00+01:00',source_url='https://visit.example/exhibit/slot')).json()
    root=db_session.get(Event,first['id'])
    alias=Event(title='Painter exhibition',category='Exhibitions',description=DESCRIPTION,
        start_time=datetime(2026,12,31,23),end_date=datetime(2027,2,1).date(),
        latitude=root.latitude,longitude=root.longitude,venue_id=root.venue_id,address=root.address,
        source_url='https://visit.example/exhibit/calendar')
    db_session.add(alias);db_session.flush()
    db_session.add(EventSource(event_id=alias.id,source_url=alias.source_url,start_time=alias.start_time,
        title_key='painter exhibition',reliability=.9,facts={
            'observed_schedule':{'start_time':'2027-01-01T00:00:00+01:00','end_date':'2027-02-01'},
            'identity_kind':'single'}))
    db_session.commit()
    result=reconcile(db_session,True);db_session.commit()
    assert result['aliases']==1
    db_session.refresh(root)
    assert root.identity_kind=='single'
    assert root.end_date.isoformat()=='2027-02-01'
    assert root.start_time==datetime(2026,12,31,23)
    assert db_session.query(EventSource).filter_by(event_id=root.id).count()==2


def test_similar_performances_remain_separate(client):
    a=client.post('/events',json=payload()).json()
    b=client.post('/events',json=payload(start_time='2027-01-03T20:00:00+01:00')).json()
    c=client.post('/events',json=payload(title='Jazz Light',source_url='https://different.example/other')).json()
    assert len({a['id'],b['id'],c['id']})==3


def test_reconciliation_is_dry_repeatable_preserves_alias_provenance(client,db_session):
    first=client.post('/events',json=listing()).json()
    root=db_session.get(Event,first['id']) if False else db_session.query(Event).one()
    alias=Event(title=root.title,start_time=root.start_time+timedelta(hours=1),end_time=root.start_time+timedelta(hours=2),description=DESCRIPTION,
        category='Sports',latitude=root.latitude,longitude=root.longitude,venue_id=root.venue_id,source_url='https://venue.example/session/duplicate')
    db_session.add(alias);db_session.flush()
    db_session.add(EventSource(event_id=alias.id,source_url=alias.source_url,start_time=alias.start_time,title_key='an artist',reliability=.9))
    db_session.commit();alias_id=alias.id
    dry=reconcile(db_session)
    assert dry['aliases']==1 and db_session.query(EventReconciliation).count()==0
    result=reconcile(db_session,True);db_session.commit()
    assert result['identities_after']==1 and db_session.query(Event).count()==2
    assert db_session.get(Event,alias_id).merged_into_id==root.id
    assert db_session.query(EventSource).filter_by(event_id=root.id).count()==2
    assert client.get('/events/'+str(alias_id)).json()['id']==str(root.id)
    assert reconcile(db_session,True)['aliases']==0
    assert client.get('/events/map/clusters',params=dict(min_lat=48,max_lat=48.35,min_lng=16.9,max_lng=17.35)).json()['total']==1


def test_past_sessions_do_not_surface_as_upcoming(db_session):
    event=Event(title='Exhibition',identity_kind='recurring',source_url='https://venue.example/x',start_time=datetime(2026,7,1))
    db_session.add(event);db_session.flush()
    for day in (datetime(2026,7,1),datetime(2027,1,2)):
        db_session.add(EventOccurrence(event_id=event.id,source_url='https://venue.example/'+day.isoformat(),start_time=day,end_time=day+timedelta(hours=1),status='fresh'))
    refresh_identity(db_session,event,now=datetime(2026,10,21))
    assert event.start_time==datetime(2027,1,2)
    assert db_session.query(EventOccurrence).count()==2


def test_date_only_source_is_refined_to_real_clock_without_extra_session(client,db_session):
    a=client.post('/events',json=payload(start_time='2027-01-02T00:00:00+01:00',start_precision='date',source_url='https://venue.example/en/program/jazz/2027-01-02')).json()
    b=client.post('/events',json=payload(start_time='2027-01-02T20:00:00+01:00',source_url='https://venue.example/sk/program/jazz/2027-01-02')).json()
    assert a['id']==b['id']
    assert b['start_time'].startswith('2027-01-02T19:00')
    assert db_session.query(EventOccurrence).count()==1
    assert db_session.query(EventSource).count()==2


def test_different_exhibition_content_venue_and_season_not_merged(client):
    a=client.post('/events',json=listing()).json()
    b=client.post('/events',json=listing(description='An exhibition of an unrelated collection',source_url='https://calendar.example/other')).json()
    c=client.post('/events',json=listing(start_time='2028-01-02T20:00:00+01:00',source_url='https://venue.example/new-season')).json()
    assert len({a['id'],b['id'],c['id']})==3


def test_recurring_session_date_filter_matches_later_availability(client):
    a=client.post('/events',json=listing(end_time='2027-01-02T22:00:00+01:00')).json()
    client.post('/events',json=listing(start_time='2027-01-03T12:00:00+01:00',end_time='2027-01-03T14:00:00+01:00',source_url='https://venue.example/session/2'))
    params=dict(min_lat=48,max_lat=48.35,min_lng=16.9,max_lng=17.35,starts_after='2027-01-03T00:00:00+01:00',starts_before='2027-01-03T23:59:00+01:00')
    data=client.get('/events/map/clusters',params=params).json()
    assert data['total']==1
    assert client.get('/events/map/area',params={'area_token':data['area_token']}).json()['items'][0]['id']==a['id']
    params.update(starts_after='2027-01-04T00:00:00+01:00',starts_before='2027-01-04T23:59:00+01:00')
    assert client.get('/events/map/clusters',params=params).json()['total']==0


def test_metadata_repair_is_audited_idempotent_and_does_not_delete(client,db_session):
    from app.operations.repair_event_metadata import repair
    item=client.post('/events',json=payload(title='An exhibition',description='An immersive exhibition at Sport Mall',category='Sports')).json()
    assert len(repair(db_session))==1
    assert db_session.query(Event).one().category.value=="Sports"
    changes=repair(db_session,True);db_session.commit()
    assert changes[0]['after']['category']=='Exhibitions'
    assert db_session.query(Event).count()==1
    assert db_session.query(EventSource).one().facts['canonical_metadata_corrections']
    assert repair(db_session,True)==[]


def test_ticket_offer_arriving_first_does_not_create_independent_discovery(client):
    offer=client.post('/events',json={**listing(source_url='https://venue.example/vip'),'title':'An Artist – VIP fast track'}).json()
    assert offer['title']=='An Artist'
    assert client.get('/events').json()['total']==0
    regular=client.post('/events',json=listing(source_url='https://venue.example/entry')).json()
    assert regular['id']==offer['id'] and regular['title']=='An Artist'
    assert client.get('/events').json()['total']==1


def test_city_only_address_is_not_evidence_of_same_physical_event(client):
    a=client.post('/events',json=payload(address='Bratislava',venue_name=None,latitude=None,longitude=None)).json()
    b=client.post('/events',json=payload(address='Bratislava',venue_name=None,latitude=None,longitude=None,source_url='https://other.example/x')).json()
    assert a['id']!=b['id']


def test_cross_source_cosmetic_qualifier_is_not_a_new_event(client):
    a=client.post('/events',json=payload(title='Bookclub: A particular novel')).json()
    b=client.post('/events',json=payload(title='International Bookclub: A particular novel',source_url='https://calendar.example/bookclub')).json()
    assert a['id']==b['id']


def test_publisher_ticket_tiers_same_url_are_one_identity_and_one_session(client,db_session):
    ids=[]
    for tier in ('KLASIK','VIP','MEET & GREET','BACKSTAGE'):
        response=client.post('/events',json=payload(title=f'Two Artists Tour 02.01.2027 20:00 - {tier}',description=None))
        assert response.status_code==201,response.text
        ids.append(response.json()['id'])
    assert len(set(ids))==1
    root=client.get('/events/'+ids[0]).json()
    assert root['title']=='Two Artists Tour' and len(root['offers'])==4
    assert db_session.query(EventOccurrence).count()==1
    assert db_session.query(EventSource).count()==4
    assert client.get('/events').json()['total']==1


def test_ticket_product_date_must_match_actual_session(client):
    a=client.post('/events',json=payload(title='Two Artists Tour',description=None)).json()
    b=client.post('/events',json=payload(title='Two Artists Tour 03.01.2027 20:00 - VIP',description=None)).json()
    assert a['id']!=b['id']


def test_explicit_weekly_and_irregular_schedules_preserve_evidence(client,db_session):
    for day in ('02','09'):
        response=client.post('/events',json=payload(start_time=f'2027-01-{day}T20:00:00+01:00',identity_kind='recurring',publisher_event_id='weekly-uid',recurrence_rule='FREQ=WEEKLY;BYDAY=FR;COUNT=4'))
        assert response.status_code==201,response.text
        assert response.json()['recurrence_label']=='Every Friday'
    assert db_session.query(Event).count()==1
    assert db_session.query(EventOccurrence).count()==2
    irregular=client.post('/events',json=payload(title='Irregular series',identity_kind='recurring',publisher_event_id='other-uid',recurrence_rule='FREQ=MONTHLY;BYDAY=2SA;COUNT=3')).json()
    assert irregular['recurrence_label']=='Selected dates'


def test_standalone_pass_is_an_offer_not_a_session(client,db_session):
    response=client.post('/events',json=payload(title='Annual pass'))
    assert response.status_code==201,response.text
    assert response.json()['identity_kind']=='offer'
    assert len(response.json()['offers'])==1
    assert client.get('/events').json()['total']==0
    assert db_session.query(EventOccurrence).count()==0


def test_centroid_and_multivenue_are_not_exact_locations(client,db_session):
    response=client.post('/events',json=payload(venue_name=None,address='Bratislava',latitude=48.1486,longitude=17.1077))
    assert response.status_code==201,response.text
    assert response.json()['latitude'] is None
    assert db_session.query(EventSource).one().facts['observed_coordinates']['latitude']==48.1486
    response=client.post('/events',json=payload(title='Across the city',venue_name='Bratislava – various venues'))
    assert response.json()['latitude'] is None


def test_permanent_listing_sentinel_is_not_a_future_thirty_year_event(client,db_session):
    response=client.post('/events',json=payload(start_time='2000-01-01T12:00:00Z',end_time='2030-01-01T22:00:00Z'))
    assert response.status_code==201,response.text
    assert response.json()['end_time'] is None
    assert client.get('/events').json()['total']==0
    assert db_session.query(EventSource).one().facts['observed_schedule']['end_time'].startswith('2030')


def test_continuous_multiday_exhibition_is_not_an_inferred_recurring_series(client,db_session):
    first=client.post('/events',json=listing(start_time='2027-01-02T12:00:00Z',end_time='2027-02-01T18:00:00Z')).json()
    second=client.post('/events',json=listing(start_time='2027-01-02T12:00:00Z',end_time='2027-02-01T18:00:00Z',source_url='https://calendar.example/the-same-exhibition')).json()
    assert first['id']==second['id']
    assert second['identity_kind']=='single'
    assert second['end_time'].startswith('2027-02-01')
    assert db_session.query(EventOccurrence).count()==1


def test_offline_and_live_taxonomy_share_the_same_rules():
    import ast
    from pathlib import Path
    root=Path(__file__).resolve().parents[2]
    def rules(path):
        tree=ast.parse(path.read_text())
        return [ast.dump(node) for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='guess_category' or isinstance(node,ast.Assign) and any(isinstance(target,ast.Name) and target.id=='CATEGORY_KEYWORDS' for target in node.targets)]
    assert rules(root/'api/app/core/event_taxonomy.py')==rules(root/'crawler/crawler/processing/normalize.py')


def test_date_only_precision_survives_canonical_serialization(client):
    item=client.post('/events',json=payload(start_time='2027-01-02T00:00:00+01:00',start_precision='date')).json()
    assert item['start_precision']=='date'
    assert client.get('/events/'+item['id']).json()['start_precision']=='date'
