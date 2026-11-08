from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.core.entitlements import BACITY_PLUS
from app.core.recommendations import RecommendationContext
from app.core.tonight import (
    MAX_CANDIDATES,
    MAX_RESULTS,
    TonightClassification,
    classify_event,
    rank_tonight_events,
    tonight_window,
)
from app.models.entitlement import EntitlementGrant
from app.models.event import Event, EventCategory, EventStatus
from app.models.user import User

NOW = datetime(2026, 6, 15, 18, 0)  # 20:00 Europe/Bratislava (CEST)


def _context(**changes):
    values = dict(
        interests=frozenset(), saved_categories=frozenset(), following=frozenset(),
        save_counts={}, saved_event_ids=frozenset(), latitude=None, longitude=None,
    )
    values.update(changes)
    return RecommendationContext(**values)


def _event(number, *, start=None, end=None, title=None, category="Culture", status="fresh",
           latitude=48.1486, longitude=17.1077, organization_id=None, venue_id=None):
    return SimpleNamespace(
        id=UUID(int=number), title=title or f"Tonight event {number}", description="Local event",
        start_time=start or NOW + timedelta(hours=1), end_time=end,
        category=category, tags=[], latitude=latitude, longitude=longitude,
        venue_id=venue_id, organization_id=organization_id, contributor_id=None,
        neighborhood="Staré Mesto", address="Bratislava", extraction_confidence=.9,
        source_reliability=.9, created_at=NOW - timedelta(days=1), status=status,
    )


def test_right_now_requires_known_active_end_and_excludes_finished():
    window = tonight_window(NOW, "Europe/Bratislava")
    active = _event(1, start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=1))
    unknown_end = _event(2, start=NOW - timedelta(minutes=30), end=None)
    finished = _event(3, start=NOW - timedelta(hours=2), end=NOW - timedelta(seconds=1))
    future = _event(4, start=NOW + timedelta(minutes=30))
    invalid = _event(5, start=NOW + timedelta(minutes=30), end=NOW + timedelta(minutes=20))
    assert classify_event(active, window) == TonightClassification.happening_now
    assert classify_event(unknown_end, window) is None
    assert classify_event(finished, window) is None
    assert classify_event(future, window) == TonightClassification.starting_soon
    assert classify_event(invalid, window) is None


def test_starting_soon_is_exactly_two_hours_and_later_tonight_is_bounded():
    window = tonight_window(NOW, "Europe/Bratislava")
    assert classify_event(_event(1, start=NOW + timedelta(hours=2)), window) == TonightClassification.starting_soon
    assert classify_event(_event(2, start=NOW + timedelta(hours=2, seconds=1)), window) == TonightClassification.later_tonight
    tomorrow_afternoon = datetime(2026, 6, 16, 13, 0)  # 15:00 local
    assert classify_event(_event(3, start=tomorrow_afternoon), window) is None


def test_crossing_midnight_and_post_midnight_same_evening():
    before_midnight = tonight_window(datetime(2026, 1, 10, 22, 30), "Europe/Bratislava")
    crossing = _event(1, start=datetime(2026, 1, 10, 21, 0), end=datetime(2026, 1, 11, 1, 30))
    assert classify_event(crossing, before_midnight) == TonightClassification.happening_now

    after_midnight = tonight_window(datetime(2026, 1, 11, 0, 0), "Europe/Bratislava")
    assert after_midnight.starts_at_utc == datetime(2026, 1, 10, 16, 0)
    assert after_midnight.ends_at_utc == datetime(2026, 1, 11, 2, 0)
    assert classify_event(_event(2, start=datetime(2026, 1, 11, 1, 0)), after_midnight) == TonightClassification.starting_soon
    assert classify_event(_event(3, start=datetime(2026, 1, 11, 3, 0)), after_midnight) is None


def test_timezone_aware_input_and_dst_window_conversion():
    aware_now = datetime(2026, 3, 28, 21, 0, tzinfo=ZoneInfo("Europe/Bratislava"))
    window = tonight_window(aware_now, "Europe/Bratislava")
    assert window.now_utc == datetime(2026, 3, 28, 20, 0)
    assert window.starts_at_utc == datetime(2026, 3, 28, 16, 0)
    # DST starts overnight: 03:00 CEST is 01:00 UTC.
    assert window.ends_at_utc == datetime(2026, 3, 29, 1, 0)


