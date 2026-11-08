import time
from .acquisition.policy import MAX_POSTS, DAILY_SECONDS
import secrets
from typing import Literal
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field, EmailStr, model_validator
from sqlalchemy import select, func, update
from .db import database
from .config import settings
from .security import require, authenticate, audit, budget, digest
from .models import (Staff, Credential, Invitation, StaffSession, Publisher, CollectionJob,
                     Observation, EventCandidate, CandidateReview, AuditEvent, Control)
from .acquisition.urls import normalize_target
from .extraction import filtered_reason, content_hash
from .workflows import available, stage, qualify, stopped

router = APIRouter(prefix='/api')

class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)

class PublisherInput(Input):
    posts_per_profile: int=Field(MAX_POSTS,ge=1,le=MAX_POSTS)
    url: str = Field(max_length=1024)
    name: str = Field(min_length=2, max_length=160)
    publisher_type: Literal['venue','organizer','promoter','artist','cultural_institution','community','other'] = 'other'
    relevance: str = Field(min_length=10, max_length=500)
    venue_name: str | None = Field(None, max_length=200)
    address: str | None = Field(None, max_length=300)
    latitude: float | None = Field(None, ge=48, le=48.35)
    longitude: float | None = Field(None, ge=16.9, le=17.35)
    priority: int = Field(50, ge=0, le=100)
    interval_seconds: int = Field(86400, ge=3600, le=604800)

class Decision(Input):
    decision: Literal['approved','rejected','suspended']
    note: str = Field(min_length=10, max_length=1000)

class StartApproval(Input):
    confirmed: Literal[True]
    reviewed_updated: float = Field(gt=0)

class Monitoring(Input):
    enabled: bool
    priority: int = Field(50, ge=0, le=100)
    interval_seconds: int = Field(86400, ge=3600, le=604800)

class Access(Input):
    eligibility: Literal['available','authorization_required','unsupported','blocked']
    method: Literal['submission','http','browser','scrapingant','apify']
    permission_basis: str = Field(min_length=10, max_length=1000)
    permission_expires: float = Field(gt=0)

class Evidence(Input):
    source_url: str = Field(max_length=1024)
    external_id: str = Field(min_length=1, max_length=200)
    caption: str = Field(min_length=5, max_length=20000)
    published_at: str | None = Field(None, max_length=64)
    permission_attestation: str = Field(min_length=20, max_length=1000)

class StaffInput(Input):
    email: EmailStr
    name: str = Field(min_length=2, max_length=120)
    role: Literal['OWNER','SOCIAL_ADMIN','SOCIAL_EDITOR','SOCIAL_REVIEWER','SOCIAL_VIEWER']

class StaffChange(Input):
    active: bool
    role: Literal['OWNER','SOCIAL_ADMIN','SOCIAL_EDITOR','SOCIAL_REVIEWER','SOCIAL_VIEWER']

class CandidateEdit(Input):
    title: str = Field(min_length=3, max_length=200)
    start_time: datetime
    venue_name: str = Field(min_length=2, max_length=200)
    address: str = Field(min_length=3, max_length=300)
    latitude: float = Field(ge=48, le=48.35)
    longitude: float = Field(ge=16.9, le=17.35)
    note: str = Field(min_length=10, max_length=1000)

class Review(Input):
    decision: Literal['approved','rejected']
    note: str = Field(min_length=10, max_length=1000)

class Emergency(Input):
    stopped: bool
    note: str = Field(min_length=10, max_length=1000)


def row(db, model, identity, lock=False):
    stmt = select(model).where(model.id == identity)
    if lock:
        stmt = stmt.with_for_update()
    value = db.execute(stmt).scalar_one_or_none()
    if not value:
        raise HTTPException(404, 'Record not found')
    return value


def public_publisher(value):
    from .apify_config import provider_preference
    return {**{c.name:getattr(value,c.name) for c in Publisher.__table__.columns},'default_provider':provider_preference()}


