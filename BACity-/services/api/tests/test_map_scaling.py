from datetime import datetime, timedelta
import uuid

from app.models.event import Event, EventStatus

BOUNDS = dict(min_lat=48.,max_lat=48.35,min_lng=16.9,max_lng=17.35)


def seed(db,n=1207):
    start=datetime(2027,1,1,18)
    db.add_all([Event(id=uuid.uuid4(),title=f'Concert {i}',description='Live music',start_time=start+timedelta(minutes=i%4),
        latitude=48.15 if i<1000 else 48.2,longitude=17.11 if i<1000 else 17.2,
        category='Music' if i%2 else 'Culture',source_url=f'https://venue.example/events/{i}',price=0 if i%3 else 10,
        status=EventStatus.fresh) for i in range(n)])
    db.commit()


def all_pages(client,token,**filters):
    params=dict(area_token=token,limit=73,**filters)
    ids=[];total=None
    while True:
        result=client.get('/events/map/area',params=params)
        assert result.status_code==200,result.text
        data=result.json()
        total=data['total'] if total is None else total
        assert total==data['total']
        ids.extend(e['id'] for e in data['items'])
        if not data['has_more']: break
        params['cursor']=data['next_cursor']
    assert len(ids)==len(set(ids))==total
    return ids


def test_complete_clusters_and_all_pages(client,db_session):
    seed(db_session)
    old=client.get('/events/viewport',params={**BOUNDS,'limit':500}).json()
    assert len(old)==500
    for zoom in (0,12,18,22):
        response=client.get('/events/map/clusters',params={**BOUNDS,'zoom':zoom})
        assert response.status_code==200,response.text
        data=response.json()
        assert data['total']==1207==sum(f['properties']['count'] for f in data['features'])
        assert data['individual_events']+data['clustered_events']==1207
        assert len(data['features'])<1100
        ids=[]
        for feature in data['features']:
            token=feature['properties']['area_token']
            first=client.get('/events/map/area',params={'area_token':token}).json()
            assert first['total']==feature['properties']['count']
            ids.extend(all_pages(client,token))
        assert len(set(ids))==1207
        assert len(all_pages(client,data['area_token']))==1207


def test_filters_and_missing_cancelled_postponed(client,db_session):
    seed(db_session,20)
    for status in (EventStatus.expired,EventStatus.cancelled,EventStatus.postponed):
        db_session.add(Event(title='Hidden',start_time=datetime(2027,1,1),latitude=48.15,longitude=17.11,source_url='https://venue.example',status=status))
    db_session.add(Event(title='Unmapped',start_time=datetime(2027,1,1),source_url='https://venue.example'))
    db_session.commit()
    for filters in ({},{'category':'Music'},{'q':'Concert 1'},{'free_only':True},
                    {'starts_after':'2027-01-01T18:02:00Z','starts_before':'2027-01-01T18:03:00Z'}, {'status':'fresh'}):
        data=client.get('/events/map/clusters',params={**BOUNDS,**filters}).json()
        assert data['total']<=20
        assert len(all_pages(client,data['area_token']))==data['total']
    assert client.get('/events/map/clusters',params={**BOUNDS,'q':' Concert '}).json()['total']==20
    assert client.get('/events/map/clusters',params={**BOUNDS,'status':'cancelled'}).status_code==422


def test_cursor_change_tamper_and_filter_binding(client,db_session):
    seed(db_session,120)
    data=client.get('/events/map/clusters',params=BOUNDS).json()
    params={'area_token':data['area_token'],'limit':10}
    page=client.get('/events/map/area',params=params).json()
    cursor=page['next_cursor']
    assert client.get('/events/map/area',params={**params,'cursor':cursor,'override_filters':True,'category':'Music'}).status_code==422
    assert client.get('/events/map/area',params={**params,'cursor':cursor+'x'}).status_code==422
    event=db_session.query(Event).first();event.start_time+=timedelta(days=1);db_session.commit()
    assert client.get('/events/map/area',params={**params,'cursor':cursor}).status_code==409


def test_edges_empty_one_and_bounds(client,db_session):
    assert client.get('/events/map/clusters',params=BOUNDS).json()['total']==0
    seed(db_session,1)
    data=client.get('/events/map/clusters',params={**BOUNDS,'zoom':22}).json()
    assert data['features'][0]['properties']['id']
    assert len(all_pages(client,data['features'][0]['properties']['area_token']))==1
    for invalid in ({'min_lat':50},{'min_lng':180,'max_lng':-180},{'zoom':23},{'min_lat':'nan'}):
        assert client.get('/events/map/clusters',params={**BOUNDS,**invalid}).status_code==422
    assert client.get('/events/map/clusters',params={**BOUNDS,'min_lat':-90,'max_lat':90,'min_lng':-180,'max_lng':180}).json()['total']==1


def test_official_district_polygons_counts_and_boundary_ownership(client,db_session):
    from app.crud.districts import collection,membership
    seed(db_session,807)
    data=client.get('/events/map/districts').json()
    assert len(data['features'])==17
    assert {'Staré Mesto','Petržalka','Ružinov','Rača','Karlova Ves'} <= {f['properties']['name'] for f in data['features']}
    assert sum(f['properties']['count'] for f in data['features'])+data['outside_districts']==807
    ids=[]
    for feature in data['features']:
        properties=feature['properties']
        lng,lat=properties['label_coordinates']
        assert membership(lat,lng)==properties['id']
        page=client.get('/events/map/area',params={'area_token':properties['area_token']}).json()
        assert page['name']==properties['name']
        assert page['total']==properties['count']
        if page['total']:ids.extend(all_pages(client,properties['area_token']))
    assert len(ids)==len(set(ids))
    assert membership(48.145,17.105)==next(f['properties']['id'] for f in collection()['features'] if f['properties']['name']=='Staré Mesto')
    assert membership(48.12,17.105)==next(f['properties']['id'] for f in collection()['features'] if f['properties']['name']=='Petržalka')
    star=next(f for f in collection()['features'] if f['properties']['name']=='Staré Mesto')
    boundary=star['geometry']['coordinates'][0][0]
    assert membership(boundary[1],boundary[0]) is not None
    assert client.get('/events/map/districts',params={'district':'invented'}).status_code==422


def test_nearby_radius_and_filter_independence(client,db_session):
    seed(db_session,20)
    # The diagonal fits the request bounds but is outside the original 3 km circle.
    db_session.add(Event(title='Beyond radius',start_time=datetime(2027,1,1),source_url='https://venue.example/away',latitude=48.175,longitude=17.145))
    db_session.commit()
    params={**BOUNDS,'near_lat':48.15,'near_lng':17.11,'radius_km':3}
    data=client.get('/events/map/clusters',params=params).json()
    assert data['total']==20
    assert len(all_pages(client,data['area_token']))==20
    assert client.get('/events/map/clusters',params={**BOUNDS,'near_lat':48.15}).status_code==422
    assert client.get('/events/map/clusters',params={**BOUNDS,'starts_after':'2027-01-01T00:00:00Z','starts_before':'2027-01-01T23:00:00'}).status_code==200
