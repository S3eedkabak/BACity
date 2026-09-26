from datetime import datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.routes.events import require_ingestion_key
from app.core.community import audit, require_admin
from app.models.source import CrawlerRun, Source, SourceStatus, SourceType
from app.schemas.crawler import CrawlRunReport, SourceAdminUpdate

router = APIRouter(prefix="/crawler", tags=["crawler"])


def _source_dict(source: Source):
    now = datetime.utcnow()
    stale_after = timedelta(minutes=max(source.crawl_frequency_minutes * 2, 60))
    stale = not source.last_success_at or now - source.last_success_at > stale_after
    return {
        "id": str(source.id), "name": source.name, "domain": source.domain,
        "source_type": source.source_type.value, "enabled": source.status != SourceStatus.disabled,
        "status": source.status.value, "health": "disabled" if source.status == SourceStatus.disabled else "failed" if source.status == SourceStatus.failing else "stale" if stale else source.crawl_status,
        "requires_js": source.requires_js, "crawl_frequency_minutes": source.crawl_frequency_minutes,
        "last_attempt_at": source.last_attempt_at, "last_success_at": source.last_success_at,
        "pages_processed": source.pages_processed, "items_processed": source.items_processed,
        "accepted_events": source.accepted_events, "rejected_events": source.rejected_events,
        "extraction_errors": source.extraction_errors, "consecutive_failures": source.consecutive_failures,
        "last_error": source.last_error, "skip_reasons": source.last_skip_reasons or {},
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
    return [{"domain": row.domain, "enabled": row.status != SourceStatus.disabled,
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
             "skip_reasons": row.skip_reasons, "error": row.error}
            for row in db.query(CrawlerRun).filter_by(source_id=source.id).order_by(CrawlerRun.finished_at.desc()).limit(limit)]


@router.patch("/admin/sources/{source_id}")
def update_source(source_id: UUID, payload: SourceAdminUpdate, db: Session = Depends(get_db), admin=Depends(require_admin)):
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(404, "Source not found")
    if payload.enabled is not None:
        source.status = SourceStatus.active if payload.enabled else SourceStatus.disabled
    if payload.crawl_frequency_minutes is not None:
        source.crawl_frequency_minutes = payload.crawl_frequency_minutes
    audit(db, admin, "crawler_source_updated", "source", source.id,
          {"enabled": payload.enabled, "crawl_frequency_minutes": payload.crawl_frequency_minutes})
    db.commit()
    db.refresh(source)
    return _source_dict(source)
