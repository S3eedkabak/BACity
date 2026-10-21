> Historical architecture and policy notes. [The current validation report](final-ux-validation.md) supersedes the map presentation, native findings, migration head, measurements and Git status below.

# Level 2 autonomy and complete geographic discovery

Baseline: `bc6bb4abbbf6a2be6c8719ec13f57ba9a7e425ec`, clean `FINAL-UX`.
This task follows the crawler recovery; it does not replace or undo that recovery.
Measurements refer to local development on 21 October 2026, never production.

## Map preservation and root cause

The pre-task native screen uses MapLibre React Native and
`https://tiles.openfreemap.org/styles/liberty`. Its pre-task web route was a
separate CSS schematic: three dark district shapes, decorative roads/water,
three manually positioned labels, and no tile requests. The intermediate work
made that schematic worse by widening its geographic projection, removing its
labels, and adding a permanent filter panel. It was not a failed native tile
provider. Those intermediate presentation changes were removed.

Both routes now use the original native screen, extracted to
`apps/mobile/src/map/MapScreen.tsx`. Native still uses the same MapLibre bridge;
web has a platform adapter using MapLibre GL JS 5.24.0 and the **same Liberty
style, provider, screen, controls, colors and typography**. This web dependency
is necessary to render the original detailed basemap in a browser; it adds no
native SDK or crawler browser dependency. The schematic is no longer used.

The original screen's complete StyleSheet and toilet ShapeSource/layer block
match the baseline byte-for-byte. Frozen SHA-256 contracts in the mobile
preservation tests protect both. Other intentional changes are bounded data
retrieval, new filter/area actions and direct district selection, and cluster interaction.
The original controls were not removed to make room: the existing wrapping tray
holds the additive actions, and existing BACity sheets hold their contents.

| Original capability | Final integration / regression guard |
|---|---|
| Liberty streets, water, parks, buildings, POIs and labels | Same native provider/style and full layer stack; now also rendered on web. Optional polygons do not replace tiles. |
| Search / Find events | Original Explore navigation retained. New map filters use a separate sheet. |
| Near me | Original 3 km distance, follow camera, location indicator and marker emphasis retained; PostGIS filters the complete inventory rather than a capped nearby page. No location means a waiting state, not invented nearby results. |
| Zoom, recenter, pan, attribution, rotation/pitch settings | Original controls, gestures, constants and native props retained. Web adapter exposes matching camera operations. |
| Event points and count bubbles | Original colors, radii, strokes, E labels and tap hitbox retained for event point mode. Default district exploration keeps event clusters hidden; Near Me and focused View on Map use event points. The server still aggregates complete coverage. |
| Cluster tap | Wide zoom still zooms toward the cluster; dense local groups expose the existing-style sheet with View events / Zoom in. |
| Toilets / Events layer switch | Original exclusive layer behavior, WC marker styles, utility clustering, status and detail route retained. Toilet viewport state is separate from event bounds, so toggling toilets cannot alter event totals. |
| All utilities | Existing hub and all 12 categories remain unchanged: toilets, water, bike repair, charging, Wi-Fi, benches, playgrounds, dog parks, recycling, accessible entrances, parking and lockers. The original main map specifically had a toilet layer; the other categories were in this hub, not additional main-map toggles. |
| Utility status, hours, confirmations and corrections | Existing utility detail screen and actions retained; real city data is used. |
| Existing loading, errors and cached tiles | Original screen states and 75 MiB native ambient tile cache retained. A bounded, filter-matched aggregate snapshot restores offline event context without pretending cached partial event pages are complete. |
| Event details / save | Existing EventCard and navigation reused. On web, the same bookmark control is a sibling overlay, avoiding an invalid button nested inside a button; native card touch handling and appearance remain unchanged. |
| Back / camera / filters | Camera and map session survive area/detail navigation. Shared event filters propagate between map and area; district/radius context remains geographic context rather than overwriting event or utility filters. |

The original app uses a fixed dark interface palette; no separate light UI theme
is implemented or claimed. The Liberty cartography remains its original light
style beneath those controls.

## Complete map API

Legacy `/events/viewport` remains compatible and capped at 500. Updated clients
use additive `/events/map/clusters`, `/events/map/area`, and
`/events/map/districts` routes, also available under `/v1`.

