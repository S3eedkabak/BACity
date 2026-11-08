"""Commit staging and its delivery receipt together. Never publish from the queue."""
import hashlib
import secrets
import time
import uuid
from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,ConfigDict,Field,ValidationError
from sqlalchemy import select
from .db import database
from .models import DeliveryReceipt,CollectionJob,Publisher,ApifyRun,Control
from .worker_security import cleanup_worker
from .security import digest,insert_for
from .workflows import available,stopped
from .config import settings
from .acquisition.outbox import encoded

router=APIRouter(prefix='/outbox',dependencies=[Depends(cleanup_worker)])

class Delivery(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    id:uuid.UUID
    action:str=Field(max_length=40)
    identity:uuid.UUID
    owner:str=Field(min_length=43,max_length=43)
    payload:dict=Field(default_factory=dict)

class Renewal(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:str=Field(pattern='^(apify|legacy)$')
    identity:uuid.UUID
    owner:str=Field(min_length=43,max_length=43)
    request_id:uuid.UUID|None=None
    request_kind:str|None=Field(None,pattern='^(usage|acquire)$')

class AtomicSession:
    """Existing handlers flush; only this envelope's receipt performs COMMIT."""
    def __init__(self,db):self.db=db
    def __getattr__(self,key):return getattr(self.db,key)
    def commit(self):self.db.flush()


def lock(db):
    db.execute(insert_for(db,Control).values(id=1,emergency_stop=False).on_conflict_do_nothing(index_elements=['id']))
    db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()


def legacy(db,identity,owner):
    job=db.execute(select(CollectionJob).where(CollectionJob.id==identity).with_for_update()).scalar_one_or_none()
    if not job or not secrets.compare_digest(job.lease_digest or '',digest(owner)):
        raise HTTPException(409,'Original collection lease required; buffered data retained')
    return job


def actor(db,identity,owner):
    run=db.execute(select(ApifyRun).where(ApifyRun.id==identity).with_for_update()).scalar_one_or_none()
    if not run or not secrets.compare_digest(run.owner_digest or '',digest(owner)):
        raise HTTPException(409,'Original Actor owner required; buffered data retained')
    return run


def enabled(db):
    cfg=settings()
    if not cfg.l4_enabled or not cfg.l4_collection_enabled or stopped(db):raise HTTPException(409,'Collection paused; buffered data retained')

@router.post('/renew')
def renew(payload:Renewal,db=Depends(database)):
    lock(db);enabled(db);identity=str(payload.identity)
    if payload.kind=='apify':
        from .apify_jobs import cancellation,run_view,summary
        run=actor(db,identity,payload.owner)
        if run.state not in ('reserved','dispatching','running','dataset') or cancellation(db,run):raise HTTPException(409,'Actor no longer eligible')
        if run.state in ('reserved','dispatching') and summary(db)['needs_sync']:
            raise HTTPException(409,'Billing authorization stale; journal retained')
        run.lease_until=time.time()+90;result=run_view(run)
    else:
        job=legacy(db,identity,payload.owner);p=db.get(Publisher,job.publisher_id)
        if job.state!='running' or not available(p):raise HTTPException(409,'Collection no longer eligible')
        if p.method=='scrapingant':
            from .provider_config import provider_settings
            from .provider_budget import status
            from .models import ProviderRequest
            cfg=provider_settings();request=db.get(ProviderRequest,str(payload.request_id)) if payload.request_id else None
            if not cfg.enabled or not cfg.configured or not request or request.job_id!=job.id or request.kind!=payload.request_kind or request.state!='reserved' or time.time()-request.created>120:
                raise HTTPException(409,'Provider reservation no longer authorizes networking')
            health=status(db)
            if request.kind=='acquire' and (health['needs_sync'] or health['suspension_reason'] not in (None,'budget_exhausted')):
                raise HTTPException(409,'Provider billing authorization stale')
        job.lease_until=time.time()+90;job.buffered=True;result={'active':True}
    db.commit();return result

@router.post('/deliver')
def deliver(payload:Delivery,db=Depends(database)):
    lock(db)
    try:hashed=hashlib.sha256(encoded(payload.model_dump(mode='json')).encode()).hexdigest()
    except ValueError:raise HTTPException(422,'Invalid delivery encoding') from None
    previous=db.get(DeliveryReceipt,str(payload.id))
    if previous:
        if not secrets.compare_digest(previous.body_hash,hashed):raise HTTPException(409,'Delivery identity cannot change')
        return previous.result
    if db.query(DeliveryReceipt).count()>=100000:raise HTTPException(503,'Delivery receipt capacity reached; queue retained')
    identity=str(payload.identity);job_id=None;session=AtomicSession(db)
    try:
        if payload.action=='media:complete':
            from .post_images import complete,Completion
            result=complete(db,identity,payload.owner,Completion.model_validate(payload.payload))
        elif payload.action.startswith('apify:'):
            from . import apify_jobs as a
            run=actor(db,identity,payload.owner);run.lease_until=time.time()+90
            actions={'sync':(a.sync,a.Snapshot),'reserve':(a.reserve,None),'dispatch':(a.dispatch,None),
                'progress':(a.progress,a.Progress),'page':(a.page,a.Page),'finish':(a.complete,a.Failure),'defer':(a.defer,a.Defer)}
            action=payload.action[6:]
            if action not in actions:raise HTTPException(422,'Unsupported delivery action')
            function,model=actions[action];kwargs={'x_social_lease':payload.owner,'db':session}
            if model:kwargs['payload']=model.model_validate(payload.payload)
            if action=='reserve':
                try:
                    with db.begin_nested():result=function(identity,**kwargs)
                except HTTPException as error:
                    if error.detail not in ('budget_exhausted','billing_unverified'):raise
                    result={'rejected':error.detail}
            else:result=function(identity,**kwargs)
        elif payload.action in ('legacy:complete','legacy:reserve','legacy:settle'):
            from . import worker_api as w
            job=legacy(db,identity,payload.owner);job_id=job.id
            if payload.action!='legacy:settle':
                enabled(db)
                if not available(db.get(Publisher,job.publisher_id)):raise HTTPException(409,'Publisher no longer eligible; queue retained')
            if payload.action=='legacy:complete':
                if job.state=='cancelled':raise HTTPException(409,'Collection cancelled; queue retained')
                # Only the original buffered lease can recover a timeout, never an
                # unrelated completed/failed result with a newly acquired lease.
                if job.state=='failed' and job.error=='worker_timeout' and job.buffered:job.state='running'
                if job.state!='running':raise HTTPException(409,'Terminal job without matching receipt; queue retained')
                job.lease_until=time.time()+90
                result=w.complete(identity,w.Completion.model_validate({**payload.payload,'lease':payload.owner}),db=session)
            elif payload.action=='legacy:reserve':
                job.lease_until=time.time()+90;job.buffered=True
                try:
                    with db.begin_nested():
                        result=w.provider_reserve(identity,w.QuotaReservation.model_validate({**payload.payload,'lease':payload.owner}),db=session)
                except HTTPException as error:
                    if error.detail not in ('budget_exhausted','usage_unverified','provider_not_configured'):raise
                    result={'rejected':error.detail}
            else:
                # Already incurred charges can settle while collection is off.
                from .provider_budget import settle
                p=w.QuotaSettlement.model_validate({**payload.payload,'lease':payload.owner})
                result=settle(session,job,p.request_id,p.cost,p.snapshot.model_dump() if p.snapshot else None,p.error)
        else:raise HTTPException(422,'Unsupported delivery action')
    except ValidationError:raise HTTPException(422,'Invalid delivery payload') from None
    db.flush()
    db.add(DeliveryReceipt(id=str(payload.id),body_hash=hashed,result=result,job_id=job_id))
    db.commit();return result

@router.post('/state')
def capture_state(payload:Renewal,db=Depends(database)):
    """Refresh cancellation while online; never authorizes a new provider call."""
    if payload.kind!='apify':raise HTTPException(422,'Actor state required')
    lock(db)
    from .apify_jobs import cancellation
    run=actor(db,str(payload.identity),payload.owner)
    run.lease_until=time.time()+90
    result={'cancel_requested':bool(cancellation(db,run)),'state':run.state}
    db.commit();return result
