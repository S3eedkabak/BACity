"""Real staging gateway plus fsync-backed capture; no live provider calls."""
import copy,json,os,subprocess,sys,time,urllib.error,uuid
from types import SimpleNamespace
from pathlib import Path
import httpx
import pytest
from app.social.acquisition.outbox import Outbox,OutboxUnavailable
from app.social.acquisition.durable_runner import cycle
from app.social.models import Observation,EventCandidate,CollectionJob,ApifyRun,DeliveryReceipt,Publisher,ProviderRequest
from app.social.config import settings
from app.social.workflows import schedule
from .test_apify import apify,Provider,lease
from .test_scrapingant import provider,seed_usage,document


def sender(worker,offline=None,lost=None):
 def send(path,*,payload=None,lease=None):
  if offline is not None and offline[0]:raise urllib.error.URLError('database outage')
  headers={'X-Social-Lease':lease} if lease else {}
  r=worker.post(path,json=payload,headers=headers) if payload is not None else worker.get(path,headers=headers)
  if r.status_code!=200:raise urllib.error.HTTPError(path,r.status_code,'delivery refused',{},None)
  if lost is not None and payload and payload.get('action')==lost[0]:
   lost[0]=None;raise urllib.error.URLError('ACK lost after commit')
  return r.json()
 return send


def test_reopen_lock_permissions_and_no_unacknowledged_deletion(tmp_path):
 path=tmp_path/'outbox.db';box=Outbox(path);owner=box.owner
 box.save({'kind':'legacy','done':True});box.message('legacy:complete',str(uuid.uuid4()),'x'*43,{'outcome':'empty'})
 with pytest.raises(OutboxUnavailable):Outbox(path)
 box.close();box=Outbox(path)
 assert box.owner==owner and box.status()['messages_pending']==1
 assert path.stat().st_mode&0o777==0o600
 with pytest.raises(OutboxUnavailable):box.clear()
 box.flush(lambda *a,**kw:{'ok':True});box.clear();assert not box.status()['work_pending'];box.close()


def test_process_kill_after_enqueue_preserves_message(tmp_path):
 path=tmp_path/'crash.db'
 code="from app.social.acquisition.outbox import Outbox; import os,sys,uuid; b=Outbox(sys.argv[1]); b.save({'kind':'legacy'}); b.message('legacy:complete',str(uuid.uuid4()),'x'*43,{'outcome':'empty'}); os._exit(19)"
 r=subprocess.run([sys.executable,'-c',code,str(path)],env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2])},capture_output=True)
 assert r.returncode==19
 box=Outbox(path);assert box.status()['messages_pending']==1;box.close()


def test_disk_pressure_blocks_new_work(tmp_path,monkeypatch):
 box=Outbox(tmp_path/'full.db');calls=[]
 monkeypatch.setattr('app.social.acquisition.outbox.shutil.disk_usage',lambda p:SimpleNamespace(free=0))
 with pytest.raises(OutboxUnavailable):cycle(box,lambda *a,**k:calls.append(a),'unused')
 assert calls==[];box.close()


def test_apify_database_outage_restart_and_expired_lease(apify,tmp_path):
 social,_,_,worker,_,_=apify;path=tmp_path/'apify.db';box=Outbox(path)
 batch=lease(apify,owner=box.owner);box.save({'kind':'apify','batch':batch});offline=[False]
 provider=Provider();original=provider.handler
 def network(request):
  result=original(request)
  if request.method=='POST' and request.url.path.endswith('/runs'):offline[0]=True
  return result
 from app.social.acquisition.apify import Client
 client=Client('apify-fixture-token-never-in-content',httpx.MockTransport(network));send=sender(worker,offline)
 with pytest.raises(urllib.error.URLError):cycle(box,send,'unused',apify_client=client)
 assert box.load()[1]['done'] and box.status()['messages_pending']>=3
 with social.factory() as db:
  assert db.query(Observation).count()==0
  db.get(ApifyRun,batch['id']).lease_until=time.time()-86400;db.commit()
 box.close();box=Outbox(path);offline[0]=False;cycle(box,send,'unused',apify_client=client)
 assert not box.status()['work_pending'] and len(provider.launches)==1
 with social.factory() as db:
  assert db.query(Observation).count()==1 and db.query(EventCandidate).count()==1
  assert db.get(ApifyRun,batch['id']).state=='finished'
  from app.models.event import Event
  assert db.query(Event).count()==0
 box.close()


