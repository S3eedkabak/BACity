from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.routes.events import require_ingestion_key
from app.core.community import audit, require_admin
from app.models.source import CrawlerRun, Source, SourceStatus, SourceType
from app.schemas.crawler import CrawlRunReport, SourceAdminUpdate
from app.models.candidate_source import CandidateSource
from app.models.event import Event, EventStatus
from app.models.event_source import EventSource
from app.core.source_learning import learn_public_event, public_source_url, process_public_evidence, candidate_lock, LEARNING_KEY
from app.models.community import Submission
from app.core.community import require_moderator
from app.config import get_settings
from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Literal
from sqlalchemy import func, or_
import os
import math

router = APIRouter(prefix="/crawler", tags=["crawler"])


def _source_dict(source: Source):
    now = datetime.utcnow()
    stale_after = timedelta(minutes=max(source.crawl_frequency_minutes * 2, 60))
    stale = not source.last_success_at or now - source.last_success_at > stale_after
    return {
        "id": str(source.id), "name": source.name, "domain": source.domain,
        "source_type": source.source_type.value, "enabled": source.status not in (SourceStatus.disabled, SourceStatus.paused),
        "status": source.status.value, "health": "disabled" if source.status == SourceStatus.disabled else "failed" if source.status == SourceStatus.failing else "stale" if stale else source.crawl_status,
        "requires_js": source.requires_js, "crawl_frequency_minutes": source.crawl_frequency_minutes,
        "last_attempt_at": source.last_attempt_at, "last_success_at": source.last_success_at,
        "pages_processed": source.pages_processed, "items_processed": source.items_processed,
        "accepted_events": source.accepted_events, "rejected_events": source.rejected_events,
        "extraction_errors": source.extraction_errors, "consecutive_failures": source.consecutive_failures,
        "last_error": source.last_error, "skip_reasons": source.last_skip_reasons or {},
        "quality_metrics": source.quality_metrics or {},
    }


@router.post("/runs", dependencies=[Depends(require_ingestion_key)])
def report_run(payload: CrawlRunReport, db: Session = Depends(get_db)):
    source = db.query(Source).filter(Source.domain == payload.domain).first()
    values = payload.model_dump()
    if source is None:
        try:
            source_type = SourceType(payload.source_type)
        except ValueError:
            source_type = SourceType.event_platform
        source = Source(name=payload.name, domain=payload.domain, base_url=payload.base_url,
                        event_url=payload.event_url, source_type=source_type, language=payload.language,
                        parser=payload.parser, reliability_score=payload.reliability_score,
                        requires_js=payload.requires_js, crawl_frequency_minutes=payload.crawl_frequency_minutes)
        db.add(source)
        db.flush()
    source.name = payload.name
    source.last_attempt_at = payload.finished_at.replace(tzinfo=None)
    source.last_crawled = source.last_attempt_at
    source.crawl_status = payload.status
    source.pages_processed = payload.pages_processed
    source.items_processed = payload.items_processed
    source.accepted_events = payload.accepted_events
    source.rejected_events = payload.rejected_events
    source.extraction_errors = payload.extraction_errors
    source.last_skip_reasons = dict(list(payload.skip_reasons.items())[:20])
    source.quality_metrics = {**{k:v for k,v in (source.quality_metrics or {}).items() if k.startswith('ingestion_')},**payload.quality_metrics}
    if payload.success:
        source.last_success_at = source.last_attempt_at
        source.consecutive_failures = 0
        source.last_error = None
        if source.status == SourceStatus.failing:
            source.status = SourceStatus.active
    else:
        source.consecutive_failures += 1
        source.last_error = payload.error
        if source.status == SourceStatus.active:
            source.status = SourceStatus.failing
    run = CrawlerRun(source_id=source.id, started_at=payload.started_at.replace(tzinfo=None),
                     finished_at=payload.finished_at.replace(tzinfo=None), success=payload.success,
                     status=payload.status, pages_processed=payload.pages_processed,
                     items_processed=payload.items_processed, accepted_events=payload.accepted_events,
                     rejected_events=payload.rejected_events, extraction_errors=payload.extraction_errors,
                     skip_reasons=source.last_skip_reasons, error=payload.error)
    run.quality_metrics = payload.quality_metrics
    db.add(run)
    db.flush()
    # Keep only useful recent history, not unbounded crawler logs.
    old_ids = [row[0] for row in db.query(CrawlerRun.id).filter(CrawlerRun.source_id == source.id)
               .order_by(CrawlerRun.finished_at.desc()).offset(50).all()]
    if old_ids:
        db.query(CrawlerRun).filter(CrawlerRun.id.in_(old_ids)).delete(synchronize_session=False)
    db.commit()
    return {"status": "recorded", "source_id": str(source.id)}


