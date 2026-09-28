from datetime import datetime, timedelta
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.core.entitlements import BACITY_PLUS
from app.models.area_watch import AreaWatch
from app.models.entitlement import EntitlementGrant
from app.models.event import Event, EventCategory, EventStatus
from app.models.user import User
from app.schemas.area_watch import AreaWatchCreate


class _Clock(datetime):
    current = datetime(2030, 6, 1, 12)

    @classmethod
    def utcnow(cls):
        return cls.current


@pytest.fixture(autouse=True)
def _freeze_clock(monkeypatch):
    from app.api.routes import area_watches
    _Clock.current = datetime(2030, 6, 1, 12)
    monkeypatch.setattr(area_watches, "datetime", _Clock)


def _account(client, db, email):
    client.post("/auth/register", json={"email": email, "password": "password123"})
    token = client.post("/auth/login", json={"email": email, "password": "password123"}).json()["access_token"]
    return db.query(User).filter_by(email=email).one(), {"Authorization": "Bearer " + token}


def _grant(db, user, expired=False):
    now = datetime.utcnow()
    db.add(EntitlementGrant(
        user_id=user.id, entitlement=BACITY_PLUS, source="test", reason_category="fixture",
        valid_from=now - timedelta(days=2),
        valid_until=now - timedelta(days=1) if expired else now + timedelta(days=1),
    ))
    db.commit()


def _payload(**changes):
    values = {"name": "City Centre", "center_latitude": 48.1486, "center_longitude": 17.1077, "radius_km": 2, "categories": []}
    values.update(changes)
    return values


def _create(client, db, email="watch-plus@example.com", **changes):
    user, headers = _account(client, db, email)
    _grant(db, user)
    response = client.post("/area-watches", json=_payload(**changes), headers=headers)
    assert response.status_code == 200, response.text
    return user, headers, response.json()


def _event(number, *, latitude=48.1486, longitude=17.1077, created=None, category=EventCategory.music, status=EventStatus.fresh, title=None):
    return Event(
        title=title or f"Area event {number}", description="Real discovered event",
        start_time=_Clock.current + timedelta(days=10, hours=number), end_time=_Clock.current + timedelta(days=10, hours=number + 1),
        latitude=latitude, longitude=longitude, category=category, tags=[],
        source_url=f"https://example.com/area/{number}", extraction_confidence=.9, source_reliability=.9,
        status=status, created_at=created or (_Clock.current - timedelta(hours=number)),
    )


def test_entitlement_creation_spoofing_and_expired_lock(client, db_session):
    assert client.post("/area-watches", json=_payload()).status_code == 401
    free, free_headers = _account(client, db_session, "watch-free@example.com")
    assert client.post("/area-watches?is_plus=true", json={**_payload(), "is_plus": True}, headers=free_headers).status_code == 403
    expired, expired_headers = _account(client, db_session, "watch-expired@example.com")
    _grant(db_session, expired, expired=True)
    assert client.post("/area-watches", json=_payload(), headers=expired_headers).status_code == 403

    user, headers, watch = _create(client, db_session)
    db_session.add(_event(1)); db_session.commit()
    assert client.get(f"/area-watches/{watch['id']}/events", headers=headers).status_code == 200
    db_session.query(EntitlementGrant).filter_by(user_id=user.id).delete(); db_session.commit()
    listing = client.get("/area-watches", headers=headers).json()
    assert listing[0]["locked"] is True and listing[0]["unseen_count"] == 0
    assert client.get(f"/area-watches/{watch['id']}/events", headers=headers).status_code == 403
    assert client.patch(f"/area-watches/{watch['id']}", json={"name": "Changed"}, headers=headers).status_code == 403
    assert client.delete(f"/area-watches/{watch['id']}", headers=headers).status_code == 200


def test_ownership_idor_and_malformed_ids(client, db_session):
    _, owner_headers, watch = _create(client, db_session, "watch-owner@example.com")
    _, outsider_headers = _account(client, db_session, "watch-outsider@example.com")
    for method, path, body in [
        ("get", f"/area-watches/{watch['id']}", None),
        ("patch", f"/area-watches/{watch['id']}", {"name": "Stolen"}),
        ("delete", f"/area-watches/{watch['id']}", None),
        ("get", f"/area-watches/{watch['id']}/events", None),
        ("post", f"/area-watches/{watch['id']}/seen", {"watermark": _Clock.current.isoformat()}),
    ]:
        response = getattr(client, method)(path, headers=outsider_headers, **({"json": body} if body is not None else {}))
        assert response.status_code == 404
    assert client.get("/area-watches/not-a-uuid", headers=owner_headers).status_code == 422


