"""Synthetic provider fixtures only: never make live requests in automated tests."""
import json
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone
import httpx
import pytest
from fastapi import HTTPException
from app.social.config import settings
from app.social.provider_config import provider_settings
from app.social.provider_budget import reserve,settle,status,locked
from app.social.models import ProviderBudget,ProviderRequest,Publisher,CollectionJob,Observation,EventCandidate,AuditEvent
from app.social.workflows import schedule,stage
from app.social.acquisition.urls import normalize_target
from app.social.acquisition.scrapingant import Client,ProviderFailure,parse_document,collect,usage_snapshot,media_reference

@pytest.fixture
def provider(social,monkeypatch):
    for key,value in {'ENABLED':'true','KEY_CONFIGURED':'true','API_KEY':'synthetic-key-not-live'}.items():monkeypatch.setenv('SCRAPINGANT_'+key,value)
    monkeypatch.setenv('SOCIAL_L4_COLLECTION_ENABLED','true');settings.cache_clear()
    owner,staff,_,_=social.login();publisher=social.publisher(staff,method='scrapingant')
    worker=social.client(worker=True);worker.headers['X-Social-Worker-Key']=settings().worker_key
    job=worker.post('/lease').json()['job'];assert job
    return social,owner,publisher,worker,job

def seed_usage(db,**values):
    state=ProviderBudget(**({'id':1,'period_start':time.time()-4*86400,'period_end':time.time()+26*86400,
        'provider_total':10000,'provider_remaining':10000,'provider_used':0,'synced':time.time()}|values))
    db.add(state);db.commit();return state

def document(handle='fixture_venue',posts=True,caption='Koncert Jazz Night\n2030-11-02 20:00\nFixture Hall Bratislava\nVstup 10 EUR'):
    items=[{'node':{'shortcode':code,'owner':{'username':handle},'product_type':'clips' if reel else 'feed',
        'taken_at_timestamp':int(time.time()-3600),'display_url':'https://scontent.cdninstagram.com/thumbnail.jpg',
        'edge_media_to_caption':{'edges':[{'node':{'text':caption}}]}}} for code,reel in [('FixturePost',False),('FixtureReel',True)]] if posts else []
    value={'data':{'user':{'username':handle,'is_private':False,'edge_owner_to_timeline_media':{'edges':items}}}}
    return {'status_code':200,'html':'<html><meta property="og:url" content="https://www.instagram.com/'+handle+'/"><script type="application/json">'+json.dumps(value)+'</script></html>'}

def db_quota(social,job):
    def quota(action,payload):
        with social.factory() as db:
            j=db.get(CollectionJob,job['id'])
            try:
                if action=='status':return status(db)
                if action=='reserve':return reserve(db,j,payload['request_id'],payload['kind'],payload['target'])
                return settle(db,j,payload['request_id'],payload['cost'],payload['snapshot'],payload['error'])
            except HTTPException as exc:raise ProviderFailure(exc.detail) from None
    return quota

def test_defaults_missing_key_and_secret_repr(monkeypatch):
    for key in ['ENABLED','API_KEY','KEY_CONFIGURED','MONTHLY_CREDIT_LIMIT','MONTHLY_CREDIT_RESERVE','MAX_ACTIVE_PROFILES','COLLECTION_INTERVAL_HOURS']:monkeypatch.delenv('SCRAPINGANT_'+key,raising=False)
    cfg=provider_settings();assert not cfg.enabled and not cfg.configured
    assert (cfg.monthly_credit_limit,cfg.monthly_credit_reserve,cfg.max_active_profiles,cfg.interval)==(10000,1000,20,86400)
    monkeypatch.setenv('SCRAPINGANT_API_KEY','sensitive-fixture');assert 'sensitive-fixture' not in repr(provider_settings())
    monkeypatch.setenv('SCRAPINGANT_MONTHLY_CREDIT_RESERVE','10000')
    with pytest.raises(ValueError):provider_settings()
    with pytest.raises(ProviderFailure,match='provider_not_configured'):Client('').request('usage')

