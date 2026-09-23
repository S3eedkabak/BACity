"""
Extraction priority level 1-2 (spec section 18): JSON-LD / schema.org
Event blocks. This is the highest-confidence, highest-priority extraction
path — most modern event platforms (and increasingly, venue sites built
on common CMSs) emit this directly, so it should catch a large share of
sources without ever touching heuristics or an LLM.
"""
import json
from typing import Optional

from bs4 import BeautifulSoup

from crawler.items import RawEvent

EVENT_TYPES = {"Event", "MusicEvent", "TheaterEvent", "Festival",
               "SportsEvent", "ExhibitionEvent", "ScreeningEvent",
               "SocialEvent", "EducationEvent", "ComedyEvent"}


def _flatten_jsonld(node):
    """JSON-LD can nest an @graph, or be a list of top-level nodes; flatten both."""
    if isinstance(node, list):
        for item in node:
            yield from _flatten_jsonld(item)
    elif isinstance(node, dict):
        if "@graph" in node:
            yield from _flatten_jsonld(node["@graph"])
        else:
            yield node


def _is_event_type(node: dict) -> bool:
    t = node.get("@type")
    if isinstance(t, list):
        return any(x in EVENT_TYPES for x in t)
    return t in EVENT_TYPES


def _text(value) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get("name") or value.get("@id")
    if isinstance(value, list) and value:
        return _text(value[0])
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
    soup = BeautifulSoup(html, "html.parser")
    results: list[RawEvent] = []

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text()
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
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
                geo = location.get("geo") or {}
                if isinstance(geo, dict):
                    try:
                        latitude = float(geo.get("latitude")) if geo.get("latitude") is not None else None
                        longitude = float(geo.get("longitude")) if geo.get("longitude") is not None else None
                    except (TypeError, ValueError):
                        latitude = longitude = None

            price_raw, currency = _price_from_offers(node.get("offers"))

            results.append(RawEvent(
                title=_text(node.get("name")) or "Untitled event",
                start_raw=_text(node.get("startDate")) or "",
                end_raw=_text(node.get("endDate")),
                description=_text(node.get("description")),
                venue_name=venue_name,
                address=address,
                latitude=latitude,
                longitude=longitude,
                price_raw=f"{price_raw} {currency}".strip() if price_raw else None,
                image_url=_text(node.get("image")),
                source_url=source_url,
                extraction_method="jsonld",
                extraction_confidence=0.95,
            ))

    return results
