"""Bounded, deterministic public-source lifecycle on existing worker storage."""
import ipaddress
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

STATES = ('discovered', 'inspected', 'probation', 'trusted', 'rejected', 'blocked', 'disabled')


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


def assess(attempts, good_runs, failures, metrics, blocked=False):
    if blocked:
        return 'blocked', 'robots_or_policy'
    if failures >= 3:
        return 'rejected', 'consecutive_failures'
    accepted = metrics.get('quality/events', 0)
    rejected = metrics.get('validation/rejected', 0)
    if not accepted:
        return ('rejected' if attempts >= 3 else 'inspected'), 'no_valid_events'
    if accepted / max(accepted + rejected, 1) < .8:
        return 'probation', 'low_valid_yield'
    mean_quality = metrics.get('quality/score_total', 0) / accepted
    if good_runs >= 3 and mean_quality >= 60:
        return 'trusted', 'three_valid_runs_quality_60'
    return 'probation', 'collecting_quality_evidence'