def test_geography_boundary_missing_coordinates_and_validation(client, db_session):
    _, headers, watch = _create(client, db_session, "watch-geo@example.com", radius_km=1)
    inside = _event(1, latitude=48.1486 + .0089)
    outside = _event(2, latitude=48.1486 + .0092)
    missing = _event(3, latitude=None, longitude=None)
    db_session.add_all([inside, outside, missing]); db_session.commit()
    items = client.get(f"/area-watches/{watch['id']}/events", headers=headers).json()["items"]
    assert [item["event"]["id"] for item in items] == [str(inside.id)]
    for payload in [_payload(center_latitude=47), _payload(radius_km=500)]:
        assert client.post("/area-watches", json=payload, headers=headers).status_code == 422
    for payload in [_payload(center_latitude=float("nan")), _payload(center_longitude=float("inf"))]:
        with pytest.raises(ValidationError):
            AreaWatchCreate.model_validate(payload)


def test_discovery_semantics_status_category_lookback_and_dedup(client, db_session):
    _, headers, watch = _create(client, db_session, "watch-discovery@example.com", categories=["Music"])
    fresh = _event(1, created=_Clock.current - timedelta(hours=1), title="Same concert")
    duplicate = _event(2, created=_Clock.current - timedelta(hours=2), title="Same concert")
    duplicate.start_time = fresh.start_time; duplicate.end_time = fresh.end_time; duplicate.address = fresh.address = "Square 1"
    old = _event(3, created=_Clock.current - timedelta(days=31)); old.updated_at = _Clock.current
    cancelled = _event(4, status=EventStatus.cancelled)
    removed = _event(5, status=EventStatus.removed)
    culture = _event(6, category=EventCategory.culture)
    db_session.add_all([fresh, duplicate, old, cancelled, removed, culture]); db_session.commit()
    feed = client.get(f"/area-watches/{watch['id']}/events", headers=headers).json()
    assert [item["event"]["id"] for item in feed["items"]] == [str(fresh.id)]
    assert feed["lookback_days"] == 30 and feed["items"][0]["discovered_at"].startswith("2030-06-01")


def test_seen_watermark_is_monotonic_and_race_safe(client, db_session):
    _, headers, watch = _create(client, db_session, "watch-seen@example.com")
    first = _event(1, created=_Clock.current - timedelta(minutes=10)); db_session.add(first); db_session.commit()
    feed = client.get(f"/area-watches/{watch['id']}/events", headers=headers).json()
    assert feed["unseen_count"] == 1 and feed["items"][0]["unseen"] is True
    watermark = feed["response_watermark"]
    assert client.post(f"/area-watches/{watch['id']}/seen", json={"watermark": watermark}, headers=headers).json()["unseen_count"] == 0
    old_mark = (_Clock.current - timedelta(days=1)).isoformat()
    client.post(f"/area-watches/{watch['id']}/seen", json={"watermark": old_mark}, headers=headers)
    stored = db_session.get(AreaWatch, UUID(watch["id"])); db_session.refresh(stored)
    assert stored.last_viewed_at == _Clock.current
    _Clock.current += timedelta(minutes=1)
    new = _event(2, created=_Clock.current - timedelta(seconds=1)); db_session.add(new); db_session.commit()
    next_feed = client.get(f"/area-watches/{watch['id']}/events", headers=headers).json()
    assert next_feed["unseen_count"] == 1 and next_feed["items"][0]["event"]["id"] == str(new.id)
    assert client.post(f"/area-watches/{watch['id']}/seen", json={"watermark": (_Clock.current + timedelta(minutes=1)).isoformat()}, headers=headers).status_code == 422


def test_limits_pagination_edit_and_no_category_filter(client, db_session):
    user, headers = _account(client, db_session, "watch-limits@example.com"); _grant(db_session, user)
    watch = None
    for index in range(5):
        response = client.post("/area-watches", json=_payload(name=f"Watch {index}"), headers=headers)
        assert response.status_code == 200
        watch = watch or response.json()
    assert client.post("/area-watches", json=_payload(name="Watch 6"), headers=headers).status_code == 409
    assert client.post("/area-watches", json=_payload(name="Watch 0"), headers=headers).status_code == 409
    for index in range(1, 6): db_session.add(_event(index, category=EventCategory.music if index % 2 else EventCategory.culture))
    db_session.commit()
    first = client.get(f"/area-watches/{watch['id']}/events?limit=2", headers=headers).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = client.get(f"/area-watches/{watch['id']}/events?limit=2&cursor={first['next_cursor']}", headers=headers).json()
    assert not ({item['event']['id'] for item in first['items']} & {item['event']['id'] for item in second['items']})
    assert client.get(f"/area-watches/{watch['id']}/events?limit=51", headers=headers).status_code == 422
    updated = client.patch(f"/area-watches/{watch['id']}", json={"categories": ["Culture"], "radius_km": 5}, headers=headers)
    assert updated.status_code == 200 and updated.json()["categories"] == ["Culture"]


def test_account_export_and_deletion_remove_private_coordinates(client, db_session):
    user, headers, watch = _create(client, db_session, "watch-privacy@example.com")
    exported = client.get("/community/account/export", headers=headers).json()
    assert exported["area_watches"][0]["id"] == watch["id"]
    client.request("DELETE", "/community/account", json={"reason": "privacy"}, headers=headers)
    assert db_session.query(AreaWatch).filter_by(user_id=user.id).count() == 0
