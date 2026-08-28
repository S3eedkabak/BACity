"""
Validation stage (spec section 18-19 flow: confidence -> accept / advanced
extraction). Rejects events that are structurally unusable and flags
low-confidence ones for the (currently-stubbed) LLM specialist path rather
than dropping them outright.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone as dt_timezone

from crawler.items import NormalizedEvent

MIN_CONFIDENCE_TO_ACCEPT = 0.3
LOW_CONFIDENCE_THRESHOLD = 0.5   # below this -> route to advanced/LLM extraction
MAX_FUTURE_YEARS = 2


@dataclass
class ValidationResult:
    accepted: bool
    needs_advanced_extraction: bool
    reason: str = ""


def validate_event(event: NormalizedEvent) -> ValidationResult:
    if not event.title or len(event.title.strip()) < 2:
        return ValidationResult(False, False, "missing or too-short title")

    try:
        start = datetime.fromisoformat(event.start_time)
    except ValueError:
        return ValidationResult(False, False, "unparseable start_time")

    now = datetime.now(start.tzinfo or dt_timezone.utc)
    if start < now - timedelta(days=1):
        return ValidationResult(False, False, "start date already in the past")
    if start > now + timedelta(days=365 * MAX_FUTURE_YEARS):
        return ValidationResult(False, False, "start date implausibly far in the future")

    if event.extraction_confidence < MIN_CONFIDENCE_TO_ACCEPT:
        return ValidationResult(False, False, "extraction confidence too low")

    needs_advanced = event.extraction_confidence < LOW_CONFIDENCE_THRESHOLD
    return ValidationResult(True, needs_advanced, "ok")