def public_candidate(value, observation):
    return {'id':value.id,'fields':value.fields,'missing':value.missing,'confidence':value.confidence,
            'status':value.status,'event_id':value.event_id,'observation_id':value.observation_id,
            'source_url':observation.source_url,'caption':observation.caption,'method':observation.method,
            'publisher_id':observation.publisher_id,'published_at':observation.published_at,
            'provenance':observation.provenance,'media':observation.media, 'reviewed_by':value.reviewed_by}


@router.get('/dashboard')
def dashboard(current=Depends(require('read')), db=Depends(database)):
    def count(model, *criteria):
        return db.query(model).filter(*criteria).count()
    recent = db.query(CollectionJob).order_by(CollectionJob.created.desc()).limit(10).all()
    return {'publishers':count(Publisher), 'approved':count(Publisher, Publisher.approval=='approved'),
        'pending':count(Publisher,Publisher.approval=='pending'), 'enabled':count(Publisher,Publisher.enabled.is_(True)),
        'attention':count(Publisher,Publisher.last_error.is_not(None)), 'observations':count(Observation),
        'candidates':count(EventCandidate,EventCandidate.status.notin_(['rejected','duplicate'])),'awaiting_review':count(EventCandidate, EventCandidate.status.in_(['needs_review','qualified'])),
        'published':count(EventCandidate,EventCandidate.status=='published'),
        'emergency_stop':stopped(db), 'collection_enabled':settings().l4_collection_enabled,
        'publication_enabled':settings().l4_publication_enabled,
        'recent_jobs':[job_dict(x,db) for x in recent]}


@router.get('/publishers')
def publishers(q: str=Query('', max_length=100), platform: str=Query('', max_length=20), publisher_type: str=Query('',max_length=32),
               limit: int=Query(50,ge=1,le=100), offset: int=Query(0,ge=0,le=10000), current=Depends(require('read')), db=Depends(database)):
    query = db.query(Publisher)
    if q:
        query=query.filter(Publisher.name.ilike('%'+q.replace('%','\\%').replace('_','\\_')+'%', escape='\\'))
    if platform:
        query=query.filter_by(platform=platform)
    if publisher_type:
        query=query.filter_by(publisher_type=publisher_type)
    return {'total':query.count(),'items':[public_publisher(x) for x in query.order_by(Publisher.priority.desc(),Publisher.id).offset(offset).limit(limit)]}


@router.post('/publishers/preview')
def preview(payload: dict, current=Depends(require('propose'))):
    if set(payload) != {'url'} or not isinstance(payload['url'],str):
        raise HTTPException(422,'Only a source URL is accepted')
    try:
        target=normalize_target(payload['url'])
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    return {**vars(target),'metadata_status':'URL-derived only; account ownership and access are unverified'}


@router.post('/publishers', status_code=201)
def create_publisher(payload: PublisherInput, request: Request, current=Depends(require('propose')), db=Depends(database)):
    budget(db,'publisher-create',current.staff.id,20,3600)
    try:
        target=normalize_target(payload.url)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    if db.query(Publisher).count() >= settings().max_publishers:
        raise HTTPException(409,'Publisher limit reached')
    if db.query(Publisher).filter_by(url=target.url).first():
        raise HTTPException(409,'This publisher or post is already registered')
    values=payload.model_dump(exclude={'url'})
    publisher=Publisher(**values, **vars(target), created_by=current.staff.id)
    db.add(publisher); db.flush()
    audit(db,current.staff.id,'publisher.created',publisher.id,request=request)
    db.commit()
    return public_publisher(publisher)


@router.get('/publishers/{publisher_id}')
def publisher_detail(publisher_id: str,current=Depends(require('read')),db=Depends(database)):
    publisher=row(db,Publisher,publisher_id)
    return {'publisher':public_publisher(publisher),
        'jobs':[job_dict(j,db) for j in db.query(CollectionJob).filter_by(publisher_id=publisher_id).order_by(CollectionJob.created.desc()).limit(30)],
        'observations':[{'id':o.id,'source_url':o.source_url,'observed':o.observed,'method':o.method,'caption':o.caption,'content_hash':o.content_hash,'has_images':bool(o.media),'filter_reason':filtered_reason(o.caption)}
                       for o in db.query(Observation).filter_by(publisher_id=publisher_id).order_by(Observation.observed.desc()).limit(20)]}


