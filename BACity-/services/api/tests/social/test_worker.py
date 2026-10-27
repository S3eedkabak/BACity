import time
from unittest.mock import Mock
import pytest
from app.social.config import settings
from app.social.models import Publisher,Observation,CollectionJob,EventCandidate,Control
from app.social.workflows import schedule


def enabled(social,monkeypatch):
    monkeypatch.setenv('SOCIAL_L4_COLLECTION_ENABLED','true');settings.cache_clear()
    client=social.client(worker=True);client.headers['X-Social-Worker-Key']=settings().worker_key
    return client


def test_worker_has_only_staging_endpoints_and_disabled_does_not_schedule(social,monkeypatch):
    _,staff,_,_=social.login();p=social.publisher(staff)
    worker=social.client(worker=True)
    assert worker.post('/lease').status_code==503
    with social.factory() as db:
        assert schedule(db)==[] and db.query(CollectionJob).count()==0
    worker=enabled(social,monkeypatch)
    for path in ['/api/staff','/api/auth/session','/events','/api/publishers']:
        assert worker.get(path).status_code==404
    assert worker.post('/lease',headers={'X-Social-Worker-Key':'wrong'}).status_code==401


def test_job_dedup_single_global_lease_completion_idempotency(social,monkeypatch,announcement):
    _,staff,_,_=social.login();p=social.publisher(staff)
    worker=enabled(social,monkeypatch)
    result=worker.post('/lease');assert result.status_code==200,result.text
    job=result.json()['job'];assert job['publisher_id']==p.id
    assert worker.post('/lease').json()['job'] is None
    content={k:v for k,v in announcement.items() if k!='permission_attestation'}|{'adapter':'synthetic_fixture'}
    payload={'lease':job['lease'],'outcome':'success','observations':[content]}
    done=worker.post('/jobs/'+job['id']+'/complete',json=payload)
    assert done.status_code==200,done.text
    assert done.json()['new_observations']==1
    assert worker.post('/jobs/'+job['id']+'/complete',json=payload).json()['replayed']
    with social.factory() as db:
        assert db.query(Observation).count()==1
        assert db.get(Publisher,p.id).checkpoint==announcement['external_id']
        from app.models.event import Event
        assert db.query(Event).count()==0
        assert db.query(EventCandidate).count()==1

@pytest.mark.parametrize('outcome,error',[('blocked','access_denied'),('unauthorized','login_required'),('rate_limited','rate_limit')])
def test_provider_restriction_suspends_and_never_cancels_event(social,monkeypatch,outcome,error):
    _,staff,_,_=social.login();p=social.publisher(staff)
    worker=enabled(social,monkeypatch);job=worker.post('/lease').json()['job']
    assert worker.post('/jobs/'+job['id']+'/complete',json={'lease':job['lease'],'outcome':outcome,'error':error,'retry_after':3600}).status_code==200
    with social.factory() as db:
        publisher=db.get(Publisher,p.id)
        assert not publisher.enabled and publisher.next_due>time.time()+3500
        assert publisher.last_error==error
        assert schedule(db)==[]
        from app.models.event import Event
        assert db.query(Event).count()==0


def test_cancellation_lease_expiry_and_crash_do_not_stall(social,monkeypatch):
    owner,staff,_,_=social.login();p=social.publisher(staff)
    worker=enabled(social,monkeypatch);job=worker.post('/lease').json()['job']
    with social.factory() as db:
        db.get(CollectionJob,job['id']).lease_until=time.time()-1;db.commit()
        schedule(db)
        assert db.get(CollectionJob,job['id']).state=='failed'
        assert db.get(Publisher,p.id).last_error=='worker_timeout'
    assert worker.post('/jobs/'+job['id']+'/complete',json={'lease':job['lease'],'outcome':'empty'}).status_code==200 # terminal idempotent acknowledgement, no content write
    with social.factory() as db:
        assert db.query(Observation).count()==0


def test_emergency_stop_and_suspension_reject_late_worker_results(social,monkeypatch):
    owner,staff,_,_=social.login();p=social.publisher(staff)
    worker=enabled(social,monkeypatch);job=worker.post('/lease').json()['job']
    assert owner.post('/emergency',json={}).status_code==404
    assert owner.post('/api/emergency',json={'stopped':True,'note':'Suspend all social collection now'}).status_code==200
    assert worker.get('/jobs/'+job['id']+'/active',headers={'X-Social-Lease':job['lease']}).status_code==503
    assert worker.post('/jobs/'+job['id']+'/complete',json={'lease':job['lease'],'outcome':'empty'}).status_code==503
    with social.factory() as db:
        assert db.get(CollectionJob,job['id']).state=='cancelled'
        assert not db.get(Publisher,p.id).enabled
        assert schedule(db)==[]
