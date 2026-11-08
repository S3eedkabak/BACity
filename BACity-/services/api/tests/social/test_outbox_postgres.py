"""Opt-in fault injection against a dedicated disposable PostgreSQL container."""
import json,os,subprocess,sys,time,uuid,urllib.error
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,text,event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker
from app.social.models import Staff,Publisher,Observation,EventCandidate,CollectionJob,ApifyRun,DeliveryReceipt
from app.social.config import settings
from app.social.db import database
from app.social.acquisition.apify import Client
from app.social.acquisition.outbox import Outbox
from app.social.acquisition.durable_runner import cycle
from app.social.worker_api import app
from .test_apify import Provider,TOKEN

@pytest.mark.skipif(not os.getenv('OUTBOX_POSTGRES_CONTAINER'),reason='Dedicated PostgreSQL fault-injection container not selected')
def test_real_database_stop_capture_restart_and_atomic_concurrent_delivery(tmp_path,monkeypatch):
 container=os.environ['OUTBOX_POSTGRES_CONTAINER'];assert container=='bacity-outbox-pg-test'
 url=make_url(os.environ['TEST_POSTGRES_URL']);assert url.host=='127.0.0.1' and url.port==55436
 admin=create_engine(url,isolation_level='AUTOCOMMIT',pool_pre_ping=True);name='outbox_fault_'+uuid.uuid4().hex
 with admin.connect() as db:db.execute(text('CREATE DATABASE '+name))
 target=url.set(database=name);env={**os.environ,'DATABASE_URL':target.render_as_string(hide_password=False)}
 api=Path(__file__).resolve().parents[2];engine=None;runtime_engine=None;http=None;box=None;down=False
 try:
  r=subprocess.run([sys.executable,'-m','alembic','upgrade','head'],cwd=api,env=env,capture_output=True,text=True);assert r.returncode==0,r.stderr
  engine=create_engine(target,pool_pre_ping=True);factory=sessionmaker(bind=engine,expire_on_commit=False)
  with engine.begin() as db:db.execute(text((api.parents[1]/'infrastructure/social/roles.sql').read_text()))
  for key,value in {'SOCIAL_L4_ENABLED':'true','SOCIAL_L4_COLLECTION_ENABLED':'true','SOCIAL_L4_PUBLICATION_ENABLED':'false','SOCIAL_DATABASE_URL':target.render_as_string(hide_password=False),'SOCIAL_WORKER_KEY':'fault-injection-worker-key-'+'x'*32,'APIFY_ENABLED':'true','APIFY_TOKEN_CONFIGURED':'true'}.items():monkeypatch.setenv(key,value)
  settings.cache_clear()
  with factory() as db:
   owner=Staff(email='fault@test.invalid',name='Disposable owner',role='OWNER');db.add(owner);db.flush()
   db.add(Publisher(created_by=owner.id,platform='instagram',target_type='profile',url='https://www.instagram.com/fixture_venue/',external_id='fixture_venue',name='Fixture',relevance='Disposable fault injection only',approval='approved',eligibility='available',enabled=True,permission_basis='Explicit synthetic test permission',permission_expires=time.time()+86400,method='apify'));db.commit()
  runtime_engine=create_engine(target,pool_pre_ping=True)
  @event.listens_for(runtime_engine,'begin')
  def gateway_role(connection):connection.exec_driver_sql('SET LOCAL ROLE bacity_l4_gateway')
  runtime_factory=sessionmaker(bind=runtime_engine,expire_on_commit=False)
  def dependency():
   with runtime_factory() as db:yield db
  app.dependency_overrides[database]=dependency
  http=TestClient(app,headers={'X-Social-Worker-Key':settings().worker_key},raise_server_exceptions=False)
  def send(path,*,payload=None,lease=None):
   headers={'X-Social-Lease':lease} if lease else {}
   response=http.post(path,json=payload,headers=headers) if payload is not None else http.get(path,headers=headers)
   if response.status_code!=200:raise urllib.error.HTTPError(path,response.status_code,'fault gateway unavailable',{},None)
   return response.json()
  box=Outbox(tmp_path/'surviving-volume.db');batch=send('/apify/lease',payload={'owner':box.owner})['run'];assert batch
  box.save({'kind':'apify','batch':batch});provider=Provider();original=provider.handler
  def network(request):
   nonlocal down
   response=original(request)
   if request.method=='POST' and request.url.path.endswith('/runs'):
    subprocess.run(['docker','stop','-t','1',container],check=True,capture_output=True);down=True
   return response
  client=Client(TOKEN,httpx.MockTransport(network))
  with pytest.raises(urllib.error.URLError):cycle(box,send,'unused',apify_client=client)
  assert down and box.load()[1]['done'] and box.status()['messages_pending']>0
  # Simulates restarting the collector while its independent disk survives.
  box.close();box=Outbox(tmp_path/'surviving-volume.db')
  subprocess.run(['docker','start',container],check=True,capture_output=True);down=False
  for _ in range(30):
   try:
    with engine.connect() as db:db.execute(text('SELECT 1'))
    break
   except Exception:time.sleep(0.2)
  else:pytest.fail('Disposable PostgreSQL did not recover')
  cycle(box,send,'unused',apify_client=client)
  assert not box.status()['work_pending'] and len(provider.launches)==1
  with factory() as db:
   assert db.query(Observation).count()==1 and db.query(EventCandidate).count()==1
   from app.models.event import Event
   assert db.query(Event).count()==0
   # Concurrent retries of the same receipt under the real gateway role.
   receipt=db.query(DeliveryReceipt).filter(DeliveryReceipt.result['state'].as_string()=='finished').one()
   assert receipt.body_hash and db.get(ApifyRun,batch['id']).state=='finished'
   p=db.query(Publisher).one();p.method='http'
   lease='y'*43
   from app.social.security import digest
   job=CollectionJob(publisher_id=p.id,dedup_key=uuid.uuid4().hex,state='running',buffered=True,lease_digest=digest(lease),lease_until=time.time()-100)
   db.add(job);db.commit();job_id=job.id
  body={'id':str(uuid.uuid4()),'action':'legacy:complete','identity':job_id,'owner':lease,'payload':{'outcome':'empty'}}
  def deliver(_):return send('/outbox/deliver',payload=body)
  with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(deliver,range(4)))
  assert all(r['ok'] for r in results)
  with factory() as db:assert db.query(DeliveryReceipt).filter_by(id=body['id']).count()==1
 finally:
  if box:box.close()
  if down:subprocess.run(['docker','start',container],capture_output=True)
  app.dependency_overrides.pop(database,None);settings.cache_clear()
  if http:http.close()
  if runtime_engine:runtime_engine.dispose()
  if engine:engine.dispose()
  with admin.connect() as db:db.execute(text('DROP DATABASE '+name+' WITH (FORCE)'))
  admin.dispose()