@pytest.mark.parametrize('value',['@Fixture_Venue','fixture_venue','https://instagram.com/Fixture_Venue/'])
def test_profile_normalization(value):assert normalize_target(value).url=='https://www.instagram.com/fixture_venue/'

@pytest.mark.parametrize('value',['@foo/../../login','https://127.0.0.1/','https://instagram.com.evil.test/foo','https://instagram.com/accounts/login','https://instagram.com/foo/?url=http://localhost','@login'])
def test_unsafe_urls(value):
    with pytest.raises(ValueError):normalize_target(value)

def test_feed_reel_identity_timestamp_and_media():
    posts,links=parse_document('https://www.instagram.com/fixture_venue/',document(),'fixture_venue')
    assert len(posts)==2 and links==[]
    assert {p['source_url'] for p in posts}=={'https://www.instagram.com/p/FixturePost/','https://www.instagram.com/reel/FixtureReel/'}
    assert all(p['published_at'] and p['caption'] and p['media'] and p['publisher_identifier']=='fixture_venue' for p in posts)
    for url in ['http://127.0.0.1/image.jpg','https://cdninstagram.com.evil.test/a.jpg','https://user:password@a.cdninstagram.com/a.jpg']:assert not media_reference(url)
    with pytest.raises(ProviderFailure):parse_document('https://www.instagram.com/fixture_venue/',document('other'),'fixture_venue')

@pytest.mark.parametrize('html,error',[('<html>Log in to continue</html>','login_required'),('<html>Verify you are human</html>','challenge'),('<html>Access denied</html>','access_denied'),('<html></html>','invalid_content'),('<form action="/accounts/login/"></form>','login_required'),('<meta property="og:url" content="https://www.instagram.com/fixture_venue/">','invalid_content')])
def test_http_200_is_not_success(html,error):
    with pytest.raises(ProviderFailure) as exc:parse_document('https://www.instagram.com/fixture_venue/',{'status_code':200,'html':html},'fixture_venue')
    assert exc.value.category==error

def test_missing_fields_and_explicit_empty_feed():
    page=document(caption='');value=json.loads(page['html'].split('<script type="application/json">')[1].split('</script>')[0])
    for entry in value['data']['user']['edge_owner_to_timeline_media']['edges']:
        entry['node'].pop('taken_at_timestamp');entry['node'].pop('display_url')
    page['html']='<script>'+json.dumps(value)+'</script>'
    posts,_=parse_document('https://www.instagram.com/fixture_venue/',page,'fixture_venue')
    assert len(posts)==2 and all(not p['published_at'] and not p['caption'] and not p['media'] for p in posts)
    assert parse_document('https://www.instagram.com/fixture_venue/',document(posts=False),'fixture_venue')==([],[])

@pytest.mark.parametrize('code,error',[(403,'provider_auth'),(401,'provider_denied'),(423,'provider_denied'),(429,'rate_limit'),(500,'provider_transient'),(302,'provider_denied')])
def test_provider_errors_no_retries_or_key_url(code,error):
    calls=[]
    def handler(request):
        calls.append(request);assert request.url.host=='api.scrapingant.com' and 'synthetic-secret' not in str(request.url)
        assert request.headers['x-api-key']=='synthetic-secret'
        assert request.url.params['browser']=='false' and request.url.params['proxy_type']=='datacenter'
        return httpx.Response(code,headers={'Ant-credits-cost':'1','Retry-After':'123','Location':'https://127.0.0.1'},json={'detail':'synthetic-secret must never escape'})
    with pytest.raises(ProviderFailure) as exc:Client('synthetic-secret',httpx.MockTransport(handler)).request('acquire','https://www.instagram.com/fixture_venue/')
    assert exc.value.category==error and len(calls)==1 and 'synthetic-secret' not in str(exc.value)
    if code==429:assert exc.value.retry_after==123

@pytest.mark.parametrize('body',[b'x'*(2*1024*1024+1),b'not json',b'[]'])
def test_malformed_and_large_responses(body):
    with pytest.raises(ProviderFailure):Client('synthetic-provider-key-not-in-content',httpx.MockTransport(lambda _:httpx.Response(200,content=body))).request('usage')

