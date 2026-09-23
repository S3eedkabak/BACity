"""GoOut feeder API adapter.

The public site is client-rendered, while its event data is available through
the same feeder endpoint used by the site. The adapter is intentionally
schema-tolerant because the feeder response has changed shape over time.
"""
from datetime import datetime
from typing import Any

from crawler.items import RawEvent


def _first(obj: dict, *keys):
    for key in keys:
        value = obj.get(key)
        if value not in (None, ""):
            return value
    return None


def _flatten_events(value: Any):
    if isinstance(value, list):
        for item in value:
            yield from _flatten_events(item)
    elif isinstance(value, dict):
        if _first(value, "title", "name", "eventName") and _first(
            value, "start", "startDate", "startsAt", "date", "dates"
        ):
            yield value
        else:
            for child in value.values():
                yield from _flatten_events(child)


def _location(event: dict):
    location = _first(event, "location", "venue", "place")
    if isinstance(location, str):
        return location, None
    if isinstance(location, dict):
        return (
            _first(location, "name", "title", "venueName"),
            _first(location, "address", "addressLine", "street"),
        )
    return None, None


def extract_goout_events(data: Any, source_url: str) -> list[RawEvent]:
    results = []
    seen = set()

    for event in _flatten_events(data):
        title = _first(event, "title", "name", "eventName")
        start = _first(event, "startDate", "start", "startsAt", "date")
        end = _first(event, "endDate", "end", "endsAt")
        if isinstance(start, dict):
            start = _first(start, "date", "start", "value")
        if isinstance(end, dict):
            end = _first(end, "date", "end", "value")
        if not isinstance(title, str) or not isinstance(start, str):
            continue

        venue, address = _location(event)
        key = (title.strip().lower(), start.strip())
        if key in seen:
            continue
        seen.add(key)

        results.append(
            RawEvent(
                title=title.strip(),
                start_raw=start.strip(),
                end_raw=end.strip() if isinstance(end, str) else None,
                description=_first(event, "description", "summary"),
                venue_name=venue,
                address=address,
                image_url=_first(event, "image", "imageUrl", "image_url"),
                source_url=source_url,
                extraction_method="goout_feeder",
                extraction_confidence=0.9 if venue else 0.75,
                language="en",
            )
        )

    return results
