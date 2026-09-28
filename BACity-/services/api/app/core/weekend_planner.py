"""Bounded day-scale planning for the BACity+ Weekend Generator."""
from dataclasses import dataclass
from datetime import date, time
from enum import Enum

from app.core.planning import PlanningWindow, following_transition, local_planning_window, utc_naive, valid_event_interval
from app.core.recommendations import RecommendationContext, RankedEvent, rank_events

MAX_CANDIDATES = 600
MAX_RANKED_PER_DAY = 70
BEAM_WIDTH = 32
MAX_EVENTS_PER_DAY = 4
MAX_WEEKEND_EVENTS = 8
MAX_PLANS = 3
DAY_START = time(8)
DAY_END = time(3)

CULTURE_CATEGORIES = frozenset({
    "culture", "arts", "theatre", "education", "exhibitions", "festivals",
})


class WeekendMode(str, Enum):
    saturday = "saturday"
    sunday = "sunday"
    weekend = "weekend"


class WeekendStrategy(str, Enum):
    relaxed = "relaxed"
    culture_heavy = "culture_heavy"
    something_different = "something_different"


@dataclass(frozen=True)
class WeekendDayInput:
    day: date
    window: PlanningWindow
    candidates: tuple[object, ...]


@dataclass(frozen=True)
class WeekendPlanItem:
    event: object
    reasons: tuple[str, ...]
    location_confidence: str | None


@dataclass(frozen=True)
class WeekendDayPlan:
    day: date
    window: PlanningWindow
    items: tuple[WeekendPlanItem, ...]
    limited: bool


@dataclass(frozen=True)
class WeekendPlan:
    strategy: WeekendStrategy
    explanation: str
    days: tuple[WeekendDayPlan, ...]
    limited: bool
    score: float


@dataclass(frozen=True)
class _State:
    events: tuple[object, ...]
    score: float


def weekend_window(day: date, timezone_name: str) -> PlanningWindow:
    """A local planning day runs from 08:00 until 03:00 the following night."""
    return local_planning_window(day, DAY_START, DAY_END, timezone_name)


def _category(event) -> str:
    return str(getattr(event.category, "value", event.category))


def _fits_day(event, window: PlanningWindow) -> bool:
    if not valid_event_interval(event):
        return False
    start = utc_naive(event.start_time)
    if not window.starts_at_utc <= start < window.ends_at_utc:
        return False
    return event.end_time is None or utc_naive(event.end_time) <= window.ends_at_utc


def _signature(events: tuple[object, ...]) -> tuple[str, ...]:
    return tuple(str(event.id) for event in events)


def _state_score(events, scores, strategy: WeekendStrategy, context: RecommendationContext) -> float:
    base = sum(scores[event.id] for event in events) / len(events)
    categories = [_category(event).casefold() for event in events]
    organizers = [str(event.organization_id) for event in events if event.organization_id]
    venues = [str(event.venue_id) for event in events if event.venue_id]
    repetition = (
        (len(categories) - len(set(categories))) * .8
        + (len(organizers) - len(set(organizers))) * 1.1
        + (len(venues) - len(set(venues))) * .7
    )
    comfort = 0.0
    movement = 0.0
    for index in range(len(events) - 1):
        transition = following_transition(events[index], events[index + 1])
        if transition is None:
            return float("-inf")
        gap = utc_naive(events[index + 1].start_time) - utc_naive(events[index].end_time)
        comfort += min(3.0, max(0.0, (gap - transition.required_gap).total_seconds() / 3600))
        movement += transition.distance_km if transition.distance_km is not None else 6.0

    if strategy == WeekendStrategy.relaxed:
        return base * .75 + comfort * 1.1 - movement * .09 - (len(events) - 1) * 3.4 - repetition
    if strategy == WeekendStrategy.culture_heavy:
        culture_count = sum(category in CULTURE_CATEGORIES for category in categories)
        return base * .8 + culture_count * 2.4 + len(set(categories)) * .35 - movement * .035 - repetition
    novelty = sum(category not in context.interests and category not in context.saved_categories for category in categories)
    return base * .55 + len(set(categories)) * 1.5 + novelty * .9 - movement * .035 - repetition


