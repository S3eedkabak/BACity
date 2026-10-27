"""Trusted, separate relay. Collector containers cannot import or invoke ingestion.

Default shadow mode. Explicit dual human approval is required for every event;
there is no automatic-publication claim without a measured quality corpus.
"""
import time
from datetime import datetime, timezone, timedelta
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from .models import EventCandidate, Observation, Publisher, Staff, CandidateReview
from .security import audit
from .config import settings
from .extraction import content_hash
from .workflows import qualify, stopped


def payload_for(candidate,observation,publisher):
    from app.schemas.event import EventCreate
    fields=candidate.fields
    return EventCreate(**{key:fields[key] for key in ('title','description','start_time','end_time','venue_name','address','latitude','longitude','price','currency','organizer_name') if key in fields},
        source_url=observation.source_url, original_source_url=observation.source_url,
        source_name=publisher.name, extraction_method='social_'+observation.method,
        publisher_event_id=publisher.id+':'+observation.external_id,
        extraction_confidence=candidate.confidence,source_reliability=0.5,start_precision='time',
        timezone='Europe/Bratislava')


def shadow_matches(db,candidate,observation,publisher):
    """Use the existing pure identity comparator; never call find_canonical_event."""
    from app.models.event import Event
    from app.crud.event_identity import match
    payload=payload_for(candidate,observation,publisher)
    payload.start_time=payload.start_time.astimezone(timezone.utc).replace(tzinfo=None)
    matches=[]
    events=db.query(Event).filter(Event.merged_into_id.is_(None),
        Event.start_time.between(payload.start_time-timedelta(days=1),payload.start_time+timedelta(days=1))).limit(200).all()
    for event in events:
        reason=match(event,payload)
        if reason:
            matches.append({'event_id':str(event.id),'title':event.title,'reason':reason[0],'confidence':reason[1]})
    return matches


def deliver_one(db):
    cfg=settings()
    if not cfg.l4_enabled or not cfg.l4_publication_enabled or stopped(db):
        return None
    from .database_policy import verify_database_policy
    verify_database_policy(db,service_role='relay',consumer_role=cfg.consumer_db_role)
    candidate=db.execute(select(EventCandidate).where(EventCandidate.status=='publication_queued')
                         .order_by(EventCandidate.created).with_for_update(skip_locked=True).limit(1)).scalar_one_or_none()
    if not candidate:
        return None
    observation=db.get(Observation,candidate.observation_id)
    publisher=db.execute(select(Publisher).where(Publisher.id==observation.publisher_id).with_for_update()).scalar_one()
    reviewer=db.get(Staff,candidate.reviewed_by) if candidate.reviewed_by else None
    if (not reviewer or not reviewer.active or reviewer.role not in ('OWNER','SOCIAL_ADMIN','SOCIAL_EDITOR','SOCIAL_REVIEWER') or publisher.approval!='approved' or observation.retention_until<=time.time()
            or candidate.missing or qualify(candidate.fields) or candidate.reviewed_hash!=content_hash(candidate.fields)):
        candidate.status='needs_review'
        audit(db,'publication-relay','candidate.publication_invalidated',candidate.id); db.commit()
        return None
    publisher_actor=db.get(Staff,candidate.publication_requested_by) if candidate.publication_requested_by else None
    if (not publisher_actor or not publisher_actor.active or publisher_actor.role not in ('OWNER','SOCIAL_ADMIN')
            or publisher_actor.id==reviewer.id):
        candidate.status='needs_review'; db.commit(); return None
    audit(db,'publication-relay','candidate.publication_started',candidate.id)
    payload=payload_for(candidate,observation,publisher)
    # A crash after ingest's own commit is safe to replay by its existing identity contract.
    from app.crud.ingestion import ingest
    event=ingest(db,payload)
    candidate.status,candidate.event_id='published',str(event.id)
    audit(db,'publication-relay','candidate.published',candidate.id,details={'event_id':str(event.id)})
    db.commit()
    return str(event.id)


def main():
    import argparse
    from .db import session_factory
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');args=parser.parse_args()
    while True:
        try:
            with session_factory()() as db:
                deliver_one(db)
        except Exception:
            # No payloads, DB credentials or token-bearing URLs in diagnostics.
            print('Social publication failed; candidate retained for retry',flush=True)
        if args.once:
            return
        time.sleep(30)

if __name__=='__main__':
    main()
