"""Explicit learning from already-public canonical events, never private activity."""
import ipaddress
import time
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from fastapi import HTTPException
from app.models.candidate_source import CandidateSource
from app.models.event import EventStatus


def public_source_url(value):
    try:
        p = urlsplit(value)
        host = (p.hostname or '').lower().rstrip('.')
        if p.scheme not in ('http','https') or not host or '.' not in host or p.username or p.password or p.port not in (None,80,443):
            raise ValueError()
        if host.endswith(('.localhost','.local','.internal')):
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
    domain, url = public_source_url(event.source_url)
    candidate = db.get(CandidateSource, domain)
    if candidate is None:
        if db.query(CandidateSource).count() >= 250:
            raise HTTPException(409,'Candidate queue capacity reached')
        candidate = CandidateSource(domain=domain,url=url,origin=url,discovered=time.time())
        db.add(candidate)
    return candidate