def _states(ranked: list[RankedEvent], strategy: WeekendStrategy, context: RecommendationContext) -> list[_State]:
    scores = {item.event.id: item.score for item in ranked}
    events = sorted((item.event for item in ranked), key=lambda event: (utc_naive(event.start_time), str(event.id)))
    beam = [_State((event,), _state_score((event,), scores, strategy, context)) for event in events]
    beam = sorted(beam, key=lambda state: (-state.score, _signature(state.events)))[:BEAM_WIDTH]
    all_states = list(beam)
    for _ in range(2, MAX_EVENTS_PER_DAY + 1):
        extensions: dict[tuple[str, ...], _State] = {}
        for state in beam:
            last = state.events[-1]
            used = {event.id for event in state.events}
            for event in events:
                if event.id in used or utc_naive(event.start_time) <= utc_naive(last.start_time):
                    continue
                if following_transition(last, event) is None:
                    continue
                sequence = state.events + (event,)
                extensions[_signature(sequence)] = _State(sequence, _state_score(sequence, scores, strategy, context))
        if not extensions:
            break
        beam = sorted(extensions.values(), key=lambda state: (-state.score, _signature(state.events)))[:BEAM_WIDTH]
        all_states.extend(beam)
    return sorted(all_states, key=lambda state: (-state.score, _signature(state.events)))


def _rank_day(day: WeekendDayInput, context: RecommendationContext, selected_categories: frozenset[str]):
    eligible = [event for event in day.candidates if _fits_day(event, day.window)]

    def request_signal(event):
        category = _category(event).casefold()
        score = 7.0 if category in selected_categories else 0.0
        reasons = (f"Matches your selected {_category(event)} interest",) if score else ()
        return score, reasons

    return rank_events(
        eligible,
        context,
        now=day.window.starts_at_utc,
        include_started=True,
        include_timing_signal=False,
        additional_signal=request_signal,
        max_reasons=6,
    )[:MAX_RANKED_PER_DAY]


def _item(event, ranked: RankedEvent, selected_categories: frozenset[str], previous=None) -> WeekendPlanItem:
    reasons = ["Fits this planning day"]
    category = _category(event)
    if category.casefold() in selected_categories:
        reasons.append(f"Matches your selected {category} interest")
    if previous is not None:
        transition = following_transition(previous, event)
        if transition and transition.location_confidence == "nearby":
            reasons.append("Nearby venue")
    reasons.extend(reason for reason in ranked.reasons if reason not in {"Upcoming in Bratislava", "Matches your interests"})
    if event.end_time is None:
        reasons.append("End time is not published")
    transition = following_transition(previous, event) if previous is not None else None
    return WeekendPlanItem(event, tuple(dict.fromkeys(reasons))[:3], transition.location_confidence if transition else None)


def build_weekend_plans(
    days: tuple[WeekendDayInput, ...],
    context: RecommendationContext,
    selected_categories: frozenset[str],
) -> list[WeekendPlan]:
    ranked_days = [(day, _rank_day(day, context, selected_categories)) for day in days]
    explanations = {
        WeekendStrategy.relaxed: "Fewer events, comfortable gaps, and less movement",
        WeekendStrategy.culture_heavy: "Favors BACity's culture, arts, theatre, education, exhibition, and festival events",
        WeekendStrategy.something_different: "Adds category, organizer, and venue variety beyond your usual preferences",
    }
    plans: list[WeekendPlan] = []
    used_signatures: set[tuple[tuple[str, ...], ...]] = set()
    for strategy in WeekendStrategy:
        planned_days: list[WeekendDayPlan] = []
        total_score = 0.0
        signature_parts: list[tuple[str, ...]] = []
        for day, ranked in ranked_days:
            states = _states(ranked, strategy, context)
            selected = states[0] if states else None
            events = selected.events if selected else ()
            ranked_by_id = {item.event.id: item for item in ranked}
            items = tuple(
                _item(event, ranked_by_id[event.id], selected_categories, events[index - 1] if index else None)
                for index, event in enumerate(events)
            )
            planned_days.append(WeekendDayPlan(day.day, day.window, items, len(items) <= 1))
            signature_parts.append(_signature(events))
            total_score += selected.score if selected else -2.0
        signature = tuple(signature_parts)
        if not any(signature) or signature in used_signatures:
            continue
        used_signatures.add(signature)
        total_events = sum(len(day.items) for day in planned_days)
        plans.append(WeekendPlan(
            strategy,
            explanations[strategy],
            tuple(planned_days),
            total_events <= 1 or any(day.limited for day in planned_days),
            total_score,
        ))
        if len(plans) == MAX_PLANS:
            break
    return plans
