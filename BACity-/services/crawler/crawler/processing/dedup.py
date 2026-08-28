"""
Deduplication (spec section 27). Computes a duplicate probability from
title similarity + date/time proximity + venue match, and only calls two
events duplicates above a conservative combined threshold — false merges
are explicitly worse than duplicate entries per the spec, so this errs
toward under-merging.
"""
from dataclasses import dataclass
from datetime import datetime

from rapidfuzz import fuzz

from crawler.items import NormalizedEvent

TITLE_WEIGHT = 0.5
TIME_WEIGHT = 0.3
VENUE_WEIGHT = 0.2

DUPLICATE_THRESHOLD = 0.82
TIME_WINDOW_MINUTES = 90  # events within this window can still score high on time


@dataclass
class DuplicateScore:
    score: float
    is_duplicate: bool
    title_similarity: float
    time_similarity: float
    venue_similarity: float


def _title_similarity(a: str, b: str) -> float:
    return fuzz.token_sort_ratio(a.lower().strip(), b.lower().strip()) / 100.0


def _time_similarity(a_iso: str, b_iso: str) -> float:
    try:
        a = datetime.fromisoformat(a_iso)
        b = datetime.fromisoformat(b_iso)
    except ValueError:
        return 0.0
    delta_minutes = abs((a - b).total_seconds()) / 60.0
    if delta_minutes == 0:
        return 1.0
    if delta_minutes >= TIME_WINDOW_MINUTES:
        return 0.0
    return 1.0 - (delta_minutes / TIME_WINDOW_MINUTES)


def _venue_similarity(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.5  # unknown -> neutral, don't punish or reward
    return fuzz.token_sort_ratio(a.lower().strip(), b.lower().strip()) / 100.0


def score_duplicate(a: NormalizedEvent, b: NormalizedEvent) -> DuplicateScore:
    title_sim = _title_similarity(a.title, b.title)
    time_sim = _time_similarity(a.start_time, b.start_time)
    venue_sim = _venue_similarity(a.venue_name, b.venue_name)

    combined = (
        title_sim * TITLE_WEIGHT
        + time_sim * TIME_WEIGHT
        + venue_sim * VENUE_WEIGHT
    )

    # Guardrail: even a near-perfect title match shouldn't merge two events
    # on genuinely different days (spec: false merges are worse than dupes).
    if time_sim == 0.0:
        combined = min(combined, 0.5)

    return DuplicateScore(
        score=combined,
        is_duplicate=combined >= DUPLICATE_THRESHOLD,
        title_similarity=title_sim,
        time_similarity=time_sim,
        venue_similarity=venue_sim,
    )


def find_duplicate_groups(events: list[NormalizedEvent]) -> list[list[int]]:
    """Greedy grouping: returns index groups (into `events`) that mutually
    look like the same event. Each event ends up in exactly one group."""
    n = len(events)
    assigned = [False] * n
    groups: list[list[int]] = []

    for i in range(n):
        if assigned[i]:
            continue
        group = [i]
        assigned[i] = True
        for j in range(i + 1, n):
            if assigned[j]:
                continue
            if score_duplicate(events[i], events[j]).is_duplicate:
                group.append(j)
                assigned[j] = True
        groups.append(group)

    return groups
