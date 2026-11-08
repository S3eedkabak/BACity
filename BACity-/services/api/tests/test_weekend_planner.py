from datetime import date, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.core.entitlements import BACITY_PLUS
from app.core.recommendations import RecommendationContext
from app.core.weekend_planner import (
    BEAM_WIDTH,
    MAX_CANDIDATES,
    MAX_EVENTS_PER_DAY,
    MAX_PLANS,
    MAX_RANKED_PER_DAY,
    MAX_WEEKEND_EVENTS,
    WeekendDayInput,
    WeekendStrategy,
    build_weekend_plans,
    weekend_window,
)
from app.models.entitlement import EntitlementGrant
from app.models.event import Event, EventCategory, EventStatus
from app.models.user import User

SATURDAY = date(2030, 6, 15)
SATURDAY_WINDOW = weekend_window(SATURDAY, "Europe/Bratislava")
SUNDAY_WINDOW = weekend_window(SATURDAY + timedelta(days=1), "Europe/Bratislava")
BASE = SATURDAY_WINDOW.starts_at_utc + timedelta(hours=2)


def _context(**changes):
    values = dict(
        interests=frozenset(), saved_categories=frozenset(), following=frozenset(),
        save_counts={}, saved_event_ids=frozenset(), latitude=None, longitude=None,
    )
    values.update(changes)
    return RecommendationContext(**values)


def _event(number, *, start=None, duration=1, end_marker="default", category="Music", title=None,
           status="fresh", latitude=48.1486, longitude=17.1077, organization_id=None, venue_id=None):
    start = start or BASE
    end = start + timedelta(hours=duration) if end_marker == "default" else end_marker
    return SimpleNamespace(
        id=UUID(int=number), title=title or f"Weekend event {number}", description="Real event",
        start_time=start, end_time=end, timezone="Europe/Bratislava", category=category, tags=[],
        latitude=latitude, longitude=longitude, venue=None, venue_id=venue_id,
        organization_id=organization_id, contributor_id=None, neighborhood=None, address="Bratislava",
        extraction_confidence=.9, source_reliability=.9, created_at=BASE - timedelta(days=1), status=status,
    )


def _input(day, window, events):
    return WeekendDayInput(day, window, tuple(events))


def _signatures(plans):
    return [tuple(tuple(str(item.event.id) for item in day.items) for day in plan.days) for plan in plans]


def test_weekend_windows_use_bratislava_time_and_keep_days_distinct():
    assert SATURDAY.weekday() == 5
    assert SATURDAY_WINDOW.starts_at_utc == datetime(2030, 6, 15, 6)
    assert SATURDAY_WINDOW.ends_at_utc == datetime(2030, 6, 16, 1)
    assert SUNDAY_WINDOW.starts_at_utc == datetime(2030, 6, 16, 6)
    assert SUNDAY_WINDOW.ends_at_utc == datetime(2030, 6, 17, 1)
    winter = weekend_window(date(2030, 12, 7), "Europe/Bratislava")
    assert winter.starts_at_utc.hour == 7 and winter.ends_at_utc.hour == 2
    spring_dst = weekend_window(date(2030, 3, 30), "Europe/Bratislava")
    assert spring_dst.ends_at_utc == datetime(2030, 3, 31, 1)


def test_temporal_transition_unknown_end_and_missing_coordinates_are_conservative():
    first = _event(1, duration=2, latitude=None, longitude=None)
    overlap = _event(2, start=BASE + timedelta(hours=1), latitude=None, longitude=None)
    too_tight = _event(3, start=BASE + timedelta(hours=2, minutes=30), latitude=None, longitude=None)
    unknown = _event(4, start=BASE + timedelta(hours=4), end_marker=None, latitude=None, longitude=None)
    later = _event(5, start=BASE + timedelta(hours=7), latitude=None, longitude=None)
    plans = build_weekend_plans((_input(SATURDAY, SATURDAY_WINDOW, [first, overlap, too_tight, unknown, later]),), _context(), frozenset())
    signatures = _signatures(plans)
    assert all(not ({str(first.id), str(overlap.id)} <= set(signature[0])) for signature in signatures)
    assert all(not ({str(first.id), str(too_tight.id)} <= set(signature[0])) for signature in signatures)
    assert all(not any(item.event.id == unknown.id for item in plan.days[0].items[:-1]) for plan in plans)
    assert all(item.location_confidence in {None, "location_unknown"} for plan in plans for day in plan.days for item in day.items)
    unknown_only = build_weekend_plans((_input(SATURDAY, SATURDAY_WINDOW, [unknown]),), _context(), frozenset())
    assert unknown_only[0].days[0].items[-1].event.id == unknown.id


