from typing import Optional
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode, urljoin
from bs4 import BeautifulSoup
from html import unescape

from crawler.items import NormalizedEvent, RawEvent
from crawler.extraction.date_parser import parse_event_datetime, parse_price

CATEGORY_KEYWORDS = {
    "Festivals": ["festival"],
    "Community": ["community", "komunit"],
    "Student": ["student", "študent", "univerzita", "university"],
    "Comedy": ["comedy", "standup", "stand-up", "komédia"],
    "Theatre": ["divadlo", "theatre", "theater", "drama", "činohra", "opera", "balet"],
    "Sports": ["sport", "šport", "run", "marathon", "tournament"],
    "Family": ["family", "rodina", "kids", "deti", "detské"],
    "Markets": ["market", "trh", "trhy"],
    "Workshops": ["workshop", "dielňa", "dielna", "seminar"],
    "Food & Drink": ["food", "wine", "beer", "tasting", "degustácia", "degustacia"],
    "Culture": ["kultúra", "kultura", "culture", "exhibition", "výstava", "vystava"],
    "Music": ["concert", "jazz", "rock", "metal", "gig", "band", "koncert"],
    "Nightlife": ["techno", "house", "club", "party", "night", "dj"],
}


def clean_text(value):
    if not value:
        return None
    if '<' not in value:
        return ' '.join(unescape(value).split())
    soup = BeautifulSoup(value, "html.parser")
    for node in soup(['script', 'style']):
        node.decompose()
    return ' '.join(soup.get_text(' ', strip=True).split())


def clean_url(value):
    if not value:
        return value
    url = urlsplit(value)
    if url.scheme not in ('http', 'https') or not url.hostname:
        return ''
    query = [(k, v) for k, v in parse_qsl(url.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in ('fbclid', 'gclid', 'mc_cid', 'mc_eid')]
    return urlunsplit((url.scheme.lower(), url.netloc.lower(), url.path or '/', urlencode(query), ''))


def guess_category(title: str, description: Optional[str], hint: Optional[str]) -> str:
    haystack = " ".join(filter(None, [title, description, hint])).lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in haystack for keyword in keywords):
            return category
    return "Other"


def normalize_event(
    raw: RawEvent, *, default_timezone: str = "Europe/Bratislava"
) -> Optional[NormalizedEvent]:
    start_dt = parse_event_datetime(raw.start_raw)
    if start_dt is None:
        return None

    end_dt = parse_event_datetime(raw.end_raw) if raw.end_raw else None
    price, currency = parse_price(raw.price_raw)

    return NormalizedEvent(
        title=clean_text(raw.title) or '',
        start_time=start_dt.isoformat(),
        end_time=end_dt.isoformat() if end_dt else None,
        timezone=default_timezone,
        description=clean_text(raw.description),
        venue_name=clean_text(raw.venue_name),
        address=clean_text(raw.address),
        latitude=raw.latitude,
        longitude=raw.longitude,
        price=price,
        currency=currency,
        image_url=clean_url(urljoin(raw.source_url, raw.image_url)) if raw.image_url else None,
        category=guess_category(raw.title, raw.description, ' '.join(filter(None, [raw.category_hint, raw.venue_name]))),
        tags=list(dict.fromkeys(raw.tags + [category.lower() for category, words in CATEGORY_KEYWORDS.items() if any(word in ' '.join(filter(None, [raw.title, raw.description, raw.venue_name, raw.category_hint])).lower() for word in words)])),
        language=raw.language,
        source_url=clean_url(raw.source_url),
        source_name=raw.source_name,
        source_reliability=raw.source_reliability,
        extraction_confidence=raw.extraction_confidence,
        event_status=raw.event_status,
        original_source_url=raw.original_source_url or raw.source_url,
    )
