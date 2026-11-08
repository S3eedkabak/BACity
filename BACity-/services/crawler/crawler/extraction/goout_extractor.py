"""GoOut feeder API adapter.

The public site is client-rendered, while its event data is available through
the same feeder endpoint used by the site. The adapter is intentionally
schema-tolerant because the feeder response has changed shape over time.
"""
from datetime import datetime
from urllib.parse import urljoin
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
    if isinstance(data, dict) and isinstance(data.get('schedule'), list) and isinstance(data.get('events'), dict):
        return _scheduled_events(data, source_url)
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


def _scheduled_events(data, source_url):
    """Join the publisher's actual schedule/event/venue tables by IDs."""
    results = []
    seen = set()
    venues = data.get('venues') or {}
    for show in data['schedule'][:1000]:
        if not isinstance(show, dict):
            continue
        event = data['events'].get(str(show.get('eventId')), {})
        venue = venues.get(str(show.get('venueId')), {})
        locality = show.get('venueLocality') or venue.get('locality') or {}
        if locality.get('enum') != 'SK_BRATISLAVA' and locality.get('name', '').casefold() != 'bratislava':
            continue
        title = event.get('name')
        start = show.get('startISO8601')
        if not title or not start or not show.get('url') or not venue.get('name'):
            continue
        if show.get('id') in seen:
            continue
        seen.add(show.get('id'))
        end = show.get('endISO8601')
        # GoOut uses 2038 as a sentinel for permanent exhibitions. It is not
        # evidence of a real closing date; ignored clocks are not event times.
        if end and (end.startswith('2038-') or show.get('hourEndIgnored')):
            end = None
        if show.get('hourIgnored'):
            start = start[:10]
        try:
            lat = float(venue['latitude']) if venue.get('latitude') is not None else None
            lng = float(venue['longitude']) if venue.get('longitude') is not None else None
        except (ValueError, TypeError):
            lat = lng = None
        image = (event.get('mainImage') or {}).get('src')
        if image:
            image = urljoin(source_url, image.replace('%%%', '600'))
        results.append(RawEvent(title=title, start_raw=start, end_raw=end,
            description=event.get('textHtml') or event.get('text') or None,
            venue_name=venue['name'], address=', '.join(filter(None,[venue.get('address'),venue.get('city')])),
            latitude=lat, longitude=lng, source_url=urljoin(source_url, show['url']),
            original_source_url=source_url, image_url=image, category_hint=(event.get('category') or {}).get('name') if isinstance(event.get('category'),dict) else event.get('category'),
            event_status='cancelled' if show.get('cancelled') else 'fresh',
            publisher_event_id=str(show.get('eventId')),
            identity_kind='recurring' if any(word in str(event.get('category','')).casefold() for word in ('exhibition','výstav','vystav','market')) else 'single',
            extraction_method='goout_schedule', extraction_confidence=.95, language='en'))
    return results
