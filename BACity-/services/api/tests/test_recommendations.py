from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.core.recommendations import RecommendationContext, rank_events
from app.models.event import Event, EventCategory, EventStatus
from app.models.saved_event import SavedEvent
from app.models.community import Follow
from app.models.user import User


NOW = datetime(2026, 1, 10, 12, 0)


def _context(**changes):
    values = dict(
        interests=frozenset(),
        saved_categories=frozenset(),
        following=frozenset(),
        save_counts={},
        saved_event_ids=frozenset(),
        latitude=None,
        longitude=None,
    )
    values.update(changes)
    return RecommendationContext(**values)


def _event(number, *, category="Culture", hours=48, latitude=48.1486,
           longitude=17.1077, title=None, organization_id=None, created_days=10,
           status="fresh", venue_id=None, address="Bratislava"):
    return SimpleNamespace(
        id=UUID(int=number),
        title=title or f"Event {number}",
        description="Useful local event",
        start_time=NOW + timedelta(hours=hours),
        category=category,
        tags=[],
        latitude=latitude,
        longitude=longitude,
        venue_id=venue_id,
        organization_id=organization_id,
        contributor_id=None,
        neighborhood="Staré Mesto",
        address=address,
        extraction_confidence=0.8,
        source_reliability=0.8,
        created_at=NOW - timedelta(days=created_days),
        status=status,
    )


def test_new_user_feed_is_deterministic_and_excludes_expired_events():
    events = [_event(1, hours=-1), _event(2, hours=24), _event(3, hours=72)]
    first = rank_events(events, _context(), now=NOW)
    second = rank_events(list(reversed(events)), _context(), now=NOW)
    assert [item.event.id for item in first] == [item.event.id for item in second]
    assert UUID(int=1) not in {item.event.id for item in first}
    assert first[0].reasons


def test_interest_and_saved_category_affinity_improve_placement():
    culture = _event(1, category="Culture")
    music = _event(2, category="Music")
    ranked = rank_events([culture, music], _context(
        interests=frozenset({"music"}), saved_categories=frozenset({"music"})
    ), now=NOW)
    assert ranked[0].event.id == music.id
    assert "Based on your interest in Music" in ranked[0].reasons
    assert "Because you saved similar events" in ranked[0].reasons


def test_family_interest_and_followed_organizer_are_explainable():
    organizer_id = uuid4()
    family = _event(1, category="Family", organization_id=organizer_id)
    other = _event(2, category="Nightlife")
    ranked = rank_events([other, family], _context(
        interests=frozenset({"family"}),
        following=frozenset({("organizer", str(organizer_id).casefold())}),
    ), now=NOW)
    assert ranked[0].event.id == family.id
    assert "Based on your interest in Family" in ranked[0].reasons
    assert "From an organizer you follow" in ranked[0].reasons


def test_location_only_affects_ranking_when_coordinates_are_supplied():
    near = _event(1, latitude=48.1486, longitude=17.1077)
    far = _event(2, latitude=48.30, longitude=17.30)
    without_location = rank_events([far, near], _context(), now=NOW)
    with_location = rank_events([far, near], _context(
        latitude=48.149, longitude=17.108
    ), now=NOW)
    assert with_location[0].event.id == near.id
    assert "Near you" in with_location[0].reasons
    assert all("Near you" not in item.reasons for item in without_location)


def test_popularity_is_unique_bounded_and_cannot_overpower_relevance():
    popular = _event(1, category="Culture")
    relevant = _event(2, category="Music", created_days=0)
    ranked = rank_events([popular, relevant], _context(
        interests=frozenset({"music"}), save_counts={popular.id: 10_000}
    ), now=NOW)
    assert ranked[0].event.id == relevant.id
    assert ranked[1].score < ranked[0].score
    assert "Popular in Bratislava" in ranked[1].reasons


def test_near_duplicates_are_suppressed_but_separate_occurrences_remain():
    first = _event(1, title="City Concert", hours=24, venue_id=UUID(int=99))
    duplicate = _event(2, title="City  Concert!", hours=25, venue_id=UUID(int=99))
    later = _event(3, title="City Concert", hours=31, venue_id=UUID(int=99))
    ranked = rank_events([first, duplicate, later], _context(), now=NOW)
    assert len(ranked) == 2
    assert later.id in {item.event.id for item in ranked}


