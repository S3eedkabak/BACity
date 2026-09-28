"""Deterministic, explainable recommendation ranking for upcoming events."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import asin, cos, log1p, radians, sin, sqrt
from typing import Callable
import re
import unicodedata


@dataclass(frozen=True)
class RecommendationContext:
    interests: frozenset[str]
    saved_categories: frozenset[str]
    following: frozenset[tuple[str, str]]
    save_counts: dict
    saved_event_ids: frozenset
    latitude: float | None = None
    longitude: float | None = None


@dataclass(frozen=True)
class RankedEvent:
    event: object
    score: float
    reasons: tuple[str, ...]


def _category(event) -> str:
    return getattr(event.category, "value", event.category)


def _normalized(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "").casefold()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def _duplicate_key(event) -> tuple:
    place = str(event.venue_id) if event.venue_id else _normalized(event.address)
    time_bucket = (event.start_time.date(), event.start_time.hour // 2)
    return (_normalized(event.title), time_bucket, place)


def _distance_km(latitude: float, longitude: float, event) -> float | None:
    if event.latitude is None or event.longitude is None:
        return None
    lat1, lat2 = radians(latitude), radians(event.latitude)
    delta_lat = lat2 - lat1
    delta_lng = radians(event.longitude - longitude)
    root = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lng / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(root))


def _follow_reasons(event, following: frozenset[tuple[str, str]]) -> list[str]:
    candidates = [
        ("organizer", event.organization_id, "From an organizer you follow"),
        ("venue", event.venue_id, "From a venue you follow"),
        ("neighborhood", event.neighborhood, "In a neighborhood you follow"),
        ("category", _category(event), f"Because you follow {_category(event)}"),
        ("guide", event.contributor_id, "From a local guide you follow"),
        ("user", event.contributor_id, "From someone you follow"),
    ]
    return [reason for kind, value, reason in candidates
            if value is not None and (kind, str(value).casefold()) in following]


def rank_events(
    events,
    context: RecommendationContext,
    *,
    now: datetime | None = None,
    include_started: bool = False,
    include_timing_signal: bool = True,
    additional_signal: Callable[[object], tuple[float, tuple[str, ...]]] | None = None,
    max_reasons: int = 3,
) -> list[RankedEvent]:
    """Rank, suppress near-duplicates, and diversify a bounded candidate set."""
    now = now or datetime.utcnow()
    scored: list[RankedEvent] = []
    for event in events:
        status = str(getattr(event.status, "value", event.status))
        if (event.start_time < now and not include_started) or status not in {"fresh", "stale"}:
            continue
        score = 0.0
        reasons: list[str] = []
        category = _category(event)
        category_key = category.casefold()
        tags = {str(tag).casefold(): str(tag) for tag in (event.tags or [])}

        matched_interest = category if category_key in context.interests else next(
            (label for key, label in tags.items() if key in context.interests), None
        )
        if matched_interest:
            score += 5.0
            reasons.append("Matches your interests")
            reasons.append(f"Based on your interest in {matched_interest}")

        if category_key in context.saved_categories:
            score += 2.0
            reasons.append("Because you saved similar events")

        follow_reasons = _follow_reasons(event, context.following)
        if follow_reasons:
            score += min(5.0, 4.0 + 0.5 * (len(follow_reasons) - 1))
            reasons.extend(follow_reasons[:1])

        distance = None
        if context.latitude is not None and context.longitude is not None:
            distance = _distance_km(context.latitude, context.longitude, event)
            if distance is not None:
                if distance <= 2:
                    score += 3.0
                    reasons.append("Near you")
                elif distance <= 5:
                    score += 2.0
                    reasons.append("Near you")
                elif distance <= 10:
                    score += 1.0
                elif distance > 20:
                    score -= min(2.5, (distance - 20) / 10)

        if include_timing_signal:
            until = event.start_time - now
            if until <= timedelta(days=3):
                score += 1.5
                reasons.append("Happening soon")
            elif until <= timedelta(days=7):
                score += 1.0
                reasons.append("Happening this week")

        if event.created_at and event.created_at >= now - timedelta(days=3):
            score += 0.75
            reasons.append("New in BACity")

        quality = (float(event.extraction_confidence or 0) + float(event.source_reliability or 0)) / 2
        score += max(0.0, min(1.0, quality)) * 0.8

        unique_saves = max(0, int(context.save_counts.get(event.id, 0)))
        score += min(1.5, log1p(unique_saves) * 0.45)
        if unique_saves >= 2:
            reasons.append("Popular nearby" if distance is not None and distance <= 8 else "Popular in Bratislava")

        if status == "stale":
            score -= 0.5

        if additional_signal:
            extra_score, extra_reasons = additional_signal(event)
            score += extra_score
            reasons = list(extra_reasons) + reasons

        scored.append(RankedEvent(
            event=event,
            score=score,
            reasons=tuple(dict.fromkeys(reasons))[:max_reasons] or ("Upcoming in Bratislava",),
        ))

    scored.sort(key=lambda item: (-item.score, item.event.start_time, str(item.event.id)))

    deduplicated: list[RankedEvent] = []
    seen = set()
    for item in scored:
        key = _duplicate_key(item.event)
        if key in seen:
            continue
        seen.add(key)
        deduplicated.append(item)

    diversified: list[RankedEvent] = []
    remaining = deduplicated[:]
    category_counts: dict[str, int] = {}
    organizer_counts: dict[str, int] = {}
    while remaining:
        def adjusted(item: RankedEvent):
            category_key = _category(item.event).casefold()
            organizer_key = str(item.event.organization_id or "")
            penalty = category_counts.get(category_key, 0) * 0.4
            if organizer_key:
                penalty += organizer_counts.get(organizer_key, 0) * 0.8
            return item.score - penalty

        best = max(enumerate(remaining), key=lambda pair: (adjusted(pair[1]), -pair[0]))[1]
        remaining.remove(best)
        diversified.append(best)
        category_key = _category(best.event).casefold()
        organizer_key = str(best.event.organization_id or "")
        category_counts[category_key] = category_counts.get(category_key, 0) + 1
        if organizer_key:
            organizer_counts[organizer_key] = organizer_counts.get(organizer_key, 0) + 1

    return diversified
