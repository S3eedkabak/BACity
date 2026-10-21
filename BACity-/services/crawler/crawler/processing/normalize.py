import re
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
    "Culture": ["kultúra", "kultura", "culture", "exhibition", "výstava", "vystava", "film", "cinema", "premietanie", "documentary"],
    "Music": ["concert", "jazz", "rock", "metal", "gig", "band", "koncert"],
    "Nightlife": ["techno", "house music", "house party", "party", "nightclub", "dj", "clubbing", "rave", "clubnight"],
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
    # Publisher taxonomy and title outrank prose; venues never supply taxonomy.
    canonical={name.casefold():name for name in [*CATEGORY_KEYWORDS,'Arts','Exhibitions','Education','Networking','Technology','Other']}
    if (hint or '').strip().casefold() in canonical:
        return canonical[hint.strip().casefold()]
    def matching(value):
        value = (value or '').casefold()
        for category, keywords in CATEGORY_KEYWORDS.items():
            if any(re.search(r'(?<!\w)' + re.escape(keyword) + r'\w*', value) for keyword in keywords):
                return category
    exhibition = r'(?<!\w)(exhibition|výstav|vystav|expozíci|expozici)\w*'
    for value in (hint, title):
        if re.search(r'(?<!\w)(workshop|dielňa|dielna|seminar)\w*',(value or '').casefold()):
            return 'Workshops'
        if re.search(exhibition, (value or '').casefold()):
            return 'Exhibitions'
        result = matching(value)
        if result:
            return result
    if re.search(exhibition, (description or '').casefold()):
        return 'Exhibitions'
    return matching(description) or 'Other'


def normalize_event(
    raw: RawEvent, *, default_timezone: str = "Europe/Bratislava"
) -> Optional[NormalizedEvent]:
    from crawler.extraction.temporal import interval
    date_end = raw.end_date_raw or (raw.end_raw if re.fullmatch(r'\d{4}-\d{2}-\d{2}', raw.end_raw or '') else None)
    start_dt, end_dt, temporal_evidence = interval(raw.start_raw, None if date_end else raw.end_raw, raw.duration_raw)
    if date_end and end_dt is None:
        temporal_evidence = 'date_range'
    if start_dt is None:
        return None
    if end_dt and end_dt.year==2038 and end_dt.month==end_dt.day==1 and start_dt.year in (2000,2016):
        end_dt=None;temporal_evidence='unknown'


    if start_dt.year in (2000,2016) and start_dt.month==start_dt.day==1 and ((end_dt and end_dt.year>=2030) or (date_end and date_end[:4]>='2030')):
        end_dt=None;date_end=None;temporal_evidence='unknown'

    price, currency = parse_price(raw.price_raw)
    previous = parse_event_datetime(raw.previous_start_raw) if raw.previous_start_raw else None

    category=guess_category(raw.title,raw.description,raw.category_hint)
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
        category=category,
        tags=list(dict.fromkeys(raw.tags+[category.casefold()])),
        language=raw.language,
        source_url=clean_url(raw.source_url),
        source_name=raw.source_name,
        source_reliability=raw.source_reliability,
        extraction_confidence=raw.extraction_confidence,
        event_status='cancelled' if re.match(r'^(cancelled|canceled|zrušené|zrusene)\s*(?://|:|[-–])',raw.title,re.I) else raw.event_status,
        original_source_url=raw.original_source_url or raw.source_url,
        temporal_evidence=temporal_evidence, extraction_method=raw.extraction_method,
        organizer_name=clean_text(raw.organizer_name),
        previous_start_time=previous.isoformat() if previous else None,
        end_date=date_end,
        publisher_event_id=raw.publisher_event_id, identity_kind=raw.identity_kind, recurrence_rule=raw.recurrence_rule,
        start_precision="date" if re.fullmatch(r"\d{4}-\d{2}-\d{2}",raw.start_raw or "") else "time",
    )
