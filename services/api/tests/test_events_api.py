

from datetime import datetime, timedelta


def test_crawler_can_ingest_event_and_is_idempotent(client):
    payload = {
        "title": "Bratislava Test Concert",
        "description": "Created by the crawler ingestion contract.",
        "start_time": (datetime.utcnow() + timedelta(days=3)).isoformat(),
        "timezone": "Europe/Bratislava",
        "address": "Bratislava, Slovakia",
        "category": "Music",
        "tags": ["music"],
        "price": 0,
        "currency": "EUR",
        "source_url": "https://visitbratislava.com/events/bratislava-test-concert",
        "language": "en",
        "extraction_confidence": 0.95,
        "source_reliability": 0.9,
    }

    first = client.post("/events", json=payload)
    assert first.status_code == 201
    event_id = first.json()["id"]

    second = client.post("/events", json=payload)
    assert second.status_code == 201
    assert second.json()["id"] == event_id

    listed = client.get("/events").json()
    assert listed["total"] == 1
    assert listed["items"][0]["title"] == "Bratislava Test Concert"


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_list_events_empty(client):
    resp = client.get("/events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["items"] == []


def test_list_events_returns_seeded_event(client, sample_event):
    resp = client.get("/events")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Techno Night"
    assert body["items"][0]["venue"]["name"] == "Fuga"


def test_get_event_by_id(client, sample_event):
    resp = client.get(f"/events/{sample_event.id}")
    assert resp.status_code == 200
    assert resp.json()["title"] == "Techno Night"


def test_get_event_404(client):
    import uuid
    resp = client.get(f"/events/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_search_events(client, sample_event):
    resp = client.get("/events/search", params={"q": "techno"})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Techno Night"


def test_search_events_no_match(client, sample_event):
    resp = client.get("/events/search", params={"q": "jazz"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_nearby_events_within_radius(client, sample_event):
    # ~500m from the venue used in sample_event
    resp = client.get("/events/nearby", params={"lat": 48.1420, "lng": 17.1190, "radius_km": 2})
    assert resp.status_code == 200
    results = resp.json()
    assert len(results) == 1
    assert results[0]["title"] == "Techno Night"


def test_nearby_events_outside_radius(client, sample_event):
    # Vienna - ~55km away, well outside a 5km radius
    resp = client.get("/events/nearby", params={"lat": 48.2082, "lng": 16.3738, "radius_km": 5})
    assert resp.status_code == 200
    assert resp.json() == []


def test_free_only_filter(client, db_session, sample_venue):
    from app.models.event import Event, EventCategory
    from datetime import datetime, timedelta
    import uuid

    free_event = Event(
        id=uuid.uuid4(), title="Free Jam Session",
        start_time=datetime.utcnow() + timedelta(days=2),
        venue_id=sample_venue.id, category=EventCategory.music,
        price=0.0, source_url="https://example.com/jam",
    )
    paid_event = Event(
        id=uuid.uuid4(), title="Paid Concert",
        start_time=datetime.utcnow() + timedelta(days=2),
        venue_id=sample_venue.id, category=EventCategory.music,
        price=25.0, source_url="https://example.com/concert",
    )
    db_session.add_all([free_event, paid_event])
    db_session.commit()

    resp = client.get("/events", params={"free_only": True})
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["title"] == "Free Jam Session"


def test_venue_events(client, sample_venue, sample_event):
    resp = client.get(f"/venues/{sample_venue.id}/events")
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    

def test_save_and_unsave_event_flow(client, sample_event):
    client.post("/auth/register", json={"email": "saver@example.com", "password": "pw123456"})
    token = client.post("/auth/login", json={
        "email": "saver@example.com", "password": "pw123456",
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post(f"/events/{sample_event.id}/save", headers=headers)
    assert resp.status_code == 201
    assert resp.json()["saved"] is True

    resp = client.get("/users/me/saved-events", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["title"] == "Techno Night"

    resp = client.delete(f"/events/{sample_event.id}/save", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["saved"] is False

    resp = client.get("/users/me/saved-events", headers=headers)
    assert resp.json() == []


def test_save_event_requires_auth(client, sample_event):
    resp = client.post(f"/events/{sample_event.id}/save")
    assert resp.status_code == 401


def test_save_nonexistent_event_404s(client):
    import uuid
    client.post("/auth/register", json={"email": "saver2@example.com", "password": "pw123456"})
    token = client.post("/auth/login", json={
        "email": "saver2@example.com", "password": "pw123456",
    }).json()["access_token"]
    resp = client.post(f"/events/{uuid.uuid4()}/save", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