def test_strategies_are_real_distinct_deterministic_and_diverse():
    organizer = uuid4()
    events = [
        _event(1, category="Music", organization_id=organizer),
        _event(2, start=BASE + timedelta(hours=2), category="Culture"),
        _event(3, start=BASE + timedelta(hours=4), category="Exhibitions"),
        _event(4, start=BASE + timedelta(hours=7), category="Community"),
        _event(5, start=BASE + timedelta(hours=10), category="Theatre"),
    ]
    context = _context(interests=frozenset({"music"}), following=frozenset({("organizer", str(organizer).casefold())}))
    first = build_weekend_plans((_input(SATURDAY, SATURDAY_WINDOW, events),), context, frozenset({"culture"}))
    second = build_weekend_plans((_input(SATURDAY, SATURDAY_WINDOW, list(reversed(events))),), context, frozenset({"culture"}))
    assert _signatures(first) == _signatures(second)
    assert len(_signatures(first)) == len(set(_signatures(first)))
    strategies = {plan.strategy for plan in first}
    assert WeekendStrategy.relaxed in strategies
    assert WeekendStrategy.culture_heavy in strategies
    culture = next(plan for plan in first if plan.strategy == WeekendStrategy.culture_heavy)
    assert any(item.event.category in {"Culture", "Exhibitions", "Theatre"} for item in culture.days[0].items)
    relaxed = next(plan for plan in first if plan.strategy == WeekendStrategy.relaxed)
    assert len(relaxed.days[0].items) <= MAX_EVENTS_PER_DAY
    if WeekendStrategy.something_different in strategies:
        different = next(plan for plan in first if plan.strategy == WeekendStrategy.something_different)
        assert len({item.event.category for item in different.days[0].items}) >= 1


def test_status_duplicates_selected_categories_and_output_bounds():
    duplicate_venue = UUID(int=88)
    music = _event(1, category="Music", venue_id=duplicate_venue, title="City concert")
    duplicate = _event(2, category="Music", venue_id=duplicate_venue, title="City concert!")
    culture = _event(3, start=BASE + timedelta(hours=3), category="Culture")
    cancelled = _event(4, start=BASE + timedelta(hours=5), status="cancelled")
    removed = _event(5, start=BASE + timedelta(hours=7), status="removed")
    plans = build_weekend_plans(
        (_input(SATURDAY, SATURDAY_WINDOW, [duplicate, culture, removed, music, cancelled]),),
        _context(interests=frozenset({"music"})),
        frozenset({"culture"}),
    )
    assert len(plans) <= MAX_PLANS == 3
    assert len(_signatures(plans)) == len(set(_signatures(plans)))
    for plan in plans:
        ids = {item.event.id for item in plan.days[0].items}
        assert len(ids & {music.id, duplicate.id}) <= 1
        assert not ids & {cancelled.id, removed.id}
        assert len(plan.days[0].items) <= MAX_EVENTS_PER_DAY == 4
    reasons = {reason for plan in plans for day in plan.days for item in day.items for reason in item.reasons}
    assert "Matches your selected Culture interest" in reasons


def test_full_weekend_sparse_empty_single_and_large_sets_are_bounded():
    saturday_event = _event(1)
    plans = build_weekend_plans(
        (_input(SATURDAY, SATURDAY_WINDOW, [saturday_event]), _input(SATURDAY + timedelta(days=1), SUNDAY_WINDOW, [])),
        _context(),
        frozenset(),
    )
    assert len(plans) == 1 and plans[0].limited
    assert len(plans[0].days) == 2 and not plans[0].days[1].items
    assert build_weekend_plans((_input(SATURDAY, SATURDAY_WINDOW, []),), _context(), frozenset()) == []
    large = [_event(index + 1, start=BASE + timedelta(minutes=index * 5), duration=.25, title=f"Unique {index}")
             for index in range(MAX_RANKED_PER_DAY + 30)]
    bounded = build_weekend_plans((_input(SATURDAY, SATURDAY_WINDOW, large),), _context(), frozenset())
    assert BEAM_WIDTH == 32 and MAX_CANDIDATES == 600 and MAX_WEEKEND_EVENTS == 8
    assert all(sum(len(day.items) for day in plan.days) <= MAX_WEEKEND_EVENTS for plan in bounded)


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