@router.get("/runtime", dependencies=[Depends(require_ingestion_key)])
def runtime_config(db: Session = Depends(get_db)):
    return [{"domain": row.domain, "enabled": row.status not in (SourceStatus.disabled,SourceStatus.paused),
             "crawl_frequency_minutes": row.crawl_frequency_minutes}
            for row in db.query(Source).all()]


@router.get("/admin/sources")
def list_sources(db: Session = Depends(get_db), _=Depends(require_admin)):
    return [_source_dict(row) for row in db.query(Source).order_by(Source.name).all()]


@router.get("/admin/sources/{source_id}/runs")
def source_runs(source_id: UUID, limit: int = Query(20, ge=1, le=50), db: Session = Depends(get_db), _=Depends(require_admin)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    return [{"id": str(row.id), "started_at": row.started_at, "finished_at": row.finished_at,
             "success": row.success, "status": row.status, "pages_processed": row.pages_processed,
             "items_processed": row.items_processed, "accepted_events": row.accepted_events,
             "rejected_events": row.rejected_events, "extraction_errors": row.extraction_errors,
             "skip_reasons": row.skip_reasons, "error": row.error, "quality_metrics": row.quality_metrics,
             "duration_seconds": max(0,(row.finished_at-row.started_at).total_seconds())}
            for row in db.query(CrawlerRun).filter_by(source_id=source.id).order_by(CrawlerRun.finished_at.desc()).limit(limit)]


@router.patch("/admin/sources/{source_id}")
def update_source(source_id: UUID, payload: SourceAdminUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    if payload.enabled is not None:
        source.status = SourceStatus.active if payload.enabled else SourceStatus.disabled
        candidate=db.get(CandidateSource,source.domain.removeprefix('www.'))
        if candidate:
            candidate.enabled=payload.enabled
            candidate.status='discovered' if payload.enabled else 'disabled'
            if payload.enabled:
                candidate.attempts=candidate.good_runs=candidate.failures=0
    if payload.crawl_frequency_minutes is not None:
        source.crawl_frequency_minutes = payload.crawl_frequency_minutes
    audit(db, admin, "crawler_source_updated", "source", source.id,
          {"enabled": payload.enabled, "crawl_frequency_minutes": payload.crawl_frequency_minutes})
    db.commit()
    db.refresh(source)
    return _source_dict(source)


def require_learning_key(_=Depends(require_ingestion_key)):
    if not os.getenv('INGESTION_API_KEY',get_settings().ingestion_api_key):
        raise HTTPException(503,'Source learning authentication is not configured')


class CandidateReport(BaseModel):
    model_config = ConfigDict(extra='forbid')
    domain: str = Field(max_length=255)
    url: str = Field(max_length=2048)
    origin: str = Field(max_length=2048)
    status: Literal['discovered','inspected','probation','trusted','rejected','blocked','disabled']
    discovered: float = Field(ge=0)
    inspected: float | None = Field(default=None,ge=0)
    attempts: int = Field(ge=0)
    good_runs: int = Field(ge=0)
    failures: int = Field(ge=0)
    reason: str | None = Field(default=None,max_length=100)
    metrics: dict[str,float] = Field(default_factory=dict,max_length=30)

    @field_validator('metrics')
    @classmethod
    def finite_metrics(cls,value):
        if any(not math.isfinite(v) or v < 0 or len(k) > 100 for k,v in value.items()):
            raise ValueError('Invalid quality metric')
        return value


class CandidateBatch(BaseModel):
    items: list[CandidateReport] = Field(max_length=250)


def candidate_dict(row):
    return {key:getattr(row,key) for key in ('domain','url','origin','status','enabled','discovered','inspected','attempts','good_runs','failures','reason','metrics')}


@router.post('/learning/process', dependencies=[Depends(require_learning_key)])
def process_learning(db: Session = Depends(get_db)):
    return process_public_evidence(db)


@router.get('/admin/learning')
def learning_history(limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db), _=Depends(require_moderator)):
    rows = db.query(Submission).filter(Submission.kind == 'event', Submission.state == 'approved',
        Submission.payload[LEARNING_KEY]['state'].as_string().isnot(None)).order_by(Submission.updated_at.desc(), Submission.id).limit(limit).all()
    candidates = {c.domain: c for c in db.query(CandidateSource).limit(250)}
    result = []
    for row in rows:
        work = row.payload[LEARNING_KEY]
        evidence = []
        for url in work['urls']:
            domain, _ = public_source_url(url)
            candidate = candidates.get(domain)
            evidence.append({'domain': domain, 'status': candidate.status if candidate else 'queued',
                             'reason': candidate.reason if candidate else None})
        result.append({'id': str(row.id), 'event_id': row.published_id, 'origin': 'published_contribution',
                       'state': work['state'], 'attempts': work['attempts'],
                       'ineligible': work.get('ineligible', 0), 'reason': work.get('reason'),
                       'results': work['results'], 'sources': evidence})
    return result


@router.get('/candidates/runtime', dependencies=[Depends(require_learning_key)])
def candidate_runtime(db: Session=Depends(get_db)):
    return [candidate_dict(r) for r in db.query(CandidateSource).order_by(CandidateSource.domain).limit(250)]


@router.post('/candidates/report', dependencies=[Depends(require_learning_key)])
def candidate_report(payload:CandidateBatch, db:Session=Depends(get_db)):
    candidate_lock(db)
    existing = {r.domain:r for r in db.query(CandidateSource).limit(250)}
    for item in payload.items:
        domain,url = public_source_url(item.url)
        _,origin = public_source_url(item.origin)
        if domain != item.domain:
            raise HTTPException(422,'Candidate domain does not match URL')
        row = existing.get(domain)
        if row is None:
            if len(existing) >= 250:
                continue
            row = CandidateSource(domain=domain,url=url,origin=origin,discovered=item.discovered)
            db.add(row); existing[domain]=row
        # Admin disable always wins over a stale worker snapshot.
        if row.enabled is False:
            continue
        for key,value in item.model_dump(exclude={'domain','url','origin','discovered'}).items():
            setattr(row,key,value)
    db.commit()
    return {'recorded':len(payload.items)}


@router.get('/admin/candidates')
def admin_candidates(db:Session=Depends(get_db), _=Depends(require_admin)):
    return [candidate_dict(r) for r in db.query(CandidateSource).order_by(CandidateSource.domain).limit(250)]


class CandidateControl(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool


@router.patch('/admin/candidates/{domain}')
def control_candidate(domain:str,payload:CandidateControl,db:Session=Depends(get_db),admin=Depends(require_admin)):
    row=db.get(CandidateSource,domain)
    if not row:
        raise HTTPException(404,'Candidate not found')
    row.enabled=payload.enabled
    row.status='discovered' if payload.enabled else 'disabled'
    for source in db.query(Source).filter(Source.domain.in_((domain,'www.'+domain))):
        source.status=SourceStatus.active if payload.enabled else SourceStatus.disabled
    if payload.enabled:
        row.attempts=row.good_runs=row.failures=0
        row.inspected=None
        row.reason=None
    audit(db,admin,'crawler_candidate_control','candidate',domain,{'enabled':payload.enabled})
    db.commit()
    return candidate_dict(row)


class PublicEventEvidence(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event_id: UUID


@router.post('/evidence',dependencies=[Depends(require_learning_key)])
def public_evidence(payload:PublicEventEvidence,db:Session=Depends(get_db)):
    row=learn_public_event(db,db.get(Event,payload.event_id))
    db.commit()
    return {'domain':row.domain,'status':row.status}


@router.get('/admin/quality')
def data_quality(db:Session=Depends(get_db),_=Depends(require_admin)):
    now=datetime.utcnow()
    eligible=db.query(Event).filter(Event.status.in_((EventStatus.fresh,EventStatus.stale)),Event.start_time>=now)
    total=eligible.count()
    predicates={'end_datetime':Event.end_time.isnot(None),'coordinates':Event.latitude.isnot(None)&Event.longitude.isnot(None),
                'venue':Event.venue_id.isnot(None),'category':Event.category!='Other',
                'organizer':or_(Event.organization_id.isnot(None),db.query(EventSource.id).filter(
                    EventSource.event_id==Event.id,EventSource.facts['organizer'].as_string().isnot(None)).exists())}
    fields={key:{'count':eligible.filter(condition).count()} for key,condition in predicates.items()}
    for value in fields.values():
        value['percentage']=round(100*value['count']/total,2) if total else 0
    multi=db.query(EventSource.event_id).group_by(EventSource.event_id).having(func.count(EventSource.id)>1).subquery()
    source_counts=dict(db.query(EventSource.source_id,func.count(func.distinct(EventSource.event_id))).group_by(EventSource.source_id).all())
    durations={}
    for source_id,started,finished in db.query(CrawlerRun.source_id,CrawlerRun.started_at,CrawlerRun.finished_at).order_by(CrawlerRun.finished_at.desc()).limit(12500):
        bucket=durations.setdefault(str(source_id),[])
        bucket.append(max(0,(finished-started).total_seconds()))
    return {'future_events':total,'total_events':db.query(Event).count(),
            'total_with_end_datetime':db.query(Event).filter(Event.end_time.isnot(None)).count(),'coverage':fields,
            'multi_source_future_events':eligible.filter(Event.id.in_(db.query(multi.c.event_id))).count(),
            'candidate_states':dict(db.query(CandidateSource.status,func.count()).group_by(CandidateSource.status).all()),
            'events_per_source':{str(key):value for key,value in source_counts.items()},
            'rejection_rates':{s.domain:s.rejected_events/max(s.rejected_events+s.accepted_events,1) for s in db.query(Source).limit(250)},
            'ingestion_outcomes':{s.domain:{k:v for k,v in (s.quality_metrics or {}).items() if k.startswith('ingestion_')} for s in db.query(Source).limit(250)},
            'average_crawl_seconds':{key:sum(values)/len(values) for key,values in durations.items()},
            'definition':'published future starts; no production delta inferred'}


@router.get('/admin/events/{event_id}/quality')
def event_quality(event_id:UUID,db:Session=Depends(get_db),_=Depends(require_admin)):
    event=db.get(Event,event_id)
    if not event:
        raise HTTPException(404,'Event not found')
    fields=('title','description','start_time','end_time','venue_id','latitude','longitude','category','organization_id','source_url','image_url')
    return {'event_id':str(event.id),'status':event.status,'last_verified_at':event.last_verified_at,
            'missing':[key for key in fields if not getattr(event,key)],
            'sources':[{'url':s.source_url,'reliability':s.reliability,'last_seen_at':s.last_seen_at,'facts':s.facts}
                for s in db.query(EventSource).filter_by(event_id=event.id).order_by(EventSource.source_url).limit(50)]}