@router.patch('/publishers/{publisher_id}')
def edit_publisher(publisher_id: str,payload: PublisherInput,request: Request,current=Depends(require('propose')),db=Depends(database)):
    publisher=row(db,Publisher,publisher_id,True)
    try:
        target=normalize_target(payload.url)
    except ValueError as exc:
        raise HTTPException(422,str(exc)) from None
    if target.url != publisher.url:
        raise HTTPException(409,'Register a different source as a new proposal')
    for key,value in payload.model_dump(exclude={'url'}).items():
        setattr(publisher,key,value)
    publisher.approval, publisher.enabled, publisher.updated = 'pending',False,time.time()
    publisher.collection_approved=False
    db.query(CollectionJob).filter(CollectionJob.publisher_id==publisher.id, CollectionJob.state.in_(['queued','running'])).update({'state':'cancelled','finished':time.time(),'error':'cancelled'})
    audit(db,current.staff.id,'publisher.edited',publisher.id,request=request); db.commit()
    return public_publisher(publisher)


@router.post('/publishers/{publisher_id}/decision')
def publisher_decision(publisher_id: str,payload: Decision,request: Request,current=Depends(require('approve')),db=Depends(database)):
    budget(db,'publisher-approval',current.staff.id,30,3600)
    publisher=row(db,Publisher,publisher_id,True)
    publisher.approval,publisher.approved_by,publisher.updated=payload.decision,current.staff.id,time.time()
    publisher.enabled=False
    publisher.collection_approved=False
    db.query(CollectionJob).filter(CollectionJob.publisher_id==publisher.id,CollectionJob.state.in_(['queued','running'])).update({'state':'cancelled','finished':time.time(),'error':'cancelled'})
    audit(db,current.staff.id,'publisher.'+payload.decision,publisher.id,request=request,details={'note':payload.note})
    db.commit(); return public_publisher(publisher)


@router.post('/publishers/{publisher_id}/approve-and-start')
def approve_and_start(publisher_id: str,payload: StartApproval,request: Request,
                      current=Depends(require('approve')),db=Depends(database)):
    """One explicit human review approves the source and daily collection.

    This records the staff decision, not a claim of external platform permission.
    Provider restrictions, spending policy and emergency stops still apply.
    """
    from .security import insert_for
    from .apify_config import provider_preference,apify_settings
    from .provider_config import provider_settings
    budget(db,'publisher-approval',current.staff.id,30,3600)
    db.execute(insert_for(db,Control).values(id=1,emergency_stop=False).on_conflict_do_nothing(index_elements=['id']))
    db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()
    p=row(db,Publisher,publisher_id,True)
    if p.updated!=payload.reviewed_updated:
        raise HTTPException(409,'This publisher changed. Reopen the review before approving.')
    if stopped(db) or not settings().l4_enabled or not settings().l4_collection_enabled:
        raise HTTPException(409,'Automatic checks are paused in system settings. Your publisher is saved.')
    if p.eligibility in ('blocked','unsupported','rate_limited'):
        raise HTTPException(409,'This source has an access restriction. An owner must review it in advanced settings.')
    if p.platform=='instagram' and p.target_type=='profile':
        method=provider_preference();provider=apify_settings() if method=='apify' else provider_settings()
        if not provider.enabled or not provider.configured:
            raise HTTPException(409,'The collection service is unavailable. Ask the owner to check Settings.')
        count=db.query(Publisher).filter(Publisher.platform=='instagram',Publisher.target_type=='profile',
            Publisher.method.in_(('apify','scrapingant')),Publisher.enabled.is_(True),Publisher.id!=p.id).count()
        if count>=min(20,provider.max_active_profiles):
            raise HTTPException(409,'The active publisher limit has been reached. Pause another publisher first.')
    elif p.platform=='event_url':method='http'
    else:
        raise HTTPException(422,'Automatic checks support Instagram profile links and supported event pages. Edit the publisher link before starting.')
    now=time.time()
    p.approval,p.approved_by,p.enabled='approved',current.staff.id,True
    p.collection_approved=True;p.eligibility='available';p.method=method
    p.permission_basis='Staff-reviewed approval for public-source BACity event discovery'
    p.permission_expires=None
    p.interval_seconds=DAILY_SECONDS;p.posts_per_profile=MAX_POSTS;p.priority=50
    p.next_due=max(now,(p.last_attempt or 0)+DAILY_SECONDS,p.next_due if p.last_attempt else 0)
    p.updated=now
    audit(db,current.staff.id,'publisher.approved_and_started',p.id,request=request,
          details={'method':method,'enabled':True,'note':'Reviewed source details; approved daily checks, at most two posts'})
    db.commit();return public_publisher(p)


