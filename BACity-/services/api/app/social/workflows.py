import time
from .acquisition.policy import MAX_POSTS, DAILY_SECONDS
from datetime import datetime, timezone
from sqlalchemy import select, update
from fastapi import HTTPException
from .models import Publisher, CollectionJob, Observation, EventCandidate, Control
from .security import digest, audit
from .config import settings
from .extraction import extract, content_hash, event_key
from .acquisition.urls import normalize_target


def stopped(db):
    row = db.get(Control, 1)
    return bool(row and row.emergency_stop)


def available(publisher, now=None):
    return (publisher.approval == 'approved' and publisher.enabled
            and publisher.eligibility == 'available' and publisher.permission_basis
            and (publisher.collection_approved or
                 (publisher.permission_expires and publisher.permission_expires > (now or time.time()))))


def schedule(db, *, now=None, limit=10,provider_filter=None):
    cfg = settings()
    if not cfg.l4_enabled or not cfg.l4_collection_enabled or stopped(db):
        return []
    now = now or time.time()
    from .security import insert_for
    db.execute(insert_for(db,Control).values(id=1,emergency_stop=False).on_conflict_do_nothing(index_elements=['id']))
    control=db.execute(select(Control).where(Control.id==1).with_for_update()).scalar_one()
    if control.emergency_stop:
        db.commit(); return []
    # Reclaim abandoned leases without blocking the website crawler worker.
    for job in db.execute(select(CollectionJob).where(CollectionJob.state == 'running', CollectionJob.lease_until < now,CollectionJob.apify_run_id.is_(None),CollectionJob.buffered.is_(False))
                          .with_for_update(skip_locked=True).limit(10)).scalars():
        publisher = db.get(Publisher, job.publisher_id)
        job.state, job.finished, job.error = 'failed', now, 'worker_timeout'
        publisher.failures += 1
        publisher.last_error = 'worker_timeout'
        publisher.next_due = now + min(86400, 300 * 2 ** min(publisher.failures, 8))
    queue=db.query(CollectionJob).join(Publisher,CollectionJob.publisher_id==Publisher.id).filter(CollectionJob.state.in_(['queued','running']))
    queue=queue.filter(Publisher.method=='apify' if provider_filter=='apify' else Publisher.method!='apify')
    if queue.count() >= (20 if provider_filter=='apify' else 10):
        db.commit(); return []
    if db.query(CollectionJob).count() >= cfg.max_jobs:
        db.commit(); return []
    rows = db.execute(select(Publisher).where(Publisher.enabled.is_(True), Publisher.approval == 'approved',
                      Publisher.eligibility == 'available', Publisher.next_due <= now,
                      Publisher.method=='apify' if provider_filter=='apify' else Publisher.method!='apify')
                      .order_by(Publisher.priority.desc(), Publisher.next_due, Publisher.id)
                      .with_for_update(skip_locked=True).limit(min(limit,20 if provider_filter=='apify' else 10))).scalars().all()
    from .provider_config import provider_settings
    provider=provider_settings()
    active_provider_ids={p.id for p in db.query(Publisher).filter_by(platform='instagram',target_type='profile',method='scrapingant',enabled=True).order_by(Publisher.priority.desc(),Publisher.id).limit(provider.max_active_profiles)}
    from .apify_config import apify_settings
    apify=apify_settings()
    apify_ids={p.id for p in db.query(Publisher).filter_by(platform='instagram',target_type='profile',method='apify',enabled=True).order_by(Publisher.priority.desc(),Publisher.id).limit(apify.max_active_profiles)}
    ids = []
    for publisher in rows:
        # A provider switch, manual retry or pause/resume cannot multiply the
        # daily allowance. Failed checks also keep the existing spending limit.
        if publisher.last_attempt and now-publisher.last_attempt<DAILY_SECONDS:
            continue
        if publisher.method=='scrapingant' and (not provider.enabled or not provider.configured or publisher.id not in active_provider_ids or (publisher.last_attempt and now-publisher.last_attempt<provider.interval)):
            continue
        if publisher.method=='apify' and (not apify.enabled or not apify.configured or publisher.id not in apify_ids or (publisher.last_attempt and now-publisher.last_attempt<apify.interval)):
            continue
        if not available(publisher, now) or publisher.method not in ('http', 'browser','scrapingant','apify'):
            continue
        if db.query(CollectionJob).filter(CollectionJob.publisher_id == publisher.id, CollectionJob.state.in_(['queued','running'])).first():
            continue
        key = digest(publisher.id + ':' + str(int(now // publisher.interval_seconds)))
        if db.query(CollectionJob).filter_by(dedup_key=key).first():
            continue
        job = CollectionJob(publisher_id=publisher.id, dedup_key=key)
        db.add(job); db.flush(); ids.append(job.id)
        publisher.next_due = now + max(DAILY_SECONDS,publisher.interval_seconds,provider.interval if publisher.method=='scrapingant' else apify.interval if publisher.method=='apify' else 0)
        audit(db, 'scheduler', 'collection.scheduled', job.id)
    db.commit()
    return ids


def stage(db, publisher, content, actor, *, job=None, request=None):
    cfg = settings()
    target = normalize_target(content['source_url'])
    if target.platform != publisher.platform or (publisher.target_type == 'post' and target.url != publisher.url):
        raise HTTPException(422, 'Observation source must match the approved target')
    if target.target_type != 'post':
        raise HTTPException(422, 'A direct post or event page is required as evidence')
    if target.external_id != content['external_id']:
        raise HTTPException(422, 'Post identifier does not match its source URL')
    if job and publisher.method in ('scrapingant','apify') and content.get('publisher_identifier')!=publisher.external_id:
        raise HTTPException(422,'Observation publisher must match the approved Instagram identity')
    caption = content['caption']
    if len(caption.encode()) > 30000:
        raise HTTPException(413, 'Caption exceeds the private staging limit')
    published = content.get('published_at')
    if published:
        try:
            dt = datetime.fromisoformat(published.replace('Z','+00:00'))
            if not dt.tzinfo or dt.timestamp() > time.time() + 300:
                raise ValueError()
        except (TypeError,ValueError):
            raise HTTPException(422, 'Publication timestamp must be an actual past timestamp with timezone') from None
    identity_url=f'https://www.instagram.com/p/{target.external_id}/' if job and publisher.method in ('scrapingant','apify') else target.url
    hashed = content_hash({'caption':caption, 'published_at':published, 'source_url':identity_url})
    previous = db.query(Observation).filter_by(publisher_id=publisher.id, external_id=target.external_id, content_hash=hashed).first()
    if not previous and job and publisher.method in ('apify','scrapingant'):
        # Match observations staged before provider-independent URL canonicalization.
        previous=db.query(Observation).filter_by(publisher_id=publisher.id,external_id=target.external_id,caption=caption,published_at=published).first()
    persistent=bool(job and publisher.platform=='instagram' and publisher.method in ('apify','scrapingant'))
    if persistent:
        from .models import InstagramItem
        item=db.get(InstagramItem,(publisher.id,target.external_id))
        if previous or (item and item.content_hash==hashed):
            if not item:db.add(InstagramItem(publisher_id=publisher.id,external_id=target.external_id,content_hash=hashed))
            else:item.last_seen=time.time()
            return previous,False
    if previous:
        return previous,False
    if job and db.query(Observation).filter_by(job_id=job.id).count() >= MAX_POSTS:
        raise HTTPException(422, 'Daily collection is limited to two posts')
    if db.query(Observation).count() >= cfg.max_observations:
        raise HTTPException(409, 'Private observation storage is at capacity')
    from .acquisition.scrapingant import media_reference
    observation = Observation(publisher_id=publisher.id, job_id=job.id if job else None,
        external_id=target.external_id, source_url=target.url, content_hash=hashed, caption=caption,
        published_at=published, method=publisher.method if job and publisher.method in ('scrapingant','apify') else 'browser' if job and publisher.method=='browser' else 'http' if job else 'user_submission',
        provenance={'permission_basis':publisher.permission_basis if job else content['permission_attestation'],
                    'actor':actor, 'content_type':content.get('content_type','text'),
                    'adapter':content.get('adapter','staff_evidence'),'publisher_identifier':content.get('publisher_identifier'),
                    **{k:content[k] for k in ('source_author','source_relationship') if content.get(k)}},
        media=[m for m in content.get('media',[]) if publisher.method in ('scrapingant','apify') and media_reference(m)],
        retention_until=time.time()+cfg.observation_retention_days*86400)
    db.add(observation); db.flush()
    if persistent:
        if item:item.content_hash=hashed;item.last_seen=time.time()
        else:db.add(InstagramItem(publisher_id=publisher.id,external_id=target.external_id,content_hash=hashed))
    # Preserve every post/version as evidence; repeated announcements do not
    # multiply the review queue. Identity is intentionally publisher-local.
    known={event_key(c.fields) for c in db.query(EventCandidate).join(Observation,Observation.id==EventCandidate.observation_id)
        .filter(Observation.publisher_id==publisher.id,EventCandidate.status.notin_(['rejected','duplicate']))
        .order_by(EventCandidate.created.desc()).limit(1000) if event_key(c.fields)}
    structured=bool(job and publisher.platform=='event_url' and content.get('content_type')=='event')
    for ordinal, item in enumerate(extract(caption, published, publisher,structured_event=structured)):
        if job and publisher.platform=='event_url' and content.get('content_type')=='event':
            item['missing']=[m for m in item['missing'] if m!='event_evidence']
            if not item['missing']:
                item['status'],item['confidence']='qualified',0.9
        item['fields']['source_url'] = target.url
        key=event_key(item['fields'])
        if key and key in known:
            audit(db,actor,'candidate.duplicate_skipped',observation.id,details={'outcome':'same_publisher_title_schedule_venue'})
            continue
        if key:known.add(key)
        db.add(EventCandidate(observation_id=observation.id, ordinal=ordinal, **item))
    audit(db, actor, 'observation.staged', observation.id, request=request)
    return observation, True


def qualify(fields):
    required = ['title','start_time','venue_name','latitude','longitude']
    missing = [key for key in required if fields.get(key) is None or fields.get(key) == '']
    try:
        start = datetime.fromisoformat(fields['start_time'])
        if start.tzinfo is None or start <= datetime.now(timezone.utc):
            missing.append('upcoming_date')
        end = datetime.fromisoformat(fields['end_time']) if fields.get('end_time') else None
        if end and (end.tzinfo is None or end < start):
            missing.append('end_after_start')
    except (ValueError,TypeError,KeyError):
        missing.append('valid_start_time')
    lat, lng = fields.get('latitude'), fields.get('longitude')
    if lat is None or lng is None or not (48 <= lat <= 48.35 and 16.9 <= lng <= 17.35):
        missing.append('verified_bratislava_location')
    return sorted(set(missing))
