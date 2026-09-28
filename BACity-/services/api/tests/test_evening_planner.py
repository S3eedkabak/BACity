from datetime import date, datetime, time, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.entitlements import BACITY_PLUS
from app.core.evening_planner import (
    BEAM_WIDTH,
    MAX_CANDIDATES,
    MAX_PLAN_EVENTS,
    MAX_PLANS,
    PlanningStrategy,
    build_evening_plans,
)
from app.core.planning import PlanningWindow, local_planning_window
from app.core.recommendations import RecommendationContext
from app.models.entitlement import EntitlementGrant
from app.models.event import Event, EventCategory, EventStatus
from app.models.user import User

BASE = datetime(2030, 6, 15, 18, 0)
WINDOW = PlanningWindow("Europe/Bratislava", BASE, BASE + timedelta(hours=7))


def _context(**changes):
    values = dict(
        interests=frozenset(), saved_categories=frozenset(), following=frozenset(),
        save_counts={}, saved_event_ids=frozenset(), latitude=None, longitude=None,
    )
    values.update(changes)
    return RecommendationContext(**values)


def _event(number, *, start=None, end_marker="default", duration=1, title=None, category="Culture",
           status="fresh", latitude=48.1486, longitude=17.1077, organization_id=None, venue_id=None):
    start = start or BASE
    end = start + timedelta(hours=duration) if end_marker == "default" else end_marker
    return SimpleNamespace(
        id=UUID(int=number), title=title or f"Evening event {number}", description="Real event",
        start_time=start, end_time=end, timezone="Europe/Bratislava", category=category, tags=[],
        latitude=latitude, longitude=longitude, venue=None, venue_id=venue_id,
        organization_id=organization_id, contributor_id=None, neighborhood=None, address="Bratislava",
        extraction_confidence=.9, source_reliability=.9, created_at=BASE - timedelta(days=1), status=status,
    )


def _signatures(plans):
    return [tuple(item.event.id for item in plan.items) for plan in plans]


def test_local_window_normal_cross_midnight_timezone_and_dst_validation():
    normal = local_planning_window(date(2030, 6, 15), time(18), time(23), "Europe/Bratislava")
    assert normal.starts_at_utc == datetime(2030, 6, 15, 16)
    assert normal.ends_at_utc == datetime(2030, 6, 15, 21)
    crossing = local_planning_window(date(2030, 6, 15), time(18), time(0), "Europe/Bratislava")
    assert crossing.duration == timedelta(hours=6)
    with pytest.raises(ValueError):
        local_planning_window(date(2030, 6, 15), time(18), time(18), "Europe/Bratislava")
    with pytest.raises(ValueError):
        local_planning_window(date(2030, 3, 31), time(2, 30), time(5), "Europe/Bratislava")


def test_compatible_events_are_chronological_bounded_and_real():
    events = [
        _event(1, start=BASE, duration=1),
        _event(2, start=BASE + timedelta(hours=1, minutes=30), duration=1),
        _event(3, start=BASE + timedelta(hours=3), duration=1),
        _event(4, start=BASE + timedelta(hours=4, minutes=30), duration=1),
        _event(5, start=BASE + timedelta(hours=6), duration=1),
    ]
    plans = build_evening_plans(events, _context(), WINDOW, frozenset())
    assert 0 < len(plans) <= MAX_PLANS == 3
    assert all(1 <= len(plan.items) <= MAX_PLAN_EVENTS == 4 for plan in plans)
    assert all([item.event.start_time for item in plan.items] == sorted(item.event.start_time for item in plan.items) for plan in plans)
    assert all(item.event in events for plan in plans for item in plan.items)


def test_overlap_tight_and_geographically_impractical_transitions_are_rejected():
    first = _event(1, start=BASE, duration=2)
    overlap = _event(2, start=BASE + timedelta(hours=1), duration=1)
    tight_nearby = _event(3, start=BASE + timedelta(hours=2, minutes=10), duration=1)
    distant = _event(4, start=BASE + timedelta(hours=2, minutes=45), duration=1,
                     latitude=48.30, longitude=17.30)
    plans = build_evening_plans([first, overlap, tight_nearby, distant], _context(), WINDOW, frozenset())
    signatures = _signatures(plans)
    assert all(not ({first.id, overlap.id} <= set(signature)) for signature in signatures)
    assert all(not ({first.id, tight_nearby.id} <= set(signature)) for signature in signatures)
    assert all(not ({first.id, distant.id} <= set(signature)) for signature in signatures)


