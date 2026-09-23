from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone

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
    if start < now - timedelta(days=1):
        return ValidationResult(False, False, "start date already in the past")
    if start > now + timedelta(days=365 * MAX_FUTURE_YEARS):
        return ValidationResult(False, False, "start date implausibly far in the future")

    online = "online" in " ".join(
        filter(None, [event.title, event.description, event.venue_name, event.address])
    ).lower()
    if not online and not (event.venue_name or event.address):
        return ValidationResult(False, False, "missing location")

    if event.extraction_confidence < MIN_CONFIDENCE_TO_ACCEPT:
        return ValidationResult(False, False, "extraction confidence too low")

    needs_advanced = event.extraction_confidence < LOW_CONFIDENCE_THRESHOLD
    return ValidationResult(True, needs_advanced, "ok")
