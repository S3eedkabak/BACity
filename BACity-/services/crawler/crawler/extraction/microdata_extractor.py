"""Schema.org microdata fallback for sites without JSON-LD."""
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from crawler.items import RawEvent


def extract_microdata_events(html, source_url):
    soup = BeautifulSoup(html, 'html.parser')
    scopes = soup.select('[itemscope][itemtype$="Event"]')
    if not scopes and soup.select_one('[itemprop="startDate"]'):
        scopes = [soup]
    events = []
    for scope in scopes:
        def value(prop):
            tag = scope.select_one(f'[itemprop="{prop}"]')
            if tag:
                return tag.get('content') or tag.get('datetime') or tag.get('href') or tag.get('src') or tag.get_text(' ', strip=True)
            return None
        start = value('startDate')
        title_tag = scope.select_one('h1, h2, [itemprop="name"]')
        if not start or not title_tag:
            continue
        location = scope.select_one('[itemprop="location"]')
        name = location.select_one('[itemprop="name"]') if location else None
        venue = name.get_text(' ', strip=True) if name else (location.get_text(' ', strip=True) if location else None)
        lat = lng = None
        try:
            if value('latitude') and value('longitude'):
                lat, lng = float(value('latitude')), float(value('longitude'))
        except ValueError:
            pass
        image = value('image')
        events.append(RawEvent(title=title_tag.get_text(' ', strip=True), start_raw=start, end_raw=value('endDate'),
                               description=value('description'), venue_name=venue, address=value('address'),
                               latitude=lat, longitude=lng, image_url=urljoin(source_url, image) if image else None,
                               price_raw=' '.join(filter(None, [value('price'), value('priceCurrency')])),
                               source_url=source_url, extraction_method='microdata', extraction_confidence=.85))
    return events
