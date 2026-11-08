"""Window-constrained, bounded planning for BACity+ Build My Evening."""
from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from app.core.planning import PlanningWindow, following_transition, utc_naive, valid_event_interval
from app.core.recommendations import RecommendationContext, RankedEvent, rank_events

MAX_WINDOW = timedelta(hours=10)
MAX_CANDIDATES = 400
MAX_RANKED_CANDIDATES = 60
BEAM_WIDTH = 24
MAX_PLAN_EVENTS = 4
MAX_PLANS = 3


class PlanningStrategy(str, Enum):
    best_match = "best_match"
    relaxed = "relaxed"
    something_different = "something_different"


@dataclass(frozen=True)
class EveningPlanItem:
    event: object
    reasons: tuple[str, ...]
    location_confidence: str | None


@dataclass(frozen=True)
class EveningPlan:
    strategy: PlanningStrategy
    explanation: str
    items: tuple[EveningPlanItem, ...]
    limited: bool
    score: float


@dataclass(frozen=True)
class _State:
    events: tuple[object, ...]
    score: float


def _category(event) -> str:
    return str(getattr(event.category, "value", event.category))


def _fits_window(event, window: PlanningWindow) -> bool:
    if not valid_event_interval(event):
        return False
    start = utc_naive(event.start_time)
    if not window.starts_at_utc <= start < window.ends_at_utc:
        return False
    return event.end_time is None or utc_naive(event.end_time) <= window.ends_at_utc


def _signature(events: tuple[object, ...]) -> tuple[str, ...]:
    return tuple(str(event.id) for event in events)


def _state_score(
    events: tuple[object, ...],
    scores: dict,
    strategy: PlanningStrategy,
    context: RecommendationContext,
) -> float:
    base = sum(scores[event.id] for event in events) / len(events)
    categories = [_category(event).casefold() for event in events]
    organizers = [str(event.organization_id) for event in events if event.organization_id]
    repeated_categories = len(categories) - len(set(categories))
    repeated_organizers = len(organizers) - len(set(organizers))
    transitions = [following_transition(events[index], events[index + 1]) for index in range(len(events) - 1)]
    comfort = 0.0
    movement = 0.0
    for index, transition in enumerate(transitions):
        if transition is None:
            return float("-inf")
        gap = utc_naive(events[index + 1].start_time) - utc_naive(events[index].end_time)
        comfort += min(2.0, max(0.0, (gap - transition.required_gap).total_seconds() / 3600))
        movement += transition.distance_km if transition.distance_km is not None else 6.0
    repetition = repeated_categories * 0.7 + repeated_organizers * 1.1

    if strategy == PlanningStrategy.relaxed:
        return base * 0.75 + comfort * 0.9 - movement * 0.08 - (len(events) - 1) * 5.0 - repetition
    if strategy == PlanningStrategy.something_different:
        novelty = sum(category not in context.interests and category not in context.saved_categories for category in categories)
        return base * 0.55 + len(set(categories)) * 1.2 + novelty * 0.8 + (len(events) - 1) * 0.15 - repetition
    return base + comfort * 0.25 + (len(events) - 1) * 0.4 - movement * 0.025 - repetition


def _strategy_states(
    ranked: list[RankedEvent],
    scores: dict,
    strategy: PlanningStrategy,
    context: RecommendationContext,
) -> list[_State]:
    events = sorted((item.event for item in ranked), key=lambda event: (utc_naive(event.start_time), str(event.id)))
    beam = [_State((event,), _state_score((event,), scores, strategy, context)) for event in events]
    beam = sorted(beam, key=lambda state: (-state.score, _signature(state.events)))[:BEAM_WIDTH]
    all_states = list(beam)
    for _ in range(2, MAX_PLAN_EVENTS + 1):
        extensions: dict[tuple[str, ...], _State] = {}
        for state in beam:
            last = state.events[-1]
            for event in events:
                if utc_naive(event.start_time) <= utc_naive(last.start_time) or event.id in {item.id for item in state.events}:
                    continue
                if following_transition(last, event) is None:
                    continue
                sequence = state.events + (event,)
                candidate = _State(sequence, _state_score(sequence, scores, strategy, context))
                extensions[_signature(sequence)] = candidate
        if not extensions:
            break
        beam = sorted(extensions.values(), key=lambda state: (-state.score, _signature(state.events)))[:BEAM_WIDTH]
        all_states.extend(beam)
    return sorted(all_states, key=lambda state: (-state.score, _signature(state.events)))


def _item(event, ranked: RankedEvent, selected_categories: frozenset[str], previous=None) -> EveningPlanItem:
    reasons = ["Fits your selected time"]
    category = _category(event)
    if category.casefold() in selected_categories:
        reasons.append(f"Matches your {category} preference")
    if previous is not None:
        transition = following_transition(previous, event)
        if transition and transition.location_confidence == "nearby":
            reasons.append("Nearby venue")
    reasons.extend(reason for reason in ranked.reasons if reason not in {"Upcoming in Bratislava", "Matches your interests"})
    if event.end_time is None:
        reasons.append("End time is not published")
    transition = following_transition(previous, event) if previous is not None else None
    return EveningPlanItem(event, tuple(dict.fromkeys(reasons))[:3], transition.location_confidence if transition else None)


def build_evening_plans(
    candidates,
    context: RecommendationContext,
    window: PlanningWindow,
    selected_categories: frozenset[str],
) -> list[EveningPlan]:
    eligible = [event for event in candidates if _fits_window(event, window)]

    def explicit_signal(event):
        category = _category(event)
        if category.casefold() in selected_categories:
            return 7.0, (f"Matches your {category} preference",)
        return 0.0, ()

    ranked = rank_events(
        eligible,
        context,
        now=window.starts_at_utc,
        include_started=True,
        include_timing_signal=False,
        additional_signal=explicit_signal,
        max_reasons=6,
    )[:MAX_RANKED_CANDIDATES]
    if not ranked:
        return []
    ranked_by_id = {item.event.id: item for item in ranked}
    scores = {item.event.id: item.score for item in ranked}
    explanations = {
        PlanningStrategy.best_match: "Best balance of your preferences, quality, and practical fit",
        PlanningStrategy.relaxed: "More relaxed pacing with comfortable transitions",
        PlanningStrategy.something_different: "Adds category variety beyond your usual preferences",
    }
    plans: list[EveningPlan] = []
    used: set[tuple[str, ...]] = set()
    for strategy in PlanningStrategy:
        states = _strategy_states(ranked, scores, strategy, context)
        selected = next((state for state in states if _signature(state.events) not in used), None)
        if selected is None:
            continue
        signature = _signature(selected.events)
        used.add(signature)
        items = tuple(
            _item(event, ranked_by_id[event.id], selected_categories, selected.events[index - 1] if index else None)
            for index, event in enumerate(selected.events)
        )
        plans.append(EveningPlan(strategy, explanations[strategy], items, len(items) == 1, selected.score))
        if len(plans) == MAX_PLANS:
            break
    return plans
