from dataclasses import dataclass
import math
from datetime import date, datetime, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from crawler.items import NormalizedEvent

MIN_CONFIDENCE_TO_ACCEPT = 0.3
LOW_CONFIDENCE_THRESHOLD = 0.5
MAX_FUTURE_YEARS = 2


@dataclass
class ValidationResult:
    accepted: bool
    needs_advanced_extraction: bool
    reason: str = ""


def validate_event(event: NormalizedEvent) -> ValidationResult:
    if not event.title or len(event.title.strip()) < 2:
        return ValidationResult(False, False, "missing or too-short title")

    if not event.source_url:
        return ValidationResult(False, False, "missing source_url")

    try:
        start = datetime.fromisoformat(event.start_time)
    except ValueError:
        return ValidationResult(False, False, "unparseable start_time")

    now = datetime.now(start.tzinfo or dt_timezone.utc)
    if start.tzinfo is None:
        return ValidationResult(False, False, "start_time must include timezone")
    end = start
    if event.end_time:
        try:
            end = datetime.fromisoformat(event.end_time)
            if end.tzinfo is None or end < start:
                return ValidationResult(False, False, "invalid end_time")
        except ValueError:
            return ValidationResult(False, False, "invalid end_time")
    date_current = False
    if event.end_date:
        try:
            end_day = date.fromisoformat(event.end_date)
            zone = ZoneInfo(event.timezone)
            if end_day < start.astimezone(zone).date():
                return ValidationResult(False,False,'invalid end_date')
            date_current = end_day >= now.astimezone(zone).date()-timedelta(days=1)
        except (ValueError,ZoneInfoNotFoundError):
            return ValidationResult(False,False,'invalid end_date')
    lifecycle_update = event.event_status in ('cancelled','postponed') and event.extraction_confidence>=.85
    if end < now - timedelta(days=1) and not date_current and not lifecycle_update:
        return ValidationResult(False, False, "start date already in the past")
    if start > now + timedelta(days=365 * MAX_FUTURE_YEARS):
        return ValidationResult(False, False, "start date implausibly far in the future")

    online = "online" in " ".join(
        filter(None, [event.title, event.description, event.venue_name, event.address])
    ).lower()
    if not online and not (event.venue_name or event.address or (event.latitude is not None and event.longitude is not None)):
        return ValidationResult(False, False, "missing location")

    if event.latitude is not None or event.longitude is not None:
        if event.latitude is None or event.longitude is None or not (
            math.isfinite(event.latitude) and math.isfinite(event.longitude)
            and 48.0 <= event.latitude <= 48.35 and 16.9 <= event.longitude <= 17.35
        ):
            return ValidationResult(False, False, "coordinates outside Bratislava")

    if event.extraction_confidence < MIN_CONFIDENCE_TO_ACCEPT:
        return ValidationResult(False, False, "extraction confidence too low")

    needs_advanced = event.extraction_confidence < LOW_CONFIDENCE_THRESHOLD
    return ValidationResult(True, needs_advanced, "ok")