@router.post('/publishers/{publisher_id}/access')
def publisher_access(publisher_id: str,payload: Access,request: Request,current=Depends(require('access',recent=True)),db=Depends(database)):
    publisher=row(db,Publisher,publisher_id,True)
    if payload.permission_expires <= time.time() or payload.permission_expires > time.time()+90*86400:
        raise HTTPException(422,'Collection permission must expire within 90 days')
    if payload.eligibility=='available' and payload.method=='submission':
        raise HTTPException(422,'Submission is an evidence fallback, not automatic collection')
    if payload.method in ('scrapingant','apify') and (publisher.platform!='instagram' or publisher.target_type!='profile'):
        raise HTTPException(422,'Provider collection requires an Instagram profile')
    publisher.eligibility,publisher.method=payload.eligibility,payload.method
    publisher.permission_basis,publisher.permission_expires=payload.permission_basis,payload.permission_expires
    publisher.collection_approved=False
    publisher.enabled=False; publisher.updated=time.time()
    audit(db,current.staff.id,'publisher.access_reviewed',publisher.id,request=request,details={'eligibility':payload.eligibility,'method':payload.method})
    db.commit(); return public_publisher(publisher)


@router.post('/publishers/{publisher_id}/monitoring')
def monitoring(publisher_id: str,payload: Monitoring,request: Request,current=Depends(require('approve')),db=Depends(database)):
    from .security import insert_for
    db.execute(insert_for(db,Control).values(id=1,emergency_stop=False).on_conflict_do_nothing(index_elements=['id']))
    db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()
    publisher=row(db,Publisher,publisher_id,True)
    if payload.enabled and (publisher.approval!='approved' or publisher.eligibility!='available'
                            or not (publisher.collection_approved or (publisher.permission_expires and publisher.permission_expires>time.time()))
                            or not publisher.permission_basis or stopped(db)):
        raise HTTPException(409,'Approval, current collection authorization and an active system are required')
    interval=max(DAILY_SECONDS,payload.interval_seconds)
    if publisher.method in ('scrapingant','apify'):
        from .provider_config import provider_settings
        from .apify_config import apify_settings
        provider=apify_settings() if publisher.method=='apify' else provider_settings()
        if payload.enabled:
            if not provider.enabled or not provider.configured:
                raise HTTPException(409,'Instagram provider is disabled or not configured')
            count=db.query(Publisher).filter(Publisher.platform=='instagram',Publisher.target_type=='profile',Publisher.method.in_(('scrapingant','apify')),Publisher.enabled.is_(True),Publisher.id!=publisher.id).count()
            if count>=min(20,provider.max_active_profiles):raise HTTPException(409,'Active Instagram profile limit reached')
            if not publisher.last_attempt:
                if publisher.method=='scrapingant':
                    import hashlib
                    slot=int(hashlib.sha256(publisher.id.encode()).hexdigest()[:8],16)%provider.interval
                    publisher.next_due=max(publisher.next_due,time.time()+slot)
                else:publisher.next_due=time.time()
        interval=max(payload.interval_seconds,provider.interval)
    publisher.enabled,publisher.priority,publisher.interval_seconds=payload.enabled,payload.priority,interval
    publisher.updated=time.time()
    if not payload.enabled:
        db.query(CollectionJob).filter(CollectionJob.publisher_id==publisher.id,CollectionJob.state.in_(['queued','running'])).update({'state':'cancelled','finished':time.time(),'error':'cancelled'})
    audit(db,current.staff.id,'publisher.monitoring_changed',publisher.id,request=request,details={'enabled':payload.enabled})
    db.commit(); return public_publisher(publisher)