def test_unknown_end_is_allowed_only_as_final_item_and_missing_coordinates_are_safe():
    known = _event(1, start=BASE, duration=1, latitude=None, longitude=None)
    unknown = _event(2, start=BASE + timedelta(hours=2), end_marker=None, latitude=None, longitude=None)
    later = _event(3, start=BASE + timedelta(hours=4), duration=1, latitude=None, longitude=None)
    plans = build_evening_plans([known, unknown, later], _context(), WINDOW, frozenset())
    assert any(plan.items[-1].event.id == unknown.id for plan in plans)
    assert all(not any(item.event.id == unknown.id for item in plan.items[:-1]) for plan in plans)
    assert all(item.location_confidence in {None, "location_unknown"} for plan in plans for item in plan.items)


def test_status_duplicates_explicit_categories_interests_and_follows_affect_results():
    organizer = uuid4()
    music = _event(1, start=BASE, category="Music", organization_id=organizer, venue_id=UUID(int=8))
    duplicate = _event(2, start=BASE, title=music.title + "!", category="Music",
                       organization_id=organizer, venue_id=UUID(int=8))
    culture = _event(3, start=BASE, category="Culture")
    cancelled = _event(4, start=BASE + timedelta(hours=2), status="cancelled")
    removed = _event(5, start=BASE + timedelta(hours=3), status="removed")
    context = _context(interests=frozenset({"culture"}), following=frozenset({("organizer", str(organizer).casefold())}))
    plans = build_evening_plans([culture, removed, duplicate, cancelled, music], context, WINDOW, frozenset({"music"}))
    first_ids = {item.event.id for item in plans[0].items}
    assert music.id in first_ids or duplicate.id in first_ids
    assert len(first_ids & {music.id, duplicate.id}) == 1
    assert not first_ids & {cancelled.id, removed.id}
    reasons = {reason for plan in plans for item in plan.items for reason in item.reasons}
    assert "Matches your Music preference" in reasons
    assert "From an organizer you follow" in reasons


def test_strategies_are_distinct_deterministic_and_relaxed_is_not_density_driven():
    events = [
        _event(1, start=BASE, category="Music"),
        _event(2, start=BASE + timedelta(hours=1, minutes=30), category="Culture"),
        _event(3, start=BASE + timedelta(hours=3), category="Family"),
        _event(4, start=BASE + timedelta(hours=5), category="Arts"),
    ]
    context = _context(interests=frozenset({"music"}), saved_categories=frozenset({"culture"}))
    first = build_evening_plans(events, context, WINDOW, frozenset({"music"}))
    second = build_evening_plans(list(reversed(events)), context, WINDOW, frozenset({"music"}))
    assert _signatures(first) == _signatures(second)
    assert len(_signatures(first)) == len(set(_signatures(first)))
    assert {plan.strategy for plan in first}.issubset(set(PlanningStrategy))
    best = next(plan for plan in first if plan.strategy == PlanningStrategy.best_match)
    relaxed = next(plan for plan in first if plan.strategy == PlanningStrategy.relaxed)
    different = next(plan for plan in first if plan.strategy == PlanningStrategy.something_different)
    assert len(best.items) == 1  # a strong match can beat a longer, weaker sequence
    assert len(relaxed.items) <= len(best.items)
    assert len({item.event.category for item in different.items}) >= len({item.event.category for item in best.items})


def test_empty_single_sparse_and_large_sets_stay_bounded():
    assert build_evening_plans([], _context(), WINDOW, frozenset()) == []
    single = build_evening_plans([_event(1)], _context(), WINDOW, frozenset())
    assert len(single) == 1 and single[0].limited is True and len(single[0].items) == 1
    events = [_event(index + 1, start=BASE + timedelta(minutes=index), duration=.25,
                     title=f"Distinct event {index}") for index in range(MAX_CANDIDATES)]
    plans = build_evening_plans(events, _context(), WINDOW, frozenset())
    assert MAX_CANDIDATES == 400 and BEAM_WIDTH == 24
    assert len(plans) <= MAX_PLANS and all(len(plan.items) <= MAX_PLAN_EVENTS for plan in plans)


