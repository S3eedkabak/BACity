"""Read-only quality probe for BACity+ planners against the configured database.

This intentionally uses neutral, synthetic recommendation contexts and reports
only aggregate counts/categories. It never reads or emits user data.

Run inside the API container:
    python -m scripts.premium_inventory
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.orm import Session, joinedload

from app.core.evening_planner import build_evening_plans
from app.core.event_chains import ChainMode, CHAIN_HORIZON, build_event_chains
from app.core.group_match import ParticipantPreference, rank_group_candidates
from app.core.planning import haversine_km, local_planning_window, utc_naive
from app.core.recommendations import RecommendationContext
from app.core.tonight import rank_tonight_events, tonight_window
from app.core.weekend_planner import WeekendDayInput, build_weekend_plans, weekend_window
from app.database import engine
from app.models.event import Event, EventStatus

ZONE_NAME = "Europe/Bratislava"
ZONE = ZoneInfo(ZONE_NAME)
CITY_CENTER = (48.1486, 17.1077)


def context(*, interests=(), latitude=None, longitude=None) -> RecommendationContext:
    return RecommendationContext(
        interests=frozenset(item.casefold() for item in interests),
        saved_categories=frozenset(),
        following=frozenset(),
        save_counts={},
        saved_event_ids=frozenset(),
        latitude=latitude,
        longitude=longitude,
    )


def category(event) -> str:
    return str(getattr(event.category, "value", event.category))


def plan_summary(plans) -> list[dict[str, object]]:
    return [
        {
            "strategy": plan.strategy.value,
            "events": len(plan.items),
            "categories": [category(item.event) for item in plan.items],
            "limited": plan.limited,
        }
        for plan in plans
    ]


def main() -> None:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    local_today = now.replace(tzinfo=timezone.utc).astimezone(ZONE).date()
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            db = Session(bind=connection)
            events = list(db.scalars(
                select(Event)
                .options(joinedload(Event.venue))
                .where(Event.status.in_([EventStatus.fresh, EventStatus.stale]))
                .where(Event.start_time >= now - timedelta(hours=12))
                .where(Event.start_time < now + timedelta(days=75))
                .order_by(Event.start_time, Event.id)
            ).unique())

            evening_rows = []
            for offset in range(1, 31):
                day = local_today + timedelta(days=offset)
                window = local_planning_window(day, time(18), time(0), ZONE_NAME)
                candidates = [event for event in events if window.starts_at_utc <= utc_naive(event.start_time) < window.ends_at_utc]
                if not candidates:
                    continue
                plans = build_evening_plans(candidates, context(), window, frozenset())
                music = build_evening_plans(candidates, context(interests=("Music",)), window, frozenset({"music"}))
                located = build_evening_plans(candidates, context(latitude=CITY_CENTER[0], longitude=CITY_CENTER[1]), window, frozenset())
                evening_rows.append({
                    "date": str(day),
                    "raw": len(candidates),
                    "known_end": sum(event.end_time is not None for event in candidates),
                    "neutral": plan_summary(plans),
                    "music": plan_summary(music),
                    "location": plan_summary(located),
                })
            evening_rows.sort(key=lambda row: (-max((plan["events"] for plan in row["neutral"]), default=0), -row["raw"], row["date"]))

            weekend_rows = []
            saturday = local_today + timedelta(days=(5 - local_today.weekday()) % 7)
            if saturday < local_today:
                saturday += timedelta(days=7)
            for offset in range(8):
                start = saturday + timedelta(days=7 * offset)
                days = (start, start + timedelta(days=1))
                windows = tuple(weekend_window(day, ZONE_NAME) for day in days)
                inputs = tuple(WeekendDayInput(day, window, tuple(events)) for day, window in zip(days, windows))
                plans = build_weekend_plans(inputs, context(), frozenset())
                raw = [sum(window.starts_at_utc <= utc_naive(event.start_time) < window.ends_at_utc for event in events) for window in windows]
                weekend_rows.append({
                    "saturday": str(start),
                    "raw_by_day": raw,
                    "strategies": [
                        {
                            "strategy": plan.strategy.value,
                            "events_by_day": [len(day.items) for day in plan.days],
                            "categories_by_day": [[category(item.event) for item in day.items] for day in plan.days],
                        }
                        for plan in plans
                    ],
                })
            weekend_rows.sort(key=lambda row: (-sum(row["raw_by_day"]), row["saturday"]))

            current_window = tonight_window(now, ZONE_NAME)
            tonight_candidates = [
                event for event in events
                if utc_naive(event.start_time) < current_window.ends_at_utc
                and (utc_naive(event.start_time) >= current_window.starts_at_utc or (event.end_time and utc_naive(event.end_time) > now))
            ]
            tonight_ranked = rank_tonight_events(tonight_candidates, context(), current_window)
            tonight_counts = Counter(item.classification.value for item in tonight_ranked)

            chain_best = []
            known_end = [event for event in events if event.end_time and utc_naive(event.end_time) > now]
            for anchor in known_end:
                lower = utc_naive(anchor.start_time) - CHAIN_HORIZON
                upper = utc_naive(anchor.end_time) + CHAIN_HORIZON
                candidates = [event for event in events if event.id != anchor.id and lower <= utc_naive(event.start_time) <= upper]
                chains = build_event_chains(anchor, candidates, context(), ChainMode.full)
                chain_best.append({
                    "anchor_start": str(anchor.start_time),
                    "category": category(anchor),
                    "candidates": len(candidates),
                    "alternatives": len(chains),
                    "lengths": [len(chain.items) for chain in chains],
                })
            chain_best.sort(key=lambda row: (-max(row["lengths"], default=0), -row["alternatives"], row["anchor_start"]))

            mapped = [event for event in events if event.latitude is not None and event.longitude is not None]
            area_counts = {
                str(radius): sum(haversine_km(CITY_CENTER[0], CITY_CENTER[1], event.latitude, event.longitude) <= radius for event in mapped)
                for radius in (1, 2, 5)
            }
            area_music = sum(
                haversine_km(CITY_CENTER[0], CITY_CENTER[1], event.latitude, event.longitude) <= 5 and category(event) == "Music"
                for event in mapped
            )

            densest = max(evening_rows, key=lambda row: row["raw"], default=None)
            group_summary = None
            if densest:
                day = datetime.fromisoformat(densest["date"]).date()
                window = local_planning_window(day, time(18), time(23), ZONE_NAME)
                candidates = [event for event in events if window.starts_at_utc <= utc_naive(event.start_time) < window.ends_at_utc]
                participants = (
                    ParticipantPreference(context(interests=("Music",)), frozenset({"music"}), frozenset()),
                    ParticipantPreference(context(interests=("Culture",)), frozenset({"culture"}), frozenset({"nightlife"})),
                )
                ranked = rank_group_candidates(candidates, participants, frozenset(), window.starts_at_utc)
                group_summary = {
                    "date": str(day), "candidates": len(candidates), "returned": len(ranked),
                    "categories": [category(item.event) for item in ranked],
                }

            report = {
                "database_dialect": connection.dialect.name,
                "event_pool": len(events),
                "evening_top_dates": evening_rows[:8],
                "weekend_top_dates": weekend_rows[:5],
                "tonight": {"candidate_count": len(tonight_candidates), "returned": len(tonight_ranked), "buckets": dict(tonight_counts)},
                "event_chains_top": chain_best[:5],
                "area_watch_city_center": {"all_by_radius_km": area_counts, "music_within_5km": area_music},
                "group_match": group_summary,
            }
            print(json.dumps(report, indent=2, default=str, sort_keys=True))
        finally:
            transaction.rollback()


if __name__ == "__main__":
    main()