A single SQL aggregation groups **all** eligible rows into zoom-dependent grid
cells. A viewport-width/height floor bounds output to approximately 33 × 33 cells,
without truncating matching events. No full Event-object collection is loaded
into Python to make clusters. Single events keep their actual coordinates;
count bubbles use actual point centroids, with actual point bounds for camera movement. A cluster is not labelled as a district.

Every feature carries its count, stable cell identity within the query context,
bounds and a signed area token. The response distinguishes total, clustered and
individual event counts. Dense identical coordinates stay grouped at high zoom.
Area lists fetch 30 events, with a server maximum of 100 per page.

One predicate implements published fresh/stale status, credible mapped coordinates
within the existing Bratislava bounds, dates, category, free status, literal text
search, optional fresh/stale status, radius and official district membership.
Cancelled/postponed/expired records are excluded. Existing unmapped Explore flows,
Home's future/90-day definition, saved IDs and historical canonical data are not
changed. Search wildcards are escaped; all SQL values are bound parameters.

Ordering is `(start_time, canonical_id)`, with signed, query-bound keyset cursors.
Count/max-update revisions detect ordinary application writes between pages and
return 409 with a refresh instruction rather than silently skipping changed
records. A list opened after a cluster changes returns the current count and a
visible refresh notice. PostgreSQL area responses use one REPEATABLE READ
transaction. This is change detection, not a historical snapshot service;
backdated direct SQL writes that bypass application timestamps are outside that
contract. Tokens expire after 24 hours and must then be refreshed.

Requests use cancellation and the existing 700 ms camera debounce; insignificant
pans remain inside a padded viewport. Query keys include zoom, bounds and filters.
At most seven inactive event-map queries are retained in addition to active
queries, with a one-minute GC lifetime. Lists are virtualized. Old filter results
do not replace new results or navigate using a pending filter's old area token.
The named-area page uses the same 760 px content width as Explore.

## Verified districts, independent of clusters

The City of Bratislava's public administrative-boundary FeatureServer supplied
all 17 polygons in WGS84. Full geometry is checked in under `app/data`; no polygon
was drawn from the reference image or simplified. The data README records its
publisher URL, query, retrieval date and response ETag.

Restrained fill, boundary strokes and labels sit below the event and
utility layers. Streets, parks, labels, POIs and marker taps remain usable.
District selection opens its named, complete filtered inventory. PostGIS
`ST_Covers` determines membership, with lowest official district ID owning shared
boundaries; SQLite's isolated tests implement the same boundary rule. A bbox is
only a prefilter, never district membership. Events outside all official polygons
remain reachable through city/viewport browsing and are reported separately.

Migrations 0017–0018 add the degradation constraint, geographic query index,
official polygon table, polygon GiST index and a published-event point-expression
GiST index. Existing canonical rows and user references are preserved.
Selective district predicates use the event point GiST index. Aggregated district
counts use one spatial join plus an eligibility total, not one HTTP/ORM query per
event. Geometry and filters are shared by district counts and pages.

## Balanced Level 2 evidence

The old 80% raw acceptance gate treated correct past/out-of-city exclusions as
extraction failures. BKIS accepted 5 of 8 observations and was held below 80%;
Billy Barman accepted 1 of 3 and Pána Kráľa 2 of 3, despite valid Bratislava yield.
A4 had only one old good run. The scheduler already ingested probation events;
the missing pieces were realistic qualification and bounded expansion from them.

Named values live in `crawler/qualification.py`, not scattered thresholds:

| Policy | Final default |
|---|---:|
| Minimum independent productive runs | 2 |
| Minimum spacing / actual scheduled eligibility | 1 hour and a genuinely due persisted job |
| Distinct validated future-start observations | 3 total across qualifying runs |
| Low-volume alternative | 3 independent productive runs |
| Mean completeness floor | 45 |
| Mean extraction confidence | 0.65 |
| Maximum genuine extraction-defect fraction | 0.35 |
| Repeated genuine failures for degradation | 3 |
| Productive probation / trusted recurrence | 1 hour / 6 hours |
| Empty/seasonal recurrence | 24 hours; still revisited |
| External discovery depth | Registry → productive Level 2 → one additional host |

The completeness floor was evaluated against real data: Ticketportal produced
9 valid future observations with mean completeness 51.7 and confidence 0.85;
missing optional fields should not block that source at a preliminary floor of
55, or count as serious integrity degradation. The final 45-point floor retains
core evidence without requiring closing clocks or images. Existing assessment
records are not rewritten to manufacture a good run; the next genuine scheduled
run uses the final policy.