@router.post('/publishers/{publisher_id}/retry')
def retry(publisher_id: str,request: Request,current=Depends(require('approve')),db=Depends(database)):
    budget(db,'collection-retry',current.staff.id,10,3600)
    publisher=row(db,Publisher,publisher_id,True)
    if not available(publisher) or stopped(db) or not settings().l4_collection_enabled:
        raise HTTPException(409,'Collection is unavailable; approval does not bypass access restrictions')
    if publisher.method in ('scrapingant','apify'):
        from .provider_config import provider_settings
        from .apify_config import apify_settings
        from .provider_budget import status
        from .apify_jobs import summary
        provider=apify_settings() if publisher.method=='apify' else provider_settings()
        health=summary(db) if publisher.method=='apify' else status(db)
        if not provider.enabled or not provider.configured or (publisher.last_attempt and time.time()-publisher.last_attempt<provider.interval):
            raise HTTPException(409,'Instagram daily interval or provider activation prevents this check')
        if health['suspension_reason'] not in (None,'usage_unverified','billing_unverified'):
            raise HTTPException(409,'Instagram collection is suspended by the spending policy')
        if publisher.last_attempt and publisher.next_due>time.time():raise HTTPException(409,'Publisher backoff has not elapsed')
        publisher.next_due=time.time()
    elif publisher.next_due>time.time():raise HTTPException(409,'Publisher backoff or interval has not elapsed')
    audit(db,current.staff.id,'publisher.retry_requested',publisher.id,request=request)
    db.commit(); return {'ok':True,'state':'due; scheduler will collect within its budget'}


@router.post('/publishers/{publisher_id}/evidence',status_code=201)
def submit_evidence(publisher_id: str,payload: Evidence,request: Request,current=Depends(require('propose')),db=Depends(database)):
    budget(db,'evidence-submit',current.staff.id,30,3600)
    publisher=row(db,Publisher,publisher_id,True)
    if publisher.approval!='approved' or stopped(db):
        raise HTTPException(409,'An approved, unsuspended publisher is required')
    observation,created=stage(db,publisher,payload.model_dump(),current.staff.id,request=request)
    db.commit(); return {'id':observation.id,'created':created,'method':'user_submission','public_event_writes':0}


@router.get('/candidates')
def candidates(limit: int=Query(50,ge=1,le=100),offset: int=Query(0,ge=0,le=10000),view: str=Query('all',pattern='^(all|active)$'),current=Depends(require('read')),db=Depends(database)):
    query=db.query(EventCandidate,Observation).join(Observation,Observation.id==EventCandidate.observation_id)
    if view=='active':query=query.filter(EventCandidate.status.in_(['needs_review','qualified','approved','publication_queued']))
    return {'total':query.count(),'items':[public_candidate(c,o) for c,o in query.order_by(EventCandidate.created.desc(),EventCandidate.id).offset(offset).limit(limit)]}


