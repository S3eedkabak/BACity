from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from app.core.entitlements import BACITY_PLUS
from app.core.event_chains import (
    MAX_ALTERNATIVES,
    MAX_CANDIDATES,
    MAX_CHAIN_EVENTS,
    ChainMode,
    build_event_chains,
    required_transition,
)
from app.core.recommendations import RecommendationContext
from app.models.entitlement import EntitlementGrant
from app.models.event import Event, EventCategory, EventStatus
from app.models.user import User

BASE = datetime(2030, 6, 15, 20, 0)


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
        id=UUID(int=number), title=title or f"Chain event {number}", description="Real event",
        start_time=start or BASE, end_time=end, timezone="Europe/Bratislava",
        category=category, tags=[], latitude=latitude, longitude=longitude, venue=None,
        venue_id=venue_id, organization_id=organization_id, contributor_id=None,
        neighborhood="Staré Mesto", address="Bratislava", extraction_confidence=.9,
        source_reliability=.9, created_at=BASE - timedelta(days=1), status=status,
    )


def _anchor(*, end=BASE + timedelta(hours=2)):
    return _event(100, start=BASE, end=end, title="Anchor concert", category="Music")


def test_transition_buffers_use_distance_bands_and_missing_location_is_not_zero_distance():
    anchor = _anchor()
    nearby = _event(1, latitude=48.149, longitude=17.108)
    farther = _event(2, latitude=48.21, longitude=17.18)
    unknown = _event(3, latitude=None, longitude=None)
    assert required_transition(anchor, nearby).required_gap == timedelta(minutes=20)
    assert required_transition(anchor, farther).required_gap == timedelta(minutes=60)
    transition = required_transition(anchor, unknown)
    assert transition.required_gap == timedelta(minutes=60)
    assert transition.distance_km is None
    assert transition.location_confidence == "location_unknown"


def test_before_after_and_full_modes_keep_anchor_once_and_reject_overlap_or_tight_gaps():
    anchor = _anchor()
    before = _event(1, start=BASE - timedelta(hours=2), end=BASE - timedelta(minutes=45))
    after = _event(2, start=BASE + timedelta(hours=2, minutes=30), end=BASE + timedelta(hours=4))
    overlap = _event(3, start=BASE + timedelta(hours=1), end=BASE + timedelta(hours=3))
    too_tight = _event(4, start=BASE + timedelta(hours=2, minutes=10), end=BASE + timedelta(hours=3))
    candidates = [overlap, too_tight, after, before]
    before_chains = build_event_chains(anchor, candidates, _context(), ChainMode.before)
    after_chains = build_event_chains(anchor, candidates, _context(), ChainMode.after)
    full_chains = build_event_chains(anchor, candidates, _context(), ChainMode.full)
    assert all([item.relation.value for item in chain.items] == ["before", "anchor"] for chain in before_chains)
    assert all([item.relation.value for item in chain.items] == ["anchor", "after"] for chain in after_chains)
    assert any([item.relation.value for item in chain.items] == ["before", "anchor", "after"] for chain in full_chains)
    for chain in before_chains + after_chains + full_chains:
        assert sum(item.event.id == anchor.id for item in chain.items) == 1
        assert overlap.id not in {item.event.id for item in chain.items}
        assert too_tight.id not in {item.event.id for item in chain.items}


def test_unknown_end_is_only_safe_as_final_and_unknown_anchor_allows_before_only():
    anchor = _anchor()
    unknown_before = _event(1, start=BASE - timedelta(hours=2), end=None)
    unknown_after = _event(2, start=BASE + timedelta(hours=3), end=None)
    chains = build_event_chains(anchor, [unknown_before, unknown_after], _context(), ChainMode.full)
    assert chains
    assert unknown_before.id not in {item.event.id for chain in chains for item in chain.items}
    assert any(chain.items[-1].event.id == unknown_after.id for chain in chains)

    open_anchor = _anchor(end=None)
    known_before = _event(3, start=BASE - timedelta(hours=2), end=BASE - timedelta(hours=1))
    future = _event(4, start=BASE + timedelta(hours=2), end=BASE + timedelta(hours=3))
    result = build_event_chains(open_anchor, [known_before, future], _context(), ChainMode.full)
    assert result and all(chain.items[-1].event.id == open_anchor.id for chain in result)
    assert build_event_chains(open_anchor, [future], _context(), ChainMode.after) == []