def test_launch_response_survives_crash_before_progress(apify,tmp_path,monkeypatch):
 social,_,_,worker,_,_=apify;path=tmp_path/'launch.db';box=Outbox(path)
 batch=lease(apify,owner=box.owner);box.save({'kind':'apify','batch':batch});provider=Provider();original=box.message
 def crash(action,*a,**kw):
  if action=='apify:progress':raise SystemExit(19)
  return original(action,*a,**kw)
 monkeypatch.setattr(box,'message',crash)
 with pytest.raises(SystemExit):cycle(box,sender(worker),'unused',apify_client=provider.client())
 assert box.load()[1]['launch_response']['id']=='ActorRun123'
 box.close();box=Outbox(path);cycle(box,sender(worker),'unused',apify_client=provider.client())
 assert len(provider.launches)==1
 with social.factory() as db:assert db.query(Observation).count()==1
 box.close()


def test_lost_ack_after_commit_is_exactly_once(apify,tmp_path):
 social,_,_,worker,_,_=apify;path=tmp_path/'ack.db';box=Outbox(path)
 batch=lease(apify,owner=box.owner);box.save({'kind':'apify','batch':batch});provider=Provider();send=sender(worker,lost=['apify:finish'])
 with pytest.raises(urllib.error.URLError):cycle(box,send,'unused',apify_client=provider.client())
 with social.factory() as db:assert db.query(Observation).count()==1
 box.close();box=Outbox(path);cycle(box,send,'unused',apify_client=provider.client())
 with social.factory() as db:assert db.query(Observation).count()==1 and db.query(EventCandidate).count()==1
 assert len(provider.launches)==1 and not box.status()['work_pending'];box.close()


def legacy_setup(social,monkeypatch):
 monkeypatch.setenv('SOCIAL_L4_COLLECTION_ENABLED','true');settings.cache_clear()
 _,staff,_,_=social.login();publisher=social.publisher(staff)
 worker=social.client(worker=True);worker.headers['X-Social-Worker-Key']=settings().worker_key
 return publisher,worker,worker.post('/lease').json()['job']


def content_for(announcement):return {k:v for k,v in announcement.items() if k!='permission_attestation'}|{'adapter':'fixture'}


def test_legacy_outage_and_expired_lease(social,monkeypatch,announcement,tmp_path):
 p,worker,job=legacy_setup(social,monkeypatch);offline=[False]
 def capture(*a):offline[0]=True;return {'outcome':'success','observations':[content_for(announcement)]}
 monkeypatch.setattr('app.social.acquisition.runner.bounded',capture)
 path=tmp_path/'legacy.db';box=Outbox(path);box.save({'kind':'legacy','job':job})
 with pytest.raises(urllib.error.URLError):cycle(box,sender(worker,offline),'unused')
 with social.factory() as db:
  j=db.get(CollectionJob,job['id']);assert j.buffered;j.lease_until=time.time()-86400;db.commit();schedule(db)
  assert db.get(CollectionJob,job['id']).state=='running'
 box.close();box=Outbox(path);offline[0]=False;cycle(box,sender(worker,offline),'unused')
 with social.factory() as db:assert db.query(Observation).count()==1 and not db.get(CollectionJob,job['id']).buffered
 box.close()


def test_suspension_retains_queue(social,monkeypatch,announcement,tmp_path):
 p,worker,job=legacy_setup(social,monkeypatch)
 box=Outbox(tmp_path/'suspend.db');box.save({'kind':'legacy','job':job,'done':True})
 box.message('legacy:complete',job['id'],job['lease'],{'outcome':'success','observations':[content_for(announcement)]})
 with social.factory() as db:db.get(Publisher,p.id).enabled=False;db.commit()
 with pytest.raises(urllib.error.HTTPError):cycle(box,sender(worker),'unused')
 assert box.status()['messages_pending']==1
 with social.factory() as db:assert db.query(Observation).count()==0 and db.query(DeliveryReceipt).count()==0
 box.close()


def test_transaction_rollback_preserves_retry(social,monkeypatch,announcement,tmp_path):
 from app.social import worker_api
 _,worker,job=legacy_setup(social,monkeypatch);box=Outbox(tmp_path/'rollback.db');box.save({'kind':'legacy','job':job,'done':True})
 box.message('legacy:complete',job['id'],job['lease'],{'outcome':'success','observations':[content_for(announcement)]})
 original=worker_api.stage
 def fail(*a,**kw):original(*a,**kw);raise RuntimeError('transaction failure')
 monkeypatch.setattr(worker_api,'stage',fail)
 with pytest.raises(RuntimeError):cycle(box,sender(worker),'unused')
 with social.factory() as db:assert db.query(Observation).count()==0 and db.query(DeliveryReceipt).count()==0
 monkeypatch.setattr(worker_api,'stage',original);cycle(box,sender(worker),'unused')
 with social.factory() as db:assert db.query(Observation).count()==1 and db.query(DeliveryReceipt).count()==1
 box.close()


