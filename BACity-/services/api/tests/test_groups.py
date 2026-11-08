from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.entitlements import BACITY_PLUS
from app.core.group_match import MAX_DB_CANDIDATES, MAX_PARTICIPANTS, MAX_VOTING_CANDIDATES, ParticipantPreference, rank_group_candidates
from app.core.recommendations import RecommendationContext
from app.models.community import UserBlock
from app.models.entitlement import EntitlementGrant
from app.models.event import Event, EventCategory, EventStatus
from app.models.group import GroupCandidate, GroupMatchRound, GroupParticipant, GroupSession, GroupVote
from app.models.user import User


class _FixedDateTime(datetime):
    @classmethod
    def utcnow(cls):
        return cls(2030, 6, 1, 12)


@pytest.fixture(autouse=True)
def _freeze_group_clock(monkeypatch):
    from app.api.routes import groups
    monkeypatch.setattr(groups, "datetime", _FixedDateTime)


def _context(**changes):
    values = dict(
        interests=frozenset(), saved_categories=frozenset(), following=frozenset(),
        save_counts={}, saved_event_ids=frozenset(), latitude=None, longitude=None,
    )
    values.update(changes)
    return RecommendationContext(**values)


def _simple_event(number, *, category="Music", title=None, hour=10, organization_id=None, venue_id=None, status="fresh"):
    start = datetime(2030, 6, 15, hour)
    return SimpleNamespace(
        id=UUID(int=number), title=title or f"Group event {number}", start_time=start,
        end_time=start + timedelta(hours=1), category=category, tags=[], status=status,
        latitude=48.1486, longitude=17.1077, venue=None, venue_id=venue_id,
        organization_id=organization_id, contributor_id=None, neighborhood=None, address="Bratislava",
        extraction_confidence=.9, source_reliability=.9, created_at=start - timedelta(days=1),
    )


def _account(client, db, email):
    client.post("/auth/register", json={"email": email, "password": "password123"})
    token = client.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    return db.query(User).filter_by(email=email).one(), {"Authorization": "Bearer " + token}


def _grant(db, user, *, expired=False):
    now = datetime.utcnow()
    grant = EntitlementGrant(
        user_id=user.id, entitlement=BACITY_PLUS, source="test", reason_category="fixture",
        valid_from=now - timedelta(days=2 if expired else 0),
        valid_until=now - timedelta(days=1) if expired else now + timedelta(days=1),
    )
    db.add(grant)
    db.commit()
    return grant


def _group_payload(**changes):
    values = {
        "name": "Saturday crew", "target_date": "2030-06-15",
        "start_time": "10:00", "end_time": "23:00",
        "categories": ["Music", "Culture"], "max_participants": 8,
    }
    values.update(changes)
    return values


def _create(client, db, email="host@example.com", **payload):
    host, headers = _account(client, db, email)
    _grant(db, host)
    response = client.post("/groups", json=_group_payload(**payload), headers=headers)
    assert response.status_code == 200, response.text
    return host, headers, response.json()


def _join(client, db, code, email):
    user, headers = _account(client, db, email)
    response = client.post("/groups/join", json={"code": code}, headers=headers)
    assert response.status_code == 200, response.text
    return user, headers, response.json()