def _account(client, db, email):
    client.post("/auth/register", json={"email": email, "password": "password123"})
    token = client.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    return db.query(User).filter_by(email=email).one(), {"Authorization": "Bearer " + token}


def _grant(db, user, *, expired=False):
    now = datetime.utcnow()
    db.add(EntitlementGrant(
        user_id=user.id, entitlement=BACITY_PLUS, source="test", reason_category="fixture",
        valid_from=now - timedelta(days=2 if expired else 0),
        valid_until=now - timedelta(days=1) if expired else now + timedelta(days=1),
    ))
    db.commit()


def _db_event(number, *, hour=18, minute=0, duration=1, status=EventStatus.fresh):
    start = datetime(2030, 6, 15, hour, minute)
    return Event(
        title=f"Evening DB event {number}", description="Real event", start_time=start,
        end_time=start + timedelta(hours=duration) if duration is not None else None,
        category=EventCategory.music, tags=[], latitude=48.1486, longitude=17.1077,
        source_url=f"https://example.com/evening/{number}", extraction_confidence=.9,
        source_reliability=.9, status=status,
    )


def _payload(**changes):
    values = {"date": "2030-06-15", "start_time": "20:00", "end_time": "02:00", "categories": ["Music"]}
    values.update(changes)
    return values


def test_evening_api_entitlement_spoofing_and_window_validation(client, db_session):
    path = "/recommendations/evening-plan"
    assert client.post(path, json=_payload()).status_code == 401
    free, free_headers = _account(client, db_session, "evening-free@example.com")
    assert client.post(path + "?is_plus=true", json={**_payload(), "is_plus": True}, headers=free_headers).status_code == 403
    expired, expired_headers = _account(client, db_session, "evening-expired@example.com")
    _grant(db_session, expired, expired=True)
    assert client.post(path, json=_payload(), headers=expired_headers).status_code == 403
    plus, headers = _account(client, db_session, "evening-plus@example.com")
    _grant(db_session, plus)
    assert client.post(path, json=_payload(), headers=headers).status_code == 200
    assert client.post(path, json=_payload(start_time="18:00", end_time="18:00"), headers=headers).status_code == 422
    assert client.post(path, json=_payload(start_time="10:00", end_time="23:00"), headers=headers).status_code == 422
    assert client.post(path, json=_payload(date="2020-01-01"), headers=headers).status_code == 422
    assert client.post(path, json=_payload(latitude=48.15), headers=headers).status_code == 422
    assert client.post(path, json=_payload(budget=20), headers=headers).status_code == 422
    assert client.post(path, json=_payload(area="Old Town"), headers=headers).status_code == 422


def test_evening_api_results_location_privacy_profile_stability_and_candidate_cap(client, db_session, caplog, monkeypatch):
    from app.api.routes import discovery

    user, headers = _account(client, db_session, "evening-results@example.com")
    user.interests = ["Culture"]
    _grant(db_session, user)
    original_interests = list(user.interests)
    events = [_db_event(index, hour=18 + (index % 6), minute=(index // 6) % 60)
              for index in range(MAX_CANDIDATES + 20)]
    events.append(_db_event(999, hour=21, status=EventStatus.cancelled))
    db_session.add_all(events)
    db_session.commit()
    received = []
    actual = discovery.build_evening_plans

    def capture(rows, context, window, categories):
        received.append(len(rows))
        return actual(rows, context, window, categories)

    monkeypatch.setattr(discovery, "build_evening_plans", capture)
    response = client.post("/recommendations/evening-plan", json=_payload(
        latitude=48.149, longitude=17.108,
    ), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert received == [MAX_CANDIDATES]
    assert body["location_used"] is True
    assert len(body["plans"]) <= MAX_PLANS
    assert all(len(plan["items"]) <= MAX_PLAN_EVENTS for plan in body["plans"])
    assert all("score" not in plan for plan in body["plans"])
    assert all("score" not in item for plan in body["plans"] for item in plan["items"])
    assert "48.149" not in caplog.text and "17.108" not in caplog.text
    db_session.refresh(user)
    assert user.interests == original_interests
    assert not hasattr(user, "latitude") and not hasattr(user, "longitude")