@router.patch('/candidates/{candidate_id}')
def edit_candidate(candidate_id: str,payload: CandidateEdit,request: Request,current=Depends(require('propose')),db=Depends(database)):
    candidate=row(db,EventCandidate,candidate_id,True)
    if candidate.status in ('published','publication_queued'):
        raise HTTPException(409,'Published or queued evidence cannot be edited')
    fields={**candidate.fields,**payload.model_dump(mode='json',exclude={'note'})}
    fields['evidence']={**fields.get('evidence',{}),'staff_edit':True,'staff_editor':current.staff.id}
    candidate.fields, candidate.missing, candidate.status=fields,qualify(fields),'needs_review'
    candidate.reviewed_by=candidate.reviewed_hash=None
    candidate.confidence=0.8 if not candidate.missing else min(candidate.confidence,0.7)
    audit(db,current.staff.id,'candidate.edited',candidate.id,request=request,details={'note':payload.note})
    db.commit(); return {'ok':True}


@router.post('/candidates/{candidate_id}/review')
def review(candidate_id: str,payload: Review,request: Request,current=Depends(require('review')),db=Depends(database)):
    candidate=row(db,EventCandidate,candidate_id,True)
    if candidate.status in ('published','publication_queued'):
        raise HTTPException(409,'Candidate already queued or published')
    observation=row(db,Observation,candidate.observation_id)
    publisher=row(db,Publisher,observation.publisher_id)
    if payload.decision=='approved' and (candidate.missing or qualify(candidate.fields) or publisher.approval!='approved'):
        raise HTTPException(409,'Resolve missing fields and publisher approval before approving')
    if payload.decision=='approved' and candidate.fields.get('evidence',{}).get('staff_editor')==current.staff.id:
        raise HTTPException(403,'A different reviewer must approve edited evidence')
    candidate.status,candidate.reviewed_by=payload.decision,current.staff.id
    candidate.reviewed_hash=content_hash(candidate.fields)
    db.add(CandidateReview(candidate_id=candidate.id,actor=current.staff.id,decision=payload.decision,
                           evidence_hash=candidate.reviewed_hash,note=payload.note))
    audit(db,current.staff.id,'candidate.'+payload.decision,candidate.id,request=request,details={'note':payload.note})
    db.commit(); return {'ok':True,'publication_enabled':settings().l4_publication_enabled}


@router.post('/candidates/{candidate_id}/publish')
def publish(candidate_id: str,request: Request,current=Depends(require('publish',recent=True)),db=Depends(database)):
    budget(db,'publication',current.staff.id,5,3600)
    candidate=row(db,EventCandidate,candidate_id,True)
    observation=row(db,Observation,candidate.observation_id)
    publisher=row(db,Publisher,observation.publisher_id,True)
    if not settings().l4_publication_enabled or stopped(db):
        raise HTTPException(409,'Publication is disabled; candidates remain private')
    reviewer=db.get(Staff,candidate.reviewed_by) if candidate.reviewed_by else None
    if (candidate.status!='approved' or not reviewer or not reviewer.active or reviewer.role not in ('OWNER','SOCIAL_ADMIN','SOCIAL_EDITOR','SOCIAL_REVIEWER') or candidate.reviewed_by==current.staff.id
        or candidate.reviewed_hash!=content_hash(candidate.fields) or candidate.missing or qualify(candidate.fields)
        or publisher.approval!='approved' or observation.retention_until <= time.time()):
        raise HTTPException(409,'A current independent review and complete evidence are required')
    candidate.status='publication_queued'
    candidate.publication_requested_by=current.staff.id
    audit(db,current.staff.id,'candidate.publication_requested',candidate.id,request=request); db.commit()
    return {'ok':True,'state':'publication_queued'}


def job_dict(job,db=None):
    p=db.get(Publisher,job.publisher_id) if db is not None else None
    return {'publisher_name':p.name if p else None,**{key:getattr(job,key) for key in ('id','publisher_id','state','created','started','finished','error','metrics')}}


