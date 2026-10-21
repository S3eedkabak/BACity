"""Transactional, repeatable ingestion with source evidence and quality-aware merging."""
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from sqlalchemy import func, text, or_
from sqlalchemy.orm import selectinload
from app.models.event import Event, EventStatus
from app.models.event_source import EventSource
from app.models.source import Source, SourceStatus
from app.models.venue import Venue


def normalize(value):
    value = unicodedata.normalize('NFKD', value or '').casefold()
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(re.findall(r'\w+', value))


def canonical_url(value):
    url = urlsplit(value)
    return urlunsplit((url.scheme.lower(), url.netloc.lower(), url.path or '/',
                      urlencode([(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
                                 if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid')]), ''))


def utc(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value and value.tzinfo else value


def find_canonical_event(db, payload):
    """Shared conservative occurrence matching; caller owns the transaction."""
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(82619422)'))
    title_key = normalize(payload.title)
    evidence = db.query(EventSource).filter_by(source_url=payload.source_url, start_time=payload.start_time, title_key=title_key).first() if payload.source_url else None
    existing = evidence.event if evidence else (db.query(Event).filter_by(source_url=payload.source_url, start_time=payload.start_time, title=payload.title).first() if payload.source_url else None)
    if existing is None and payload.previous_start_time:
        previous = db.query(EventSource).filter_by(source_url=payload.source_url,
            start_time=utc(payload.previous_start_time),title_key=title_key).first()
        existing = previous.event if previous else None
    if existing is not None and existing.merged_into_id:
        from app.crud.event import get_event
        existing = get_event(db,existing.id)
    score = 1.0
    if existing is None:
        from app.crud.event_identity import find_identity
        existing, reason = find_identity(db, payload)
        if reason:
            score = reason[1]
            if reason[0] in ('publisher_recurring_market_place','publisher_series_place','recurring_exhibition_content_place','recurring_market_schedule_place_title'):existing.identity_kind='recurring'
    return existing, evidence, score


def ingest(db, payload):
    from app.crud.event_identity import imprecise_location,standalone_offer,implausible_listing_range
    observed_coordinates={'latitude':payload.latitude,'longitude':payload.longitude}
    observed_schedule={'start_time':payload.start_time.isoformat(),'end_time':payload.end_time.isoformat() if payload.end_time else None,'end_date':str(payload.end_date) if payload.end_date else None}
    if implausible_listing_range(payload.start_time,payload.end_time,payload.end_date):
        payload=payload.model_copy(update={'end_time':None,'end_date':None,'temporal_evidence':'unknown'})
    if imprecise_location(payload):
        payload=payload.model_copy(update={'latitude':None,'longitude':None})
    if standalone_offer(payload):payload=payload.model_copy(update={'identity_kind':'offer'})
    payload = payload.model_copy(update={'start_time': utc(payload.start_time), 'end_time': utc(payload.end_time),
                                        'source_url': canonical_url(payload.source_url)})
    existing, evidence, score = find_canonical_event(db, payload)
    now = datetime.utcnow()
    # Attribute observations to the crawled publisher, not a ticketing link
    # embedded in its calendar. Keep legacy www rows readable without a data
    # rewrite; new observations prefer the normalized registry identity.
    domain = urlsplit(payload.original_source_url or payload.source_url).hostname.removeprefix('www.')
    source = db.query(Source).filter(Source.domain.in_((domain, 'www.'+domain))).order_by((Source.domain == domain).desc()).first()
    if source is None:
        source = Source(name=payload.source_name or domain, domain=domain,
                        base_url=f'{urlsplit(payload.source_url).scheme}://{domain}',
                        event_url=payload.original_source_url or payload.source_url,
                        reliability_score=payload.source_reliability)
        db.add(source)
        db.flush()
    source.last_crawled = now
    title_key = normalize(payload.title)
    venue = None
    if payload.venue_id:
        venue = db.get(Venue, payload.venue_id)
    elif payload.venue_name or payload.address:
        name = payload.venue_name or payload.address
        venue = db.query(Venue).filter(func.lower(Venue.name) == name.lower(), Venue.address == payload.address).first()
        if venue is None:
            venue = Venue(name=name, address=payload.address, city='Bratislava', latitude=payload.latitude, longitude=payload.longitude)
            db.add(venue)
            db.flush()
        elif (venue.latitude is None or venue.longitude is None) and payload.latitude is not None and payload.longitude is not None:
            # Event-source trust does not confer ownership of a shared venue.
            # Established coordinates may only be corrected through moderation.
            venue.latitude, venue.longitude = payload.latitude, payload.longitude
    values = payload.model_dump(exclude={'venue_name', 'source_name', 'venue_id', 'source_id', 'original_source_url', 'temporal_evidence', 'extraction_method', 'organizer_name','previous_start_time','publisher_event_id','identity_kind','start_precision','recurrence_rule'})
    temporal_rank = {'explicit_end': 3, 'explicit_duration': 2, 'text_range': 1}.get(payload.temporal_evidence, 0)
    old_facts = [item.facts for item in db.query(EventSource).filter_by(event_id=existing.id).limit(50)] if existing else []
    old_end_key = max(((fact.get('best_end', {}).get('rank', 0), fact.get('best_end', {}).get('quality', 0))
                       for fact in old_facts if fact.get('best_end', {}).get('value') == (existing.end_time.isoformat() if existing and existing.end_time else None)), default=(3,existing.source_reliability*existing.extraction_confidence) if existing and existing.end_time else (0, 0))
    incoming_end_key = (temporal_rank, payload.source_reliability * payload.extraction_confidence)
    outcome = 'created' if existing is None else 'updated' if evidence is not None else 'merged'
    if existing is None:
        existing = Event(**values, identity_kind=payload.identity_kind, venue_id=venue.id if venue else None, source_id=source.id)
        from app.crud.event_identity import is_offer, exhibition,canonical_title
        if is_offer(payload):
            existing.title=canonical_title(payload)
            existing.identity_kind='recurring' if exhibition(payload) else 'single';existing.price=None
        db.add(existing)
        db.flush()
    elif not existing.is_manual_override:
        quality = payload.source_reliability * payload.extraction_confidence
        preferred = quality >= existing.source_reliability * existing.extraction_confidence
        same_source = payload.source_url == existing.source_url
        if (preferred or same_source) and payload.previous_start_time and payload.start_time != existing.start_time and payload.end_time is None:
            existing.end_time = None
            existing.end_date = None
        if same_source and payload.end_date and not payload.end_time and payload.temporal_evidence=='date_range':
            if any(fact.get('best_end',{}).get('method')==payload.extraction_method for fact in old_facts):
                existing.end_time=None  # Correct this publisher's previous midnight placeholder.
        from app.crud.event_identity import is_offer,documented_exhibition_span
        for field, value in values.items():
            if is_offer(payload) and field in ("title","start_time","end_time","end_date","price","source_url"):continue
            if existing.identity_kind=='recurring' and field in ('title','start_time','end_time','end_date','price','source_url','status'):
                continue
            if documented_exhibition_span(existing) and field in ('start_time','end_time','end_date'):
                continue
            if field=='start_time' and payload.start_precision=='date' and any(fact.get('start_precision')=='time' for fact in old_facts):continue
            if field == 'end_time':
                if value is not None and (existing.end_time is None or incoming_end_key >= old_end_key):
                    existing.end_time = value
                continue
            source_lifecycle_update = same_source and field in ('status','start_time')
            if value is not None and (preferred or source_lifecycle_update or getattr(existing, field) is None):
                setattr(existing, field, value)
        existing.tags = sorted(set(existing.tags or []) | set(payload.tags))
        if venue and (preferred or not existing.venue_id):
            existing.venue_id = venue.id
        if preferred or same_source:
            existing.source_id = source.id
    existing.last_verified_at = now
    if evidence is None:
        evidence = EventSource(event_id=existing.id, source_id=source.id, source_url=payload.source_url,
                               start_time=payload.start_time, reliability=payload.source_reliability, title_key=title_key)
        db.add(evidence)
    # A real crawl can strengthen previously human-only provenance; submitting
    # public evidence alone never creates a crawled Source association.
    evidence.source_id = source.id
    evidence.original_source_url = payload.original_source_url or payload.source_url
    evidence.source_name = payload.source_name or domain
    evidence.reliability = payload.source_reliability
    evidence.dedup_confidence = score
    evidence.last_seen_at = now
    best_end = (evidence.facts or {}).get('best_end', {})
    if payload.end_time and incoming_end_key >= (best_end.get('rank',0),best_end.get('quality',0)):
        best_end = {'value': payload.end_time.isoformat(), 'rank': temporal_rank,
                    'quality': incoming_end_key[1], 'method': payload.extraction_method, 'observed_at': now.isoformat()}
    human_contribution = bool((evidence.facts or {}).get('human_contribution'))
    evidence.facts = {**(evidence.facts or {}), 'human_contribution': human_contribution, 'start_time': payload.start_time.isoformat(),
                      'end_time': payload.end_time.isoformat() if payload.end_time else None,
                      'end_date':payload.end_date.isoformat() if payload.end_date else None,
                      'end_rank': temporal_rank, 'temporal_evidence': payload.temporal_evidence,
                      'method': payload.extraction_method, 'confidence': payload.extraction_confidence,
                      'observed_schedule':observed_schedule,'observed_coordinates':observed_coordinates, 'recurrence_rule':payload.recurrence_rule, 'organizer': payload.organizer_name, 'source_title':payload.title, 'publisher_event_id':payload.publisher_event_id, 'identity_kind':payload.identity_kind, 'start_precision':payload.start_precision, 'observed_at': now.isoformat(), 'best_end': best_end}
    from app.crud.event_identity import record_listing, refresh_identity,documented_exhibition_span
    record_listing(db,existing,payload)
    span=documented_exhibition_span(existing)
    if span:
        existing.identity_kind='single';existing.start_time,existing.end_date=span;existing.end_time=None
    elif existing.identity_kind=='recurring':refresh_identity(db,existing)
    metrics = dict(source.quality_metrics or {})
    metrics['ingestion_'+outcome] = metrics.get('ingestion_'+outcome,0) + 1
    source.quality_metrics = metrics
    db.commit()
    db.refresh(existing)
    return existing


def expire_events(db, now=None, commit=True):
    """Expire only after verified availability ends; never infer removal from a failed crawl."""
    from datetime import timezone
    from zoneinfo import ZoneInfo
    from app.models.event_identity import EventOccurrence
    now = now or datetime.utcnow()
    local_day = now.replace(tzinfo=timezone.utc).astimezone(ZoneInfo('Europe/Bratislava')).date()
    active_session = db.query(EventOccurrence.id).filter(
        EventOccurrence.event_id == Event.id,
        EventOccurrence.status.in_(['fresh', 'stale']),
        func.coalesce(EventOccurrence.end_time, EventOccurrence.start_time) >= now,
    ).exists()
    completed = or_(
        (Event.end_date.isnot(None)) & (Event.end_date < local_day),
        (Event.end_date.is_(None)) & (func.coalesce(Event.end_time, Event.start_time) < now),
    )
    expired = db.query(Event).filter(Event.merged_into_id.is_(None),
        Event.status.in_([EventStatus.fresh, EventStatus.stale]),
        or_((Event.identity_kind == 'recurring') & ~active_session,
            (Event.identity_kind != 'recurring') & completed)).update(
                {Event.status: EventStatus.expired}, synchronize_session=False)
    expired_occurrences = db.query(EventOccurrence).filter(
        EventOccurrence.status.in_(['fresh', 'stale']),
        func.coalesce(EventOccurrence.end_time, EventOccurrence.start_time) < now,
    ).update({EventOccurrence.status: 'expired'}, synchronize_session=False)
    db.query(Event).filter(Event.status == EventStatus.fresh, Event.last_verified_at < now - timedelta(days=3)).update(
        {Event.status: EventStatus.stale}, synchronize_session=False)
    # Removal requires positive evidence from a non-failing source. Merely aging
    # while every publisher is unavailable must never look like upstream removal.
    evidence = db.query(EventSource.id).filter(EventSource.event_id == Event.id).exists()
    from app.models.source import CrawlerRun
    healthy_scans = db.query(func.count(CrawlerRun.id)).filter(
        CrawlerRun.source_id == EventSource.source_id,
        CrawlerRun.success.is_(True), CrawlerRun.status == 'healthy',
        CrawlerRun.finished_at > EventSource.last_seen_at,
    ).correlate(EventSource).scalar_subquery()
    uncertain = db.query(EventSource.id).outerjoin(Source,EventSource.source_id == Source.id).filter(
        EventSource.event_id == Event.id,
        or_(EventSource.source_id.is_(None), Source.status != SourceStatus.active, Source.crawl_status != 'healthy',
            Source.last_success_at.is_(None), Source.last_success_at <= EventSource.last_seen_at,
            healthy_scans < 2),
    ).exists()
    db.query(Event).filter(Event.status == EventStatus.stale,
        Event.last_verified_at < now - timedelta(days=14), evidence, ~uncertain).update(
            {Event.status: EventStatus.removed}, synchronize_session=False)
    if commit:db.commit()
    return {'expired_events':expired,'expired_occurrences':expired_occurrences}
