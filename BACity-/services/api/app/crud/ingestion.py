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


def ingest(db, payload):
    payload = payload.model_copy(update={'start_time': utc(payload.start_time), 'end_time': utc(payload.end_time),
                                        'source_url': canonical_url(payload.source_url)})
    # Serializes crawler writes across API replicas; evidence unique constraint also
    # protects exact occurrences. Transactions are short and contain no network IO.
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(82619422)'))
    now = datetime.utcnow()
    domain = urlsplit(payload.source_url).hostname
    source = db.query(Source).filter(Source.domain == domain).first()
    if source is None:
        source = Source(name=payload.source_name or domain, domain=domain,
                        base_url=f'{urlsplit(payload.source_url).scheme}://{domain}',
                        event_url=payload.original_source_url or payload.source_url,
                        reliability_score=payload.source_reliability)
        db.add(source)
        db.flush()
    source.last_crawled = now
    title_key = normalize(payload.title)
    evidence = db.query(EventSource).filter_by(source_url=payload.source_url, start_time=payload.start_time, title_key=title_key).first()
    existing = evidence.event if evidence else db.query(Event).filter_by(source_url=payload.source_url, start_time=payload.start_time, title=payload.title).first()
    if existing is None and payload.previous_start_time:
        previous = db.query(EventSource).filter_by(source_url=payload.source_url,
            start_time=utc(payload.previous_start_time),title_key=title_key).first()
        existing = previous.event if previous else None
    score = 1.0
    if existing is None:
        # Conservative match: near-identical title + same place and nearby time.
        # A shared venue alone never merges two different performances.
        candidates = db.query(Event).options(selectinload(Event.venue)).filter(Event.start_time.between(payload.start_time - timedelta(minutes=15), payload.start_time + timedelta(minutes=15))).order_by(Event.start_time, Event.id).limit(500).all()
        for candidate in candidates:
            title_score = SequenceMatcher(None, normalize(payload.title), normalize(candidate.title)).ratio()
            same_place = bool(payload.address and normalize(payload.address) == normalize(candidate.address)) or bool(
                payload.venue_name and candidate.venue and normalize(payload.venue_name) == normalize(candidate.venue.name))
            if (not same_place and payload.latitude is not None and payload.longitude is not None
                    and candidate.latitude is not None and candidate.longitude is not None):
                # ~150 m in Bratislava; enough for formatting/address variation,
                # too small to collapse different venues across a neighborhood.
                same_place = abs(payload.latitude - candidate.latitude) <= .00135 and abs(payload.longitude - candidate.longitude) <= .002
            if payload.venue_name and candidate.venue and SequenceMatcher(None,normalize(payload.venue_name),normalize(candidate.venue.name)).ratio() < .8:
                same_place = False
            same_time = abs((candidate.start_time - payload.start_time).total_seconds()) <= 900
            if same_place and title_score >= .90 and same_time:
                existing, score = candidate, .8 * title_score + .2
                break
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
        elif payload.latitude is not None and payload.longitude is not None:
            venue.latitude, venue.longitude = payload.latitude, payload.longitude
    values = payload.model_dump(exclude={'venue_name', 'source_name', 'venue_id', 'source_id', 'original_source_url', 'temporal_evidence', 'extraction_method', 'organizer_name','previous_start_time'})
    temporal_rank = {'explicit_end': 3, 'explicit_duration': 2, 'text_range': 1}.get(payload.temporal_evidence, 0)
    old_facts = [item.facts for item in db.query(EventSource).filter_by(event_id=existing.id).limit(50)] if existing else []
    old_end_key = max(((fact.get('best_end', {}).get('rank', 0), fact.get('best_end', {}).get('quality', 0))
                       for fact in old_facts if fact.get('best_end', {}).get('value') == (existing.end_time.isoformat() if existing and existing.end_time else None)), default=(3,existing.source_reliability*existing.extraction_confidence) if existing and existing.end_time else (0, 0))
    incoming_end_key = (temporal_rank, payload.source_reliability * payload.extraction_confidence)
    outcome = 'created' if existing is None else 'updated' if evidence is not None else 'merged'
    if existing is None:
        existing = Event(**values, venue_id=venue.id if venue else None, source_id=source.id)
        db.add(existing)
        db.flush()
    elif not existing.is_manual_override:
        quality = payload.source_reliability * payload.extraction_confidence
        preferred = quality >= existing.source_reliability * existing.extraction_confidence
        same_source = payload.source_url == existing.source_url
        if (preferred or same_source) and payload.previous_start_time and payload.start_time != existing.start_time and payload.end_time is None:
            existing.end_time = None
        for field, value in values.items():
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
    evidence.original_source_url = payload.original_source_url or payload.source_url
    evidence.source_name = payload.source_name or domain
    evidence.reliability = payload.source_reliability
    evidence.dedup_confidence = score
    evidence.last_seen_at = now
    best_end = (evidence.facts or {}).get('best_end', {})
    if payload.end_time and incoming_end_key >= (best_end.get('rank',0),best_end.get('quality',0)):
        best_end = {'value': payload.end_time.isoformat(), 'rank': temporal_rank,
                    'quality': incoming_end_key[1], 'method': payload.extraction_method, 'observed_at': now.isoformat()}
    evidence.facts = {'start_time': payload.start_time.isoformat(),
                      'end_time': payload.end_time.isoformat() if payload.end_time else None,
                      'end_rank': temporal_rank, 'temporal_evidence': payload.temporal_evidence,
                      'method': payload.extraction_method, 'confidence': payload.extraction_confidence,
                      'organizer': payload.organizer_name, 'observed_at': now.isoformat(), 'best_end': best_end}
    metrics = dict(source.quality_metrics or {})
    metrics['ingestion_'+outcome] = metrics.get('ingestion_'+outcome,0) + 1
    source.quality_metrics = metrics
    db.commit()
    db.refresh(existing)
    return existing


def expire_events(db):
    now = datetime.utcnow()
    db.query(Event).filter(Event.status.in_([EventStatus.fresh, EventStatus.stale]),
                          func.coalesce(Event.end_time, Event.start_time) < now - timedelta(days=1)).update(
                              {Event.status: EventStatus.expired}, synchronize_session=False)
    db.query(Event).filter(Event.status == EventStatus.fresh, Event.last_verified_at < now - timedelta(days=3)).update(
        {Event.status: EventStatus.stale}, synchronize_session=False)
    # Removal requires positive evidence from a non-failing source. Merely aging
    # while every publisher is unavailable must never look like upstream removal.
    evidence = db.query(EventSource.id).filter(EventSource.event_id == Event.id).exists()
    uncertain = db.query(EventSource.id).join(Source,EventSource.source_id == Source.id).filter(
        EventSource.event_id == Event.id,
        or_(Source.status != SourceStatus.active, Source.crawl_status != 'healthy',
            Source.last_success_at.is_(None), Source.last_success_at <= EventSource.last_seen_at),
    ).exists()
    db.query(Event).filter(Event.status == EventStatus.stale,
        Event.last_verified_at < now - timedelta(days=14), evidence, ~uncertain).update(
            {Event.status: EventStatus.removed}, synchronize_session=False)
    db.commit()
