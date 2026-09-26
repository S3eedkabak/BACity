"""Import and normalize Bratislava's official public-toilet ArcGIS dataset."""
import re
from datetime import datetime

import httpx

from app.core.utilities import OFFICIAL_TOILET_SOURCE
from app.database import SessionLocal
from app.models.community import CityUtility

QUERY_URL = OFFICIAL_TOILET_SOURCE + "/query"


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


def sync_bratislava_toilets(db, client=None) -> dict:
    requester = client or httpx
    response = requester.get(QUERY_URL, params={
        "where": "1=1", "outFields": "*", "returnGeometry": "true", "outSR": 4326, "f": "geojson",
    }, timeout=30.0)
    response.raise_for_status()
    features = response.json().get("features") or []
    if not features:
        raise ValueError("Official public-toilet dataset returned no features")

    now, seen, created, updated, skipped = datetime.utcnow(), set(), 0, 0, 0
    for feature in features:
        try:
            values = normalize_feature(feature)
        except ValueError:
            # The city feed currently includes a planned toilet without a point.
            skipped += 1
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
    return {"received": len(features), "created": created, "updated": updated, "skipped": skipped, "missing": len(missing)}


def main():
    with SessionLocal() as db:
        print(sync_bratislava_toilets(db))


if __name__ == "__main__":
    main()
