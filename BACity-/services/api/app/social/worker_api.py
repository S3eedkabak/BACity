"""Machine-only staging gateway, on a private container network; no staff routes."""
import time
import secrets
from typing import Literal
from fastapi import FastAPI, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from app.core.http import RequestMiddleware
from .config import settings
from .db import database
from .models import Publisher, CollectionJob, Observation
from .security import digest, audit, budget
from .workflows import schedule, available, stage, stopped

app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
app.add_middleware(RequestMiddleware,max_body=65536)


from .worker_security import worker,Content

class Completion(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    lease: str=Field(min_length=43,max_length=43)
    outcome: Literal['success','empty','partial','unauthorized','blocked','rate_limited','failed']
    error: Literal['none','login_required','access_denied','robots_denied','rate_limit','timeout','network_error','unsupported','permission_required','invalid_content','response_limit','worker_timeout','resource_limit','provider_not_configured','provider_configuration','provider_auth','provider_denied','provider_transient','usage_unverified','budget_exhausted','provider_request_in_flight','provider_job_request_limit','provider_request_already_reserved','provider_cost_exceeded_reservation','challenge','unavailable_content']='none'
    observations: list[Content]=Field(default_factory=list,max_length=5)
    provider_metrics: dict[str,int]=Field(default_factory=dict,max_length=10)
    retry_after: int=Field(0,ge=0,le=604800)
    bytes_received: int=Field(0,ge=0,le=20000000)
    requests: int=Field(0,ge=0,le=12)
    elapsed_ms: int=Field(0,ge=0,le=60000)


@app.post('/lease',dependencies=[Depends(worker)])
def lease(db=Depends(database)):
    schedule(db)
    # A single global in-flight browser/HTTP job. Database lock serializes gateways.
    from .models import Control
    from .security import insert_for
    db.execute(insert_for(db,Control).values(id=1,emergency_stop=False).on_conflict_do_nothing(index_elements=['id']))
    db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()
    if db.query(CollectionJob).filter_by(state='running').count():
        db.commit(); return {'job':None}
    for job in db.execute(select(CollectionJob).join(Publisher,Publisher.id==CollectionJob.publisher_id).where(CollectionJob.state=='queued',Publisher.method!='apify').order_by(CollectionJob.created)
                          .with_for_update(skip_locked=True).limit(10)).scalars():
        publisher=db.execute(select(Publisher).where(Publisher.id==job.publisher_id).with_for_update()).scalar_one()
        from .provider_config import provider_settings
        provider=provider_settings()
        if not available(publisher) or (publisher.method=='scrapingant' and (not provider.enabled or not provider.configured)):
            job.state,job.finished,job.error='cancelled',time.time(),'provider_disabled' if publisher.method=='scrapingant' else 'cancelled'
            continue
        raw=secrets.token_urlsafe(32)
        job.state,job.started,job.lease_until,job.lease_digest='running',time.time(),time.time()+90,digest(raw)
        job.attempts+=1; publisher.last_attempt=time.time()
        audit(db,'L4_WORKER','collection.started',job.id)
        db.commit()
        return {'job':{'id':job.id,'publisher_id':publisher.id,'platform':publisher.platform,
                       'url':publisher.url,'method':publisher.method,'checkpoint':publisher.checkpoint,
                       'permission_expires':publisher.permission_expires,'lease':raw}}
    db.commit(); return {'job':None}


@app.get('/jobs/{job_id}/active',dependencies=[Depends(worker)])
def active(job_id:str,x_social_lease:str=Header(''),db=Depends(database)):
    job=db.get(CollectionJob,job_id)
    publisher=db.get(Publisher,job.publisher_id) if job else None
    if not job or job.state!='running' or job.lease_until<=time.time() or not secrets.compare_digest(job.lease_digest or '',digest(x_social_lease)):
        raise HTTPException(409,'Collection job is no longer active')
    return {'active':bool(publisher and available(publisher))}


@app.post('/jobs/{job_id}/complete',dependencies=[Depends(worker)])
def complete(job_id:str,payload:Completion,db=Depends(database)):
    job=db.execute(select(CollectionJob).where(CollectionJob.id==job_id).with_for_update()).scalar_one_or_none()
    if not job:
        raise HTTPException(404,'Job not found')
    if not secrets.compare_digest(job.lease_digest or '',digest(payload.lease)):
        raise HTTPException(403,'Lease verification failed')
    if job.state in ('success','empty','partial','unauthorized','blocked','rate_limited','failed'):
        return {'ok':True,'replayed':True}
    publisher=db.execute(select(Publisher).where(Publisher.id==job.publisher_id).with_for_update()).scalar_one()
    if job.state!='running' or job.lease_until<=time.time() or not available(publisher):
        raise HTTPException(409,'Collection was cancelled, expired or suspended')
    if payload.observations and payload.outcome not in ('success','partial'):
        raise HTTPException(422,'Restricted or failed jobs cannot submit content')
    if payload.outcome=='success' and not payload.observations:
        raise HTTPException(422,'A successful collection requires actual content')
    added=0;new_posts=0;new_reels=0
    for content in payload.observations:
        observation,created=stage(db,publisher,content.model_dump(),'L4_WORKER',job=job)
        added+=int(created)
        if created:
            new_reels+=int("/reel/" in content.source_url);new_posts+=int("/p/" in content.source_url)
        publisher.checkpoint=content.external_id
    now=time.time()
    job.state,job.finished,job.error=payload.outcome,now,payload.error if payload.error!='none' else None
    metrics={'bytes_received':payload.bytes_received,'elapsed_ms':payload.elapsed_ms,'requests':payload.requests,'new_observations':added}
    if publisher.method=='scrapingant':
        allowed={'posts_discovered','reels_discovered','captions_available','dates_available','media_available','credits_accounted','estimated_requests'}
        metrics.update({k:min(10000000,max(0,v)) for k,v in payload.provider_metrics.items() if k in allowed})
        from .models import EventCandidate
        metrics.update({'new_posts':new_posts,'new_reels':new_reels,'new_candidates':db.query(EventCandidate).join(Observation,EventCandidate.observation_id==Observation.id).filter(Observation.job_id==job.id).count()})
    job.metrics=metrics;job.buffered=False
    if payload.outcome in ('success','empty','partial'):
        publisher.last_success=now; publisher.failures=0; publisher.last_error=None
        from .provider_config import provider_settings
        publisher.next_due=now+max(publisher.interval_seconds,provider_settings().interval if publisher.method=='scrapingant' else 0)
    else:
        publisher.failures+=1; publisher.last_error=payload.error
        publisher.next_due=now+max(payload.retry_after,min(86400,300*2**min(publisher.failures,8)))
        if publisher.method=='scrapingant':
            from .provider_config import provider_settings
            publisher.next_due=max(publisher.next_due,(publisher.last_attempt or now)+provider_settings().interval)
        if payload.error=='unsupported':
            publisher.eligibility='unsupported'; publisher.enabled=False
        elif payload.outcome in ('unauthorized','blocked'):
            publisher.eligibility='blocked'; publisher.enabled=False
        elif payload.outcome=='rate_limited':
            # Require an explicit owner access review after provider restrictions.
            publisher.eligibility='rate_limited'; publisher.enabled=False
    audit(db,'L4_WORKER','collection.finished',job.id,details={'outcome':job.state,'observations':added})
    db.commit(); return {'ok':True,'new_observations':added,'public_event_writes':0}

class QuotaReservation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    lease: str=Field(min_length=43,max_length=43)
    request_id: str=Field(pattern=r'^[0-9a-f-]{36}$')
    kind: Literal['usage','acquire']
    target: str=Field('',max_length=1024)

class UsageSnapshot(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    start: float
    end: float
    total: int=Field(ge=0,le=1000000000,strict=True)
    remaining: int=Field(ge=0,le=1000000000,strict=True)

class QuotaSettlement(BaseModel):
    model_config=ConfigDict(extra='forbid')
    lease: str=Field(min_length=43,max_length=43)
    request_id: str=Field(pattern=r'^[0-9a-f-]{36}$')
    cost: int|None=Field(None,ge=0,le=10000000,strict=True)
    snapshot: UsageSnapshot|None=None
    error: Literal['provider_not_configured','provider_configuration','response_limit','timeout','rate_limit','provider_auth','provider_denied','provider_transient','invalid_content','network_error','usage_unverified']|None=None


def provider_job(db,job_id,lease,*,settlement=False):
    from .provider_config import provider_settings
    if not provider_settings().enabled:
        raise HTTPException(409,'provider_disabled')
    job=db.get(CollectionJob,job_id)
    publisher=db.get(Publisher,job.publisher_id) if job else None
    if (not job or not secrets.compare_digest(job.lease_digest or '',digest(lease)) or
        not publisher or publisher.method!='scrapingant' or publisher.platform!='instagram' or publisher.target_type!='profile'):
        raise HTTPException(403,'Provider lease required')
    if not settlement and (job.state!='running' or job.lease_until<=time.time() or not available(publisher)):
        raise HTTPException(409,'Provider collection is no longer active')
    return job,publisher


@app.get('/jobs/{job_id}/provider/status',dependencies=[Depends(worker)])
def provider_status(job_id:str,x_social_lease:str=Header(''),db=Depends(database)):
    provider_job(db,job_id,x_social_lease)
    from .provider_budget import status
    return status(db)


@app.post('/jobs/{job_id}/provider/reserve',dependencies=[Depends(worker)])
def provider_reserve(job_id:str,payload:QuotaReservation,db=Depends(database)):
    job,publisher=provider_job(db,job_id,payload.lease)
    from .acquisition.urls import normalize_target
    if payload.kind=='acquire':
        try:target=normalize_target(payload.target)
        except ValueError:raise HTTPException(422,'Invalid provider target') from None
        if target.platform!='instagram' or (target.target_type=='profile' and target.url!=publisher.url):
            raise HTTPException(422,'Only this approved Instagram profile and direct posts are supported')
    elif payload.target:
        raise HTTPException(422,'Usage status has no target URL')
    from .provider_budget import reserve
    return reserve(db,job,payload.request_id,payload.kind,payload.target)


@app.post('/jobs/{job_id}/provider/settle',dependencies=[Depends(worker)])
def provider_settle(job_id:str,payload:QuotaSettlement,db=Depends(database)):
    job,_=provider_job(db,job_id,payload.lease,settlement=True)
    from .provider_budget import settle
    return settle(db,job,payload.request_id,payload.cost,payload.snapshot.model_dump() if payload.snapshot else None,payload.error)


# The same private machine app owns provider batches and per-publisher jobs.
from .apify_jobs import router as apify_router
app.include_router(apify_router)

from .delivery import router as delivery_router
app.include_router(delivery_router)
