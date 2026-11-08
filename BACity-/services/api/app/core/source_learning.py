"""Explicit learning from already-public canonical events, never private activity."""
import ipaddress
import time
import logging
from uuid import UUID
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from fastapi import HTTPException
from app.models.candidate_source import CandidateSource
from app.models.event import EventStatus
from app.models.event import Event
from app.models.community import Submission
from sqlalchemy import text

log = logging.getLogger(__name__)
LEARNING_KEY = '_source_learning'
SOCIAL_DOMAINS = ('facebook.com', 'fb.com', 'instagram.com', 'tiktok.com', 'twitter.com', 'x.com', 'youtube.com', 'youtu.be')


def candidate_lock(db):
    if db.bind.dialect.name == 'postgresql':
        db.execute(text('SELECT pg_advisory_xact_lock(82619423)'))


def public_source_url(value):
    try:
        p = urlsplit(value)
        host = (p.hostname or '').lower().rstrip('.')
        if p.scheme not in ('http','https') or not host or '.' not in host or p.username or p.password or p.port not in (None,80,443):
            raise ValueError()
        if host.endswith(('.localhost','.local','.internal')):
            raise ValueError()
        if len(value) > 2048 or len(host) > 255 or any(host == d or host.endswith('.' + d) for d in SOCIAL_DOMAINS):
            raise ValueError()
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError()
        query = []
        for k,v in parse_qsl(p.query):
            if k.lower() in ('token','key','auth','access_token','password','signature'):
                raise ValueError()
            if not k.lower().startswith('utm_') and k.lower() not in ('fbclid','gclid'):
                query.append((k,v))
        return host.removeprefix('www.'), urlunsplit((p.scheme,host,p.path or '/',urlencode(sorted(query)),''))
    except (ValueError, TypeError):
        raise HTTPException(422,'Public source URL required')


def learn_public_event(db, event):
    if not event or event.status not in (EventStatus.fresh, EventStatus.stale):
        raise HTTPException(422,'Only published canonical event evidence may be submitted')
    return learn_public_url(db, event.source_url)


def learn_public_url(db, value):
    domain, url = public_source_url(value)
    candidate_lock(db)
    candidate = db.get(CandidateSource, domain)
    if candidate is None:
        if db.query(CandidateSource).count() >= 250:
            raise HTTPException(409,'Candidate queue capacity reached')
        candidate = CandidateSource(domain=domain,url=url,origin=url,discovered=time.time())
        db.add(candidate)
    return candidate


def queue_public_evidence(item, urls):
    """Publication transaction is the durable outbox. No requests or user data."""
    previous = item.payload.get(LEARNING_KEY, {})
    evidence = {public_source_url(url)[0]: url for url in previous.get('urls', [])}
    rejected = previous.get('ineligible', 0)
    for value in list(urls)[:3]:
        if not value:
            continue
        try:
            domain, url = public_source_url(value)
        except HTTPException:
            rejected += 1
            continue
        if len(evidence) < 3 or domain in evidence:
            evidence.setdefault(domain, url)
    urls = list(evidence.values())[:3]
    # Repeated calls without new evidence must not amplify retries.
    if previous and urls == previous.get('urls', []):
        return
    item.payload = {**item.payload, LEARNING_KEY: {
        'state': 'pending' if urls else 'no_eligible_public_source',
        'origin': 'published_contribution', 'urls': urls, 'ineligible': rejected,
        'attempts': 0, 'next_attempt': 0, 'results': [],
    }}


def process_public_evidence(db, limit=25):
    """Bounded, idempotent local DB work; fetching belongs to Crawler V2."""
    candidate_lock(db)
    state = Submission.payload[LEARNING_KEY]['state'].as_string()
    due = Submission.payload[LEARNING_KEY]['next_attempt'].as_float()
    jobs = db.query(Submission).filter(
        Submission.kind == 'event', Submission.state == 'approved',
        state.in_(('pending', 'retry')), due <= time.time(),
    ).order_by(Submission.created_at, Submission.id).limit(min(max(limit, 1), 25)).with_for_update(skip_locked=True).all()
    for item in jobs:
        work = dict(item.payload[LEARNING_KEY])
        work['attempts'] += 1
        try:
            with db.begin_nested():
                event = db.get(Event, UUID(item.published_id)) if item.published_id else None
                if not event or event.status not in (EventStatus.fresh, EventStatus.stale):
                    work.update(state='skipped', reason='event_not_published')
                else:
                    results = []
                    for url in work['urls'][:3]:
                        domain, _ = public_source_url(url)
                        existed = db.get(CandidateSource, domain) is not None
                        candidate = learn_public_url(db, url)
                        db.flush()
                        results.append({'domain': candidate.domain, 'outcome': 'existing' if existed else 'created'})
                    work.update(state='completed', results=results)
        except Exception as exc:
            # Never log URLs, contribution content, identities or exception text.
            log.warning('Published-source learning failed (%s)', type(exc).__name__)
            retryable = not isinstance(exc, HTTPException) or exc.status_code >= 500 or exc.status_code == 409
            work.update(state=('retry' if retryable and work['attempts'] < 5 else 'failed'),
                        reason='capacity' if isinstance(exc, HTTPException) and exc.status_code == 409 else 'learning_failed',
                        next_attempt=time.time() + min(3600, 60 * 2 ** work['attempts']))
        item.payload = {**item.payload, LEARNING_KEY: work}
    db.commit()
    return {'processed': len(jobs)}
