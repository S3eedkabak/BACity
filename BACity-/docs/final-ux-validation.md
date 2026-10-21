# FINAL-UX validation — 21 October 2026

Development environment only. The protected pre-task revision is `bc6bb4abbbf6a2be6c8719ec13f57ba9a7e425ec` on `FINAL-UX`. No production deployment was performed.

## Original map and native interaction

The original iOS MapLibre screen was extracted to `apps/mobile/src/map/MapScreen.tsx`. Its OpenFreeMap Liberty style, geographic tiles and labels, original StyleSheet, WC ShapeSource/layers, utility routing, search, Near Me, zoom, recenter, location indicator, attribution and event/toilet controls remain. Frozen tests compare the original StyleSheet and WC block to the pre-task revision. The 12-category All Utilities hub remains.

The degraded browser preview came from its separate schematic CSS map and intermediate projection changes. Web now uses the shared map with MapLibre GL JS and the original Liberty style; the native tile provider was retained. Official 17-district polygons add restrained fills, boundaries and labels over the detailed map. Default district exploration shows no generic red event clusters. Near Me may show event aggregates; View on Map shows one focused event pin. Districts and utility markers are independent.

The native `Invalid geometry in line layer` warning came from district boundaries supplied in polygon/multiline geometry. Each ring is now a valid GeoJSON `LineString` feature. The `"45"` numeric warning was fixed by numeric SVG props in `MediaScrim`. Both warnings disappeared in later iOS Simulator interactions and screenshots.

Actual iPhone 17 Pro Simulator checks: direct taps on Staré Mesto, Nové Mesto and Ružinov polygons opened matching Area Events pages; toilet toggle showed WC points above polygons and tapping Medická záhrada opened its original utility detail; Area Events → View on Map focused Bassizm festival at Refinery Gallery, then Back restored the Ružinov list and prior city camera/toilet state. Home → View Spicy Depository on Map focused its precise pin and preview. Streets, parks, POIs, buildings and labels rendered at district and street zoom. Screenshot evidence: `/Users/s3eed/.codex/bacity-validation/2026-10-21/screenshots/native-district-overview.png`, `native-district-toilets.png`, `native-event-focus-final.png`.

Final browser check loaded the Liberty streets and labels, opened Devín from its district card, showed its one event with the corrected singular count, and returned to the same selected district on the map. Browser screenshots: `web-district-final.png` and `web-area-final.png` in the same evidence folder. Browser automation's accessibility-index clicks moved beneath changing map targets; stable role-based clicks verified the route.

Native pan/pinch quality and physical haptic strength could not be verified with single-pointer Simulator automation; its drag registered as a tap. The haptic API is installed and type-checked. Android visuals were not tested. These are explicit limits, not device passes.

## Geographic coverage and area browsing

Server-side PostGIS aggregation queries the complete eligible identity set at each zoom. Updated clients do not rely on the legacy capped 500-item viewport response. Official district counts and area lists share filters, spatial membership, signed area tokens and stable keyset pagination. Area pages reuse event cards, search/filters, details/save actions, loading/error/empty states, and restore camera/filter/navigation context. Clusters apply only to events; utility markers and totals remain independent.

A fresh isolated PostgreSQL proof created 6,007 synthetic distinct events and reached every ID through city and represented-district pagination with no duplicates, then removed the disposable database. Totals equalled cluster sums at zoom 0/12/22. Cluster SQL took 91.8/61.5/61.3 ms respectively. A selective geographic query used `ix_events_lat_lng` (0.747 ms execution). Full district pagination took 7.30 s in that fixture. The earlier 735 development map-eligible rows were a pre-reconciliation row count; current counts below are distinct identities, not a revived 500-item cap.

## Canonical data and autonomous maintenance

The live audit at 2026-10-21 16:54:06 UTC found 795 retained physical events, 863 source observations, 246 distinct identities, 207 discoverable distinct events and 189 geolocated discoverable events. It found 709 retained occurrences, 546 alias/reconciliation rows, 14 cross-source identity groups and zero exact-key duplicate groups. Six decades-long catalog placeholders were corrected from publisher observations. Vincent van Gogh's timed admission listings and publisher exhibition range now resolve to one discoverable identity with a documented 30 September 2026–17 January 2027 span. Source observations and aliases remain. Current dry runs propose zero metadata repairs and zero further aliases.

The existing worker cadence performs transactional reconciliation of changed identities, documented metadata repair, expiry, and bounded archive/delete of only old expired/superseded/cancelled occurrences or expired offers after 90 days. PostgreSQL advisory locking prevents overlapping cycles. Canonical Events, sources, aliases, bookmarks and reconciliation records are never garbage-collected. A disappeared listing requires two healthy publisher scans before removal; failed/incomplete crawls cannot remove it. Finished scratch crawler run statistics are pruned after 24 hours. The live database has six maintenance run records and nine archives. Four-cycle isolated tests cover discovery, stable refresh, expiry, archive and idempotence, plus DST recurrence and long-lived placeholders. Backups and applied/dry-run audits are saved outside the repository in the evidence folder.

Current district discoverable counts: Staré Mesto 109, Ružinov 5, Nové Mesto 33, Rača 7, Karlova Ves 10, Devín 1, Záhorská Bystrica 1 and Petržalka 16. The other nine districts have zero; 25 discoverable identities are unlocated or outside polygons and remain reachable in city browsing.

## Level 2 discovery

The rigid raw 80% gate was replaced by independent scheduled qualifying runs, validated future yield, confidence/completeness/integrity and a low-volume productive path. Probation events ingest when individually valid; trust can degrade and recover. No source was force-promoted. A bounded second discovery hop follows observed publisher evidence. SSRF/DNS/redirect, robots, resource and endpoint provenance safeguards remain.

The crawler mirror has 15 candidates and 72 retained runs (66 successful). Trusted publishers and recorded qualifying runs: A4 3, BKIS 3, Edison Filmhub 3, Pána Kráľa 3, Ticketportal 2, Billy Barman tickets 4. Edison was a real second-hop discovery from BKIS. Their current exclusive discoverable contributions are 3, 7, 1, 1, 13 and 1; shared identities are not summed. Eight candidates remain inspected with `unsupported_extraction` and no validated future observations: bjd.sk, bratislavavpohybe.sk, falstaff.sk, hotelmodena.sk, offbratislava.sk, ticketlive.sk, tootoot.fm and tuba.mib.sk. Google remains blocked by robots/policy. There are no active probation candidates in this mirror; the eight need genuine usable publisher endpoints, not administrative promotion.

## Verification and limits

Final API suite: 352 passed, 2 skipped. Crawler suite: 171 passed. Isolated PostgreSQL map/migration suite: 2 passed, including 6,007-event proof. Mobile TypeScript and 19 map preservation/area/district tests passed; all 13 mobile npm scripts passed. Live Alembic head is `0023`; Docker API, maintenance and crawler worker are healthy. The database was backed up before live repairs. No canonical data was intentionally removed. Final Git state is recorded at delivery.

The iOS Simulator is the native visual baseline; browser verification is secondary. Native pan/pinch, physical haptics and Android remain unverified. Screenshots and logs are local evidence, not production validation.
