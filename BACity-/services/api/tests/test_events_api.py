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
