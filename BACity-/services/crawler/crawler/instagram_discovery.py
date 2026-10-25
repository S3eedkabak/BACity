"""Private account leads only. No Instagram requests, posts or event publication.

Observe links on website responses already acquired under the crawler's network
policy. A declared profile is neither verified ownership nor collection consent.
"""
import json
import math
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from crawler.discovery import candidate_url
from crawler.sources import ACTIVE_SOURCES

MAX_PUBLISHERS = 250
MAX_PROFILES_PER_PAGE = 10
MAX_EVIDENCE_PER_PUBLISHER = 4
MAX_HTML_BYTES = 2 * 1024 * 1024
_RESERVED = {
    'accounts', 'about', 'api', 'challenge', 'developer', 'direct', 'directory',
    'explore', 'graphql', 'legal', 'oauth', 'p', 'privacy', 'reel', 'reels',
    'share', 'stories', 'tv', 'web',
}


def profile_url(value):
    """Canonical identity fallback until an authorized stable account ID exists."""
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value.strip())
        if (parsed.scheme not in ('http', 'https') or parsed.username or parsed.password
                or parsed.port not in (None, 80, 443)
                or (parsed.hostname or '').lower().rstrip('.') not in ('instagram.com', 'www.instagram.com')):
            return None
    except ValueError:
        return None
    if not re.fullmatch(r'/[a-zA-Z0-9_.]+/?', parsed.path):
        return None
    handle = parsed.path.strip('/').lower()
    if (not re.fullmatch(r'[a-z0-9_][a-z0-9_.]{0,29}', handle)
            or handle.endswith('.') or '..' in handle or handle in _RESERVED):
        return None
    return f'https://www.instagram.com/{handle}/'


@dataclass(frozen=True)
class ProfileLead:
    profile_url: str
    evidence_url: str
    source_domain: str
    source_name: str
    source_role: str
    relevance_basis: str
    priority: int


def discover_profiles(response, source, db):
    """Extract at most ten leads from an existing verified local website response.

    Known BACity seeds and qualified local candidates are eligible evidence.
    Unknown hosts, cross-host redirects and unsupported content fail closed.
    This function does not fetch links or create registry tables.
    """
    try:
        evidence_domain, evidence_url = candidate_url(response.url)
    except (TypeError, ValueError):
        return []
    domain = source.domain.lower().removeprefix('www.')
    if evidence_domain != domain and not evidence_domain.endswith('.' + domain):
        return []
    if domain in {s.domain.removeprefix('www.') for s in ACTIVE_SOURCES}:
        basis = 'bacity_registered_bratislava_source'
    else:
        candidate = db.execute(
            'SELECT status,qualified_observations FROM candidates WHERE domain=?', (domain,)
        ).fetchone()
        if not candidate or candidate[0] not in ('probation', 'trusted') or candidate[1] < 1:
            return []
        basis = 'bacity_qualified_local_source'
    if len(response.body) > MAX_HTML_BYTES or not hasattr(response, 'text'):
        return []
    if not response.text.lstrip().startswith('<'):
        return []
    reliability = source.reliability_score
    priority = round(100 * min(1, max(0, reliability))) if math.isfinite(reliability) else 0
    result = {}
    for href in response.xpath('(//a/@href)[position() <= 2000]').getall():
        # Relative links belong to the source website, not Instagram. Resolving
        # against the response also supports explicitly declared //instagram URLs.
        try:
            url = profile_url(response.urljoin(href))
        except ValueError:
            continue
        if url:
            result.setdefault(url, ProfileLead(
                url, evidence_url, domain, source.name[:160], source.source_type[:32], basis, priority,
            ))
        if len(result) >= MAX_PROFILES_PER_PAGE:
            break
    return list(result.values())


def record_profiles(db, leads, now=None):
    """Bounded SQLite operational registry; never a public event or source row.

    No access-grant writer or content collector exists in this foundation.
    Existing leads retain up to four independently linked evidence URLs.
    Returns the number of newly registered profiles, not events or observations.
    """
    if not leads:
        return 0
    now = time.time() if now is None else now
    added = 0
    with db:
        db.execute('''CREATE TABLE IF NOT EXISTS instagram_publishers (
            profile_url TEXT PRIMARY KEY, handle TEXT NOT NULL,
            discovered REAL NOT NULL, last_seen REAL NOT NULL,
            priority INTEGER NOT NULL CHECK(priority BETWEEN 0 AND 100),
            evidence TEXT NOT NULL,
            access_eligibility TEXT NOT NULL DEFAULT 'authorization_required'
                CHECK(access_eligibility='authorization_required'),
            last_collection_status TEXT NOT NULL DEFAULT 'not_attempted'
                CHECK(last_collection_status='not_attempted')
        )''')
        count = db.execute('SELECT count(*) FROM instagram_publishers').fetchone()[0]
        for lead in leads[:MAX_PROFILES_PER_PAGE]:
            if profile_url(lead.profile_url) != lead.profile_url:
                raise ValueError('Profile identity must be canonical')
            previous = db.execute(
                'SELECT evidence,priority FROM instagram_publishers WHERE profile_url=?', (lead.profile_url,)
            ).fetchone()
            if not previous and count >= MAX_PUBLISHERS:
                continue
            evidence = json.loads(previous[0]) if previous else []
            entry = {
                'url': lead.evidence_url, 'source_domain': lead.source_domain,
                'source_name': lead.source_name, 'source_role': lead.source_role,
                'relevance_basis': lead.relevance_basis, 'relationship': 'site_declared_profile',
            }
            if entry not in evidence and len(evidence) < MAX_EVIDENCE_PER_PUBLISHER:
                evidence.append(entry)
            if previous:
                db.execute('''UPDATE instagram_publishers SET last_seen=max(last_seen,?),
                    priority=max(priority,?),evidence=? WHERE profile_url=?''',
                    (now, lead.priority, json.dumps(evidence), lead.profile_url))
            else:
                db.execute('''INSERT INTO instagram_publishers
                    (profile_url,handle,discovered,last_seen,priority,evidence) VALUES(?,?,?,?,?,?)''',
                    (lead.profile_url, lead.profile_url.rstrip('/').rsplit('/', 1)[-1],
                     now, now, lead.priority, json.dumps(evidence)))
                added += 1
                count += 1
    return added
