"""Local-time eligibility and shared-signal ranking for Tonight / Right Now."""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from enum import Enum
from math import ceil
from zoneinfo import ZoneInfo

from app.core.recommendations import RecommendationContext, rank_events

SOON_WINDOW = timedelta(hours=2)
TONIGHT_START = time(17, 0)
TONIGHT_END = time(3, 0)
MAX_CANDIDATES = 500
MAX_RESULTS = 12
SECTION_LIMITS = {
    "happening_now": 4,
    "starting_soon": 4,
    "later_tonight": 6,
}


class TonightClassification(str, Enum):
    happening_now = "happening_now"
    starting_soon = "starting_soon"
    later_tonight = "later_tonight"


@dataclass(frozen=True)
class TonightWindow:
    timezone: str
    now_utc: datetime
    starts_at_utc: datetime
    ends_at_utc: datetime
    soon_ends_at_utc: datetime


@dataclass(frozen=True)
class TonightRankedEvent:
    event: object
    classification: TonightClassification
    reasons: tuple[str, ...]


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _local_to_utc_naive(day: date, value: time, zone: ZoneInfo) -> datetime:
    return datetime.combine(day, value, tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)


def tonight_window(now: datetime, timezone_name: str) -> TonightWindow:
    zone = ZoneInfo(timezone_name)
    now_utc = _utc_naive(now)
    local_now = now_utc.replace(tzinfo=timezone.utc).astimezone(zone)
    anchor = local_now.date() - timedelta(days=1) if local_now.time() < TONIGHT_END else local_now.date()
    starts_at = _local_to_utc_naive(anchor, TONIGHT_START, zone)
    ends_at = _local_to_utc_naive(anchor + timedelta(days=1), TONIGHT_END, zone)
    return TonightWindow(
        timezone=timezone_name,
        now_utc=now_utc,
        starts_at_utc=starts_at,
        ends_at_utc=ends_at,
        soon_ends_at_utc=now_utc + SOON_WINDOW,
    )


def classify_event(event, window: TonightWindow) -> TonightClassification | None:
    start = _utc_naive(event.start_time)
    end = _utc_naive(event.end_time) if event.end_time else None
    if end and end <= start:
        return None
    in_evening_now = window.starts_at_utc <= window.now_utc < window.ends_at_utc
    if in_evening_now and end and start < window.ends_at_utc and start <= window.now_utc < end:
        return TonightClassification.happening_now
    if start <= window.now_utc:
        # An unknown end time can never prove that a started event is still underway.
        return None
    if end and end <= window.now_utc:
        return None
    if not window.starts_at_utc <= start < window.ends_at_utc:
        return None
    if start <= window.soon_ends_at_utc:
        return TonightClassification.starting_soon
    return TonightClassification.later_tonight


def _temporal_reason(event, classification: TonightClassification, window: TonightWindow) -> str:
    if classification == TonightClassification.happening_now:
        return "Happening now"
    if classification == TonightClassification.starting_soon:
        minutes = max(1, ceil((_utc_naive(event.start_time) - window.now_utc).total_seconds() / 60))
        return f"Starts in {minutes} min"
    return "Later tonight"


def rank_tonight_events(events, context: RecommendationContext, window: TonightWindow) -> list[TonightRankedEvent]:
    classifications = {event.id: classify_event(event, window) for event in events}
    eligible = [event for event in events if classifications[event.id] is not None]
    temporal_scores = {
        TonightClassification.happening_now: 4.0,
        TonightClassification.starting_soon: 3.0,
        TonightClassification.later_tonight: 1.0,
    }

    def temporal_signal(event):
        classification = classifications[event.id]
        return temporal_scores[classification], (_temporal_reason(event, classification, window),)

    ranked = rank_events(
        eligible,
        context,
        now=window.now_utc,
        include_started=True,
        include_timing_signal=False,
        additional_signal=temporal_signal,
        max_reasons=6,
    )
    counts = {classification: 0 for classification in TonightClassification}
    results: list[TonightRankedEvent] = []
    for item in ranked:
        classification = classifications[item.event.id]
        if counts[classification] >= SECTION_LIMITS[classification.value]:
            continue
        counts[classification] += 1
        reasons = tuple(reason for reason in item.reasons if reason != "Matches your interests")[:3]
        results.append(TonightRankedEvent(item.event, classification, reasons))
        if len(results) == MAX_RESULTS:
            break
    return results
