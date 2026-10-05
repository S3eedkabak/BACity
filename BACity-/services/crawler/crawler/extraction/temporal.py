"""Explicit source intervals only; unknown duration remains unknown."""
import re
from datetime import datetime, timedelta
import pytz
from crawler.extraction.date_parser import parse_event_datetime

CLOCK = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*(?:h|hod\.?|hodín)?\s*$")
RANGE = re.compile(r"(?P<a>\d{1,2}[:.]\d{2})\s*(?:–|—|-|až)\s*(?P<b>\d{1,2}[:.]\d{2})(?!\d)")
DURATION = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


def _clock(value, start):
    match = CLOCK.fullmatch(value or '')
    if not match:
        return None
    start = start.astimezone(pytz.timezone('Europe/Bratislava'))
    local = start.replace(tzinfo=None, hour=int(match[1]), minute=int(match[2]), second=0, microsecond=0)
    if local < start.replace(tzinfo=None):
        local += timedelta(days=1)
    return pytz.timezone('Europe/Bratislava').localize(local, is_dst=None)


def interval(start_raw, end_raw=None, duration_raw=None):
    start = None
    try:
        parts = re.split(r'\s+(?:–|—|-|až)\s+', start_raw, maxsplit=1)
        start = parse_event_datetime(parts[0])
        if not start:
            # Preserve existing shared-month date ranges ("2. – 4. októbra").
            # A calendar date alone does not supply an actual closing clock.
            start = parse_event_datetime(start_raw)
        if not start:
            return None, None, 'unknown'
        end, evidence = None, 'unknown'
        if end_raw:
            end = _clock(end_raw, start) if CLOCK.fullmatch(end_raw) else parse_event_datetime(end_raw)
            evidence = 'explicit_end'
        else:
            # Do not mine descriptions: opening hours/doors times are not event durations.
            parts = re.split(r'\s+(?:–|—|-|až)\s+', start_raw, maxsplit=1)
            time_range = RANGE.search(start_raw)
            if len(parts) == 2 and not CLOCK.fullmatch(parts[1]) and re.search(r'\d{1,2}[:.]\d{2}',parts[1]):
                end = parse_event_datetime(parts[1])
                evidence = 'text_range'
            elif time_range:
                end = _clock(time_range['b'], start)
                evidence = 'text_range'
            elif duration_raw:
                match = DURATION.fullmatch(duration_raw)
                if match and any(match.groups()):
                    duration = timedelta(days=int(match[1] or 0), hours=int(match[2] or 0),
                                         minutes=int(match[3] or 0), seconds=int(match[4] or 0))
                    if timedelta(0) < duration <= timedelta(days=31):
                        end = start + duration
                        evidence = 'explicit_duration'
        if end is not None and end <= start:
            end, evidence = None, 'invalid_end'
        return start, end, evidence
    except (ValueError, OverflowError, TypeError, pytz.InvalidTimeError):
        return start, None, 'invalid_local_time'
