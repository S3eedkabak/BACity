"""
Extraction priority level 1-2 (spec section 18): JSON-LD / schema.org
Event blocks. This is the highest-confidence, highest-priority extraction
path — most modern event platforms (and increasingly, venue sites built
on common CMSs) emit this directly, so it should catch a large share of
sources without ever touching heuristics or an LLM.
"""
import json
from urllib.parse import urljoin
from typing import Optional

from bs4 import BeautifulSoup

from crawler.items import RawEvent

EVENT_TYPES = {"Event", "MusicEvent", "TheaterEvent", "Festival",
               "SportsEvent", "ExhibitionEvent", "ScreeningEvent",
               "SocialEvent", "EducationEvent", "ComedyEvent"}

MAX_EVENTS = 100
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_DEPTH = 64
MAX_NODES = 10000


def _flatten_jsonld(node):
    """Bounded iterative traversal: hostile nesting must not exhaust recursion."""
    stack = [(node, 0)]
    visited = 0
    while stack and visited < MAX_NODES:
        node, depth = stack.pop()
        visited += 1
        if depth > MAX_DEPTH:
            continue
        if isinstance(node, dict):
            if _is_event_type(node):
                yield node
            children = list(node.values())
        elif isinstance(node, list):
            children = node
        else:
            continue
        # Preserve source order while bounding queued work as well as visits.
        remaining = MAX_NODES - visited - len(stack)
        stack.extend((child, depth + 1) for child in reversed(children[:max(0, remaining)])
                     if isinstance(child, (dict, list)))


def _is_event_type(node: dict) -> bool:
    t = node.get("@type")
    if isinstance(t, list):
        return any(isinstance(x, str) and x.rsplit('/', 1)[-1] in EVENT_TYPES for x in t)
    return isinstance(t, str) and t.rsplit('/', 1)[-1] in EVENT_TYPES


def _text(value) -> Optional[str]:
    for _ in range(MAX_DEPTH):
        if not isinstance(value, list):
            break
        value = value[0] if value else None
    else:
        return None
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("name") or value.get("url") or value.get("contentUrl") or value.get("@id")
    return str(value)


def _price_from_offers(offers) -> tuple[Optional[str], Optional[str]]:
    if not offers:
        return None, None
    if isinstance(offers, list) and offers:
        offers = offers[0]
    if not isinstance(offers, dict):
        return None, None
    price = offers.get("price")
    currency = offers.get("priceCurrency")
    return (str(price) if price is not None else None, currency)


def extract_jsonld_events(html: str, source_url: str) -> list[RawEvent]:
    """Parse every <script type="application/ld+json"> block on a page and
    return one RawEvent per schema.org Event node found."""
    if len(html.encode('utf-8')) > 5 * 1024 * 1024:
        return []
    soup = BeautifulSoup(html, "html.parser")
    results: list[RawEvent] = []

    total_bytes = 0
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}, limit=32):
        raw = tag.string or tag.get_text()
        if not raw or not raw.strip():
            continue
        total_bytes += len(raw.encode('utf-8'))
        if total_bytes > MAX_JSON_BYTES:
            break
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError, RecursionError):
            continue

        for node in _flatten_jsonld(data):
            if not isinstance(node, dict) or not _is_event_type(node):
                continue

            location = node.get("location") or {}
            if isinstance(location, list) and location:
                location = location[0]
            venue_name = _text(location) if isinstance(location, dict) else _text(location)
            address = None
            latitude = None
            longitude = None
            if isinstance(location, dict):
                addr = location.get("address")
                address = _text(addr)
                if isinstance(addr, dict):
                    address = ', '.join(str(addr[k]) for k in ('streetAddress', 'postalCode', 'addressLocality', 'addressRegion') if addr.get(k)) or address
                geo = location.get("geo") or {}
                if isinstance(geo, dict):
                    try:
                        latitude = float(geo.get("latitude")) if geo.get("latitude") is not None else None
                        longitude = float(geo.get("longitude")) if geo.get("longitude") is not None else None
                    except (TypeError, ValueError):
                        latitude = longitude = None

            price_raw, currency = _price_from_offers(node.get("offers"))

            results.append(RawEvent(
                title=_text(node.get("name")) or "",
                start_raw=_text(node.get("startDate")) or "",
                end_raw=_text(node.get("endDate")), duration_raw=_text(node.get("duration")),
                organizer_name=_text(node.get("organizer")),
                previous_start_raw=_text(node.get('previousStartDate')),
                description=_text(node.get("description")),
                venue_name=venue_name,
                address=address,
                latitude=latitude,
                longitude=longitude,
                price_raw="0 EUR" if node.get("isAccessibleForFree") is True else (f"{price_raw} {currency or 'EUR'}".strip() if price_raw is not None else None),
                image_url=urljoin(source_url, _text(node.get("image"))) if _text(node.get("image")) else None,
                source_url=urljoin(source_url, _text(node.get("url")) or source_url),
                original_source_url=source_url,
                # Postponed is uncertain, not removed. A later crawl can supply the
                # replacement date without losing the original provenance.
                event_status={'EventCancelled': 'cancelled', 'EventPostponed': 'stale'}.get(str(node.get('eventStatus', '')).rsplit('/', 1)[-1], 'fresh'),
                extraction_method="jsonld",
                extraction_confidence=0.95,
            ))
            if len(results) >= MAX_EVENTS:
                return results

    return results
