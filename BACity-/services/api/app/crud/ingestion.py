"""Transactional, repeatable ingestion with source evidence and quality-aware merging."""
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from sqlalchemy import func, text
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
    score = 1.0
    if existing is None:
        # Conservative match: near-identical title + same place and nearby time.
        # A shared venue alone never merges two different performances.
        candidates = db.query(Event).filter(Event.start_time.between(payload.start_time - timedelta(hours=3), payload.start_time + timedelta(hours=3))).all()
        for candidate in candidates:
            title_score = SequenceMatcher(None, normalize(payload.title), normalize(candidate.title)).ratio()
            same_place = bool(payload.address and normalize(payload.address) == normalize(candidate.address)) or bool(
                payload.venue_name and candidate.venue and normalize(payload.venue_name) == normalize(candidate.venue.name))
            if (not same_place and payload.latitude is not None and payload.longitude is not None
                    and candidate.latitude is not None and candidate.longitude is not None):
                # ~150 m in Bratislava; enough for formatting/address variation,
                # too small to collapse different venues across a neighborhood.
                same_place = abs(payload.latitude - candidate.latitude) <= .00135 and abs(payload.longitude - candidate.longitude) <= .002
            same_time = abs((candidate.start_time - payload.start_time).total_seconds()) <= 900
            description_score = SequenceMatcher(None, normalize(payload.description), normalize(candidate.description)).ratio() if payload.description and candidate.description else 0
            if same_place and title_score >= .90 and (same_time or description_score > .8):
                existing, score = candidate, .8 * title_score + .2 * (1 if same_time else description_score)
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
    values = payload.model_dump(exclude={'venue_name', 'source_name', 'venue_id', 'source_id', 'original_source_url'})
    if existing is None:
        existing = Event(**values, venue_id=venue.id if venue else None, source_id=source.id)
        db.add(existing)
        db.flush()
    elif not existing.is_manual_override:
        quality = payload.source_reliability * payload.extraction_confidence
        preferred = quality >= existing.source_reliability * existing.extraction_confidence
        same_source = payload.source_url == existing.source_url
        for field, value in values.items():
            if value is not None and (preferred or same_source or getattr(existing, field) is None):
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
    removal_candidates = db.query(Event).filter(
        Event.status == EventStatus.stale,
        Event.last_verified_at < now - timedelta(days=14),
    ).all()
    for event in removal_candidates:
        evidence = db.query(EventSource, Source).join(Source, EventSource.source_id == Source.id).filter(
            EventSource.event_id == event.id,
            Source.status == SourceStatus.active,
        ).all()
        if any(source.last_success_at is None or source.last_success_at > item.last_seen_at
               for item, source in evidence):
            event.status = EventStatus.removed
    db.commit()
