"""Persistent Actor batches and atomic micro-dollar reservations in the L4 gateway."""
import time
import secrets
from datetime import datetime,timezone
from fastapi import APIRouter,Depends,HTTPException,Header
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,update
from .db import database
from .models import ApifyBudget,ApifyRun,CollectionJob,Publisher,Control,EventCandidate,Observation
from .security import insert_for,digest,audit
from .workflows import available,stopped,schedule,stage
from .apify_config import apify_settings
from .worker_security import cleanup_worker,Content
from .acquisition.apify import actor_input,TERMINAL

router=APIRouter(prefix='/apify',dependencies=[Depends(cleanup_worker)])
OPEN=('planned','reserved','dispatching','running','dataset')
OVERHEAD=5000 # Conservative API/storage uncertainty, retained even after run billing settles.


def budget_lock(db):
    db.execute(insert_for(db,ApifyBudget).values(id=1).on_conflict_do_nothing(index_elements=['id']))
    return db.execute(select(ApifyBudget).where(ApifyBudget.id==1).with_for_update()).scalar_one()


def summary(db):
    cfg=apify_settings();b=db.get(ApifyBudget,1);now=time.time()
    fresh=bool(b and b.synced and now-b.synced<3600 and b.period_start<=now<b.period_end-600)
    ceiling=min(cfg.budget,5000000-cfg.reserve,(b.provider_limit-cfg.reserve) if b else cfg.budget)
    spent=max(b.spent,b.provider_used+b.since_sync) if b else 0
    return {'enabled':cfg.enabled,'configured':cfg.configured,'actor':'apify/instagram-scraper','default_posts':cfg.default_posts_per_profile,
        'max_profiles':cfg.max_active_profiles,'interval_hours':cfg.collection_interval_hours,'budget_micro_usd':cfg.budget,'reserve_micro_usd':cfg.reserve,
        'spent_micro_usd':spent,'estimated_micro_usd':b.estimated if b else 0,'reserved_micro_usd':b.reserved if b else 0,
        'remaining_micro_usd':max(0,ceiling-spent-(b.reserved if b else 0)), 'period_start':b.period_start if b else None,'period_end':b.period_end if b else None,
        'needs_sync':not fresh,'suspension_reason':b.blocked if b and b.blocked else 'billing_unverified' if not fresh else None,
        'price_per_result_micro_usd':b.price if b else None,'last_sync':b.synced if b else None,
        'coverage':'Bounded posts feed; Reels present in that feed are accepted. Complete combined newest-item coverage is not live verified.'}


def run_view(run):
    return {key:getattr(run,key) for key in ('id','state','run_id','dataset_id','actor_input','members','created','launched','offset','total','dataset_done','actor_cap','reservation','build','error','next_poll','provider_status')}


def owned(db,identity,owner,*,allow_finished=False):
    if db.bind.dialect.name=='sqlite':
        # Disposable live-probe databases have no SELECT FOR UPDATE. Acquire the
        # write lock BEFORE reading state so two callers cannot receive a launch.
        db.execute(update(ApifyRun).where(ApifyRun.id==identity).values(lease_until=ApifyRun.lease_until))
    run=db.execute(select(ApifyRun).where(ApifyRun.id==identity).with_for_update()).scalar_one_or_none()
    if not run or not secrets.compare_digest(run.owner_digest or '',digest(owner)) or run.lease_until<=time.time():
        raise HTTPException(409,'Actor batch lease expired')
    if not allow_finished and run.state not in OPEN:raise HTTPException(409,'Actor batch is terminal')
    run.lease_until=time.time()+90
    return run


def cancellation(db,run):
    from .config import settings
    cfg=settings()
    return not cfg.l4_enabled or not cfg.l4_collection_enabled or not apify_settings().enabled or stopped(db) or any(not available(p:=db.get(Publisher,m['publisher_id'])) or p.method!='apify' or p.posts_per_profile!=m['limit'] or db.get(CollectionJob,m['job_id']).state=='cancelled' for m in run.members)

class Input(BaseModel):model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
class Claim(Input):
    owner: str=Field(min_length=43,max_length=43)
    cleanup_only:bool=False
class Snapshot(Input):
    start:float
    end:float
    used:int=Field(ge=0,le=1000000000000)
    limit:int=Field(ge=0,le=5000000)
    price:int=Field(gt=0,le=100000000)
    startup:int=Field(0,ge=0,le=100000000)
    build:str=Field(pattern=r'^\d+\.\d+\.\d+$',max_length=40)

