"""One transactional maintenance cycle on the existing crawler/worker cadence."""
from datetime import datetime, timedelta
from sqlalchemy import select, text
from app.models.event import Event
from app.models.event_identity import EventOccurrence, EventOffer
from app.models.event_maintenance import EventMaintenanceRun, EventMaintenanceArchive
from app.crud.ingestion import expire_events
from app.operations.reconcile_events import reconcile
from app.operations.repair_event_metadata import repair

RETENTION_DAYS = 90
GC_BATCH = 250
LOCK_ID = 82619423


def _snapshot(row):
    return {column.name: (value.isoformat() if hasattr(value, 'isoformat') else str(value) if value is not None else None)
            for column in row.__table__.columns
            for value in [getattr(row, column.name)]}


def _archive(db, rows, kind, now):
    for row in rows:
        db.add(EventMaintenanceArchive(kind=kind, record_id=row.id, event_id=row.event_id,
                                       snapshot=_snapshot(row), archived_at=now))
        db.delete(row)
    db.flush()
    return len(rows)


def run_maintenance(db, now=None, retention_days=RETENTION_DAYS):
    """Reconcile changed identities, expire availability and archive old children.

    Never removes an Event, EventSource, alias, saved event, or reconciliation
    record. A failed cycle rolls back all database mutations. Postgres permits
    one caller at a time even when the API and existing worker race.
    """
    now = now or datetime.utcnow()
    if db.bind.dialect.name == 'postgresql':
        if not db.scalar(text('SELECT pg_try_advisory_xact_lock(:key)').bindparams(key=LOCK_ID)):
            db.rollback()
            return {'status':'already_running'}
    previous = db.scalar(select(EventMaintenanceRun).order_by(EventMaintenanceRun.finished_at.desc()).limit(1))
    changed = previous is None or bool(db.scalar(select(Event.id).where(Event.merged_into_id.is_(None),
        Event.updated_at >= previous.started_at).limit(1)))
    report = {'status':'ok', 'reconciled_aliases':0}
    if changed:
        report['reconciled_aliases'] = reconcile(db, apply=True)['aliases']
        report['metadata_repairs'] = len(repair(db,apply=True))
    else:
        report['metadata_repairs'] = 0
    report.update(expire_events(db, now=now, commit=False))
    cutoff = now - timedelta(days=retention_days)
    old_occurrences = list(db.scalars(select(EventOccurrence).where(
        EventOccurrence.start_time < cutoff,
        EventOccurrence.status.in_(['expired', 'superseded', 'cancelled', 'removed']),
        (EventOccurrence.end_time.is_(None)) | (EventOccurrence.end_time < cutoff),
    ).order_by(EventOccurrence.start_time, EventOccurrence.id).limit(GC_BATCH)))
    report['archived_occurrences'] = _archive(db, old_occurrences, 'occurrence', now)
    old_offers = list(db.scalars(select(EventOffer).where(
        EventOffer.valid_until.isnot(None),EventOffer.valid_until < cutoff,
    ).order_by(EventOffer.valid_until, EventOffer.id).limit(GC_BATCH)))
    report['archived_offers'] = _archive(db, old_offers, 'offer', now)
    if changed or any(report[key] for key in ('expired_events','expired_occurrences','archived_occurrences','archived_offers')) or previous is None or now-previous.finished_at >= timedelta(hours=1):
        db.add(EventMaintenanceRun(started_at=now, finished_at=now,
            reconciled_aliases=report['reconciled_aliases'], expired_events=report['expired_events'],
            expired_occurrences=report['expired_occurrences'],
            archived_occurrences=report['archived_occurrences'], archived_offers=report['archived_offers'],
            diagnostics={'retention_days':retention_days,'gc_batch':GC_BATCH,'identity_scan':changed,
                         'metadata_repairs':report['metadata_repairs']}))
    db.commit()
    return report
