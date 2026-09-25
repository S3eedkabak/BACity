"""Visit Bratislava's event microdata; dates and clock times are separate fields."""
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from crawler.items import RawEvent


def extract_visit_events(html, source_url):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.select_one('h1[itemprop="name"], h1.title')
    date = soup.select_one('.event-date .start-date')
    if not title or not date:
        return []
    start_day = (date.get('content') or '')[:10]
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', start_day):
        return []
    clock = soup.select_one('.event-date .start-time')
    start = start_day + 'T' + (clock.get_text(strip=True) if clock else '00:00')
    end_date = soup.select_one('.event-date .end-date')
    end_clock = soup.select_one('.event-date .end-time')
    end = None
    if end_date:
        end_day = (end_date.get('content') or '')[:10]
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', end_day) and (end_clock or end_day > start_day):
            end = end_day + 'T' + (end_clock.get_text(strip=True) if end_clock else '23:59')
    place = soup.select_one('li.address .value')
    desc = soup.select_one('[itemprop="description"] .content, [itemprop="description"]')
    price = soup.select_one('.price .value, li.price')
    geo = soup.select_one('#osm-map')
    lat = lng = None
    if geo:
        try:
            lat, lng = float(geo.get('data-lat')), float(geo.get('data-lng'))
        except (ValueError, TypeError):
            pass
    poster = soup.select_one('.poster [style]')
    image = None
    if poster:
        match = re.search(r'url\([\s\"\']?([^\)\"\']+)', poster.get('style', ''))
        if match:
            image = urljoin(source_url, match.group(1))
    return [RawEvent(title=title.get_text(' ', strip=True), start_raw=start, end_raw=end,
                     venue_name=place.get_text(' ', strip=True) if place else None,
                     address=geo.get('data-address') or None if geo else None,
                     latitude=lat, longitude=lng, description=desc.get_text(' ', strip=True) if desc else None,
                     price_raw=price.get_text(' ', strip=True) if price else None,
                     image_url=image, source_url=source_url, extraction_method='visit_microdata', extraction_confidence=.9)]
