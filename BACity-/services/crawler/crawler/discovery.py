"""Bounded, deterministic public-source lifecycle on existing worker storage."""
import ipaddress
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

STATES = ('discovered', 'inspected', 'probation', 'trusted', 'degraded', 'rejected', 'blocked', 'disabled')


def candidate_url(value):
    from crawler.spiders.discovery import allowed_url
    if len(value) > 2048 or not allowed_url(value):
        raise ValueError('url_policy')
    url = urlsplit(value)
    host = (url.hostname or '').lower().rstrip('.')
    if '.' not in host or host.endswith(('.local', '.internal', '.localhost')):
        raise ValueError('non_public_host')
    try:
        if not ipaddress.ip_address(host).is_global:
            raise ValueError('non_public_address')
    except ValueError as exc:
        if str(exc) == 'non_public_address':
            raise
    query = []
    for key, val in parse_qsl(url.query):
        if key.lower() in ('token', 'key', 'password', 'auth', 'signature', 'access_token'):
            raise ValueError('credential_url')
        if not key.lower().startswith('utm_') and key.lower() not in ('fbclid', 'gclid'):
            query.append((key, val))
    return host.removeprefix('www.'), urlunsplit((url.scheme.lower(), host, url.path or '/', urlencode(sorted(query)), ''))


def endpoint_rank(url):
    """Rank only URL evidence already linked by a public event source."""
    path = urlsplit(url).path.lower().rstrip('/')
    if path.endswith(('.ics','.rss','.atom')) or any(x in path for x in ('/feed','/rss','/ical')):
        return 100
    if path.split('/')[-1] in ('events','event','program','calendar','podujatia','agenda'):
        return 80
    return 40