@router.post('/lease')
def lease(payload:Claim,db=Depends(database)):
    cfg=apify_settings()
    from .config import settings
    social=settings()
    cleanup_only=payload.cleanup_only or not cfg.enabled or not cfg.configured or not social.l4_enabled or not social.l4_collection_enabled or stopped(db)
    db.execute(insert_for(db,Control).values(id=1,emergency_stop=False).on_conflict_do_nothing(index_elements=['id']))
    db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()
    run=db.execute(select(ApifyRun).where(ApifyRun.state.in_(OPEN)).order_by(ApifyRun.created).with_for_update().limit(1)).scalar_one_or_none()
    if run:
        if run.lease_until and run.lease_until>time.time() and run.owner_digest!=digest(payload.owner):
            db.commit();return {'run':None}
        run.owner_digest,run.lease_until=digest(payload.owner),time.time()+90
        view=run_view(run);view['cancel_requested']=cleanup_only or cancellation(db,run)
        db.commit();return {'run':view}
    if cleanup_only:db.commit();return {'run':None}
    if db.query(CollectionJob).filter(CollectionJob.state=='running').count():
        db.commit();return {'run':None}
    db.commit();schedule(db,limit=20,provider_filter='apify')
    db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()
    # Recheck after scheduler commit; another worker may have claimed the batch.
    if db.query(ApifyRun).filter(ApifyRun.state.in_(OPEN)).count():db.commit();return {'run':None}
    jobs=db.execute(select(CollectionJob).join(Publisher,CollectionJob.publisher_id==Publisher.id).where(
        CollectionJob.state=='queued',Publisher.method=='apify').order_by(CollectionJob.created).with_for_update().limit(20)).scalars().all()
    members=[];selected=[];limit=None
    for job in jobs:
        p=db.get(Publisher,job.publisher_id)
        if not available(p):job.state='cancelled';job.finished=time.time();continue
        if limit is not None and p.posts_per_profile!=limit:continue
        limit=p.posts_per_profile
        members.append({'job_id':job.id,'publisher_id':p.id,'handle':p.external_id,'url':p.url,'limit':limit,'checkpoint_timestamp':p.instagram_timestamp})
        selected.append(job)
    if not members:db.commit();return {'run':None}
    run=ApifyRun(dedup_key=digest(':'.join(sorted(j.id for j in selected))),members=members,actor_input=actor_input(members,limit),
        owner_digest=digest(payload.owner),lease_until=time.time()+90)
    db.add(run);db.flush()
    for job in selected:
        job.state,job.started,job.lease_until,job.lease_digest,job.apify_run_id='running',time.time(),time.time()+90,digest(payload.owner),run.id
        job.attempts+=1;db.get(Publisher,job.publisher_id).last_attempt=time.time()
    audit(db,'L4_WORKER','apify.batch_planned',run.id,details={'observations':len(members)})
    db.commit();return {'run':run_view(run)}

@router.get('/runs/{identity}')
def inspect_run(identity:str,x_social_lease:str=Header(''),db=Depends(database)):
    run=owned(db,identity,x_social_lease);view=run_view(run);view['cancel_requested']=cancellation(db,run)
    db.commit();return view

@router.post('/runs/{identity}/sync')
def sync(identity:str,payload:Snapshot,x_social_lease:str=Header(''),db=Depends(database)):
    run=owned(db,identity,x_social_lease);b=budget_lock(db);now=time.time()
    if run.state!='planned' or cancellation(db,run):raise HTTPException(409,'Batch is no longer eligible')
    if not payload.start<=now<payload.end or payload.end-payload.start>40*86400:raise HTTPException(422,'Unverified billing period')
    if b.period_start!=payload.start or b.period_end!=payload.end:
        if b.reserved or (b.period_end and (now<b.period_end or payload.start<b.period_end-1)):
            raise HTTPException(409,'Pending charges prevent period reset')
        b.spent=b.since_sync=b.estimated=0;b.blocked=None
        b.period_start,b.period_end=payload.start,payload.end
    elif payload.used<b.provider_used:raise HTTPException(409,'Usage counter regressed')
    b.provider_used,b.provider_limit,b.price,b.startup,b.build=payload.used,payload.limit,payload.price,payload.startup,payload.build
    b.since_sync=0;b.synced=now;db.commit();return summary(db)

@router.post('/runs/{identity}/reserve')
def reserve(identity:str,x_social_lease:str=Header(''),db=Depends(database)):
    run=owned(db,identity,x_social_lease);b=budget_lock(db);cfg=apify_settings()
    if run.state!='planned':raise HTTPException(409,'Batch already reserved')
    if cancellation(db,run):raise HTTPException(409,'Batch cancelled')
    health=summary(db)
    if health['needs_sync'] or b.blocked:raise HTTPException(409,'billing_unverified')
    count=sum(m['limit'] for m in run.members)
    run.actor_cap=(count*b.price*11+9)//10+b.startup+1000
    run.reservation=run.actor_cap+OVERHEAD
    if health['remaining_micro_usd']<run.reservation:raise HTTPException(409,'budget_exhausted')
    b.reserved+=run.reservation
    run.state,run.period_start,run.build='reserved',b.period_start,b.build
    db.commit();return run_view(run)

