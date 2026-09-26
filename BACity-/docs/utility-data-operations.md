# Bratislava utility data operations

BACity imports public toilets from the City of Bratislava's official ArcGIS FeatureServer:

`https://geoportal.bratislava.sk/hSite/rest/services/Hosted/verejne_toalety_data_/FeatureServer/1`

The importer requests GeoJSON in WGS84, normalizes whitespace, coordinates, fees, opening hours and accessibility, and upserts by the city's stable `objectid`. Records without coordinates are skipped because they cannot be safely mapped. Official records removed from a later feed are retained but reset to `unknown` so bookmarks and public links do not break.

## Run and schedule

Run a manual synchronization from `services/api`:

```bash
python -m app.utility_import
```

The production maintenance service sets `UTILITY_SYNC_ENABLED=true` and checks the dataset daily. `UTILITY_SYNC_INTERVAL_HOURS` can be changed from its 24-hour default. Development keeps network synchronization disabled unless explicitly enabled.

After each deployment or provider schema change, confirm that the importer reports a nonzero `received` count and inspect the skipped count. A zero-feature response aborts without modifying stored data. Provider/network errors are logged and retried on the next maintenance cycle; they do not stop email or retention maintenance.

## Query and trust model

- `GET /community/utilities/viewport` returns only utilities within map bounds.
- `GET /community/utilities/nearby` returns distance-sorted utilities within a radius.
- `GET /community/utilities/{id}` returns one utility and its aggregate freshness/confidence metadata.
- Native maps use a clustered GeoJSON layer and switch to the nearby endpoint in near-me mode.

Confirmations from the last 180 days are recency-weighted. A leading status needs at least 67% of weighted evidence; otherwise the public status is `unknown` and `status_conflict=true`. Confidence combines official-source provenance, confirmation volume and agreement. Freshness decays through `current`, `recent`, `aging`, and `stale`; a stale unconfirmed or more-than-180-day-old community status is never presented as current fact.
