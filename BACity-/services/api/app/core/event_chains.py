"""Bounded, deterministic planning primitives for BACity+ Event Chains."""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from math import asin, cos, radians, sin, sqrt

from app.core.recommendations import RecommendationContext, RankedEvent, rank_events

CHAIN_HORIZON = timedelta(hours=8)
MAX_CANDIDATES = 300
MAX_CHAIN_EVENTS = 3
MAX_ALTERNATIVES = 3
BEAM_WIDTH = 12


class ChainMode(str, Enum):
    before = "before"
    after = "after"
    full = "full"


class ChainRelation(str, Enum):
    before = "before"
    anchor = "anchor"
    after = "after"


@dataclass(frozen=True)
class Transition:
    feasible: bool
    required_gap: timedelta
    distance_km: float | None
    location_confidence: str


@dataclass(frozen=True)
class PlannedItem:
    event: object
    relation: ChainRelation
    reasons: tuple[str, ...]
    location_confidence: str | None = None


@dataclass(frozen=True)
class PlannedChain:
    items: tuple[PlannedItem, ...]
    score: float


def utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def event_coordinates(event) -> tuple[float, float] | None:
    if event.latitude is not None and event.longitude is not None:
        return float(event.latitude), float(event.longitude)
    venue = getattr(event, "venue", None)
    if venue and venue.latitude is not None and venue.longitude is not None:
        return float(venue.latitude), float(venue.longitude)
    return None


def distance_km(first, second) -> float | None:
    left, right = event_coordinates(first), event_coordinates(second)
    if left is None or right is None:
        return None
    lat1, lng1 = left
    lat2, lng2 = right
    lat1r, lat2r = radians(lat1), radians(lat2)
    delta_lat = lat2r - lat1r
    delta_lng = radians(lng2 - lng1)
    root = sin(delta_lat / 2) ** 2 + cos(lat1r) * cos(lat2r) * sin(delta_lng / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(root))


def required_transition(first, second) -> Transition:
    """Conservative buffers are feasibility heuristics, never travel-time claims."""
    distance = distance_km(first, second)
    if distance is None:
        return Transition(True, timedelta(minutes=60), None, "location_unknown")
    if distance <= 1.5:
        return Transition(True, timedelta(minutes=20), distance, "nearby")
    if distance <= 5:
        return Transition(True, timedelta(minutes=35), distance, "nearby")
    if distance <= 10:
        return Transition(True, timedelta(minutes=60), distance, "distance_buffered")
    return Transition(True, timedelta(minutes=90), distance, "distance_buffered")


def _valid_interval(event) -> bool:
    start = utc_naive(event.start_time)
    return event.end_time is None or utc_naive(event.end_time) > start


def _before_transition(candidate, anchor) -> Transition | None:
    if not _valid_interval(candidate) or candidate.end_time is None:
        return None
    transition = required_transition(candidate, anchor)
    gap = utc_naive(anchor.start_time) - utc_naive(candidate.end_time)
    return transition if transition.feasible and gap >= transition.required_gap else None


def _after_transition(anchor, candidate) -> Transition | None:
    if not _valid_interval(anchor) or not _valid_interval(candidate) or anchor.end_time is None:
        return None
    transition = required_transition(anchor, candidate)
    gap = utc_naive(candidate.start_time) - utc_naive(anchor.end_time)
    return transition if transition.feasible and gap >= transition.required_gap else None


def _candidate_score(ranked: RankedEvent, transition: Transition, first, second) -> float:
    gap = utc_naive(second.start_time) - utc_naive(first.end_time)
    comfort = min(1.0, max(0.0, (gap - transition.required_gap).total_seconds() / 3600))
    geography = 1.5 if transition.location_confidence == "nearby" else (
        -0.5 if transition.location_confidence == "location_unknown" else 0.0
    )
    same_organizer = first.organization_id and first.organization_id == second.organization_id
    same_category = str(first.category) == str(second.category)
    diversity_penalty = (0.8 if same_organizer else 0.0) + (0.3 if same_category else 0.0)
    return ranked.score + comfort + geography - diversity_penalty


def _candidate_item(ranked: RankedEvent, relation: ChainRelation, transition: Transition) -> PlannedItem:
    relation_reason = "Fits before your selected event" if relation == ChainRelation.before else "Starts after your selected event"
    reasons = [relation_reason]
    if transition.location_confidence == "nearby":
        reasons.append("Nearby venue")
    reasons.extend(reason for reason in ranked.reasons if reason not in {"Upcoming in Bratislava", "Matches your interests"})
    return PlannedItem(ranked.event, relation, tuple(dict.fromkeys(reasons))[:3], transition.location_confidence)


def _signature(items: tuple[PlannedItem, ...]) -> tuple[str, ...]:
    return tuple(str(item.event.id) for item in items)


def build_event_chains(
    anchor,
    candidates,
    context: RecommendationContext,
    mode: ChainMode,
) -> list[PlannedChain]:
    """Rank bounded candidates, then keep a small deterministic beam of valid chains."""
    horizon_start = utc_naive(anchor.start_time) - CHAIN_HORIZON
    ranked = rank_events(
        candidates,
        context,
        now=horizon_start,
        include_started=True,
        include_timing_signal=False,
        max_reasons=5,
    )
    before: list[tuple[RankedEvent, Transition, float]] = []
    after: list[tuple[RankedEvent, Transition, float]] = []
    for item in ranked:
        prior = _before_transition(item.event, anchor)
        if prior:
            before.append((item, prior, _candidate_score(item, prior, item.event, anchor)))
        following = _after_transition(anchor, item.event)
        if following:
            after.append((item, following, _candidate_score(item, following, anchor, item.event)))
    ordering = lambda value: (-value[2], utc_naive(value[0].event.start_time), str(value[0].event.id))
    before = sorted(before, key=ordering)[:BEAM_WIDTH]
    after = sorted(after, key=ordering)[:BEAM_WIDTH]

    anchor_item = PlannedItem(anchor, ChainRelation.anchor, ("Selected event",))
    before_states = [
        PlannedChain((_candidate_item(item, ChainRelation.before, transition), anchor_item), score)
        for item, transition, score in before
    ]
    after_states = [
        PlannedChain((anchor_item, _candidate_item(item, ChainRelation.after, transition)), score)
        for item, transition, score in after
    ]
    states: list[PlannedChain] = []
    if mode in {ChainMode.before, ChainMode.full}:
        states.extend(before_states)
    if mode in {ChainMode.after, ChainMode.full}:
        states.extend(after_states)
    if mode == ChainMode.full and before and after:
        for state in before_states[:BEAM_WIDTH]:
            before_event = state.items[0].event
            for item, transition, score in after:
                if item.event.id == before_event.id:
                    continue
                same_organizer = before_event.organization_id and before_event.organization_id == item.event.organization_id
                same_category = str(before_event.category) == str(item.event.category)
                diversity_penalty = (1.0 if same_organizer else 0.0) + (0.4 if same_category else 0.0)
                states.append(PlannedChain(
                    (state.items[0], anchor_item, _candidate_item(item, ChainRelation.after, transition)),
                    state.score + score - diversity_penalty,
                ))

    unique: list[PlannedChain] = []
    seen: set[tuple[str, ...]] = set()
    for chain in sorted(states, key=lambda value: (-value.score, _signature(value.items))):
        signature = _signature(chain.items)
        if signature in seen or len(chain.items) > MAX_CHAIN_EVENTS:
            continue
        seen.add(signature)
        unique.append(chain)
        if len(unique) == MAX_ALTERNATIVES:
            break
    return unique
