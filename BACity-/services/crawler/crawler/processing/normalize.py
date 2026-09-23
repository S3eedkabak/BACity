from typing import Optional

from crawler.items import NormalizedEvent, RawEvent
from crawler.extraction.date_parser import parse_event_datetime, parse_price

CATEGORY_KEYWORDS = {
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
        title=raw.title.strip(),
        start_time=start_dt.isoformat(),
        end_time=end_dt.isoformat() if end_dt else None,
        timezone=default_timezone,
        description=raw.description.strip() if raw.description else None,
        venue_name=raw.venue_name.strip() if raw.venue_name else None,
        address=raw.address.strip() if raw.address else None,
        latitude=None,
        longitude=None,
        price=price,
        currency=currency,
        image_url=raw.image_url,
        category=guess_category(raw.title, raw.description, raw.category_hint),
        tags=raw.tags,
        language=raw.language,
        source_url=raw.source_url,
        source_name=raw.source_name,
        source_reliability=raw.source_reliability,
        extraction_confidence=raw.extraction_confidence,
    )
