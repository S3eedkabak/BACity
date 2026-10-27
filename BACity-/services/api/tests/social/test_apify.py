"""Selected Actor fixtures only. No live Actor runs or provider calls in tests."""
import json
import time
import uuid
import secrets
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest
from app.social.config import settings
from app.social.apify_config import apify_settings,provider_preference
from app.social.models import Publisher,ApifyRun,ApifyBudget,Observation,EventCandidate,CollectionJob,InstagramItem
from app.social.acquisition.apify import Client,ACTOR_ID,actor_input,normalize_record,billing_snapshot,money
from app.social.acquisition.apify_worker import step
from app.social.acquisition.scrapingant import ProviderFailure

TOKEN='apify-fixture-token-never-in-content'
def iso(value):return datetime.fromtimestamp(value,timezone.utc).isoformat()
def billing():
    return {'monthlyUsageCycle':{'startAt':iso(int(time.time()//86400)*86400-5*86400),'endAt':iso(int(time.time()//86400)*86400+25*86400)},
            'limits':{'maxMonthlyUsageUsd':5},'current':{'monthlyUsageUsd':0}}
def actor():
    return {'id':ACTOR_ID,'username':'apify','name':'instagram-scraper','taggedBuilds':{'latest':{'buildNumber':'0.0.831'}},
        'pricingInfos':[{'startedAt':iso(time.time()-86400),'pricingModel':'PAY_PER_EVENT','pricingPerEvent':{'actorChargeEvents':{
            'result':{'eventTieredPricingUsd':{'FREE':{'tieredEventPriceUsd':0.0027}}}}}}]}
def item(handle='fixture_venue',code='FixturePost',reel=False,stamp=None,caption='Koncert Jazz Night\n2030-11-02 20:00\nFixture Hall Bratislava'):
    return {'id':'12345','shortCode':code,'url':f'https://www.instagram.com/{"reel" if reel else "p"}/{code}/','type':'Video' if reel else 'Image',
        'productType':'clips' if reel else 'feed','caption':caption,'timestamp':iso(stamp or time.time()-3600),'ownerUsername':handle,
        'inputUrl':f'https://www.instagram.com/{handle}/','displayUrl':'https://scontent.cdninstagram.com/post.jpg',
        'videoUrl':'https://example.test/video-must-never-download.mp4','likesCount':42,'comments':[{'text':'must not be retained'}]}

@pytest.fixture
def apify(social,monkeypatch):
    monkeypatch.setenv('APIFY_ENABLED','true');monkeypatch.setenv('APIFY_TOKEN_CONFIGURED','true');monkeypatch.setenv('APIFY_API_TOKEN',TOKEN)
    monkeypatch.setenv('SOCIAL_L4_COLLECTION_ENABLED','true');settings.cache_clear()
    owner,staff,_,_=social.login();p=social.publisher(staff,method='apify')
    worker=social.client(worker=True);worker.headers['X-Social-Worker-Key']=settings().worker_key
    identity=secrets.token_urlsafe(32)
    return social,owner,p,worker,identity,staff

def lease(apify,owner=None):
    r=apify[3].post('/apify/lease',json={'owner':owner or apify[4]});assert r.status_code==200,r.text
    return r.json()['run']
def call_for(apify,batch,owner=None):
    def call(action,payload):
        r=apify[3].post('/apify/runs/'+batch['id']+'/'+action,json=payload or {},headers={'X-Social-Lease':owner or apify[4]})
        if r.status_code!=200:
            detail=r.json().get('detail');raise ProviderFailure(detail if detail in ('budget_exhausted','billing_unverified') else 'invalid_content')
        return r.json()
    return call
class Provider:
    def __init__(self,items=None,status='SUCCEEDED',cost=0.0027):self.items=items if items is not None else [item()];self.status=status;self.cost=cost;self.calls=[]
    def handler(self,request):
        self.calls.append(request)
        assert request.url.host=='api.apify.com' and TOKEN not in str(request.url)
        assert request.headers['Authorization']=='Bearer '+TOKEN
        path=request.url.path
        if path.endswith('/users/me/limits'):return httpx.Response(200,json={'data':billing()})
        if path.endswith('/acts/apify~instagram-scraper'):return httpx.Response(200,json={'data':actor()})
        if path.endswith('/runs'):
            assert request.method=='POST';data=json.loads(request.content)
            assert data['resultsType']=='posts' and data['resultsLimit'] in (1,2,3) and data['skipPinnedPosts'] is True
            assert 'token' not in request.url.params and float(request.url.params['maxTotalChargeUsd'])<=4
            assert request.url.params['restartOnError']=='false' and int(request.url.params['timeout'])==300
            return httpx.Response(201,json={'data':{'id':'ActorRun123','actId':ACTOR_ID,'status':'RUNNING','defaultDatasetId':'Dataset123'}})
        if '/actor-runs/' in path:
            return httpx.Response(200,json={'data':{'id':'ActorRun123','actId':ACTOR_ID,'status':self.status,'defaultDatasetId':'Dataset123','usageTotalUsd':self.cost}})
        if path.endswith('/datasets/Dataset123'):return httpx.Response(200,json={'data':{'itemCount':len(self.items)}})
        if path.endswith('/items'):
            offset=int(request.url.params['offset']);return httpx.Response(200,json=self.items[offset:offset+5])
        raise AssertionError(path)
    def client(self):return Client(TOKEN,httpx.MockTransport(self.handler))
    @property
    def launches(self):return [r for r in self.calls if r.method=='POST' and r.url.path.endswith('/runs')]


def test_defaults_and_selected_actor_only(monkeypatch):
    for key in ('ENABLED','API_TOKEN','TOKEN_CONFIGURED','MONTHLY_BUDGET_USD','MONTHLY_RESERVE_USD','MAX_ACTIVE_PROFILES','DEFAULT_POSTS_PER_PROFILE','COLLECTION_INTERVAL_HOURS','INSTAGRAM_ACTOR_ID'):monkeypatch.delenv('APIFY_'+key,raising=False)
    monkeypatch.delenv('INSTAGRAM_ACQUISITION_PROVIDER',raising=False)
    cfg=apify_settings();assert not cfg.enabled and not cfg.configured
    assert cfg.budget==4000000 and cfg.reserve==1000000 and cfg.default_posts_per_profile==1 and cfg.max_active_profiles==20
    assert provider_preference()=='apify'
    monkeypatch.setenv('APIFY_API_TOKEN',TOKEN);assert TOKEN not in repr(apify_settings())
    monkeypatch.setenv('APIFY_INSTAGRAM_ACTOR_ID','other/actor')
    with pytest.raises(ValueError):apify_settings()
    with pytest.raises(ProviderFailure,match='provider_not_configured'):Client('').preflight()

@pytest.mark.parametrize('value',[0,4,10])
def test_invalid_limits_rejected(apify,value):
    social,owner,p,_,_,_=apify
    response=owner.post('/api/publishers',json={'url':'@limit_fixture','name':'Fixture','relevance':'Explicit Bratislava synthetic test','posts_per_profile':value})
    assert response.status_code==422

@pytest.mark.parametrize('limit',[1,2,3])
def test_verified_input_shape(limit):
    members=[{'url':'https://www.instagram.com/fixture_venue/','checkpoint_timestamp':time.time()-3600}]
    value=actor_input(members,limit)
    assert value['resultsType']=='posts' and value['resultsLimit']==limit and value['addParentData'] is True
    assert 'onlyPostsNewerThan' in value and 'search' not in value

@pytest.mark.parametrize('reel',[False,True])
def test_post_and_reel_normalization_discards_analytics(reel):
    members=[{'handle':'fixture_venue','job_id':'job','checkpoint_timestamp':None}]
    key,content,error=normalize_record(item(reel=reel),members)
    assert key=='job' and error is None and ('/reel/' in content['source_url'])==reel
    assert content['caption'] and content['published_at'] and content['media']
    assert 'videoUrl' not in content and 'likesCount' not in content and 'comments' not in content

@pytest.mark.parametrize('change',[{'ownerUsername':'wrong'},{'url':'http://127.0.0.1/a'},{'type':'Story'},{'timestamp':None},{'shortCode':'WrongId'},{'ownerUsername':None},{'timestamp':iso(time.time()+86400)}])
def test_irrelevant_malformed_records_rejected(change):
    with pytest.raises(ProviderFailure):normalize_record(item()|change,[{'handle':'fixture_venue','job_id':'job','checkpoint_timestamp':None}])

def test_carousel_and_old_pinned_order():
    members=[{'handle':'fixture_venue','job_id':'job','checkpoint_timestamp':None}]
    record=item()|{'type':'Sidecar','childPosts':[{'displayUrl':'https://scontent.cdninstagram.com/child.jpg'}]}
    assert len(normalize_record(record,members)[1]['media'])==2
    assert normalize_record(item(stamp=time.time()-2*86400)|{'isPinned':True},members)[2]=='pinned_item_skipped'
    members[0]['checkpoint_timestamp']=time.time()-100
    assert normalize_record(item(stamp=time.time()-3600),members)[2]=='older_item_skipped'


def test_two_profiles_one_run_stages_and_bills_once(apify):
    social,owner,p,worker,identity,staff=apify
    social.publisher(staff,method='apify',url='https://www.instagram.com/second_fixture/',external_id='second_fixture')
    batch=lease(apify);assert len(batch['members'])==2 and batch['actor_input']['resultsLimit']==1
    provider=Provider([item(),item('second_fixture','ReelTwo',True)],cost=0.0054)
    step(batch,provider.client(),call_for(apify,batch))
    assert len(provider.launches)==1
    with social.factory() as db:
        run=db.get(ApifyRun,batch['id']);assert run.state=='finished' and run.cost_kind=='reported_with_overhead'
        assert db.query(Observation).count()==2 and db.query(EventCandidate).count()==2
        assert all(o.method=='apify' for o in db.query(Observation))
        metrics=[j.metrics for j in db.query(CollectionJob)]
        assert sum(m['new_posts'] for m in metrics)==1 and sum(m['new_reels'] for m in metrics)==1
        assert sum(m['new_candidates'] for m in metrics)==2
        assert db.get(ApifyBudget,1).reserved==0 and db.get(ApifyBudget,1).spent>=10400
        from app.models.event import Event
        assert db.query(Event).count()==0
    assert lease(apify) is None
    ui=owner.get('/api/instagram-collection').json();assert ui['apify']['actor']=='apify/instagram-scraper' and len(ui['apify_runs'])==1
    assert TOKEN not in json.dumps(ui)


def test_actual_empty_run_does_not_claim_profile_access(apify):
    social,_,p,_,_,_=apify;batch=lease(apify);provider=Provider([],cost=0)
    step(batch,provider.client(),call_for(apify,batch))
    with social.factory() as db:
        assert db.get(ApifyRun,batch['id']).state=='finished'
        job=db.query(CollectionJob).one();assert job.state=='empty' and job.error=='no_items_unverified'
        assert db.get(Publisher,p.id).last_success is None and db.query(Observation).count()==0

@pytest.mark.parametrize('state',['FAILED','TIMED-OUT','ABORTED'])
def test_failed_actor_is_not_a_successful_batch(apify,state):
    social,_,p,_,_,_=apify;batch=lease(apify);provider=Provider(status=state,cost=0.001)
    step(batch,provider.client(),call_for(apify,batch))
    with social.factory() as db:
        assert db.get(ApifyRun,batch['id']).state=='failed'
        assert db.query(CollectionJob).one().state=='failed' and db.get(Publisher,p.id).last_success is None
        assert db.query(Observation).count()==0


def test_private_profile_is_attributed_and_suspended(apify):
    social,_,p,_,_,_=apify;batch=lease(apify)
    provider=Provider([{'inputUrl':p.url,'error':'private_profile','errorDescription':'access denied'}])
    step(batch,provider.client(),call_for(apify,batch))
    with social.factory() as db:
        assert not db.get(Publisher,p.id).enabled and db.query(CollectionJob).one().state=='blocked'
        assert db.query(Observation).count()==0


def test_unknown_launch_is_never_repeated(apify):
    social,_,_,_,_,_=apify;batch=lease(apify);calls=call_for(apify,batch)
    calls('sync',billing_snapshot(billing(),actor()));calls('reserve',{});calls('dispatch',{})
    recovered=lease(apify)
    provider=Provider();step(recovered,provider.client(),calls)
    assert provider.calls==[]
    with social.factory() as db:
        run=db.get(ApifyRun,batch['id']);assert run.error=='launch_uncertain' and run.cost_kind=='estimated'
        assert db.get(ApifyBudget,1).spent==run.reservation


def test_known_run_restart_reuses_run_id_and_dataset_cursor(apify):
    social,_,_,_,identity,staff=apify
    for i in range(5):social.publisher(staff,method='apify',url=f'https://www.instagram.com/batch_fixture_{i}/',external_id=f'batch_fixture_{i}')
    batch=lease(apify);items=[item()]+[item(f'batch_fixture_{i}',f'Item{i}') for i in range(5)]
    provider=Provider(items,cost=0.0162);call=call_for(apify,batch)
    def crash(action,payload):
        response=call(action,payload)
        if action=='page':raise SystemExit('Synthetic worker restart after durable page acknowledgement')
        return response
    with pytest.raises(SystemExit):step(batch,provider.client(),crash)
    with social.factory() as db:
        run=db.get(ApifyRun,batch['id']);assert run.offset==5 and run.run_id=='ActorRun123'
        run.lease_until=time.time()-1;db.commit()
    new_owner=secrets.token_urlsafe(32);resumed=lease(apify,new_owner)
    step(resumed,provider.client(),call_for(apify,resumed,new_owner))
    assert len(provider.launches)==1
    offsets=[int(r.url.params['offset']) for r in provider.calls if r.url.path.endswith('/items')]
    assert offsets==[0,5]
    with social.factory() as db:assert db.query(Observation).count()==6


def test_concurrent_budget_reservation_and_dispatch(apify):
    social,_,_,worker,identity,_=apify;batch=lease(apify);call=call_for(apify,batch)
    call('sync',billing_snapshot(billing(),actor()))
    def attempt(action):return worker.post('/apify/runs/'+batch['id']+'/'+action,json={},headers={'X-Social-Lease':identity}).status_code
    for action in ('reserve','dispatch'):
        with ThreadPoolExecutor(max_workers=5) as pool:codes=list(pool.map(lambda _:attempt(action),range(5)))
        assert codes.count(200)==1 and codes.count(409)==4


def test_exhausted_budget_never_launches(apify):
    social,_,_,_,_,_=apify;batch=lease(apify);call=call_for(apify,batch)
    call('sync',billing_snapshot(billing(),actor()))
    with social.factory() as db:db.get(ApifyBudget,1).spent=4000000;db.commit()
    provider=Provider();step(batch,provider.client(),call)
    assert provider.launches==[]
    with social.factory() as db:assert db.get(ApifyRun,batch['id']).error=='budget_exhausted'

@pytest.mark.parametrize('status,category',[(401,'provider_auth'),(403,'provider_auth'),(429,'rate_limit'),(500,'provider_transient'),(302,'provider_denied')])
def test_api_errors_redacted_and_not_retried(status,category):
    calls=[]
    def handler(request):calls.append(request);return httpx.Response(status,headers={'Retry-After':'80','Location':'http://127.0.0.1'},json={'error':{'message':TOKEN}})
    with pytest.raises(ProviderFailure) as exc:Client(TOKEN,httpx.MockTransport(handler)).request('GET','/users/me/limits')
    assert exc.value.category==category and TOKEN not in str(exc.value) and len(calls)==1

@pytest.mark.parametrize('path',['https://evil.test','/datasets/../private/items','/actor-runs/../../users/me','/acts/other~actor/runs'])
def test_api_destination_allowlist(path):
    with pytest.raises(ProviderFailure,match='provider_configuration'):Client(TOKEN).request('GET',path)

def test_dedup_across_providers_and_after_raw_retention(apify):
    social,_,p,_,_,_=apify;batch=lease(apify);provider=Provider([item(reel=True)])
    step(batch,provider.client(),call_for(apify,batch))
    from app.social.workflows import stage
    from app.social.maintenance import prune
    with social.factory() as db:
        obs=db.query(Observation).one();published=obs.published_at;caption=obs.caption
        publisher=db.get(Publisher,p.id);publisher.method='scrapingant';db.commit()
        content={'source_url':'https://www.instagram.com/p/FixturePost/','external_id':'FixturePost','caption':caption,
            'published_at':published,'publisher_identifier':p.external_id,'adapter':'fixture_cross_provider','media':[]}
        job=db.query(CollectionJob).one()
        assert stage(db,publisher,content,'L4_WORKER',job=job)[1] is False
        obs.retention_until=time.time()-1
        db.get(ApifyRun,batch['id']).finished=time.time()-15*86400
        db.commit();prune(db)
        assert db.get(ApifyRun,batch['id']).items=={}
        assert db.get(ApifyRun,batch['id']).cost==2700
        assert db.query(Observation).count()==0 and db.query(InstagramItem).count()==1
        assert stage(db,publisher,content,'L4_WORKER',job=job)==(None,False)
        assert db.query(EventCandidate).count()==0


def test_shared_cap_and_daily_interval_prevent_provider_multiplication(apify,monkeypatch):
    social,owner,p,worker,identity,staff=apify
    monkeypatch.setenv('SCRAPINGANT_ENABLED','true');monkeypatch.setenv('SCRAPINGANT_KEY_CONFIGURED','true')
    for i in range(19):social.publisher(staff,method='scrapingant',url=f'https://www.instagram.com/shared_fixture_{i}/',external_id=f'shared_fixture_{i}')
    last=social.publisher(staff,method='apify',enabled=False,url='https://www.instagram.com/over_cap_fixture/',external_id='over_cap_fixture')
    assert owner.post('/api/publishers/'+last.id+'/monitoring',json={'enabled':True}).status_code==409
    batch=lease(apify);assert batch
    with social.factory() as db:
        publisher=db.get(Publisher,p.id);publisher.method='scrapingant';publisher.next_due=0;db.commit()
    assert owner.post('/api/publishers/'+p.id+'/retry').status_code==409
    assert worker.post('/lease').json()['job'] is None # An active batch excludes overlapping provider work.


def test_limits_two_three_apply_and_newest_sort_is_not_dataset_order(apify):
    social,_,p,_,_,_=apify
    with social.factory() as db:db.get(Publisher,p.id).posts_per_profile=2;db.commit()
    batch=lease(apify);assert batch['actor_input']['resultsLimit']==2
    provider=Provider([item(code='Older',stamp=time.time()-7200),item(code='Newest',stamp=time.time()-10),item(code='Middle',stamp=time.time()-3600)],cost=0.0081)
    step(batch,provider.client(),call_for(apify,batch))
    with social.factory() as db:
        run=db.get(ApifyRun,batch['id']);values=run.items[batch['members'][0]['job_id']]
        assert [v['external_id'] for v in values]==['Newest','Middle'] and db.query(Observation).count()==2
        assert db.get(Publisher,p.id).checkpoint=='Newest'


def test_missing_caption_does_not_invent_event(apify):
    social,_,_,_,_,_=apify;batch=lease(apify);provider=Provider([item(caption='')])
    step(batch,provider.client(),call_for(apify,batch))
    with social.factory() as db:
        assert len(db.get(ApifyRun,batch['id']).items[batch['members'][0]['job_id']])==1
        assert db.query(Observation).count()==0 and db.query(EventCandidate).count()==0


def test_suspension_cancels_batch_results(apify):
    social,owner,p,_,_,_=apify;batch=lease(apify);call=call_for(apify,batch)
    call('sync',billing_snapshot(billing(),actor()));call('reserve',{})
    assert owner.post('/api/publishers/'+p.id+'/decision',json={'decision':'suspended','note':'Immediate synthetic batch suspension'}).status_code==200
    with pytest.raises(ProviderFailure):call('dispatch',{})
    current=lease(apify);assert current['cancel_requested']
    provider=Provider();step(current,provider.client(),call)
    assert provider.launches==[]
    with social.factory() as db:assert db.get(ApifyBudget,1).reserved==0 and db.query(Observation).count()==0


def test_billing_rollover_pending_and_usage_floors(apify):
    social,_,_,_,_,_=apify;batch=lease(apify);call=call_for(apify,batch)
    snapshot=billing_snapshot(billing(),actor())|{'used':3900000}
    call('sync',snapshot);call('reserve',{})
    with social.factory() as db:
        b=db.get(ApifyBudget,1);assert b.reserved>0
        b.period_start=time.time()-31*86400;b.period_end=time.time()-1;db.commit()
    # Pending actor charges cannot disappear at the next billing-period boundary.
    with pytest.raises(ProviderFailure):call('sync',snapshot)

@pytest.mark.parametrize('payload',[b'not-json',b'x'*(2*1024*1024+1)])
def test_bad_provider_response_is_bounded(payload):
    with pytest.raises(ProviderFailure):Client(TOKEN,httpx.MockTransport(lambda _:httpx.Response(200,content=payload))).request('GET','/users/me/limits')


def test_unknown_pricing_event_and_echoed_token_fail_closed():
    metadata=actor();metadata['pricingInfos'][0]['pricingPerEvent']['actorChargeEvents']['unknown-startup']={}
    with pytest.raises(ProviderFailure):billing_snapshot(billing(),metadata)
    with pytest.raises(ProviderFailure):Client(TOKEN,httpx.MockTransport(lambda _:httpx.Response(200,json={'token':TOKEN}))).request('GET','/users/me/limits')


def test_bad_dataset_does_not_stage_partial_results(apify):
    social,_,_,_,_,_=apify;batch=lease(apify);provider=Provider([item(),item()|{'ownerUsername':'unapproved'}])
    step(batch,provider.client(),call_for(apify,batch))
    with social.factory() as db:
        assert db.get(ApifyRun,batch['id']).error=='invalid_content' and db.query(Observation).count()==0


def test_owner_editor_role_and_disabled_default(apify,monkeypatch):
    social,owner,p,worker,identity,_=apify
    editor,_,_,_=social.login('SOCIAL_EDITOR')
    assert editor.post('/api/publishers/'+p.id+'/access',json={'method':'apify','eligibility':'available','permission_basis':'Synthetic verified permission','permission_expires':time.time()+3600}).status_code==403
    assert social.client(worker=True).post('/apify/lease',json={'owner':identity}).status_code==401
    monkeypatch.setenv('APIFY_ENABLED','false');assert lease(apify) is None
    assert owner.post('/api/publishers/'+p.id+'/monitoring',json={'enabled':True}).status_code==409


def test_live_probe_no_token_has_no_side_effect(monkeypatch,tmp_path):
    from app.social.apify_probe import main
    monkeypatch.setenv('APIFY_API_TOKEN','');monkeypatch.setenv('APIFY_ENABLED','false')
    path=tmp_path/'never-created.db'
    monkeypatch.setattr('sys.argv',['probe','--state-path',str(path),'--approved-profile','@fixture_venue','--permission-attestation','Synthetic explicit permission only'])
    with pytest.raises(SystemExit,match='no requests made'):main()
    assert not path.exists()

def test_emergency_stop_still_allows_remote_abort_and_accounting(apify):
    social,owner,_,_,_,_=apify;batch=lease(apify);call=call_for(apify,batch)
    call('sync',billing_snapshot(billing(),actor()));call('reserve',{});call('dispatch',{})
    call('progress',{'run_id':'ActorRun123','status':'RUNNING','dataset_id':'Dataset123'})
    assert owner.post('/api/emergency',json={'stopped':True,'note':'Synthetic remote cleanup shutdown'}).status_code==200
    resumed=lease(apify);assert resumed['cancel_requested']
    provider=Provider();step(resumed,provider.client(),call)
    assert len([r for r in provider.calls if r.url.path.endswith('/abort')])==1
    assert provider.launches==[]
    with social.factory() as db:
        assert db.get(ApifyRun,batch['id']).state=='failed' and db.get(ApifyBudget,1).reserved==0
        assert db.query(Observation).count()==0


def test_global_collection_off_can_only_clean_up_existing_runs(apify,monkeypatch):
    social,_,_,_,_,_=apify;batch=lease(apify);call=call_for(apify,batch)
    call('sync',billing_snapshot(billing(),actor()));call('reserve',{})
    monkeypatch.setenv('SOCIAL_L4_COLLECTION_ENABLED','false');settings.cache_clear()
    assert lease(apify)['cancel_requested']
    with pytest.raises(ProviderFailure):call('dispatch',{})
    provider=Provider();step(lease(apify),provider.client(),call)
    assert provider.calls==[] and lease(apify) is None
