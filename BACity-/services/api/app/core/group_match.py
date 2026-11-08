"""Deterministic, fairness-aware candidate selection for private groups."""
from dataclasses import dataclass
from datetime import datetime

from app.core.recommendations import RecommendationContext, rank_events

MAX_DB_CANDIDATES = 500
MAX_VOTING_CANDIDATES = 5
MAX_PARTICIPANTS = 12


@dataclass(frozen=True)
class ParticipantPreference:
    context: RecommendationContext
    liked_categories: frozenset[str]
    disliked_categories: frozenset[str]


@dataclass(frozen=True)
class RankedGroupCandidate:
    event: object
    score: float
    explanations: tuple[str, ...]


def _category(event) -> str:
    return str(getattr(event.category, "value", event.category))


def _bounded(value: float) -> float:
    return max(-8.0, min(10.0, value))


def rank_group_candidates(
    events,
    participants: tuple[ParticipantPreference, ...],
    session_categories: frozenset[str],
    now: datetime,
) -> list[RankedGroupCandidate]:
    if not participants:
        return []
    neutral = RecommendationContext(
        interests=frozenset(), saved_categories=frozenset(), following=frozenset(),
        save_counts={}, saved_event_ids=frozenset(), latitude=None, longitude=None,
    )
    # The shared ranker provides canonical status filtering, quality, duplicate
    # suppression, and deterministic ordering before group aggregation.
    neutral_ranked = rank_events(events, neutral, now=now, include_timing_signal=False, max_reasons=4)
    pool = [item.event for item in neutral_ranked]
    if not pool:
        return []

    score_maps = []
    for participant in participants:
        ranked = rank_events(pool, participant.context, now=now, include_timing_signal=False, max_reasons=5)
        score_maps.append({item.event.id: item.score for item in ranked})

    ranked_group: list[RankedGroupCandidate] = []
    for event in pool:
        category = _category(event).casefold()
        utilities: list[float] = []
        explicit_dislikes = 0
        matched_preferences = 0
        for preference, scores in zip(participants, score_maps):
            utility = scores.get(event.id, 0.0)
            if category in preference.liked_categories:
                utility += 4.0
                matched_preferences += 1
            if category in preference.disliked_categories:
                utility -= 8.0
                explicit_dislikes += 1
            if category in session_categories:
                utility += 1.5
            utilities.append(_bounded(utility))
        average = sum(utilities) / len(utilities)
        minimum = min(utilities)
        coverage = sum(value >= 2.5 for value in utilities) / len(utilities)
        fairness_score = average * .50 + minimum * .35 + coverage * 1.5 - explicit_dislikes * 2.0
        reasons = ["Fits everyone's selected time"]
        if matched_preferences >= max(1, len(participants) // 2):
            reasons.append("Matches several group interests")
        if explicit_dislikes == 0:
            reasons.append("No strong group dislikes")
        ranked_group.append(RankedGroupCandidate(event, fairness_score, tuple(reasons)))

    ranked_group.sort(key=lambda item: (-item.score, item.event.start_time, str(item.event.id)))
    selected: list[RankedGroupCandidate] = []
    remaining = ranked_group[:]
    category_counts: dict[str, int] = {}
    organizer_counts: dict[str, int] = {}
    venue_counts: dict[str, int] = {}
    while remaining and len(selected) < MAX_VOTING_CANDIDATES:
        def adjusted(item):
            event = item.event
            category = _category(event).casefold()
            organizer = str(event.organization_id or "")
            venue = str(event.venue_id or "")
            return (
                item.score
                - category_counts.get(category, 0) * .7
                - organizer_counts.get(organizer, 0) * .9
                - venue_counts.get(venue, 0) * .8
            )

        best = max(remaining, key=lambda item: (adjusted(item), -item.event.start_time.timestamp(), str(item.event.id)))
        remaining.remove(best)
        reasons = list(best.explanations)
        if selected and _category(best.event).casefold() not in category_counts:
            reasons.append("A different option for the group")
        selected.append(RankedGroupCandidate(best.event, best.score, tuple(reasons[:3])))
        category = _category(best.event).casefold()
        organizer = str(best.event.organization_id or "")
        venue = str(best.event.venue_id or "")
        category_counts[category] = category_counts.get(category, 0) + 1
        if organizer:
            organizer_counts[organizer] = organizer_counts.get(organizer, 0) + 1
        if venue:
            venue_counts[venue] = venue_counts.get(venue, 0) + 1
    return selected