def test_cross_midnight_timezone_and_dst_instants_remain_ordered():
    zone = ZoneInfo("Europe/Bratislava")
    anchor = _event(100, start=datetime(2030, 3, 30, 23, 30, tzinfo=zone),
                    end=datetime(2030, 3, 31, 1, 0, tzinfo=zone))
    before = _event(1, start=datetime(2030, 3, 30, 20, 0, tzinfo=zone),
                    end=datetime(2030, 3, 30, 22, 30, tzinfo=zone))
    after = _event(2, start=datetime(2030, 3, 31, 3, 30, tzinfo=zone), end=None)
    chains = build_event_chains(anchor, [before, after], _context(), ChainMode.full)
    assert chains
    assert [item.event.id for item in chains[0].items] == [before.id, anchor.id, after.id]


def test_duplicates_status_personalization_diversity_and_determinism():
    anchor = _anchor()
    organizer = uuid4()
    before = _event(1, start=BASE - timedelta(hours=2), end=BASE - timedelta(hours=1),
                    title="Gallery Opening", category="Arts", organization_id=organizer, venue_id=UUID(int=9))
    duplicate = _event(2, start=before.start_time, end=before.end_time, title="Gallery  Opening!",
                       category="Arts", organization_id=organizer, venue_id=UUID(int=9))
    after_music = _event(3, start=BASE + timedelta(hours=3), end=None, category="Music")
    after_family = _event(4, start=BASE + timedelta(hours=4), end=None, category="Family")
    cancelled = _event(5, start=BASE + timedelta(hours=3), end=None, status="cancelled")
    context = _context(interests=frozenset({"arts"}), following=frozenset({("organizer", str(organizer).casefold())}))
    source = [cancelled, after_family, duplicate, after_music, before]
    first = build_event_chains(anchor, source, context, ChainMode.full)
    second = build_event_chains(anchor, list(reversed(source)), context, ChainMode.full)
    assert [[item.event.id for item in chain.items] for chain in first] == [[item.event.id for item in chain.items] for chain in second]
    assert len(first) <= MAX_ALTERNATIVES
    assert all(len(chain.items) <= MAX_CHAIN_EVENTS for chain in first)
    assert all(cancelled.id not in {item.event.id for item in chain.items} for chain in first)
    assert all(not ({before.id, duplicate.id} <= {item.event.id for item in chain.items}) for chain in first)
    assert any("Based on your interest in Arts" in item.reasons for chain in first for item in chain.items)
    assert len({tuple(item.event.id for item in chain.items) for chain in first}) == len(first)


def test_empty_partial_and_large_candidate_sets_are_bounded():
    anchor = _anchor()
    assert build_event_chains(anchor, [], _context(), ChainMode.full) == []
    events = [_event(index + 1, start=BASE + timedelta(hours=3, minutes=index), end=None,
                     title=f"Distinct candidate {index}") for index in range(MAX_CANDIDATES)]
    result = build_event_chains(anchor, events, _context(), ChainMode.after)
    assert MAX_CANDIDATES == 300
    assert 0 < len(result) <= MAX_ALTERNATIVES == 3
    assert all(len(chain.items) == 2 for chain in result)


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


def _db_event(number, *, hours=24, duration=2, status=EventStatus.fresh):
    start = datetime.utcnow() + timedelta(hours=hours)
    return Event(
        title=f"DB chain event {number}", description="Real event", start_time=start,
        end_time=start + timedelta(hours=duration) if duration is not None else None,
        category=EventCategory.culture, tags=[], latitude=48.1486, longitude=17.1077,
        source_url=f"https://example.com/chain/{number}", extraction_confidence=.9,
        source_reliability=.9, status=status,
    )