def _payload(**changes):
    values = {"weekend_start": "2030-06-15", "mode": "weekend", "categories": ["Culture"]}
    values.update(changes)
    return values


def _db_event(number, *, day=0, hour=10, category=EventCategory.culture, duration=1):
    start = datetime(2030, 6, 15 + day, hour)
    return Event(
        title=f"Weekend DB event {number}", description="Real event", start_time=start,
        end_time=start + timedelta(hours=duration) if duration is not None else None,
        category=category, tags=[], latitude=48.1486, longitude=17.1077,
        source_url=f"https://example.com/weekend/{number}", extraction_confidence=.9,
        source_reliability=.9, status=EventStatus.fresh,
    )


def test_weekend_api_entitlement_spoofing_modes_and_validation(client, db_session):
    path = "/recommendations/weekend-plan"
    assert client.post(path, json=_payload()).status_code == 401
    free, free_headers = _account(client, db_session, "weekend-free@example.com")
    assert client.post(path + "?is_plus=true", json={**_payload(), "is_plus": True}, headers=free_headers).status_code == 403
    expired, expired_headers = _account(client, db_session, "weekend-expired@example.com")
    _grant(db_session, expired, expired=True)
    assert client.post(path, json=_payload(), headers=expired_headers).status_code == 403
    plus, headers = _account(client, db_session, "weekend-plus@example.com")
    _grant(db_session, plus)
    db_session.add_all([_db_event(900, day=0), _db_event(901, day=1)])
    db_session.commit()
    expected_days = {"saturday": ["Saturday"], "sunday": ["Sunday"], "weekend": ["Saturday", "Sunday"]}
    for mode, days in expected_days.items():
        response = client.post(path, json=_payload(mode=mode), headers=headers)
        assert response.status_code == 200
        assert [day["day"] for day in response.json()["plans"][0]["days"]] == days
    assert client.post(path, json=_payload(weekend_start="2030-06-16"), headers=headers).status_code == 422
    assert client.post(path, json=_payload(weekend_start="2020-06-13"), headers=headers).status_code == 422
    assert client.post(path, json=_payload(latitude=48.15), headers=headers).status_code == 422
    assert client.post(path, json=_payload(categories=["Culture"] * 7), headers=headers).status_code == 422
    assert client.post(path, json=_payload(budget=20), headers=headers).status_code == 422
    assert client.post(path, json=_payload(area="Old Town"), headers=headers).status_code == 422


def test_weekend_api_full_response_privacy_profile_stability_and_candidate_cap(client, db_session, caplog, monkeypatch):
    from app.api.routes import discovery

    user, headers = _account(client, db_session, "weekend-results@example.com")
    user.interests = ["Music"]
    _grant(db_session, user)
    original_interests = list(user.interests)
    events = [_db_event(index, day=index % 2, hour=10 + (index % 10)) for index in range(MAX_CANDIDATES + 20)]
    db_session.add_all(events)
    db_session.commit()
    received = []
    actual = discovery.build_weekend_plans

    def capture(days, context, categories):
        received.append(len(days[0].candidates))
        return actual(days, context, categories)

    monkeypatch.setattr(discovery, "build_weekend_plans", capture)
    response = client.post(path := "/recommendations/weekend-plan", json=_payload(
        latitude=48.149, longitude=17.108,
    ), headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert received == [MAX_CANDIDATES]
    assert body["mode"] == "weekend" and body["location_used"] is True
    assert len(body["plans"]) <= MAX_PLANS
    assert all([day["day"] for day in plan["days"]] == ["Saturday", "Sunday"] for plan in body["plans"])
    assert all(len(day["items"]) <= MAX_EVENTS_PER_DAY for plan in body["plans"] for day in plan["days"])
    assert all("score" not in plan for plan in body["plans"])
    assert "48.149" not in caplog.text and "17.108" not in caplog.text
    db_session.refresh(user)
    assert user.interests == original_interests
    assert not hasattr(user, "latitude") and not hasattr(user, "longitude")
