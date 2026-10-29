"""Private image cache/OCR queue. Caption ingestion is independent of this work."""
import base64
import hashlib
import io
import re
import secrets
import time
from fastapi import APIRouter,Depends,HTTPException,Response
from pydantic import BaseModel,ConfigDict,Field
from sqlalchemy import select,func,cast,String
from .models import PostImage,Observation,Publisher,EventCandidate,Control
from .db import database
from .config import settings
from .security import require,digest,insert_for,audit
from .worker_security import cleanup_worker
from .acquisition.scrapingant import media_reference
from .acquisition.poster import MAX_PREVIEW_BYTES,MAX_TEXT_BYTES

staff_router=APIRouter(prefix='/api')
worker_router=APIRouter(prefix='/media',dependencies=[Depends(cleanup_worker)])
MAX_ASSETS=15000


def permitted(p):
    return bool(p and p.approval=='approved' and p.eligibility=='available' and p.permission_basis
        and (p.collection_approved or (p.permission_expires and p.permission_expires>time.time())))


def system_lock(db):
    db.execute(insert_for(db,Control).values(id=1,emergency_stop=False).on_conflict_do_nothing(index_elements=['id']))
    return db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()


def enqueue(db,observation):
    if observation.retention_until<=time.time():return
    count=db.query(PostImage).count()
    for position,url in enumerate(observation.media[:3]):
        valid=bool(media_reference(url))
        url=url if isinstance(url,str) else ''
        hashed=hashlib.sha256(url.encode()).hexdigest()
        if db.query(PostImage).filter_by(observation_id=observation.id,source_hash=hashed).first():continue
        if count>=MAX_ASSETS:raise HTTPException(503,'Private image storage is full; existing evidence retained')
        db.add(PostImage(observation_id=observation.id,source_url=url,source_hash=hashed,position=position,state='queued' if valid else 'failed',error=None if valid else 'image_denied'));count+=1
    db.flush()


def metadata(db,observation):
    return [{'id':p.id,'state':p.state,'url':'/api/post-images/'+p.id if p.preview else None,
        'width':p.width,'height':p.height,'ocr_text':p.ocr_text,'ocr_status':p.ocr_status,
        'error':p.error} for p in db.query(PostImage).filter_by(observation_id=observation.id).order_by(PostImage.position)]


@staff_router.get('/observations/{identity}/images')
def observation_images(identity:str,current=Depends(require('read')),db=Depends(database)):
    observation=db.get(Observation,identity)
    if not observation or observation.retention_until<=time.time():raise HTTPException(404,'Post no longer available')
    return {'images':metadata(db,observation),'has_images':bool(observation.media)}


@staff_router.get('/post-images/{identity}')
def image(identity:str,current=Depends(require('read')),db=Depends(database)):
    asset=db.get(PostImage,identity);observation=db.get(Observation,asset.observation_id) if asset else None
    if not asset or not asset.preview or not observation or observation.retention_until<=time.time():
        raise HTTPException(404,'Image no longer available')
    return Response(bytes(asset.preview),media_type='image/jpeg',headers={'Content-Disposition':'inline; filename="post-image.jpg"','X-Content-Type-Options':'nosniff','Cache-Control':'no-store'})


class Lease(BaseModel):
    model_config=ConfigDict(extra='forbid')
    owner:str=Field(min_length=43,max_length=43)


@worker_router.post('/lease')
def lease(payload:Lease,db=Depends(database)):
    control=system_lock(db)
    if not settings().l4_enabled or not settings().media_enabled or control.emergency_stop:
        db.commit();return {'image':None}
    # Backfill existing collected posts as well as newly staged observations.
    for observation in db.query(Observation).filter(Observation.retention_until>time.time(),
        cast(Observation.media,String)!='[]',~select(PostImage.id).where(PostImage.observation_id==Observation.id).exists()).order_by(Observation.observed.desc()).limit(20):
        if observation.media and permitted(db.get(Publisher,observation.publisher_id)):enqueue(db,observation)
    owned=db.query(PostImage).filter_by(state='running',owner_digest=digest(payload.owner)).first()
    candidates=[owned] if owned else db.query(PostImage).filter(PostImage.state=='queued',PostImage.next_due<=time.time()).order_by(PostImage.created,PostImage.position).limit(20).all()
    for asset in candidates:
        observation=db.get(Observation,asset.observation_id)
        if not observation or observation.retention_until<=time.time() or not permitted(db.get(Publisher,observation.publisher_id)):
            continue
        asset.state='running';asset.owner_digest=digest(payload.owner);asset.lease_until=time.time()+90
        if not owned:asset.attempts+=1
        asset.updated=time.time();db.commit()
        return {'image':{'id':asset.id,'url':asset.source_url}}
    db.commit();return {'image':None}