def test_scrapingant_captured_response_and_settlement_survive_outage(provider,tmp_path):
 social,_,_,worker,job=provider
 with social.factory() as db:seed_usage(db)
 box=Outbox(tmp_path/'ant.db');box.save({'kind':'legacy','job':job});offline=[False];calls=[]
 def network(request):
  calls.append(request);offline[0]=True;return httpx.Response(200,json=document(),headers={'ant-credits-cost':'1'})
 from app.social.acquisition.scrapingant import Client
 client=Client('synthetic-key-not-live',httpx.MockTransport(network));send=sender(worker,offline)
 with pytest.raises(urllib.error.URLError):cycle(box,send,'unused',scraping_client=client)
 assert box.load()[1]['done'] and len(calls)==1
 box.close();box=Outbox(tmp_path/'ant.db');offline[0]=False;cycle(box,send,'unused',scraping_client=client)
 with social.factory() as db:
  assert db.query(Observation).count()==2
  assert db.query(ProviderRequest).one().cost==1
 assert len(calls)==1;box.close()


def test_receipt_collision_wrong_owner_and_auth(social,monkeypatch):
 _,worker,job=legacy_setup(social,monkeypatch)
 body={'id':str(uuid.uuid4()),'action':'legacy:complete','identity':job['id'],'owner':job['lease'],'payload':{'outcome':'empty'}}
 assert worker.post('/outbox/deliver',json=body).status_code==200
 assert worker.post('/outbox/deliver',json=body).status_code==200
 changed=copy.deepcopy(body);changed['payload']['outcome']='failed'
 assert worker.post('/outbox/deliver',json=changed).status_code==409
 changed=copy.deepcopy(body);changed['id']=str(uuid.uuid4());changed['owner']='z'*43
 assert worker.post('/outbox/deliver',json=changed).status_code==409
 assert worker.post('/outbox/deliver',json=body,headers={'X-Social-Worker-Key':'bad'}).status_code==401

@pytest.mark.parametrize('http_status',[None,503])
def test_already_authorized_child_finishes_capture_when_gateway_unavailable(monkeypatch,http_status):
 from app.social.acquisition.runner import bounded
 real=subprocess.Popen
 def launch(argv,**kw):
  return real([sys.executable,'-c',"import time,json; time.sleep(.05); print(json.dumps({'outcome':'success','observations':[{'caption':'captured fixture'}]}))"],**kw)
 def unavailable(*a,**kw):
  if http_status:raise urllib.error.HTTPError('/active',http_status,'database down',{},None)
  raise urllib.error.URLError('gateway unavailable')
 monkeypatch.setattr('app.social.acquisition.runner.subprocess.Popen',launch)
 monkeypatch.setattr('app.social.acquisition.runner.gateway',unavailable)
 result=bounded({'id':'fixture','lease':'x'*43},'not-in-child')
 assert result['outcome']=='success' and result['observations'][0]['caption']=='captured fixture'


def test_failed_intent_persistence_prevents_paid_launch(apify,tmp_path,monkeypatch):
 _,_,_,worker,_,_=apify;box=Outbox(tmp_path/'intent.db');batch=lease(apify,owner=box.owner)
 box.save({'kind':'apify','batch':batch});provider=Provider();original=box.save
 def fail(data,*a,**kw):
  if data.get('launch_intent'):raise OutboxUnavailable('disk full')
  return original(data,*a,**kw)
 monkeypatch.setattr(box,'save',fail)
 with pytest.raises(OutboxUnavailable):cycle(box,sender(worker),'unused',apify_client=provider.client())
 assert len(provider.launches)==0;box.close()


def test_stale_cached_actor_grant_cannot_start_paid_run(apify,tmp_path,monkeypatch):
 from app.social.models import ApifyBudget
 social,_,_,worker,_,_=apify;box=Outbox(tmp_path/'stale.db');batch=lease(apify,owner=box.owner)
 box.save({'kind':'apify','batch':batch});provider=Provider();original=box.online
 def expire(send,action,*a,**kw):
  response=original(send,action,*a,**kw)
  if action=='apify:dispatch':
   with social.factory() as db:db.get(ApifyBudget,1).synced=time.time()-7200;db.commit()
  return response
 monkeypatch.setattr(box,'online',expire)
 with pytest.raises(urllib.error.HTTPError):cycle(box,sender(worker),'unused',apify_client=provider.client())
 assert len(provider.launches)==0 and box.status()['work_pending'];box.close()