def test_quality_status_duplicates_personalization_location_and_determinism():
    window = tonight_window(NOW, "Europe/Bratislava")
    organizer = uuid4()
    music = _event(1, title="City Concert", category="Music", organization_id=organizer, venue_id=UUID(int=99))
    duplicate = _event(2, title="City  Concert!", category="Music", organization_id=organizer, venue_id=UUID(int=99))
    family = _event(3, category="Family", latitude=48.30, longitude=17.30)
    cancelled = _event(4, status="cancelled")
    removed = _event(5, status="removed")
    expired = _event(6, status="expired")
    stale = _event(7, title="Still verified stale event", status="stale")
    context = _context(
        interests=frozenset({"music"}), following=frozenset({("organizer", str(organizer).casefold())}),
        save_counts={family.id: 100_000}, latitude=48.149, longitude=17.108,
    )
    first = rank_tonight_events([family, cancelled, duplicate, music, removed, expired, stale], context, window)
    second = rank_tonight_events([stale, expired, removed, music, duplicate, cancelled, family], context, window)
    assert [item.event.id for item in first] == [item.event.id for item in second]
    assert first[0].event.id in {music.id, duplicate.id}
    assert "Based on your interest in Music" in first[0].reasons
    assert "From an organizer you follow" in first[0].reasons
    assert len({item.event.id for item in first} & {music.id, duplicate.id}) == 1
    assert not {cancelled.id, removed.id, expired.id} & {item.event.id for item in first}
    assert stale.id in {item.event.id for item in first}
    assert family.id in {item.event.id for item in first}  # bounded popularity cannot erase diversity
    location_only = rank_tonight_events([family, music], _context(latitude=48.149, longitude=17.108), window)
    assert location_only[0].event.id == music.id
    assert "Near you" in location_only[0].reasons


def test_empty_and_large_sets_remain_bounded():
    window = tonight_window(NOW, "Europe/Bratislava")
    assert rank_tonight_events([], _context(), window) == []
    events = [_event(index + 1, title=f"Distinct tonight event {index}") for index in range(600)]
    result = rank_tonight_events(events[:MAX_CANDIDATES], _context(), window)
    assert len(result) <= MAX_RESULTS == 12


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


def _api_event(number, *, minutes=30, end_minutes=None, status=EventStatus.fresh):
    return Event(
        title=f"Tonight API event {number}", description="Complete local event",
        start_time=NOW + timedelta(minutes=minutes),
        end_time=NOW + timedelta(minutes=end_minutes) if end_minutes is not None else None,
        category=EventCategory.music, tags=["music"], latitude=48.1486, longitude=17.1077,
        address="Bratislava", source_url=f"https://example.com/tonight/{number}",
        extraction_confidence=.9, source_reliability=.9, status=status,
    )


def test_tonight_api_enforces_plus_and_spoofing_cannot_bypass(client, db_session):
    assert client.post("/recommendations/tonight", json={}).status_code == 401
    free, free_headers = _account(client, db_session, "tonight-free@example.com")
    assert client.post("/recommendations/tonight?is_plus=true", json={"is_plus": True}, headers=free_headers).status_code == 403

    expired, expired_headers = _account(client, db_session, "tonight-expired@example.com")
    _grant(db_session, expired, expired=True)
    assert client.post("/recommendations/tonight", json={}, headers=expired_headers).status_code == 403

    plus, plus_headers = _account(client, db_session, "tonight-plus@example.com")
    _grant(db_session, plus)
    assert client.post(
        "/recommendations/tonight", json={"latitude": 48.149}, headers=plus_headers
    ).status_code == 422
    response = client.post("/recommendations/tonight", json={}, headers=plus_headers)
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_tonight_api_citywide_location_privacy_and_real_events(client, db_session, caplog, monkeypatch):
    from app.api.routes import discovery

    class FixedDateTime(datetime):
        @classmethod
        def utcnow(cls):
            return NOW

    monkeypatch.setattr(discovery, "datetime", FixedDateTime)
    user, headers = _account(client, db_session, "tonight-results@example.com")
    user.interests = ["Music"]
    _grant(db_session, user)
    db_session.add_all([
        _api_event(1, minutes=-30, end_minutes=60),
        _api_event(2, minutes=-30),  # unknown end: never happening now
        _api_event(3, minutes=45),
        _api_event(4, minutes=90, status=EventStatus.cancelled),
    ])
    db_session.commit()

    citywide = client.post("/recommendations/tonight", json={}, headers=headers)
    located = client.post("/recommendations/tonight", json={
        "latitude": 48.149, "longitude": 17.108,
    }, headers=headers)
    assert citywide.status_code == located.status_code == 200
    assert citywide.json()["location_used"] is False
    assert located.json()["location_used"] is True
    assert {item["classification"] for item in located.json()["items"]} == {"happening_now", "starting_soon"}
    assert all("score" not in item for item in located.json()["items"])
    assert any("Near you" in item["reasons"] for item in located.json()["items"])
    assert "48.149" not in caplog.text and "17.108" not in caplog.text
    db_session.refresh(user)
    assert not hasattr(user, "latitude") and not hasattr(user, "longitude")
