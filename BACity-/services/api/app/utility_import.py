"""Import and normalize Bratislava's official public-toilet ArcGIS dataset."""
import logging
import re
from collections import Counter
from datetime import datetime

import httpx

from app.core.utilities import OFFICIAL_TOILET_SOURCE
from app.database import SessionLocal
from app.models.community import CityUtility

QUERY_URL = OFFICIAL_TOILET_SOURCE + "/query"
PAGE_SIZE = 1000
log = logging.getLogger("bacity.utility_import")


def _text(value):
    return re.sub(r"\s+", " ", str(value or "")).strip() or None


def _price(value):
    text = _text(value)
    if not text:
        return None, None
    lowered = text.casefold()
    if "bezplat" in lowered:
        return True, 0.0
    match = re.search(r"(\d+(?:[,.]\d+)?)", text)
    return (False, float(match.group(1).replace(",", "."))) if match else (False, None)


def normalize_feature(feature: dict) -> dict:
    props = feature.get("properties") or {}
    coordinates = (feature.get("geometry") or {}).get("coordinates") or []
    longitude = props.get("zemepisna_dlzka") or (coordinates[0] if len(coordinates) > 1 else None)
    latitude = props.get("zemepisna_sirka") or (coordinates[1] if len(coordinates) > 1 else None)
    object_id = props.get("objectid")
    if object_id is None or latitude is None or longitude is None:
        raise ValueError("Public-toilet feature is missing its ID or coordinates")
    free, fee = _price(props.get("cena"))
    name = _text(props.get("miesto_nazov")) or f"Verejná toaleta {object_id}"
    hours = _text(props.get("otvaracia_doba"))
    return {
        "kind": "toilet",
        "name": name,
        "latitude": float(latitude),
        "longitude": float(longitude),
        "opening_hours": None if hours and hours.casefold() == "tbd" else hours,
        "free": free,
        "fee": fee,
        "wheelchair_accessible": True if "bezbari" in name.casefold() else None,
        "operational_status": "unknown",
        "source_url": f"{OFFICIAL_TOILET_SOURCE}?objectid={object_id}",
    }


def _response_json(response):
    response.raise_for_status()
    payload = response.json()
    if payload.get("error"):
        raise ValueError(f"Official public-toilet dataset query failed: {payload['error']}")
    return payload


def _upstream_count(requester) -> int:
    response = requester.get(QUERY_URL, params={
        "where": "1=1", "returnCountOnly": "true", "f": "json",
    }, timeout=30.0)
    payload = _response_json(response)
    count = payload.get("count")
    if not isinstance(count, int) or count < 0:
        raise ValueError("Official public-toilet dataset did not report a valid record count")
    return count


def _fetch_all_features(requester, upstream_total: int) -> tuple[list[dict], int]:
    features, object_ids, offset = [], set(), 0
    while True:
        response = requester.get(QUERY_URL, params={
            "where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": 4326,
            "orderByFields": "objectid ASC", "resultOffset": offset,
            "resultRecordCount": PAGE_SIZE, "f": "geojson",
        }, timeout=30.0)
        payload = _response_json(response)
        page = payload.get("features") or []
        exceeded = bool(payload.get("exceededTransferLimit") or
                        (payload.get("properties") or {}).get("exceededTransferLimit"))
        if not page:
            if len(features) < upstream_total or exceeded:
                raise ValueError(
                    f"Official public-toilet pagination stopped at {len(features)} of {upstream_total} records"
                )
            break

        for feature in page:
            properties = feature.get("properties") or {}
            object_id = properties.get("objectid", feature.get("id"))
            if object_id is not None:
                if object_id in object_ids:
                    raise ValueError(f"Official public-toilet pagination repeated objectid {object_id}")
                object_ids.add(object_id)
        features.extend(page)
        offset += len(page)

        if not exceeded and len(features) >= upstream_total:
            break

    if len(features) != upstream_total:
        refreshed_total = _upstream_count(requester)
        if len(features) != refreshed_total:
            raise ValueError(
                f"Official public-toilet count changed during pagination: "
                f"reported {upstream_total}, fetched {len(features)}, now reports {refreshed_total}"
            )
        upstream_total = refreshed_total
    return features, upstream_total


def sync_bratislava_toilets(db, client=None) -> dict:
    requester = client or httpx
    upstream_total = _upstream_count(requester)
    features, upstream_total = _fetch_all_features(requester, upstream_total)
    if not features:
        raise ValueError("Official public-toilet dataset returned no features")

    now, seen, created, updated = datetime.utcnow(), set(), 0, 0
    skip_reasons = Counter()
    for feature in features:
        try:
            values = normalize_feature(feature)
        except ValueError as exc:
            skip_reasons[str(exc)] += 1
            continue
        seen.add(values["source_url"])
        item = db.query(CityUtility).filter_by(source_url=values["source_url"]).first()
        if item is None:
            item = CityUtility(**values)
            db.add(item)
            created += 1
        else:
            for key, value in values.items():
                if key != "operational_status" or item.operational_status == "unknown":
                    setattr(item, key, value)
            item.updated_at = now
            updated += 1

    missing = db.query(CityUtility).filter(
        CityUtility.source_url.startswith(OFFICIAL_TOILET_SOURCE),
        ~CityUtility.source_url.in_(seen),
    ).all()
    for item in missing:
        item.operational_status = "unknown"
        item.updated_at = now
    db.commit()
    accepted = created + updated
    result = {
        "upstream_total": upstream_total,
        "fetched": len(features),
        "received": len(features),
        "accepted": accepted,
        "created": created,
        "updated": updated,
        "skipped": sum(skip_reasons.values()),
        "skip_reasons": dict(skip_reasons),
        "missing": len(missing),
    }
    log.info("Public-toilet synchronization: %s", result)
    return result


def main():
    with SessionLocal() as db:
        print(sync_bratislava_toilets(db))


if __name__ == "__main__":
    main()