def test_event_chain_api_entitlement_spoofing_validation_and_anchor_errors(client, db_session):
    anchor = _db_event(1)
    db_session.add(anchor)
    db_session.commit()
    path = "/recommendations/event-chain"
    payload = {"anchor_event_id": str(anchor.id), "mode": "full"}
    assert client.post(path, json=payload).status_code == 401
    free, free_headers = _account(client, db_session, "chains-free@example.com")
    assert client.post(path + "?is_plus=true", json={**payload, "is_plus": True}, headers=free_headers).status_code == 403
    expired, expired_headers = _account(client, db_session, "chains-expired@example.com")
    _grant(db_session, expired, expired=True)
    assert client.post(path, json=payload, headers=expired_headers).status_code == 403
    plus, plus_headers = _account(client, db_session, "chains-plus@example.com")
    _grant(db_session, plus)
    assert client.post(path, json={"anchor_event_id": "bad"}, headers=plus_headers).status_code == 422
    assert client.post(path, json={"anchor_event_id": str(uuid4())}, headers=plus_headers).status_code == 404
    assert client.post(path, json={**payload, "mode": "sideways"}, headers=plus_headers).status_code == 422
    assert client.post(path, json={**payload, "unexpected": True}, headers=plus_headers).status_code == 422
    assert client.post(path, json=payload, headers=plus_headers).status_code == 200

    for status in (EventStatus.cancelled, EventStatus.removed):
        invalid = _db_event(str(status), status=status)
        db_session.add(invalid)
        db_session.commit()
        invalid_payload = {"anchor_event_id": str(invalid.id), "mode": "full"}
        assert client.post(path, json=invalid_payload, headers=plus_headers).status_code == 409


def test_event_chain_api_returns_real_ordered_ephemeral_chains_and_empty_state(client, db_session):
    user, headers = _account(client, db_session, "chains-results@example.com")
    user.interests = ["Culture"]
    _grant(db_session, user)
    anchor = _db_event(10, hours=24, duration=2)
    before = _db_event(11, hours=21, duration=1)
    after = _db_event(12, hours=27, duration=None)
    cancelled = _db_event(13, hours=27, duration=None, status=EventStatus.cancelled)
    db_session.add_all([anchor, before, after, cancelled])
    db_session.commit()
    response = client.post("/recommendations/event-chain", json={
        "anchor_event_id": str(anchor.id), "mode": "full",
    }, headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert 0 < len(body["chains"]) <= MAX_ALTERNATIVES
    for chain in body["chains"]:
        ids = [item["event"]["id"] for item in chain["items"]]
        assert ids.count(str(anchor.id)) == 1
        assert str(cancelled.id) not in ids
        assert [item["relation"] for item in chain["items"]] in (
            ["before", "anchor"], ["anchor", "after"], ["before", "anchor", "after"],
        )
        assert all("score" not in item for item in chain["items"])

    isolated = _db_event(20, hours=240, duration=2)
    db_session.add(isolated)
    db_session.commit()
    empty = client.post("/recommendations/event-chain", json={
        "anchor_event_id": str(isolated.id), "mode": "full",
    }, headers=headers)
    assert empty.status_code == 200
    assert empty.json()["chains"] == []


def test_event_chain_api_caps_database_candidates(client, db_session, monkeypatch):
    from app.api.routes import discovery

    user, headers = _account(client, db_session, "chains-bounds@example.com")
    _grant(db_session, user)
    anchor = _db_event(500, hours=24, duration=2)
    candidates = [_db_event(index, hours=18 + index / 100, duration=1) for index in range(MAX_CANDIDATES + 25)]
    db_session.add_all([anchor, *candidates])
    db_session.commit()
    received = []

    def capture(anchor_event, rows, context, mode):
        received.append(len(rows))
        return []

    monkeypatch.setattr(discovery, "build_event_chains", capture)
    response = client.post("/recommendations/event-chain", json={
        "anchor_event_id": str(anchor.id), "mode": "full",
    }, headers=headers)
    assert response.status_code == 200
    assert received == [MAX_CANDIDATES]