def test_category_and_organizer_diversity_breaks_feed_monopoly():
    organizer = uuid4()
    items = [
        _event(1, category="Music", organization_id=organizer),
        _event(2, category="Music", organization_id=organizer),
        _event(3, category="Music", organization_id=organizer),
        _event(4, category="Family", organization_id=uuid4()),
    ]
    ranked = rank_events(items, _context(), now=NOW)
    assert ranked[0].event.id == items[0].id
    assert ranked[1].event.category == "Family"


def test_large_synthetic_ranking_is_bounded_and_complete():
    events = [_event(index + 1, hours=24 + index, title=f"Distinct event {index}")
              for index in range(500)]
    ranked = rank_events(events, _context(), now=NOW)
    assert len(ranked) == 500
    assert len({item.event.id for item in ranked}) == 500


def _api_event(number, *, hours=24, category=EventCategory.music, title=None, status=EventStatus.fresh):
    return Event(
        title=title or f"API recommendation {number}",
        description="Complete event details",
        start_time=datetime.utcnow() + timedelta(hours=hours),
        category=category,
        tags=[category.value.casefold()],
        latitude=48.1486,
        longitude=17.1077,
        address="Bratislava",
        source_url=f"https://example.com/recommendation/{number}",
        extraction_confidence=0.9,
        source_reliability=0.9,
        status=status,
    )


def _authenticated_user(client, db):
    email = "recommendations@example.com"
    client.post("/auth/register", json={"email": email, "password": "password123"})
    user = db.query(User).filter_by(email=email).one()
    user.email_verified = True
    db.commit()
    token = client.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    return user, {"Authorization": "Bearer " + token}


def test_recommendation_api_paginates_explains_and_keeps_location_private(client, db_session, caplog):
    user, headers = _authenticated_user(client, db_session)
    user.interests = ["Music"]
    for number in range(15):
        db_session.add(_api_event(number, hours=24 + number * 3))
    db_session.add(_api_event(99, hours=-2))
    db_session.commit()

    first = client.post("/recommendations/query", json={
        "limit": 5, "offset": 0, "latitude": 48.149, "longitude": 17.108
    }, headers=headers)
    second = client.get("/recommendations", params={"limit": 5, "offset": 5}, headers=headers)
    assert first.status_code == second.status_code == 200
    assert len(first.json()) == len(second.json()) == 5
    assert {item["event"]["id"] for item in first.json()}.isdisjoint(
        {item["event"]["id"] for item in second.json()}
    )
    assert all(item["reasons"] and "score" not in item for item in first.json())
    assert any("Near you" in item["reasons"] for item in first.json())
    assert "48.149" not in caplog.text and "17.108" not in caplog.text
    db_session.refresh(user)
    assert not hasattr(user, "latitude") and not hasattr(user, "longitude")
    assert client.get("/recommendations").status_code == 401
    assert client.post("/recommendations/query", json={}).status_code == 401


def test_repeated_save_and_follow_actions_do_not_inflate_ranking(client, db_session):
    user, headers = _authenticated_user(client, db_session)
    event = _api_event(200, category=EventCategory.music)
    db_session.add(event)
    db_session.commit()

    assert client.post(f"/events/{event.id}/save", headers=headers).status_code == 201
    assert client.post(f"/events/{event.id}/save", headers=headers).status_code == 201
    follow = {"target_type": "category", "target_id": "Music"}
    assert client.post("/community/follows", json=follow, headers=headers).status_code == 200
    assert client.post("/community/follows", json=follow, headers=headers).status_code == 200

    assert db_session.query(SavedEvent).filter_by(user_id=user.id, event_id=event.id).count() == 1
    assert db_session.query(Follow).filter_by(
        user_id=user.id, target_type="category", target_id="Music"
    ).count() == 1
    result = client.post("/recommendations/query", json={}, headers=headers).json()[0]
    assert result["saved"] is True
    assert "Because you follow Music" in result["reasons"]
    assert "Popular in Bratislava" not in result["reasons"]
