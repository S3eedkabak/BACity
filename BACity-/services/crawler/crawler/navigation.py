"""Source-specific navigation constraints and normalized public URL identity."""
import re
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit, urlunsplit
from crawler.processing.normalize import clean_url


def navigation_url(url, domain):
    url = clean_url(url)
    p = urlsplit(url)
    if domain == 'sng.sk':
        # Publisher-rendered absolute hrefs duplicate the current path before
        # an already-rooted /en/... path. Keep only the event path at the end.
        match = re.search(r'/en/slovak-national-gallery/events/[^/]+/?$', p.path)
        if not match:
            return None
        return urlunsplit((p.scheme,p.netloc,match[0],p.query,''))
    if domain == 'visitbratislava.com':
        if p.path == '/events/recommended/' or not re.match(r'^/(?:events|event)(?:/|$)',p.path):
            return None
    if domain == 'novacvernovka.eu':
        if not p.path.startswith('/program') or '/archiv' in p.path:
            return None
    if domain == 'staratrznica.sk':
        if not p.path.startswith('/sk/program'):
            return None
        day=re.search(r'/(\d{4}-\d{2}-\d{2})/?$',p.path)
        if day and date.fromisoformat(day[1]) < datetime.now(ZoneInfo('Europe/Bratislava')).date()-timedelta(days=1):
            return None
    if domain == 'bratislava.sk' and not p.path.startswith('/kultura-a-komunity/podujatia'):
        return None
    if domain == 'bkis.sk' and not p.path.startswith(('/podujatia', '/udalost/')):
        return None
    if domain == 'a4.sk' and not p.path.startswith('/events/'):
        return None
    return url


def is_detail(url, domain):
    path = urlsplit(url).path.rstrip('/')
    if domain == 'novacvernovka.eu':
        return path.startswith('/program/')
    if domain == 'visitbratislava.com':
        return bool(re.fullmatch(r'/events/(?!page/)[^/]+',path))
    if domain == 'sng.sk':
        return '/events/' in path
    if domain == 'staratrznica.sk':
        return bool(re.fullmatch(r'/sk/program/[^/]+/\d{4}-\d{2}-\d{2}',path))
    if domain == 'a4.sk':
        return bool(re.fullmatch(r'/events/\d{4}/\d{2}/\d{2}/[^/]+',path))
    if domain == 'bkis.sk':
        return path.startswith('/udalost/')
    return False
