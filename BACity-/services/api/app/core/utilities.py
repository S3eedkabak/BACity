"""Utility location querying and conservative community status aggregation."""
import math
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.models.community import CityUtility, UtilityConfirmation

EARTH_RADIUS_KM = 6371.0
OFFICIAL_TOILET_SOURCE = "https://geoportal.bratislava.sk/hSite/rest/services/Hosted/verejne_toalety_data_/FeatureServer/1"


def _freshness(age_days: float | None) -> tuple[float, str]:
    if age_days is None:
        return 0.0, "unknown"
    if age_days <= 7:
        return 1.0, "current"
    if age_days <= 30:
        return 0.8, "recent"
    if age_days <= 90:
        return 0.5, "aging"
    return max(0.05, 0.25 - (age_days - 90) / 720), "stale"


def utility_record(db, item: CityUtility, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    confirmations = db.query(UtilityConfirmation).filter(
        UtilityConfirmation.utility_id == item.id,
        UtilityConfirmation.created_at >= now - timedelta(days=180),
    ).order_by(UtilityConfirmation.created_at.desc()).all()
    counts = Counter(c.operational_status for c in confirmations)
    weights: dict[str, float] = {}
    for confirmation in confirmations:
        age = max(0.0, (now - confirmation.created_at).total_seconds() / 86400)
        weight = 1.0 if age <= 7 else 0.75 if age <= 30 else 0.45 if age <= 90 else 0.2
        weights[confirmation.operational_status] = weights.get(confirmation.operational_status, 0) + weight

    total_weight = sum(weights.values())
    winner, winner_weight = (max(weights.items(), key=lambda pair: pair[1]) if weights else (item.operational_status, 0.0))
    agreement = winner_weight / total_weight if total_weight else 1.0
    conflict = len([value for value in weights.values() if value > 0]) > 1 and agreement < 0.67
    effective_status = "unknown" if conflict else winner

    evidence_dates = [item.updated_at] + [c.created_at for c in confirmations[:1]]
    evidence_at = max(value for value in evidence_dates if value is not None) if any(evidence_dates) else None
    age_days = (now - evidence_at).total_seconds() / 86400 if evidence_at else None
    freshness_score, freshness_status = _freshness(age_days)
    official = bool(item.source_url and item.source_url.startswith(OFFICIAL_TOILET_SOURCE))
    confidence = (0.65 if official else 0.35) + min(0.2, len(confirmations) * 0.04) + 0.15 * agreement
    if conflict:
        confidence *= 0.6
    if freshness_status == "stale" and not confirmations:
        effective_status = "unknown"
    if not confirmations and item.last_confirmed_at and item.last_confirmed_at < now - timedelta(days=180):
        effective_status = "unknown"

    data = {column.name: getattr(item, column.name) for column in item.__table__.columns}
    data.update({
        "operational_status": effective_status,
        "confirmation_count": len(confirmations),
        "confirmation_summary": dict(counts),
        "status_conflict": conflict,
        "confidence_score": round(min(1.0, confidence), 3),
        "freshness_score": round(freshness_score, 3),
        "freshness_status": freshness_status,
    })
    return data


def viewport_query(db, *, min_lat: float, max_lat: float, min_lng: float, max_lng: float, kind: str, limit: int):
    return db.query(CityUtility).filter(
        CityUtility.kind == kind,
        CityUtility.latitude.between(min_lat, max_lat),
        CityUtility.longitude.between(min_lng, max_lng),
    ).order_by(CityUtility.name).limit(limit).all()


def nearby_query(db, *, lat: float, lng: float, radius_km: float, kind: str, limit: int):
    dialect = db.bind.dialect.name if db.bind is not None else "sqlite"
    if dialect == "postgresql":
        distance = func.ST_DistanceSphere(
            func.ST_MakePoint(CityUtility.longitude, CityUtility.latitude),
            func.ST_MakePoint(lng, lat),
        )
        return list(db.scalars(select(CityUtility).where(
            CityUtility.kind == kind, distance <= radius_km * 1000,
        ).order_by(distance).limit(limit)))

    pad = radius_km / 111.0
    candidates = db.query(CityUtility).filter(
        CityUtility.kind == kind,
        CityUtility.latitude.between(lat - pad, lat + pad),
        CityUtility.longitude.between(lng - pad, lng + pad),
    ).all()

    def distance(item):
        p1, p2 = math.radians(lat), math.radians(item.latitude)
        dphi = math.radians(item.latitude - lat)
        dlambda = math.radians(item.longitude - lng)
        value = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
        return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(value))

    scored = sorted(((distance(item), item) for item in candidates), key=lambda pair: pair[0])
    return [item for item_distance, item in scored if item_distance <= radius_km][:limit]