@router.post('/runs/{identity}/dispatch')
def dispatch(identity:str,x_social_lease:str=Header(''),db=Depends(database)):
    run=owned(db,identity,x_social_lease)
    if run.state!='reserved' or cancellation(db,run):raise HTTPException(409,'No launch authorization')
    run.state,run.launched='dispatching',time.time()
    audit(db,'L4_WORKER','apify.launch_authorized',run.id);db.commit();return run_view(run)

class Progress(Input):
    run_id:str=Field(pattern=r'^[A-Za-z0-9]{1,32}$')
    status:str=Field(pattern=r'^(READY|RUNNING|SUCCEEDED|FAILED|TIMING-OUT|TIMED-OUT|ABORTING|ABORTED)$')
    dataset_id:str|None=Field(None,pattern=r'^[A-Za-z0-9]{1,32}$')
    cost:int|None=Field(None,ge=0,le=100000000)
    total:int|None=Field(None,ge=0,le=80)

@router.post('/runs/{identity}/progress')
def progress(identity:str,payload:Progress,x_social_lease:str=Header(''),db=Depends(database)):
    run=owned(db,identity,x_social_lease)
    if run.state not in ('dispatching','running','dataset'):raise HTTPException(409,'Run not dispatched')
    if run.run_id and run.run_id!=payload.run_id:raise HTTPException(409,'Run identity cannot change')
    if run.dataset_id and payload.dataset_id and run.dataset_id!=payload.dataset_id:raise HTTPException(409,'Dataset identity cannot change')
    run.run_id,run.provider_status=payload.run_id,payload.status
    if payload.dataset_id:run.dataset_id=payload.dataset_id
    if payload.cost is not None and payload.status in TERMINAL:run.cost=payload.cost
    run.polls+=1
    if payload.status=='SUCCEEDED':
        if not run.dataset_id:raise HTTPException(422,'Successful run has no dataset identity')
        run.state='dataset'
        if payload.total is not None:run.total=payload.total;run.dataset_done=run.offset==run.total
    elif payload.status in TERMINAL:
        finish(db,run,'actor_'+payload.status.lower().replace('-','_'))
    else:run.state='running'
    db.commit();return run_view(run)

class DatasetContent(Content):
    caption:str=Field('',max_length=20000)

class Page(Input):
    offset:int=Field(ge=0,le=80)
    count:int=Field(ge=0,le=5)
    records:list[dict]=Field(default_factory=list,max_length=5)

@router.post('/runs/{identity}/page')
def page(identity:str,payload:Page,x_social_lease:str=Header(''),db=Depends(database)):
    run=owned(db,identity,x_social_lease)
    if run.state!='dataset' or run.total is None or cancellation(db,run):raise HTTPException(409,'Dataset is unavailable')
    if payload.offset<run.offset:return {'offset':run.offset,'replayed':True}
    if payload.offset!=run.offset or payload.offset+payload.count>run.total or len(payload.records)!=payload.count:raise HTTPException(422,'Invalid dataset cursor')
    if payload.count==0 and run.offset<run.total:raise HTTPException(422,'Incomplete dataset')
    items=dict(run.items);errors=dict(run.errors);members={m['job_id']:m for m in run.members}
    for record in payload.records:
        # Only the minimal already-normalized record is accepted; validate it again.
        if set(record)-{'job_id','content','error'} or record.get('job_id') not in members:raise HTTPException(422,'Unattributed dataset item')
        job_id=record['job_id'];member=members[job_id]
        if record.get('error'):
            if record['error'] not in ('challenge','login_required','access_denied','unavailable_content','older_item_skipped','pinned_item_skipped'):raise HTTPException(422,'Invalid source error')
            errors[job_id]=record['error'];continue
        try:content=DatasetContent.model_validate(record.get('content'))
        except ValueError:raise HTTPException(422,'Invalid normalized dataset record') from None
        value=content.model_dump()
        from .acquisition.urls import normalize_target
        try:
            target=normalize_target(content.source_url);dt=datetime.fromisoformat(content.published_at)
            if dt.tzinfo is None:raise ValueError()
            stamp=dt.timestamp();value['published_at']=dt.astimezone(timezone.utc).isoformat()
        except (ValueError,TypeError):raise HTTPException(422,'Item has no trustworthy timestamp or URL') from None
        if target.platform!='instagram' or target.target_type!='post' or target.external_id!=content.external_id or content.publisher_identifier!=member['handle'] or stamp>time.time()+300:
            raise HTTPException(422,'Dataset source attribution mismatch')
        values={c['external_id']:c for c in items.get(job_id,[])};values[content.external_id]=value
        items[job_id]=sorted(values.values(),key=lambda v:(v['published_at'],v['external_id']),reverse=True)[:member['limit']]
    run.items,run.errors,run.offset=items,errors,run.offset+payload.count
    run.dataset_done=run.offset==run.total
    db.commit();return {'offset':run.offset,'done':run.dataset_done}