def _ready(client, group_id, headers, likes=None, dislikes=None):
    response = client.patch(f"/groups/{group_id}/preferences", json={
        "liked_categories": likes or [], "disliked_categories": dislikes or [], "ready": True,
    }, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _db_event(number, *, hour=9, duration=1, category=EventCategory.music, title=None, organization_id=None, venue_id=None):
    start = datetime(2030, 6, 15, hour)
    return Event(
        title=title or f"Group DB event {number}", description="Real event", start_time=start,
        end_time=start + timedelta(hours=duration), category=category, tags=[],
        latitude=48.1486, longitude=17.1077, organization_id=organization_id, venue_id=venue_id,
        source_url=f"https://example.com/groups/{number}", extraction_confidence=.9,
        source_reliability=.9, status=EventStatus.fresh,
    )


def test_group_fairness_cold_start_diversity_duplicates_and_determinism():
    music = _simple_event(1, category="Music")
    culture = _simple_event(2, category="Culture", hour=11)
    duplicate = _simple_event(3, category="Music", title=music.title + "!", hour=10)
    arts = _simple_event(4, category="Arts", hour=12)
    participants = (
        ParticipantPreference(_context(interests=frozenset({"music"})), frozenset({"music"}), frozenset()),
        ParticipantPreference(_context(), frozenset({"culture"}), frozenset()),
        ParticipantPreference(_context(), frozenset(), frozenset({"music"})),
    )
    first = rank_group_candidates([music, culture, duplicate, arts], participants, frozenset(), datetime(2030, 6, 1))
    second = rank_group_candidates([arts, duplicate, culture, music], participants, frozenset(), datetime(2030, 6, 1))
    assert [item.event.id for item in first] == [item.event.id for item in second]
    assert first[0].event.id != music.id
    assert len({item.event.id for item in first} & {music.id, duplicate.id}) == 1
    assert len(first) <= MAX_VOTING_CANDIDATES == 5 and MAX_PARTICIPANTS == 12
    assert all("interest" not in " ".join(item.explanations).casefold() or "group" in " ".join(item.explanations).casefold() for item in first)


def test_create_entitlement_spoofing_and_host_expiry_behavior(client, db_session):
    assert client.post("/groups", json=_group_payload()).status_code == 401
    free, free_headers = _account(client, db_session, "group-free@example.com")
    assert client.post("/groups?is_plus=true", json={**_group_payload(), "is_plus": True}, headers=free_headers).status_code == 403
    expired, expired_headers = _account(client, db_session, "group-expired@example.com")
    _grant(db_session, expired, expired=True)
    assert client.post("/groups", json=_group_payload(), headers=expired_headers).status_code == 403

    host, host_headers, created = _create(client, db_session, "group-plus@example.com")
    group_id = created["group"]["id"]
    expired_join = client.post("/groups/join", json={"code": created["join_code"]}, headers=expired_headers)
    assert expired_join.status_code == 200
    participant, participant_headers, _ = _join(client, db_session, created["join_code"], "group-participant@example.com")
    _ready(client, group_id, host_headers)
    _ready(client, group_id, participant_headers)
    db_session.query(EntitlementGrant).filter_by(user_id=host.id).delete()
    db_session.commit()
    assert client.get(f"/groups/{group_id}", headers=host_headers).status_code == 200
    assert client.patch(f"/groups/{group_id}/preferences", json={"liked_categories": [], "disliked_categories": [], "ready": True}, headers=participant_headers).status_code == 200
    assert client.post(f"/groups/{group_id}/matches", json={}, headers=host_headers).status_code == 403
    assert client.post(f"/groups/{group_id}/matches", json={}, headers=participant_headers).status_code == 403


def test_invite_join_limits_blocking_idempotency_and_lifecycle(client, db_session):
    host, headers, created = _create(client, db_session, "invite-host@example.com", max_participants=2)
    group_id, code = created["group"]["id"], created["join_code"]
    participant, participant_headers, first = _join(client, db_session, code, "invite-member@example.com")
    duplicate = client.post("/groups/join", json={"code": code}, headers=participant_headers)
    assert duplicate.status_code == 200 and duplicate.json()["participant_count"] == first["participant_count"] == 2
    third, third_headers = _account(client, db_session, "invite-third@example.com")
    assert client.post("/groups/join", json={"code": code}, headers=third_headers).status_code == 409
    assert client.post("/groups/join", json={"code": "x" * 43}, headers=third_headers).status_code == 404
    assert client.delete(f"/groups/{group_id}/members/me", headers=headers).status_code == 409
    assert client.delete(f"/groups/{group_id}/members/me", headers=participant_headers).json() == {"left": True}
    assert client.get(f"/groups/{group_id}", headers=participant_headers).status_code == 404

    rotated = client.post(f"/groups/{group_id}/invite", headers=headers)
    assert rotated.status_code == 200 and rotated.json()["join_code"] != code
    session = db_session.query(GroupSession).filter_by(id=UUID(group_id)).one()
    session.invite_expires_at = _FixedDateTime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    assert client.post("/groups/join", json={"code": rotated.json()["join_code"]}, headers=third_headers).status_code == 404
    rotated = client.post(f"/groups/{group_id}/invite", headers=headers)
    assert rotated.status_code == 200
    db_session.add(UserBlock(user_id=host.id, blocked_id=third.id))
    db_session.commit()
    assert client.post("/groups/join", json={"code": rotated.json()["join_code"]}, headers=third_headers).status_code == 403
    cancelled = client.post(f"/groups/{group_id}/cancel", headers=headers)
    assert cancelled.status_code == 200 and cancelled.json()["status"] == "cancelled"
    assert client.post("/groups/join", json={"code": rotated.json()["join_code"]}, headers=third_headers).status_code == 404


def test_private_authorization_preference_and_idor_boundaries(client, db_session):
    host, headers, created = _create(client, db_session, "idor-host@example.com")
    group_id = created["group"]["id"]
    participant, participant_headers, _ = _join(client, db_session, created["join_code"], "idor-member@example.com")
    outsider, outsider_headers = _account(client, db_session, "idor-outsider@example.com")
    assert client.get("/groups/not-a-uuid", headers=outsider_headers).status_code == 422
    assert client.get(f"/groups/{group_id}", headers=outsider_headers).status_code == 404
    assert client.patch(f"/groups/{group_id}", json={"name": "stolen"}, headers=participant_headers).status_code == 403
    assert client.delete(f"/groups/{group_id}/members/{host.id}", headers=participant_headers).status_code == 403
    assert client.delete(f"/groups/{group_id}/members/{host.id}", headers=headers).status_code == 409
    malicious = client.patch(f"/groups/{group_id}/preferences", json={
        "user_id": str(host.id), "liked_categories": ["Music"], "disliked_categories": [], "ready": True,
    }, headers=participant_headers)
    assert malicious.status_code == 422
    detail = client.get(f"/groups/{group_id}", headers=headers).json()
    assert "liked_categories" not in str(detail) and "disliked_categories" not in str(detail)


def _prepared_group(client, db, prefix="match", participants=2, **payload):
    host, headers, created = _create(client, db, f"{prefix}-host@example.com", **payload)
    group_id = created["group"]["id"]
    people = [(host, headers)]
    for index in range(1, participants):
        member, member_headers, _ = _join(client, db, created["join_code"], f"{prefix}-member-{index}@example.com")
        people.append((member, member_headers))
    for index, (_, member_headers) in enumerate(people):
        _ready(client, group_id, member_headers, likes=["Music"] if index == 0 else ["Culture"], dislikes=["Nightlife"])
    return group_id, people


def test_match_candidate_bounds_privacy_sparse_and_request_location(client, db_session, caplog, monkeypatch):
    from app.api.routes import groups

    group_id, people = _prepared_group(client, db_session, "match-bounds")
    events = [_db_event(index, hour=9 + (index % 12), category=list(EventCategory)[index % len(EventCategory)])
              for index in range(MAX_DB_CANDIDATES + 20)]
    db_session.add_all(events)
    db_session.commit()
    received = []
    actual = groups.rank_group_candidates

    def capture(rows, participants, categories, now):
        received.append(len(rows))
        return actual(rows, participants, categories, now)

    monkeypatch.setattr(groups, "rank_group_candidates", capture)
    response = client.post(f"/groups/{group_id}/matches", json={"latitude": 48.149, "longitude": 17.108}, headers=people[0][1])
    assert response.status_code == 200, response.text
    body = response.json()
    assert received == [MAX_DB_CANDIDATES]
    assert body["status"] == "voting" and len(body["round"]["candidates"]) <= MAX_VOTING_CANDIDATES
    serialized = str(body)
    assert "match_score" not in serialized and "liked_categories" not in serialized and "disliked_categories" not in serialized
    assert "48.149" not in caplog.text and "17.108" not in caplog.text
    group = db_session.get(GroupSession, UUID(group_id))
    assert not hasattr(group, "latitude") and not hasattr(group, "longitude")

    empty_id, empty_people = _prepared_group(client, db_session, "match-empty", target_date="2030-06-22")
    empty = client.post(f"/groups/{empty_id}/matches", json={}, headers=empty_people[0][1])
    assert empty.status_code == 200 and empty.json()["round"]["candidates"] == [] and empty.json()["status"] == "completed"


def test_vote_privacy_update_auto_reveal_consensus_and_spoofing(client, db_session):
    group_id, people = _prepared_group(client, db_session, "votes")
    db_session.add_all([_db_event(1, hour=9), _db_event(2, hour=12, category=EventCategory.culture), _db_event(3, hour=20, duration=3, title="Ends too late")])
    db_session.commit()
    generated = client.post(f"/groups/{group_id}/matches", json={}, headers=people[0][1]).json()
    round_id = generated["round"]["id"]
    candidates = generated["round"]["candidates"]
    assert all(candidate["event"]["title"] != "Ends too late" for candidate in candidates)
    assert all(candidate["aggregate"] is None for candidate in candidates)
    first_candidate = candidates[0]["id"]
    spoof = client.patch(f"/groups/{group_id}/rounds/{round_id}/vote", json={
        "candidate_id": first_candidate, "value": 1, "user_id": str(people[1][0].id),
    }, headers=people[0][1])
    assert spoof.status_code == 422
    for value in (1, -1, 1):
        response = client.patch(f"/groups/{group_id}/rounds/{round_id}/vote", json={"candidate_id": first_candidate, "value": value}, headers=people[0][1])
        assert response.status_code == 200
    assert db_session.query(GroupVote).filter_by(user_id=people[0][0].id).count() == 1
    during = client.get(f"/groups/{group_id}", headers=people[1][1]).json()
    assert all(candidate["aggregate"] is None for candidate in during["round"]["candidates"])
    for _, member_headers in people:
        for candidate in candidates:
            client.patch(f"/groups/{group_id}/rounds/{round_id}/vote", json={
                "candidate_id": candidate["id"], "value": 1 if candidate["id"] == first_candidate else 0,
            }, headers=member_headers)
    revealed = client.get(f"/groups/{group_id}", headers=people[1][1]).json()
    assert revealed["round"]["status"] == "completed" and revealed["status"] == "completed"
    assert revealed["round"]["candidates"][0]["id"] == first_candidate
    assert revealed["round"]["candidates"][0]["aggregate"]["likes"] == 2


def test_host_reveal_participant_removal_and_plus_required_for_regeneration(client, db_session):
    group_id, people = _prepared_group(client, db_session, "reveal", participants=3)
    db_session.add_all([_db_event(10, hour=9), _db_event(11, hour=12)])
    db_session.commit()
    generated = client.post(f"/groups/{group_id}/matches", json={}, headers=people[0][1]).json()
    round_id = generated["round"]["id"]
    for candidate in generated["round"]["candidates"]:
        for _, headers in people[:2]:
            client.patch(f"/groups/{group_id}/rounds/{round_id}/vote", json={"candidate_id": candidate["id"], "value": 0}, headers=headers)
    removed = client.delete(f"/groups/{group_id}/members/{people[2][0].id}", headers=people[0][1])
    assert removed.status_code == 200 and removed.json()["round"]["status"] == "completed"
    db_session.query(EntitlementGrant).filter_by(user_id=people[0][0].id).delete()
    db_session.commit()
    assert client.post(f"/groups/{group_id}/matches", json={}, headers=people[0][1]).status_code == 403
    assert client.get(f"/groups/{group_id}", headers=people[1][1]).status_code == 200


def test_host_explicit_reveal_cross_group_vote_and_nonmember_vote_are_rejected(client, db_session):
    first_id, first_people = _prepared_group(client, db_session, "cross-first")
    second_id, second_people = _prepared_group(client, db_session, "cross-second")
    db_session.add_all([_db_event(30, hour=9), _db_event(31, hour=12, category=EventCategory.arts)])
    db_session.commit()
    first = client.post(f"/groups/{first_id}/matches", json={}, headers=first_people[0][1]).json()
    second = client.post(f"/groups/{second_id}/matches", json={}, headers=second_people[0][1]).json()
    first_round = first["round"]["id"]
    foreign_candidate = second["round"]["candidates"][0]["id"]
    assert client.patch(f"/groups/{first_id}/rounds/{first_round}/vote", json={
        "candidate_id": foreign_candidate, "value": 1,
    }, headers=first_people[1][1]).status_code == 404
    assert client.patch(f"/groups/{first_id}/rounds/{first_round}/vote", json={
        "candidate_id": first["round"]["candidates"][0]["id"], "value": 1,
    }, headers=second_people[1][1]).status_code == 404
    revealed = client.post(f"/groups/{first_id}/rounds/{first_round}/reveal", headers=first_people[0][1])
    assert revealed.status_code == 200 and revealed.json()["round"]["status"] == "completed"
    assert client.post(f"/groups/{second_id}/rounds/{second['round']['id']}/reveal", headers=first_people[1][1]).status_code == 404
    second_group = db_session.get(GroupSession, UUID(second_id))
    second_group.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    assert client.post(f"/groups/{second_id}/rounds/{second['round']['id']}/reveal", headers=second_people[0][1]).status_code == 409


def test_expiration_payload_limits_and_account_deletion_cleanup(client, db_session):
    host, headers, created = _create(client, db_session, "retention-host@example.com")
    group_id = created["group"]["id"]
    participant, participant_headers, _ = _join(client, db_session, created["join_code"], "retention-member@example.com")
    group = db_session.get(GroupSession, UUID(group_id))
    group.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db_session.commit()
    expired = client.get(f"/groups/{group_id}", headers=participant_headers)
    assert expired.status_code == 200 and expired.json()["status"] == "expired"
    assert client.patch(f"/groups/{group_id}/preferences", json={"liked_categories": [], "disliked_categories": [], "ready": True}, headers=participant_headers).status_code == 409
    assert client.delete(f"/groups/{group_id}/members/me", headers=participant_headers).status_code == 409
    assert client.delete(f"/groups/{group_id}/members/{participant.id}", headers=headers).status_code == 409
    assert client.post(f"/groups/{group_id}/cancel", headers=headers).status_code == 409
    too_many = client.post("/groups", json=_group_payload(categories=[category.value for category in list(EventCategory)[:7]]), headers=headers)
    assert too_many.status_code == 422
    client.request("DELETE", "/community/account", json={"reason": "privacy"}, headers=participant_headers)
    assert db_session.query(GroupParticipant).filter_by(user_id=participant.id).count() == 0
    assert client.get(f"/groups/{group_id}", headers=participant_headers).status_code == 401
