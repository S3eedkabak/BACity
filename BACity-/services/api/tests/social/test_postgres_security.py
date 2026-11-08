"""Real PostgreSQL privilege, immutable staging and additive rollback checks."""
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime,timezone
from pathlib import Path
import pytest
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import DBAPIError
from app.social.models import Staff,Publisher,Observation,AuditEvent
from app.social.security import audit

@pytest.mark.skipif(not os.getenv('TEST_POSTGRES_URL'),reason='TEST_POSTGRES_URL not configured')
def test_real_migrations_privilege_boundaries_audit_and_preserving_downgrade(monkeypatch):
    url=make_url(os.environ['TEST_POSTGRES_URL'])
    admin=create_engine(url,isolation_level='AUTOCOMMIT')
    name='bacity_l4_security_'+uuid.uuid4().hex
    with admin.connect() as c:c.execute(text('CREATE DATABASE '+name))
    target=url.set(database=name)
    db=create_engine(target);factory=sessionmaker(bind=db,expire_on_commit=False)
    api_dir=Path(__file__).resolve().parents[2]
    env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
    def migrate(*args):
        run=subprocess.run([sys.executable,'-m','alembic',*args],cwd=api_dir,env=env,capture_output=True,text=True)
        assert run.returncode==0,run.stderr
    try:
        migrate('upgrade','head')
        with db.begin() as c:
            c.execute(text((api_dir.parents[1]/'infrastructure/social/roles.sql').read_text()))
        with factory() as session:
            s=Staff(email='pg-fixture@staff.test',name='PG test',role='OWNER');session.add(s);session.flush()
            p=Publisher(platform='instagram',url='https://www.instagram.com/test_fixture/',external_id='test_fixture',target_type='profile',
                name='Fixture',relevance='Bratislava fixture',created_by=s.id);session.add(p);session.flush()
            o=Observation(publisher_id=p.id,external_id='ABC123',source_url='https://www.instagram.com/p/ABC123/',
                content_hash='a'*64,caption='immutable fixture',method='user_submission',provenance={},retention_until=time.time()+90*86400)
            session.add(o);audit(session,s.id,'fixture.created');session.commit()
            oid=o.id
        for statement in ["UPDATE l4_audit_events SET digest='x'",'DELETE FROM l4_audit_events',"UPDATE l4_observations SET caption='edited'"]:
            with pytest.raises(DBAPIError):
                with db.begin() as c:c.execute(text(statement))
        for role,statement in [
            ('bacity_l4_gateway','SELECT * FROM l4_staff'),
            ('bacity_l4_gateway','SELECT * FROM users'),
            ('bacity_l4_gateway',"INSERT INTO events(id,title,start_time,source_url,category,status,tags) VALUES(gen_random_uuid(),'forbidden',CURRENT_TIMESTAMP,'https://example.test','Other','fresh','[]')"),
            ('bacity_l4_staff','DELETE FROM events'),
            ('bacity_l4_staff','DELETE FROM l4_audit_events'),
        ]:
            with pytest.raises(DBAPIError):
                with db.begin() as c:
                    c.execute(text('SET LOCAL ROLE '+role));c.execute(text(statement))
        with db.begin() as c:
            c.execute(text('SET LOCAL ROLE bacity_l4_gateway'))
            assert c.execute(text('SELECT count(*) FROM l4_publishers')).scalar()==1
        from app.social.database_policy import verify_database_policy
        from fastapi import HTTPException
        with factory() as session:
            with pytest.raises(HTTPException):
                verify_database_policy(session,service_role='staff',consumer_role='bacity_public_runtime')
        for role,service in [('bacity_l4_staff','staff'),('bacity_l4_gateway','gateway')]:
            with factory() as session:
                session.execute(text('SET LOCAL ROLE '+role))
                verify_database_policy(session,service_role=service,consumer_role='bacity_public_runtime')
                with pytest.raises(HTTPException):
                    verify_database_policy(session,service_role=service,consumer_role='postgres')
        with db.begin() as c:
            c.execute(text('SET LOCAL ROLE bacity_public_runtime'))
            assert c.execute(text('SELECT count(*) FROM events')).scalar()==0
        with pytest.raises(DBAPIError):
            with db.begin() as c:
                c.execute(text('SET LOCAL ROLE bacity_public_runtime'))
                c.execute(text('SELECT * FROM l4_sessions'))
        # Real PostgreSQL row-lock serialization and private provider-table grants.
        monkeypatch.setenv('SCRAPINGANT_ENABLED','true')
        monkeypatch.setenv('SCRAPINGANT_KEY_CONFIGURED','true')
        from app.social.models import ProviderBudget,ProviderRequest,CollectionJob
        from app.social.provider_budget import reserve,settle
        from concurrent.futures import ThreadPoolExecutor
        with factory() as session:
            job=CollectionJob(publisher_id=p.id,dedup_key=uuid.uuid4().hex)
            session.add(job)
            session.add(ProviderBudget(id=1,period_start=time.time()-86400,period_end=time.time()+29*86400,
                provider_total=10000,provider_remaining=10000,synced=time.time()))
            session.commit();job_id=job.id
        def attempt(index):
            with factory() as session:
                session.execute(text('SET LOCAL ROLE bacity_l4_gateway'))
                try:return reserve(session,session.get(CollectionJob,job_id),str(uuid.uuid4()),'acquire',p.url)['reservation']
                except HTTPException:return None
        with ThreadPoolExecutor(max_workers=6) as pool:tokens=list(pool.map(attempt,range(6)))
        assert len([t for t in tokens if t])==1
        with factory() as session:
            session.execute(text('SET LOCAL ROLE bacity_l4_gateway'))
            assert settle(session,session.get(CollectionJob,job_id),next(t for t in tokens if t),1)['cost']==1
        with pytest.raises(DBAPIError):
            with db.begin() as c:
                c.execute(text('SET LOCAL ROLE bacity_public_runtime'))
                c.execute(text('SELECT * FROM l4_provider_budget'))
        with pytest.raises(DBAPIError):
            with db.begin() as c:
                c.execute(text('SET LOCAL ROLE bacity_l4_staff'))
                c.execute(text('UPDATE l4_provider_budget SET charged=0'))
        # Apify uses its own money ledger, but the SAME gateway/runtime boundary.
        from app.social.models import ApifyBudget,ApifyRun
        from app.social.apify_jobs import reserve as reserve_actor
        from app.social.config import settings
        from app.social.security import digest
        monkeypatch.setenv('APIFY_ENABLED','true');monkeypatch.setenv('APIFY_TOKEN_CONFIGURED','true')
        monkeypatch.setenv('SOCIAL_L4_ENABLED','true');monkeypatch.setenv('SOCIAL_L4_COLLECTION_ENABLED','true')
        monkeypatch.setenv('SOCIAL_DATABASE_URL',target.render_as_string(hide_password=False));settings.cache_clear()
        owner='x'*43
        with factory() as session:
            publisher=session.get(Publisher,p.id)
            publisher.method='apify';publisher.enabled=True;publisher.approval='approved';publisher.eligibility='available'
            publisher.permission_basis='Explicit synthetic PostgreSQL permission';publisher.permission_expires=time.time()+86400
            actor_run=ApifyRun(dedup_key=uuid.uuid4().hex,members=[],actor_input={},owner_digest=digest(owner),lease_until=time.time()+90)
            session.add(actor_run);session.flush()
            actor_job=CollectionJob(publisher_id=p.id,dedup_key=uuid.uuid4().hex,apify_run_id=actor_run.id,state='running')
            session.add(actor_job);session.flush()
            actor_run.members=[{'job_id':actor_job.id,'publisher_id':p.id,'url':p.url,'handle':p.external_id,'limit':publisher.posts_per_profile}]
            session.add(ApifyBudget(id=1,period_start=time.time()-86400,period_end=time.time()+29*86400,
                synced=time.time(),price=2700,provider_limit=5000000,build='0.0.831'))
            session.commit();actor_id=actor_run.id
        def actor_attempt(index):
            with factory() as session:
                session.execute(text('SET LOCAL ROLE bacity_l4_gateway'))
                try:return reserve_actor(actor_id,x_social_lease=owner,db=session)['state']
                except HTTPException:return None
        with ThreadPoolExecutor(max_workers=6) as pool:reservations=list(pool.map(actor_attempt,range(6)))
        assert reservations.count('reserved')==1
        # Exercise terminal accounting on the real schema, not only SQLite.
        from app.social.apify_jobs import dispatch,progress,page,complete,Progress,Page
        for action in (
            lambda session:dispatch(actor_id,x_social_lease=owner,db=session),
            lambda session:progress(actor_id,Progress(run_id='PgFixtureRun',dataset_id='PgFixtureDataset',status='SUCCEEDED',cost=2700,total=1),x_social_lease=owner,db=session),
            lambda session:page(actor_id,Page(offset=0,count=1,records=[{'job_id':actor_job.id,'content':{
                'external_id':'PgNewPost','source_url':'https://www.instagram.com/p/PgNewPost/',
                'caption':'Koncert Fixture Jazz 2030-11-02 20:00 Bratislava',
                'published_at':datetime.now(timezone.utc).isoformat(),
                'publisher_identifier':p.external_id,'adapter':'apify_instagram_v1'},'error':None}]),x_social_lease=owner,db=session),
            lambda session:complete(actor_id,x_social_lease=owner,db=session),
        ):
            with factory() as session:
                session.execute(text('SET LOCAL ROLE bacity_l4_gateway'));action(session)
        with factory() as session:
            assert session.get(ApifyRun,actor_id).cost_kind=='reported_with_overhead'
            assert session.get(ApifyBudget,1).reserved==0
            assert session.get(ApifyBudget,1).spent==7700
            assert session.get(Publisher,p.id).instagram_timestamp is not None
            assert session.query(Observation).filter_by(external_id='PgNewPost').count()==1
        with factory() as session:
            pending=ApifyRun(dedup_key=uuid.uuid4().hex,members=[],actor_input={})
            session.add(pending);session.flush()
            pending_job=CollectionJob(publisher_id=p.id,dedup_key=uuid.uuid4().hex,apify_run_id=pending.id,
                state='cancelled',finished=time.time()-86400)
            session.add(pending_job);session.commit();pending_job_id=pending_job.id
        from app.social import maintenance
        from types import SimpleNamespace
        monkeypatch.setattr(maintenance,'time',SimpleNamespace(time=lambda:time.time()+15*86400))
        from app.social.maintenance import prune
        with factory() as session:
            session.execute(text('SET LOCAL ROLE bacity_l4_maintenance'));assert prune(session)==1
        with factory() as session:
            assert session.get(ApifyRun,actor_id).items=={}
            assert session.get(ApifyRun,actor_id).cost==2700
            assert session.get(CollectionJob,pending_job_id) is not None
            assert session.query(Observation).count()==1
        with db.connect() as c:preserved_audits=c.execute(text('SELECT count(*) FROM l4_audit_events')).scalar()
        with pytest.raises(DBAPIError):
            with db.begin() as c:
                c.execute(text('SET LOCAL ROLE bacity_public_runtime'));c.execute(text('SELECT * FROM l4_apify_budget'))
        with pytest.raises(DBAPIError):
            with db.begin() as c:
                c.execute(text('SET LOCAL ROLE bacity_l4_staff'));c.execute(text('UPDATE l4_apify_budget SET spent=0'))
        settings.cache_clear()
        migrate('downgrade','0023')
        with db.connect() as c:
            assert c.execute(text('SELECT caption FROM l4_observations WHERE id=:id'),{'id':oid}).scalar()=='immutable fixture'
        migrate('upgrade','head')
        with db.connect() as c:
            assert c.execute(text('SELECT count(*) FROM l4_audit_events')).scalar()==preserved_audits
            assert c.execute(text('SELECT version_num FROM alembic_version')).scalar()=='0029'
    finally:
        db.dispose()
        with admin.connect() as c:c.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))
        admin.dispose()