def test_stale_scraping_reservation_cannot_start_request(provider,tmp_path,monkeypatch):
 social,_,_,worker,job=provider
 with social.factory() as db:seed_usage(db)
 box=Outbox(tmp_path/'stale-ant.db');box.save({'kind':'legacy','job':job});original=box.online;calls=[]
 def expire(send,action,*a,**kw):
  response=original(send,action,*a,**kw)
  if action=='legacy:reserve':
   with social.factory() as db:db.query(ProviderRequest).one().created=time.time()-200;db.commit()
  return response
 monkeypatch.setattr(box,'online',expire)
 from app.social.acquisition.scrapingant import Client
 client=Client('synthetic-key-not-live',httpx.MockTransport(lambda request:calls.append(request)))
 with pytest.raises(urllib.error.HTTPError):cycle(box,sender(worker),'unused',scraping_client=client)
 assert calls==[] and box.status()['work_pending'];box.close()


def test_budget_exhaustion_finishes_job_without_stalling_queue(apify,tmp_path):
 from .test_apify import billing
 social,_,_,worker,_,_=apify;box=Outbox(tmp_path/'budget.db');batch=lease(apify,owner=box.owner)
 box.save({'kind':'apify','batch':batch});provider=Provider();original=provider.handler
 def network(request):
  if request.url.path.endswith('/users/me/limits'):
   snapshot=billing();snapshot['current']['monthlyUsageUsd']=4
   return httpx.Response(200,json={'data':snapshot})
  return original(request)
 from app.social.acquisition.apify import Client
 cycle(box,sender(worker),'unused',apify_client=Client('apify-fixture-token-never-in-content',httpx.MockTransport(network)))
 assert not box.status()['work_pending'] and len(provider.launches)==0
 with social.factory() as db:
  assert db.query(CollectionJob).one().error=='budget_exhausted'
  from app.social.models import ApifyBudget
  assert db.get(ApifyBudget,1).reserved==0
 box.close()


def test_capture_survives_failure_between_result_and_enqueue(social,monkeypatch,announcement,tmp_path):
 _,worker,job=legacy_setup(social,monkeypatch);box=Outbox(tmp_path/'enqueue.db');box.save({'kind':'legacy','job':job});calls=[]
 def capture(*a):calls.append(1);return {'outcome':'success','observations':[content_for(announcement)]}
 monkeypatch.setattr('app.social.acquisition.runner.bounded',capture);original=box.message
 monkeypatch.setattr(box,'message',lambda *a,**kw:(_ for _ in ()).throw(OutboxUnavailable('temporary write failure')))
 with pytest.raises(OutboxUnavailable):cycle(box,sender(worker),'unused')
 assert box.load()[1]['result']['observations'][0]['caption']==announcement['caption']
 monkeypatch.setattr(box,'message',original);cycle(box,sender(worker),'unused')
 assert calls==[1]
 with social.factory() as db:assert db.query(Observation).count()==1
 box.close()


def test_oversized_delivery_retains_captured_payload_across_restart(social,monkeypatch,tmp_path):
 _,worker,job=legacy_setup(social,monkeypatch);path=tmp_path/'oversized.db';box=Outbox(path);box.save({'kind':'legacy','job':job});calls=[]
 def capture(*a):calls.append(1);return {'outcome':'success','observations':[{'caption':'x'*70000}]}
 monkeypatch.setattr('app.social.acquisition.runner.bounded',capture)
 with pytest.raises(OutboxUnavailable):cycle(box,sender(worker),'unused')
 box.close();box=Outbox(path)
 assert len(box.load()[1]['result']['observations'][0]['caption'])==70000
 with pytest.raises(OutboxUnavailable):cycle(box,sender(worker),'unused')
 assert calls==[1];box.close()


def test_emergency_stop_is_refreshed_before_remote_capture(apify,tmp_path):
 social,owner,_,worker,_,_=apify;box=Outbox(tmp_path/'emergency.db');batch=lease(apify,owner=box.owner)
 box.save({'kind':'apify','batch':batch});provider=Provider(status='RUNNING')
 cycle(box,sender(worker),'unused',apify_client=provider.client())
 assert box.status()['work_pending']
 assert owner.post('/api/emergency',json={'stopped':True,'note':'Stop this synthetic capture immediately'}).status_code==200
 provider.status='ABORTED'
 cycle(box,sender(worker),'unused',apify_client=provider.client())
 assert len([r for r in provider.calls if r.url.path.endswith('/abort')])==1
 assert not box.status()['work_pending']
 with social.factory() as db:assert db.query(Observation).count()==0
 box.close()