def test_usage_validation():
    with pytest.raises(ProviderFailure):usage_snapshot({'start_date':'bad'})

def test_concurrent_reservations_and_ambiguous_cost(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:seed_usage(db)
    def attempt(_):
        with social.factory() as db:
            try:return reserve(db,db.get(CollectionJob,job['id']),str(uuid.uuid4()),'acquire',publisher.url)['reservation']
            except HTTPException:return None
    with ThreadPoolExecutor(max_workers=6) as executor:results=list(executor.map(attempt,range(6)))
    assert len([x for x in results if x])==1;token=next(x for x in results if x)
    with social.factory() as db:
        result=settle(db,db.get(CollectionJob,job['id']),token,None)
        assert result['cost']==125 and result['cost_kind']=='estimated'
        assert settle(db,db.get(CollectionJob,job['id']),token,0)['replayed']
        assert db.get(ProviderBudget,1).charged==125 and db.get(ProviderBudget,1).reserved==0

def test_hard_budget_and_reported_cost(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:
        seed_usage(db,provider_used=8875,provider_remaining=1125);token=str(uuid.uuid4());j=db.get(CollectionJob,job['id'])
        reserve(db,j,token,'acquire',publisher.url);assert status(db)['remaining_budget']==0
        settle(db,j,token,1);assert status(db)['reported_credits']==1 and status(db)['remaining_budget']==124
        db.get(ProviderBudget,1).charged=9000;db.commit()
        with pytest.raises(HTTPException,match='budget_exhausted'):reserve(db,j,str(uuid.uuid4()),'acquire',publisher.url)

def test_actual_billing_period_and_crashed_call(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:
        seed_usage(db,charged=500,period_start=time.time()-35*86400,period_end=time.time()-1);j=db.get(CollectionJob,job['id']);token=str(uuid.uuid4())
        with pytest.raises(HTTPException,match='usage_unverified'):reserve(db,j,token,'acquire',publisher.url)
        db.rollback();reserve(db,j,token,'usage','')
        settle(db,j,token,0,{'start':time.time()-1,'end':time.time()+30*86400,'total':10000,'remaining':9999})
        assert status(db)['accounted_credits']==1 and db.get(ProviderBudget,1).charged==0
        token=str(uuid.uuid4());reserve(db,j,token,'acquire',publisher.url)
        db.get(ProviderRequest,token).created=time.time()-121;db.commit();locked(db);db.commit()
        assert db.get(ProviderRequest,token).cost==125 and db.get(ProviderBudget,1).reserved==0

def test_cost_change_halts(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:
        seed_usage(db);j=db.get(CollectionJob,job['id']);token=str(uuid.uuid4())
        reserve(db,j,token,'acquire',publisher.url);settle(db,j,token,126)
        assert status(db)['suspension_reason']=='provider_cost_exceeded_reservation'
        with pytest.raises(HTTPException):reserve(db,j,str(uuid.uuid4()),'acquire',publisher.url)

def test_real_pipeline_using_mocked_provider(provider):
    social,owner,publisher,worker,job=provider;calls=[]
    def handler(request):
        calls.append(request)
        if request.url.path.endswith('/usage'):
            return httpx.Response(200,headers={'Ant-credits-cost':'0'},json={'plan_total_credits':10000,'remained_credits':10000,
                'start_date':datetime.fromtimestamp(time.time()-4*86400,timezone.utc).isoformat(),
                'end_date':datetime.fromtimestamp(time.time()+26*86400,timezone.utc).isoformat()})
        return httpx.Response(200,headers={'Ant-credits-cost':'1'},json=document())
    result=collect(job,Client('fixture-key',httpx.MockTransport(handler)),db_quota(social,job))
    assert result['outcome']=='success' and len(result['observations'])==2 and len(calls)==2
    assert result['provider_metrics']['credits_accounted']==1
    response=worker.post('/jobs/'+job['id']+'/complete',json={**result,'lease':job['lease']})
    assert response.status_code==200,response.text
    assert response.json()['new_observations']==2
    with social.factory() as db:
        assert db.query(Observation).count()==2 and db.query(EventCandidate).count()==1
        assert all(o.method=='scrapingant' and o.media for o in db.query(Observation))
        assert db.get(CollectionJob,job['id']).metrics['new_reels']==1
        from app.models.event import Event
        assert db.query(Event).count()==0
        for content in result['observations']:assert not stage(db,db.get(Publisher,publisher.id),content,'L4_WORKER',job=db.get(CollectionJob,job['id']))[1]
        assert db.query(EventCandidate).count()==1
    assert worker.post('/jobs/'+job['id']+'/complete',json={**result,'lease':job['lease']}).json()['replayed']
    ui=owner.get('/api/instagram-collection').json();assert ui['posts_discovered']==2 and ui['reels_discovered']==1 and ui['event_candidates']==1
    assert 'fixture-key' not in json.dumps(ui) and worker.get('/api/instagram-collection').status_code==404

def test_daily_schedule_flags_suspension_and_expiry(provider,monkeypatch):
    social,owner,publisher,worker,job=provider
    with social.factory() as db:
        p=db.get(Publisher,publisher.id);j=db.get(CollectionJob,job['id']);j.state='failed';j.finished=time.time();p.next_due=0;db.commit()
        assert schedule(db)==[]
        future=time.time()+86401;p.permission_expires=future+86400;db.commit();assert len(schedule(db,now=future))==1;assert schedule(db,now=future)==[]
        db.query(CollectionJob).filter_by(state='queued').update({'state':'cancelled'});p.next_due=0;p.last_attempt=None;p.approval='suspended';db.commit();assert schedule(db)==[]
        p.approval='approved';p.permission_expires=time.time()-1;db.commit();assert schedule(db)==[]
        p.permission_expires=time.time()+86400;db.commit();monkeypatch.setenv('SCRAPINGANT_ENABLED','false');assert schedule(db)==[]
    assert owner.post('/api/publishers/'+publisher.id+'/retry').status_code==409

def test_profile_cap_spread_manual_rbac_and_audit(provider):
    social,owner,publisher,worker,job=provider
    with social.factory() as db:staff=db.get(Publisher,publisher.id).created_by
    profiles=[]
    for i in range(20):
        with social.factory() as db:
            p=Publisher(platform='instagram',target_type='profile',url=f'https://www.instagram.com/cap_fixture_{i}/',external_id=f'cap_fixture_{i}',name='Fixture',relevance='Test Bratislava venue',approval='approved',eligibility='available',method='scrapingant',permission_basis='Explicit synthetic test permission',permission_expires=time.time()+86400,created_by=staff)
            db.add(p);db.commit();profiles.append(p.id)
    for identity in profiles[:19]:
        r=owner.post('/api/publishers/'+identity+'/monitoring',json={'enabled':True});assert r.status_code==200,r.text
    assert owner.post('/api/publishers/'+profiles[-1]+'/monitoring',json={'enabled':True}).status_code==409
    with social.factory() as db:
        due=[db.get(Publisher,i).next_due for i in profiles[:19]]
        assert all(time.time()-5<=x<=time.time()+86400 for x in due) and len(set(int(x)//3600 for x in due))>3
        assert any(a.record['action']=='publisher.monitoring_changed' for a in db.query(AuditEvent))
    assert owner.post('/api/publishers/'+publisher.id+'/retry').status_code==409
    editor,_,_,_=social.login('SOCIAL_EDITOR')
    assert editor.post('/api/publishers/'+profiles[0]+'/monitoring',json={'enabled':False}).status_code==403
    assert owner.post('/api/publishers/'+publisher.id+'/decision',json={'decision':'suspended','note':'Synthetic immediate suspension'}).status_code==200
    assert worker.get('/jobs/'+job['id']+'/provider/status',headers={'X-Social-Lease':job['lease']}).status_code==409

def test_gateway_quota_route_contract_and_lease_rbac(provider):
    social,owner,publisher,worker,job=provider
    base='/jobs/'+job['id']+'/provider/'
    def quota(action,payload):
        response=worker.get(base+'status',headers={'X-Social-Lease':job['lease']}) if action=='status' else worker.post(base+action,json=payload|{'lease':job['lease']})
        assert response.status_code==200,response.text
        return response.json()
    def handler(request):
        if request.url.path.endswith('/usage'):
            return httpx.Response(200,headers={'Ant-credits-cost':'0'},json={'plan_total_credits':10000,'remained_credits':9990,
                'start_date':datetime.fromtimestamp(time.time()-86400,timezone.utc).isoformat(),'end_date':datetime.fromtimestamp(time.time()+29*86400,timezone.utc).isoformat()})
        return httpx.Response(200,headers={'Ant-credits-cost':'1'},json=document())
    result=collect(job,Client('synthetic-provider-key-not-in-content',httpx.MockTransport(handler)),quota)
    assert result['outcome']=='success'
    payload={'lease':job['lease'],'request_id':str(uuid.uuid4()),'kind':'acquire','target':'https://127.0.0.1/private'}
    assert worker.post(base+'reserve',json=payload).status_code==422
    payload['target']=publisher.url;payload['lease']='x'*43
    assert worker.post(base+'reserve',json=payload).status_code==403
    assert social.client(worker=True).post(base+'reserve',json=payload).status_code==401
    assert owner.get('/api/instagram-collection').status_code==200
    assert social.client().get('/api/instagram-collection').status_code==401


def test_no_request_after_budget_denial_or_access_restriction(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:seed_usage(db,charged=9000)
    calls=[]
    client=Client('synthetic-provider-key-not-in-content',httpx.MockTransport(lambda request:calls.append(request)))
    result=collect(job,client,db_quota(social,job))
    assert result['error']=='budget_exhausted' and result['requests']==0 and calls==[]
    with social.factory() as db:db.get(ProviderBudget,1).charged=0;db.commit()
    def denied(request):
        calls.append(request);return httpx.Response(200,headers={'Ant-credits-cost':'1'},json={'status_code':200,'html':'Verify you are human'})
    result=collect(job,Client('synthetic-provider-key-not-in-content',httpx.MockTransport(denied)),db_quota(social,job))
    assert result['outcome']=='blocked' and result['error']=='challenge' and len(calls)==1 and result['observations']==[]


def test_snapshot_floor_includes_external_account_use_and_new_calls(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:
        seed_usage(db,provider_used=8500,provider_remaining=1500);j=db.get(CollectionJob,job['id'])
        for _ in range(3):
            token=str(uuid.uuid4());reserve(db,j,token,'acquire',publisher.url);settle(db,j,token,100)
        assert status(db)['accounted_credits']==8800
        assert status(db)['remaining_budget']==200
        with pytest.raises(HTTPException,match='provider_job_request_limit'):reserve(db,j,str(uuid.uuid4()),'acquire',publisher.url)


def test_missing_cost_header_is_not_zero_and_past_period_cannot_reset(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:
        state=seed_usage(db);j=db.get(CollectionJob,job['id']);token=str(uuid.uuid4())
        reserve(db,j,token,'acquire',publisher.url);settle(db,j,token,None)
        assert status(db)['estimated_credits']==125
        state.synced=time.time()-86401;db.commit();token=str(uuid.uuid4());reserve(db,j,token,'usage','')
        with pytest.raises(HTTPException,match='billing_period_not_verified'):
            settle(db,j,token,0,{'start':time.time()-1,'end':time.time()+30*86400,'total':10000,'remaining':10000})
        db.rollback();assert db.get(ProviderBudget,1).reserved==125


def test_parser_rejects_private_identity_mismatch_and_misattributed_videos():
    page=document();value=json.loads(page['html'].split('<script type="application/json">')[1].split('</script>')[0])
    value['data']['user']['is_private']=True
    with pytest.raises(ProviderFailure,match='access_denied'):parse_document('https://www.instagram.com/fixture_venue/',{'status_code':200,'html':'<script>'+json.dumps(value)+'</script>'},'fixture_venue')
    page=document();page['html']=page['html'].replace('content="https://www.instagram.com/fixture_venue/"','content="https://www.instagram.com/other/"')
    with pytest.raises(ProviderFailure):parse_document('https://www.instagram.com/fixture_venue/',page,'fixture_venue')
    value['data']['user']['is_private']=False
    for entry in value['data']['user']['edge_owner_to_timeline_media']['edges']:
        entry['node'].pop('product_type');entry['node']['__typename']='GraphVideo';entry['node']['media_type']=2
    posts,_=parse_document('https://www.instagram.com/fixture_venue/',{'status_code':200,'html':'<script>'+json.dumps(value)+'</script>'},'fixture_venue')
    assert all('/p/' in p['source_url'] for p in posts) # A video is not automatically a Reel.


def test_no_poster_download_or_ocr_claim_and_bounded_captions():
    posts,_=parse_document('https://www.instagram.com/fixture_venue/',document(caption='🎵\x00\n'*10000),'fixture_venue')
    assert all(len(p['caption'].encode())<=3500 and '\x00' not in p['caption'] for p in posts)
    assert all('ocr' not in p and p['media'] for p in posts)

def test_expired_period_probes_are_bounded_and_costs_carried_forward(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:
        end=time.time()-100
        seed_usage(db,charged=9000,period_start=end-30*86400,period_end=end)
        for index in range(3):
            j=CollectionJob(publisher_id=publisher.id,dedup_key=uuid.uuid4().hex);db.add(j);db.commit()
            token=str(uuid.uuid4());reserve(db,j,token,'usage','')
            if index<2:settle(db,j,token,None,None,'usage_unverified')
            else:
                settle(db,j,token,0,{'start':end+1,'end':end+30*86400,'total':10000,'remaining':10000})
        assert status(db)['estimated_credits']==250 and status(db)['accounted_credits']==250
        assert status(db)['usage_requests']==3


def test_failed_renewal_stops_after_three_probes(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:
        seed_usage(db,charged=9000,period_start=time.time()-31*86400,period_end=time.time()-100)
        for index in range(4):
            j=CollectionJob(publisher_id=publisher.id,dedup_key=uuid.uuid4().hex);db.add(j);db.commit();token=str(uuid.uuid4())
            if index==3:
                with pytest.raises(HTTPException,match='usage_unverified'):reserve(db,j,token,'usage','')
            else:reserve(db,j,token,'usage','');settle(db,j,token,None,None,'usage_unverified')


def test_pending_profile_visible_in_collection_panel(social):
    owner,_,_,_=social.login()
    response=owner.post('/api/publishers',json={'url':'@pending_fixture','name':'Pending fixture','relevance':'Bratislava synthetic proposal visibility'})
    assert response.status_code==201
    data=owner.get('/api/instagram-collection').json()
    assert data['active_profiles']==0 and data['publishers'][0]['approval']=='pending'


def test_provider_echoed_key_never_becomes_an_observation():
    key='private-key-echo-test'
    with pytest.raises(ProviderFailure,match='invalid_content'):
        Client(key,httpx.MockTransport(lambda _:httpx.Response(200,json=document(caption=key)))).request('acquire','https://www.instagram.com/fixture_venue/')

def test_live_probe_requires_explicit_activation_and_key(monkeypatch,tmp_path):
    from app.social.scrapingant_probe import main
    monkeypatch.setenv('SCRAPINGANT_API_KEY','');monkeypatch.setenv('SCRAPINGANT_ENABLED','false')
    path=tmp_path/'not-created.db'
    monkeypatch.setattr('sys.argv',['probe','--state-path',str(path),'--approved-profile','@fixture_venue','--permission-attestation','Explicit synthetic test permission only'])
    with pytest.raises(SystemExit,match='no requests made'):main()
    assert not path.exists()


def test_timeout_still_spends_uncertain_reservation(provider):
    social,_,publisher,_,job=provider
    with social.factory() as db:seed_usage(db)
    def timeout(request):raise httpx.ReadTimeout('secret-bearing upstream message must not escape')
    result=collect(job,Client('fixture-key',httpx.MockTransport(timeout)),db_quota(social,job))
    assert result['error']=='network_error' and result['requests']==1 and result['observations']==[]
    with social.factory() as db:assert status(db)['estimated_credits']==125