def finish(db,run,error=None,retry_after=0):
    b=budget_lock(db)
    # Undispatched reservations can be released; dispatched/unknown runs cannot.
    if run.reservation and run.cost_kind is None:
        known=run.cost is not None
        floor=(run.total or 0)*(b.price or 0)
        amount=(max(run.cost,floor)+OVERHEAD) if known else run.reservation
        if not run.launched:amount=0;known=True
        b.reserved-=run.reservation;b.spent+=amount;b.since_sync+=amount;b.estimated+=(amount-run.cost) if known and run.launched else 0 if known else amount
        run.cost_kind='reported_with_overhead' if known else 'estimated'
        if run.cost and run.cost>run.actor_cap:b.blocked='provider_cost_exceeded_reservation'
    cancelled=cancellation(db,run)
    for member in run.members:
        job=db.get(CollectionJob,member['job_id']);p=db.get(Publisher,member['publisher_id'])
        if job.state=='cancelled':continue
        values=run.items.get(job.id,[]);source_error=run.errors.get(job.id)
        restriction=source_error in ('challenge','login_required','access_denied') or error in ('provider_auth','provider_denied')
        problem=error or source_error
        if cancelled or not available(p):problem='cancelled';values=[]
        new=0;new_posts=0;new_reels=0
        if not problem or source_error in ('older_item_skipped','pinned_item_skipped'):
            for value in values:
                if len(value['caption'])<5:continue
                _,created=stage(db,p,value,'L4_WORKER',job=job);new+=int(created)
                if created:
                    new_reels+=int('/reel/' in value['source_url']);new_posts+=int('/p/' in value['source_url'])
                stamp=datetime.fromisoformat(value['published_at']).timestamp()
                if p.instagram_timestamp is None or stamp>p.instagram_timestamp:p.instagram_timestamp=stamp;p.checkpoint=value['external_id']
        job.state='cancelled' if problem=='cancelled' else 'blocked' if restriction else 'failed' if error else 'partial' if values and problem else 'success' if values else 'empty'
        job.finished=time.time();job.error=problem or (None if values else 'no_items_unverified')
        job.metrics={'posts_discovered':len(values),'reels_discovered':sum('/reel/' in v['source_url'] for v in values),'new_observations':new,'new_posts':new_posts,'new_reels':new_reels,
            'new_candidates':db.query(EventCandidate).join(Observation,EventCandidate.observation_id==Observation.id).filter(Observation.job_id==job.id).count(),'apify_batch':run.id}
        if values and not error and not restriction:p.last_success=time.time();p.failures=0
        elif problem:p.failures+=1
        p.last_error=job.error;p.next_due=max(p.next_due,time.time()+max(p.interval_seconds,apify_settings().interval,retry_after))
        if restriction:p.enabled=False;p.eligibility='blocked'
    run.finished=time.time();run.error=error;run.state='failed' if error else 'finished'
    audit(db,'L4_WORKER','apify.batch_finished',run.id,details={'outcome':run.state})

class Failure(Input):
    retry_after:int=Field(0,ge=0,le=604800)
    error:str|None=Field(None,pattern=r'^(billing_unverified|budget_exhausted|network_error|provider_auth|provider_denied|rate_limit|provider_transient|response_limit|timeout|invalid_content|launch_uncertain|cancelled)$')

@router.post('/runs/{identity}/finish')
def complete(identity:str,payload:Failure|None=None,x_social_lease:str=Header(''),db=Depends(database)):
    run=owned(db,identity,x_social_lease)
    if (payload is None or payload.error is None) and (run.state!='dataset' or not run.dataset_done):raise HTTPException(409,'Dataset incomplete')
    finish(db,run,payload.error if payload else None,payload.retry_after if payload else 0);db.commit();return {'state':run.state,'cost_kind':run.cost_kind,'cost':run.cost}


class Defer(Input):
    error:str=Field('rate_limit',pattern=r'^(network_error|provider_transient|rate_limit)$')
    retry_after:int=Field(ge=1,le=604800)

@router.post('/runs/{identity}/defer')
def defer(identity:str,payload:Defer,x_social_lease:str=Header(''),db=Depends(database)):
    run=owned(db,identity,x_social_lease);run.next_poll=time.time()+payload.retry_after
    run.error=payload.error;db.commit();return {'deferred_until':run.next_poll}