@router.get('/health')
def collection_health(limit: int=Query(50,ge=1,le=100),current=Depends(require('read')),db=Depends(database)):
    jobs=db.query(CollectionJob).order_by(CollectionJob.created.desc()).limit(limit).all()
    platform_metrics=[]
    for platform in ('instagram','facebook','tiktok','event_url'):
        publishers=db.query(Publisher.id).filter(Publisher.platform==platform)
        job_query=db.query(CollectionJob).filter(CollectionJob.publisher_id.in_(publishers))
        observations=db.query(Observation.id).filter(Observation.publisher_id.in_(publishers))
        candidate_query=db.query(EventCandidate).filter(EventCandidate.observation_id.in_(observations),EventCandidate.status.notin_(['rejected','duplicate']))
        platform_metrics.append({'platform':platform,'publishers':publishers.count(),
            'collections':job_query.count(),'successful_collections':job_query.filter(CollectionJob.state.in_(['success','partial'])).count(),
            'restricted_collections':job_query.filter(CollectionJob.state.in_(['blocked','unauthorized','rate_limited'])).count(),
            'observations':observations.count(),'event_candidates':candidate_query.count(),
            'published_events':candidate_query.filter(EventCandidate.status=='published').count()})
    return {'jobs':[job_dict(j,db) for j in jobs], 'platforms':platform_metrics,
            'publication_mode':'review_gated' if settings().l4_publication_enabled else 'shadow'}



@router.get('/staff')
def staff_list(current=Depends(require('staff')),db=Depends(database)):
    return [{'id':s.id,'name':s.name,'email':s.email,'role':s.role,'active':s.active,
             'authenticators':db.query(Credential).filter_by(staff_id=s.id,revoked=False).count()}
            for s in db.query(Staff).order_by(Staff.created).limit(100)]


@router.post('/staff',status_code=201)
def invite_staff(payload: StaffInput,request: Request,current=Depends(require('staff',recent=True)),db=Depends(database)):
    budget(db,'staff-invitation',current.staff.id,10,3600)
    if db.query(Staff).count()>=50:
        raise HTTPException(409,'Staff limit reached')
    staff=Staff(email=str(payload.email).lower(),name=payload.name,role=payload.role)
    db.add(staff); db.flush()
    secret=secrets.token_urlsafe(32)
    db.add(Invitation(digest=digest(secret),staff_id=staff.id,created_by=current.staff.id,expires=time.time()+900))
    audit(db,current.staff.id,'staff.invited',staff.id,request=request,details={'role':payload.role}); db.commit()
    return {'id':staff.id,'invitation':secret,'expires_in_seconds':900}


def preserve_owner(db,staff,new_role=None,active=False):
    owners=db.execute(select(Staff).where(Staff.role=='OWNER',Staff.active.is_(True)).with_for_update()).scalars().all()
    if staff.role=='OWNER' and staff.active and (not active or new_role!='OWNER') and not any(o.id!=staff.id and db.query(Credential).filter_by(staff_id=o.id,revoked=False).count()>0 for o in owners):
        raise HTTPException(409,'Keep another active owner before offboarding or recovering this owner')


@router.patch('/staff/{staff_id}')
def change_staff(staff_id: str,payload: StaffChange,request: Request,current=Depends(require('staff',recent=True)),db=Depends(database)):
    staff=row(db,Staff,staff_id,True)
    preserve_owner(db,staff,payload.role,payload.active)
    staff.active,staff.role=payload.active,payload.role
    staff.version+=1
    db.query(StaffSession).filter_by(staff_id=staff_id).update({'revoked':True})
    db.query(Invitation).filter_by(staff_id=staff_id).update({'consumed':True})
    audit(db,current.staff.id,'staff.access_changed',staff.id,request=request,details={'active':payload.active,'role':payload.role})
    db.commit(); return {'ok':True}


@router.post('/staff/{staff_id}/recover')
def recover_staff(staff_id: str,request: Request,current=Depends(require('staff',recent=True)),db=Depends(database)):
    budget(db,'staff-recovery',current.staff.id,3,3600)
    staff=row(db,Staff,staff_id,True)
    preserve_owner(db,staff)
    if not staff.active:
        raise HTTPException(409,'Suspended staff cannot enroll')
    db.query(Credential).filter_by(staff_id=staff_id).update({'revoked':True})
    db.query(StaffSession).filter_by(staff_id=staff_id).update({'revoked':True})
    db.query(Invitation).filter_by(staff_id=staff_id).update({'consumed':True})
    staff.version+=1
    secret=secrets.token_urlsafe(32)
    db.add(Invitation(digest=digest(secret),staff_id=staff_id,created_by=current.staff.id,expires=time.time()+900))
    audit(db,current.staff.id,'staff.recovery',staff.id,request=request); db.commit()
    return {'invitation':secret,'expires_in_seconds':900}


