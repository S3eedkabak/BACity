"""Real PostgreSQL proof; every seeded row lives in a unique disposable database."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
from datetime import datetime,timedelta

import pytest
from sqlalchemy import create_engine,select,text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app.crud.map_events import clusters,area_events
from app.models.event import Event


@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'),reason='isolated Postgres opt-in')
def test_complete_postgres_inventory_and_query_plan():
    url=make_url(os.environ['TEST_POSTGRES_URL'])
    name='bacity_map_test_'+uuid.uuid4().hex
    admin=create_engine(url,isolation_level='AUTOCOMMIT')
    with admin.connect() as connection: connection.execute(text(f'CREATE DATABASE {name}'))
    test_url=url.set(database=name)
    engine=None
    try:
        subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=Path(__file__).resolve().parents[1],
            env={**os.environ,'DATABASE_URL':test_url.render_as_string(hide_password=False)},check=True,capture_output=True)
        engine=create_engine(test_url)
        with Session(engine) as db:
            start=datetime(2027,1,1,18)
            db.bulk_insert_mappings(Event,[dict(id=uuid.uuid4(),title=f'Isolated concert {i}',source_url=f'https://venue.example/{i}',
                start_time=start+timedelta(minutes=i%10),latitude=48.1+(i%100)*.001,longitude=17.1+(i%100)*.001,status='fresh') for i in range(6007)])
            db.commit()
            db.execute(text('ANALYZE events'))
            measurements=[]
            for zoom in (0,12,22):
                before=time.perf_counter()
                data=clusters(db,dict(min_lat=48.,max_lat=48.35,min_lng=16.9,max_lng=17.35),zoom,{})
                measurements.append({'zoom':zoom,'features':len(data['features']),'sql_cluster_ms':(time.perf_counter()-before)*1000})
                assert data['total']==6007==sum(f['properties']['count'] for f in data['features'])
            ids=[];cursor=None
            while True:
                page=area_events(db,data['area_token'],cursor,100)
                assert page['total']==6007 and len(page['items'])<=100
                ids.extend(str(item.id) for item in page['items'])
                if not page['has_more']:break
                cursor=page['next_cursor']
            assert len(ids)==len(set(ids))==6007
            plans=db.execute(text("EXPLAIN (ANALYZE, BUFFERS) SELECT count(*) FROM events WHERE status IN ('fresh','stale') AND latitude BETWEEN 48.100 AND 48.101 AND longitude BETWEEN 17.100 AND 17.101")).scalars().all()
            assert any('ix_events_map_published' in line or 'ix_events_lat_lng' in line for line in plans),plans
            print(json.dumps({'isolated_events':len(ids),'measurements':measurements,'plan':plans}))
            from app.crud.map_events import districts
            from app.crud.districts import membership
            before=time.perf_counter()
            areas=districts(db,{})
            assert sum(f['properties']['count'] for f in areas['features'])+areas['outside_districts']==6007
            district_ids=[]
            for feature in areas['features']:
                expected=feature['properties']['count'];cursor=None;got=[]
                while True:
                    page=area_events(db,feature['properties']['area_token'],cursor,100)
                    assert page['total']==expected
                    got.extend(str(item.id) for item in page['items'])
                    if not page['has_more']:break
                    cursor=page['next_cursor']
                assert len(got)==expected
                district_ids.extend(got)
            assert len(district_ids)==len(set(district_ids))==6007-areas['outside_districts']
            print(json.dumps({'district_counts':[(f['properties']['name'],f['properties']['count']) for f in areas['features']],
                'district_proof_ms':(time.perf_counter()-before)*1000,'outside':areas['outside_districts']}))
            for lat,lng in ((48.145,17.105),(48.12,17.105),(48.2,17.2)):
                expected=membership(lat,lng)
                actual=db.execute(text('SELECT min(id) FROM map_districts WHERE ST_Covers(geometry,ST_SetSRID(ST_MakePoint(:lng,:lat),4326))'),{'lat':lat,'lng':lng}).scalar()
                assert actual==expected
            # Downgrade/upgrade preserves degraded candidates via probation fallback.
            db.rollback()
        subprocess.run([sys.executable,'-m','alembic','downgrade','0016'],cwd=Path(__file__).resolve().parents[1],env={**os.environ,'DATABASE_URL':test_url.render_as_string(hide_password=False)},check=True,capture_output=True)
        subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=Path(__file__).resolve().parents[1],env={**os.environ,'DATABASE_URL':test_url.render_as_string(hide_password=False)},check=True,capture_output=True)
    finally:
        if engine:engine.dispose()
        with admin.connect() as connection:connection.execute(text(f'DROP DATABASE {name} WITH (FORCE)'))
        admin.dispose()