class Completion(BaseModel):
    model_config=ConfigDict(extra='forbid',allow_inf_nan=False)
    preview:str|None=Field(None,max_length=54000)
    width:int|None=Field(None,ge=1,le=1600)
    height:int|None=Field(None,ge=1,le=1600)
    image_hash:str|None=Field(None,pattern=r'^[a-f0-9]{64}$')
    ocr_text:str=Field('',max_length=3500)
    ocr_confidence:float=Field(0,ge=0,le=1)
    ocr_status:str=Field('pending',pattern=r'^(pending|ready|no_text|unavailable|timeout)$')
    error:str|None=Field(None,pattern=r'^image_(denied|expired|network|invalid|timeout|limit)$')


def candidate_key(fields):
    from .extraction import event_key,normalized
    return event_key(fields) or (normalized(fields.get('title') or ''),fields.get('start_time') or fields.get('event_date'),normalized(fields.get('venue_name') or ''))


def append_candidates(db,asset,observation,publisher):
    if not asset.ocr_text or asset.ocr_status!='ready':return 0
    from .extraction import extract,filtered_reason,event_key
    existing=db.query(EventCandidate).filter_by(observation_id=observation.id).all()
    seen={candidate_key(c.fields) for c in existing};ordinal=max((c.ordinal for c in existing),default=-1)+1;added=0
    # Keep poster lines in a coherent block; separate paragraphs on a poster are
    # not automatically separate events. Caption evidence stays unchanged.
    text='\n'.join(line.strip() for line in asset.ocr_text.splitlines() if line.strip())
    # A decorative giveaway image must not override the full caption's context.
    if filtered_reason(observation.caption)=='giveaway':return 0
    known={event_key(c.fields) for c in db.query(EventCandidate).join(Observation,Observation.id==EventCandidate.observation_id)
        .filter(Observation.publisher_id==publisher.id,EventCandidate.status.notin_(['rejected','duplicate']))
        .order_by(EventCandidate.created.desc()).limit(1000) if event_key(c.fields)}
    for item in extract(text,observation.published_at,publisher):
        fields=item['fields'];key=candidate_key(fields)
        if key in seen or (event_key(fields) and event_key(fields) in known):continue
        fields['source_url']=observation.source_url
        fields['evidence']={**fields.get('evidence',{}),'method':'local_poster_ocr_v1','post_image_id':asset.id,'ocr_confidence':asset.ocr_confidence}
        item['missing']=sorted(set(item['missing']+['poster_text_review']))
        item['status']='needs_review';item['confidence']=min(.75,item['confidence']*asset.ocr_confidence)
        db.add(EventCandidate(observation_id=observation.id,ordinal=ordinal,**item));ordinal+=1;added+=1;seen.add(key)
    return added


def complete(db,identity,owner,payload):
    # Invoked inside the delivery receipt transaction and its global lock.
    asset=db.execute(select(PostImage).where(PostImage.id==identity).with_for_update()).scalar_one_or_none()
    if not asset or not secrets.compare_digest(asset.owner_digest or '',digest(owner)):
        raise HTTPException(409,'Original image owner required; buffered evidence retained')
    observation=db.get(Observation,asset.observation_id)
    if not observation or observation.retention_until<=time.time() or not permitted(p:=db.get(Publisher,observation.publisher_id)):
        raise HTTPException(409,'Post access changed; buffered evidence retained')
    if db.get(Control,1).emergency_stop:raise HTTPException(409,'Image processing paused; evidence retained')
    if asset.state=='ready':return {'ready':True,'replayed':True}
    if asset.state!='running':raise HTTPException(409,'Image work is no longer active')
    if payload.error:
        asset.error=payload.error;asset.state='queued' if payload.error in ('image_network','image_timeout') and asset.attempts<3 else 'failed'
        asset.next_due=time.time()+300*2**min(asset.attempts,3);asset.updated=time.time();asset.ocr_status='unavailable'
        return {'ready':False,'state':asset.state}
    try:
        from PIL import Image
        raw=base64.b64decode(payload.preview or '',validate=True)
        if not 0<len(raw)<=MAX_PREVIEW_BYTES or hashlib.sha256(raw).hexdigest()!=payload.image_hash:raise ValueError()
        with Image.open(io.BytesIO(raw)) as preview:
            if preview.format!='JPEG' or preview.size!=(payload.width,payload.height) or preview.width*preview.height>2560000:raise ValueError()
            preview.verify()
        if len(payload.ocr_text.encode())>MAX_TEXT_BYTES:raise ValueError()
    except Exception:raise HTTPException(422,'Invalid sanitized preview') from None
    asset.preview=raw;asset.width=payload.width;asset.height=payload.height;asset.image_hash=payload.image_hash
    asset.ocr_text=payload.ocr_text;asset.ocr_status=payload.ocr_status;asset.ocr_confidence=payload.ocr_confidence
    asset.state='ready';asset.error=None;asset.updated=time.time()
    added=append_candidates(db,asset,observation,p)
    audit(db,'L4_WORKER','post_image.processed',asset.id,details={'observations':added})
    db.flush();return {'ready':True,'new_candidates':added,'public_event_writes':0}