@router.get('/audit')
def audit_list(limit: int=Query(50,ge=1,le=100),before: int=Query(2**31-1,ge=1),current=Depends(require('audit')),db=Depends(database)):
    return [{'sequence':a.sequence,'previous':a.previous,'digest':a.digest,**a.record} for a in
            db.query(AuditEvent).filter(AuditEvent.sequence<before).order_by(AuditEvent.sequence.desc()).limit(limit)]


@router.post('/emergency')
def emergency(payload: Emergency,request: Request,current=Depends(require('emergency',recent=True)),db=Depends(database)):
    value=db.get(Control,1)
    if not value:
        value=Control(id=1); db.add(value)
    value.emergency_stop=payload.stopped
    if payload.stopped:
        db.query(CollectionJob).filter(CollectionJob.state.in_(['queued','running'])).update({'state':'cancelled','finished':time.time(),'error':'cancelled'})
        db.query(Publisher).update({'enabled':False})
        db.query(EventCandidate).filter_by(status='publication_queued').update({'status':'approved'})
    audit(db,current.staff.id,'system.emergency_changed',request=request,details={'stopped':payload.stopped,'note':payload.note})
    db.commit(); return {'ok':True}


@router.get('/candidates/{candidate_id}/matches')
def matches(candidate_id: str,current=Depends(require('read')),db=Depends(database)):
    candidate=row(db,EventCandidate,candidate_id)
    observation=row(db,Observation,candidate.observation_id)
    publisher=row(db,Publisher,observation.publisher_id)
    if qualify(candidate.fields):
        return {'classification':'insufficient_evidence','matches':[]}
    from .publication import shadow_matches
    suggestions=shadow_matches(db,candidate,observation,publisher)
    return {'classification':'already_present' if suggestions else 'potentially_new','matches':suggestions,
            'scope':'bounded canonical identity comparison; not an exclusivity guarantee'}


@router.get('/instagram-collection')
def instagram_collection(current=Depends(require('read')),db=Depends(database)):
    from .provider_budget import status
    data=status(db)
    publishers=db.query(Publisher).filter_by(platform='instagram',target_type='profile').all()
    ids=[p.id for p in publishers]
    jobs=db.query(CollectionJob).filter(CollectionJob.publisher_id.in_(ids)).order_by(CollectionJob.created.desc()).limit(50).all()
    data.update({'collection_enabled':settings().l4_collection_enabled,'active_profiles':sum(p.enabled and p.method in ('scrapingant','apify') for p in publishers),
        'last_scheduled_run':max((j.created for j in jobs),default=None),
        'publishers':[public_publisher(p) for p in publishers], 'jobs':[job_dict(j,db) for j in jobs],
        'posts_discovered':sum(j.metrics.get('posts_discovered',0) for j in jobs),
        'reels_discovered':sum(j.metrics.get('reels_discovered',0) for j in jobs),
        'event_candidates':db.query(EventCandidate).join(Observation,EventCandidate.observation_id==Observation.id).filter(Observation.publisher_id.in_(ids),EventCandidate.status.notin_(['rejected','duplicate'])).count()})
    from .apify_jobs import summary
    from .apify_config import provider_preference
    from .models import ApifyRun
    data['apify']=summary(db)
    data['default_provider']=provider_preference()
    data['apify_runs']=[{k:getattr(r,k) for k in ('id','state','run_id','created','finished','cost','cost_kind','reservation','error','provider_status','offset','total')} for r in db.query(ApifyRun).order_by(ApifyRun.created.desc()).limit(30)]
    return data