Past records and correctly excluded out-of-city records are neutral. Malformed
extraction and low confidence remain blockers. Duplicate URLs for the same
normalized title/time/place count once per job. HTTP 200 without usable events,
cancellation-only runs, manual/audit calls, replay of an already-recorded job and
immediate retries cannot establish trust. A probation source publishes every
individually validated event immediately; source trust never bypasses validation.

States are discovered → inspected → productive probation → trusted. Repeated
operational or integrity failures produce degraded, with monitoring/recovery;
unsupported empty calendars remain revisitable, not safety-blocked. Robots/403
access exclusions retain blocked; administrator disable remains authoritative.
A failure does not delete or discredit existing canonical events by itself.

SQLite retains due times, distinct observations, last qualifying time, bad-run
counts and up to 50 auditable assessments per host. Worker completion and its
qualification decision commit together; replay cannot inflate evidence. The
migration preserves candidate rows, endpoints, existing runs and outbox data.
Old good-run counters are not treated as newly instrumented independent evidence.

## Controlled expansion and safety

Productive probation and trusted sources can provide one further external hop.
Evidence includes explicit local Event organizer/venue URLs, declared event feeds,
and event-detail links to real calendar/program endpoints. Arbitrary external
navigation does not qualify. Same-host endpoints rotate independently of host
identity; limits remain 250 hosts, 8 endpoints/host, 4 endpoints/inspection,
20 discoveries/job, 50 followed links/page, depth 3 within a host, and bounded
inspection requests/time/items. Depth-two hosts cannot expand again, including
back-link loops. Endpoint provenance records whether the exact evidence was
observed; historical host-origin hints are not presented as verified endpoint
provenance.

Priority is deterministic: distinct validated future yield and productive state,
calendar/feed evidence, failures, cost and bounded overdue age. New `next=0`
candidates age from discovery time, so a large batch of fresh links cannot jump a
due productive venue merely by having an epoch-zero timestamp.

SSRF/public DNS validation, DNS pinning/rebinding protection, redirects, robots,
Crawl-delay, rate limits, Retry-After, timeouts, response limits, URL normalization,
credential/social exclusions and per-event validation remain enforced. No browser
or CAPTCHA/authentication workaround was added. JSON-LD, microdata, feeds and
observed narrow HTML adapters remain the extraction paths. Sitemaps and JS-only
publishers without usable evidence remain explicit gaps, not date-mining targets.

Admin-protected candidate diagnostics expose states, reasons, blockers, qualifying
observations, graph depth, endpoint count, last success, next crawl and grouped
canonical/future contribution. Operational assessments remain in SQLite and the
existing API run/provenance records; no private user information is added.

## Regression and database validation

The crawler suite covers imperfect calendars, realistic missing optional fields,
low-volume trust, independent due times, replay/audit/retry rejection, duplicate
URL observations, temporary failures, degradation/recovery, restart and legacy
schema preservation, graph expansion/loops/quotas, provenance, robots, SSRF,
DNS/redirect guards, validation and canonical ingestion. The HTTP → Scrapy →
outbox → FastAPI test still verifies idempotency, locality, cancellations and
map eligibility. Fixture time advances occur only in isolated fixture state.

API fixtures seed 1,207 eligible events and prove complete counts and pagination
at zoom 0/12/18/22, filter consistency, signed cursor binding/tamper rejection,
change detection, status/locality/missing-coordinate exclusions, radius and bounds.
Official district fixtures verify names, geometry-based membership, shared-boundary
ownership, disjoint totals and complete corresponding lists.

An isolated PostgreSQL database, never development, seeds **6,007** events.
Every ID is reached through city pagination and every represented district's
pages, with no duplicates. A full Alembic upgrade and 0023→0016→0023 round trip
preserve its event rows. The existing migration/backfill test passes at 0023.
Disposable databases are removed by those tests; development data is never
replaced with fixtures. Separate local PostgreSQL reads validate real inventory.

Mobile contracts freeze the original StyleSheet and toilet layers, verify both
platforms share the screen, retain controls/utility categories/routes, exercise
cluster actions and district fallback naming, propagate event filters without
geographic context leaking into them, validate Bratislava dates across both DST
changes, and translate optional native layer fields correctly for web. Existing
map-marker, recommendation, API URL and planner contracts run as well.

The temporary native baseline comparison loaded the actual baseline source into
the existing simulator build and was then removed. No baseline-only route or
temporary fixture screen is part of the shipped implementation.
