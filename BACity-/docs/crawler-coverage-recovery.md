# Crawler coverage recovery — 21 October 2026

## Scope and reproducibility

Repository: `/Users/s3eed/Documents/GitHub/BACity`; application: `BACity-`.
Work started on clean `FINAL-UX` at
`a3f81bb5a972409a0cfdc57dc9385cc5b33f7510`. An origin fetch confirmed zero
commits ahead/behind. No branch creation, merge, rebase, reset, force push or
production deployment is part of this work.

Evidence below distinguishes persisted development history, read-only live
extraction audits, isolated PostgreSQL ingestion, and synthetic regression
fixtures. Counts describe observations unless explicitly labelled canonical.
UTC timestamps may fall on 20 October; the operator date is 21 October in
Europe/Berlin / Europe/Bratislava.

## Verified baseline

The existing worker's SQLite history contains seven registered runs and eight
candidate inspections. It records 229 accepted/delivered observations: Visit
Bratislava 102, Stará Tržnica 76, Nová Cvernovka 42, Karlova Ves 9. The existing
PostgreSQL database contains 181 canonical events, 229 EventSource references,
48 cross-source merges, no recorded updates, and no human submissions. At
`2026-10-20T22:40:20Z`, 152 canonical events had future starts; all 181 were
fresh, 179 had coordinates. There were seven inspected candidates and one
blocked Google add-to-calendar action. None had contributed through Level 2.

The reported historical 424 total events and initial 147 map features are not
comparable denominators. A later read of this unchanged development inventory
returned 179 all-city viewport records and 176 in the current expanded initial
viewport. Running the actual mobile GeoJSON builder on those responses produced
179 and 176 features respectively. The old 147-feature snapshot cannot be
reconstructed exactly without its viewport/cache/date parameters.

| Registered source | Persisted baseline | Confirmed cause / evidence |
|---|---|---|
| Visit Bratislava | Failed; 102 accepted, 157 rejected; 219.3 s | A linked `/events/recommended/` returned 404; 106 incomplete listing cards were submitted as records; 51 past records. |
| Stará Tržnica | Successful; 76 accepted, 53 past rejections; 114.4 s | Existing HTML fallback works, but produces repeated observations and visits past program pages. |
| SNG | Failed; 0 accepted; 125 request errors; 222.2 s; page limit | Rendered absolute hrefs repeat the current path before an already-rooted event path. Navigation also visits unrelated institutions and legal pages. Exhibition dates require a targeted parser. |
| Bratislava City | Failed; 0 accepted; 29 rejected; 13.9 s | Generic nested cards lose their venue; news RSS requests were robots-forbidden (two IgnoreRequest errors). The actual municipal cards have explicit dates, clock ranges and venue paragraphs. |
| GoOut | Reachable but empty; 4 location rejections; 2.5 s | The adapter assumes denormalized records, but the real feeder has separate schedule/event/venue tables. `city=bratislava` is ignored and returns multiple cities. |
| Nová Cvernovka | Partial; 42 observations; 301.4 s; page limit | Traversal enters `/program/archiv` and related event pages. Many observations repeat current listing events. |
| Karlova Ves | Successful; 9 accepted; 2.6 s | No demonstrated extraction failure; retain the working API adapter. |

SNG and Cvernovka both hit page limits; the earlier assertion of only one
limited registered source was incomplete. Four candidate inspections also
reached their much smaller inspection page budget.

## Confirmed defects and repairs

Each entry records symptom, evidence, root cause, impact, fix, test and result.

1. **SNG traversal and extraction.** The saved run has 125 request failures and
   URLs such as `.../whatson/en/slovak-national-gallery/events/...`. The
   publisher currently emits these malformed absolute links. Keeping the final
   rooted Bratislava event path and excluding unrelated navigation eliminates
   that loop. A specific adapter reads only the exhibition's explicit range,
   not dates in artist biographies. Regression coverage checks both cases.
   The read-only live audit accepted three exhibitions in 28.2 seconds with no
   request errors, versus zero accepted in 222.2 seconds previously.

2. **Visit listing/detail confusion.** Current listing cards contain dates and
   links but no location; the corresponding Berlin Manson detail has a 19:00
   clock, STARS auditorium and publisher coordinates. Those incomplete cards
   are now navigation evidence, not competing event observations. The detail
   adapter retains the local clock and published venue/map data. Both `/event/`
   and `/events/` pagination are supported; the broken recommended link is
   excluded. Regression tests retain clock, date precision, venue and coordinates.
   The first read-only audit accepted 139 observations and rejected four for
   missing location, but was page-limited. This is not 102 or 106 newly recovered
   canonical events: removing incomplete duplicate observations changes the
   denominator, and coverage expanded through pagination.

3. **Municipal cards.** Observed `h3` cards have two paragraphs: a dated clock
   range and a venue. The targeted parser uses exactly that structure, preserves
   the external detail link and municipal observation URL, and avoids generic
   container titles such as “Podstránky”. News feeds are excluded. Live audit:
   11 validated observations, no request errors, 5.8 seconds.

4. **GoOut schema and locality.** Captured public feeder responses demonstrate
   the relational schema and Bratislava locality ID 30. `locality=30` and the
   publisher's city ID both return Bratislava; `city=bratislava` does not. The
   adapter joins schedule `eventId` and `venueId`, preserves schedule URLs,
   distinct performances, explicit offsets and cancellation, and rejects
   non-Bratislava locality evidence. Five monotonic pages cap collection at 500
   schedules; a remaining `hasNext` marks the run partial. The 2038 permanent
   exhibition sentinel is not a real closing date. Cached first-page parsing
   produced 100 records, 90 valid at that observation time. Tests cover joins,
   locality, sentinel handling, separate occurrences and the page bound.

5. **Cvernovka traversal.** Restrict collection to the current program and its
   details; omit the archive and same-domain recommendations reached from a
   detail. The read-only live audit processed 23 responses and 21 observations
   in 41.4 seconds, versus 153 responses / 42 repeated observations / 301.4
   seconds. Lower observation volume does not imply lower unique coverage.

   A subsequent Stará Tržnica inspection also exposed generic card titles that
   included the date and clock, with a midnight start instead of the visible
   clock range. Its dedicated adapter now reads the dated permalink, clean
   strong title, and explicit clock range. Old dated links and detail
   recommendations are excluded. The final source run accepted 43 observations,
   coalesced to 23 outbox records, in 39.7 seconds without request errors.

6. **Level 2 unsupported markup and endpoint loss.** Candidate extraction
   previously supported JSON-LD/RSS/Atom/ICS only, even where A4 and BKIS expose
   dates and locations in HTML. Add narrowly scoped A4 and BKIS adapters and
   microdata fallback, not unrestricted generic date mining. A4 requires its
   dated event permalink, a clock in the title's own header, and the actual
   Bratislava address block. BKIS requires labelled start/address fields.
   Extract event descriptions/images from publisher metadata. News publication
   dates, unrelated footer dates and biography dates are not event starts.
   Initial bounded audits produced five valid BKIS records and three A4
   records. A4's advertised `/events/feed/` returned 404; optional feed 404/410
   errors are recorded separately from failure of the primary event page.

7. **Candidate identity and progression.** Retain one host-level trust/control
   record, with up to eight evidenced endpoints in an additive SQLite table.
   Inspect at most four entry points per host job and rotate them persistently.
   A newly evidenced calendar/feed can displace a saturated low-ranked detail
   endpoint. Repeated API synchronization does not inflate endpoint evidence
   counts. Host quotas, one-hop external discovery and per-host controls remain.
   Unsupported extraction is distinct from irrelevant/zero yield. Temporary
   failures cannot count toward a successful streak. A source needs positive
   future yield, at least 80% valid yield, mean completeness >=60 and three good
   runs to become trusted. Cancellation-only observations do not establish
   future productivity. Probation and trusted hosts remain recurring scheduled
   jobs; neither expands the external trust graph.

8. **Date precision and postponement.** Date-only endings previously became
   apparent closing clocks; postponed JSON-LD events became ordinary stale
   discovery results. `end_date` now stores an explicit inclusive publisher
   date separately from `end_time`. Ongoing exhibitions can pass validation and
   lifecycle maintenance without an invented closing hour. Existing explicit
   times retain their quality ranking. A same-publisher precision correction
   can clear that parser's old midnight placeholder. `postponed` is a distinct
   status excluded by existing fresh/stale discovery filters; a dated reschedule
   preserves the canonical ID. Authentic cancellation/postponement updates may
   describe an old occurrence. Tests cover ongoing lifecycle, precision
   correction, withholding and rescheduling. Existing planner interval checks
   still require a real `end_time` for onward transitions.

9. **Provenance and occurrence matching.** Health records used the registry
   domain, but ingestion created `www.` aliases and sometimes attributed a
   publisher's observation to its linked ticket vendor. Attribute ingestion to
   the original crawled publisher and prefer the registry's normalized domain,
   keeping old alias rows readable. Preserve both URLs in EventSource. A
   publisher's distinct explicit start times do not fuzzy-merge, including slots
   only ten minutes apart. Existing cross-source quality merging and explicit
   rescheduling remain tested. No historical data rewrite or deduplication
   disablement was performed.

10. **Scheduler and outbox.** Previously an entire registered batch could delay
    Level 2, while multiple candidate inspections delayed Level 1. Interleave
    one job from each queue. `--once` holds a finite registered-source snapshot,
    interleaving bounded candidate attempts, so short failure backoff cannot
    make it loop indefinitely. Registered failures retry after 5 minutes with
    exponential backoff capped at one hour, rather than waiting the full
    six/twelve-hour successful-source interval. Heartbeats update every 30
    seconds during jobs. Unchanged re-observations no longer reset outbox retry
    state; corrected payloads can requeue rejected records. Delivery has a wall
    budget and retains the rest. Indexed due-outbox and run-history queries,
    persistent delivery totals, oldest backlog age and attempts aid reconciliation.
    HTTP Retry-After supports both delta seconds and HTTP dates and persists
    scheduling deferral; robots Crawl-Delay is not randomized below its floor.

11. **Pipeline failure visibility and backup.** Scrapy item/close errors could
    leave the original success predicate true. Capture item-error signals and
    reject error-bearing runs. Invalid/interrupted statistics become recorded
    failures rather than crashing the scheduling loop. An initial isolated
    validation using a Mac bind-mounted SQLite database became corrupted after
    host inspection while Docker was writing. It is invalid operational proof;
    its artifacts were retained and the run was repeated with a separate named
    volume and database. No development volume was involved. The new backup
    command uses SQLite's online backup API, verifies integrity and exclusively
    publishes a new snapshot. Never open an active Docker SQLite file using a
    separate host SQLite process or copy its main file without its WAL.

## Validation, location and geocoding

Prevalidation still avoids expensive geocoding of malformed/past/low-confidence
records. A record with neither venue, address nor coordinates has no defensible
geocoding query; moving that record into a geocoder would not recover evidence.
The demonstrated Visit loss is primarily listing/detail extraction, not proof
that Nominatim could resolve 106 unknown locations.

A credible dated event with a venue/address can remain in Explore without
coordinates. Map APIs and the client GeoJSON builder require coordinates. No
city-centre fallback was added. Existing unknown-location planner transitions
are explicitly labelled uncertain and use conservative buffers; a date-only
ending supplies no onward feasibility assumption.

Known-venue and persistent geocoding caches remain. Reject non-finite,
out-of-bounds and city/suburb-level provider results; negative matches persist
for one day, and provider failures are cached for the current run to avoid
repeated requests. Do not claim that every ambiguous first result is an exact
venue match: more sophisticated matching and cache refresh remain limitations.
No provider limit or authentication restriction was bypassed.

## Observability and count definitions

`GET /crawler/admin/quality` remains admin-protected. It now returns a UTC
reconciliation snapshot distinguishing total, future starts, fresh/stale,
cancelled/postponed, ongoing, known location, location completeness, mapped
eligibility, unmapped Explore eligibility, date-only endings and Home's 90-day
candidate horizon. Diagnostics identify failures, empty extraction, location
rejection spikes and unsupported/stagnant candidates. Existing per-source
canonical ingestion outcomes and provenance counts remain available.

Explore and map use published fresh/stale status. They do not currently impose
a universal future-start filter; map results also depend on viewport, cap and
client cache. Home adds future-start and 90-day eligibility plus user filtering
and ranking. Thus Home candidate counts are not a promise of one user's visible
cards. The GeoJSON collection is built in the mobile client, not an API endpoint.

Worker `--status` includes schedules, recent runs, candidate state/reasons,
endpoint count, queue status, oldest creation time, maximum attempts and durable
delivery totals. Read-only audits never claim an outbox enqueue or API delivery.
Raw extraction, validation rejects, accepted observations, pending unique queue
rows, acknowledged deliveries and canonical inserts/updates/merges are separate
quantities. A source-limited or quota-limited crawl remains `partial` and cannot
prove an event disappeared upstream.

## Storage, restart and migration

PostgreSQL stores canonical events, venues, EventSource facts, candidate admin
mirrors, run history and public-contribution learning work. `crawlerdata`
stores SQLite schedules, candidate endpoints/qualification, run history,
geocoding cache, outbox and delivery totals. The API candidate mirror is not a
replacement for the worker database; it does not mirror every endpoint.

Changes are additive: SQLite creates the endpoint table and indexes idempotently
and seeds endpoints from existing candidates. Alembic `0015` adds nullable
`events.end_date`; `0016` adds the PostgreSQL `postponed` enum value. No existing
events, sources, volumes or learning jobs are removed. PostgreSQL cannot safely
remove an enum value in place; downgrading 0016 retains the value and requires
operator consideration before running an old application that reads it.

Safe Mac-to-Mac transfer:

1. Stop the worker and API/maintenance writers for a coordinated cross-store
   snapshot. Keep Postgres running long enough for its logical dump.
2. Inside the Docker filesystem, run
   `python -m crawler.backup --source /data/state.db --output /data/migration.sqlite`.
   Use a fresh output name; the command refuses an overwrite. Copy the completed
   snapshot out with `docker cp`, never the active database's lone main file.
3. Use `pg_dump -Fc` from the PostgreSQL container with its configured database
   and account. A logical dump is transactional; stopping writers aligns the
   Postgres and SQLite snapshots. Do not copy a live `pgdata` directory.
4. Transfer those backups and the separately secured environment configuration.
   Preserve ingestion credentials, private-data key rings and service settings;
   do not put secrets or database snapshots in Git. Named Docker volumes belong
   to Docker's VM and do not migrate merely by cloning the repository.
5. On the destination, create new named volumes and restore into an isolated
   database/volume first. Run `pg_restore` against that new database and restore
   the completed SQLite snapshot with the worker stopped. Apply Alembic upgrades
   before starting the API/worker. Destructive replacement is a separate manual
   operator decision; no automatic restore is performed by this implementation.
6. Check SQLite `PRAGMA integrity_check`, PostgreSQL canonical/provenance counts,
   candidates/endpoints, due times, cache rows, outbox counts/status/attempts,
   learning work and API visibility against the source snapshot. Start one
   worker, verify its lock, drain/reconcile the outbox and inspect fresh runs.

Do not run multiple workers with separate state volumes. Restart recovery marks
interrupted jobs failed and preserves durable schedules/outbox/candidate state.
The backup and restart tests verify that pending events, qualification and
scheduling survive a consistent snapshot and reopen.

## Regression and live verification

Commands (application root; explicit test configuration avoids development
`.env` credentials and media paths):

```sh
.venv/bin/python -m pytest services/crawler/tests -q
INGESTION_API_KEY='' MEDIA_ROOT=/tmp/bacity-test-media \
  .venv/bin/python -m pytest services/api/tests -q --disable-warnings
cd apps/mobile
npm run typecheck
npm run test:map-markers
npm run test:event-chains
npm run test:evening
npm run test:weekend
```

The API suite now creates a separate temporary database per process, rather
than sharing repository `test.db`. Its fixtures do not use development data.
The HTTP→Scrapy→outbox→FastAPI→canonical→map test runs both registered and
candidate extraction, across repeated crawls and SQLite reopens. Candidate
fixtures reach probation then trust with three valid future runs, and a final
cancellation disappears from discovery. Existing Level 3 tests exercise
publication eligibility, durable work, retry bounds, private-data exclusion and
worker synchronization. No live human contributions were fabricated.

Final results: **144 crawler tests passed; 318 API tests passed, one skipped**.
The existing PostgreSQL-specific optional test is skipped by the portable suite;
real PostgreSQL migrations and ingestion were verified separately below. Mobile
TypeScript checks passed, as did 5 map-marker, 4 Event Chains, 5 Evening and
5 Weekend presentation tests. Existing datetime deprecations remain; crawler
pipeline/middleware required-spider deprecations were removed.

## Final isolated live proof

The valid proof uses `bacity_crawler_proof_20261021` and named volume
`bacity-crawler-proof-state-20261021`. The earlier invalid bind-mount experiment
is not included. A first named-volume pass delivered 74 Visit records before
Docker DNS failed; subsequent bounded operational retries recovered collection.
Those failed attempts remain in history. No publisher authentication, CAPTCHA
or robots rule was bypassed. Timing that includes VM suspension/DNS outages is
not used as a performance benchmark.

| Source | Final health | Accepted observations | Rejected | Measured run seconds |
|---|---|---:|---:|---:|
| Visit Bratislava | Healthy, complete | 160 | 4 missing location | 361.1 |
| Stará Tržnica | Healthy, complete | 43 | 22 past | 39.7 |
| SNG | Healthy, complete | 3 ongoing exhibitions | 0 | 23.2 |
| Bratislava City | Healthy, complete | 11 | 0 | 13.8 |
| GoOut | Partial: explicit five-page safety cap | 490 | 10 past | 8.7 |
| Nová Cvernovka | Healthy, complete | 21 | 0 | 34.0 |
| Karlova Ves | Healthy, complete | 9 | 0 | 1.9 |

Visit's initial 150-page budget reached productive details, not an irrelevant
navigation loop. The observed twelve-page listing and 139 valid detail records
justify its registry-specific 260-page cap, still below the global 300-page
ceiling. Inspection remains capped at ten pages. The final Visit run finished
normally at that budget, with 160 accepted observations and 111 future starts.
The baseline's 106 incomplete-card rejections are not 106 recoverable unique
events; four detail records still genuinely lack location evidence. The former
75-future-observation Visit snapshot and current 111 have different observation
times; the fixed-window canonical comparison below is the inventory comparison.

Fourteen hosts / 34 endpoints were persisted in the valid proof. Three hosts
reached productive probation: BKIS, panakrala.sk and tickets.billybarman.sk.
Their nine canonical references include **seven events without registered-source
provenance**, all with future starts at the snapshot. BKIS supplied six accepted
observations and five such contributions. Prague/Košice records from a mixed
organizer calendar were rejected for lack of Bratislava evidence. No live source
was forced into trust. The probation sources' valid ratios were below 80%, so
successful synthetic qualification tests do not imply live trust: live trust
remains zero pending genuinely qualifying recurring runs. Eleven other hosts
remain inspected, with unsupported markup or temporary failures exposed.

Count reconciliation across all valid proof attempts and retries:

| Stage | Count | Meaning |
|---|---:|---|
| Raw extracted | 1,114 | Includes corrected/repeated observations and failed-source partial results |
| Rejected by validation | 79 | Recorded rejection reasons; not canonical deletions |
| Validated / enqueue observations | 1,035 | 1,114 minus 79 |
| Unique outbox submissions acknowledged | 1,015 | 20 identical pending observations coalesced |
| API accepted | 1,015 | 755 creates + 215 updates + 45 cross-source merges |
| Canonical records | 755 | Includes historical parser observations retained for review |
| Future starts / published future | 700 | Same UTC snapshot; no cancelled/postponed records in this dataset |
| Fresh / stale / cancelled / postponed | 755 / 0 / 0 / 0 | Proof does not run development maintenance |
| Ongoing | 49 | Explicit time or inclusive end-date evidence |
| Explicit inclusive end date | 124 | No invented closing clock |
| Location complete | 732 | Coordinates plus venue/address |
| Map eligible | 749 | Published status plus coordinates |
| Future map eligible | 696 | Also requires future start |
| Explore eligible / unmapped Explore | 755 / 6 | Coordinates are not required for credible venue records |
| Home candidate eligible | 695 | Future starts within 90 days, before ranking/user filters |
| Pending / rejected outbox | 0 / 0 | Final named-volume integrity check: `ok` |

Only 326 acknowledgements happened inside per-spider close callbacks; the worker
subsequently drained the remaining 689. Thus summing `ingestion/delivered` from
spider stats alone is not a complete delivery reconciliation. The persistent
acknowledgement total is 1,015. Queue observation/new-record counters were added
after the first 74 deliveries: 961 subsequent observations coalesced to 941 new
queue records; 941 + 74 = 1,015. This explains the counter offset without losing
records or inventing delivery.

For a fixed UTC window `[2026-10-21, 2027-01-19)`, the original development map
snapshot contains 152 future canonical records (the two unmapped baseline
records were not future events). The isolated proof contains 695 published
records in that exact window. This compares upcoming inventory, not 424
historical totals against map features. Proof and development are separate
inventories; do not describe the proof counts as development counts.

## Remaining limits and release interpretation

- Canonical totals are database records, not a manual certification that every
  record is globally unique. Twenty-two Stará Tržnica same-URL groups retain
  multiple historical canonical IDs created by the old generic parser. The new
  adapter fixes incoming titles/clocks and prevents further generic noise.
  Existing IDs/saves were not destructively merged or deleted. Cross-language
  duplicates and legacy groups still need source-aware review; unique Level 2
  contribution means unique within current canonical provenance, not a claim
  that no semantic duplicate exists anywhere.
- Live probation/trust maturation over hours/days is not accelerated. Recurring
  collection, restart and three-run qualification are proven with isolated HTTP
  integration fixtures; long-term source reliability needs continued observation.
- BKIS dynamic pagination, JavaScript-only Tootoot pages, BJD's non-structured
  festival program, richer event sitemaps, additional ICS variants and other
  unsupported publisher markup remain coverage opportunities. SND remains
  deferred. A queued/inspected domain is not counted as coverage.
- Four Visit details remain unlocated. Geocoding may be ambiguous and is still
  synchronous but rate-limited/cached; no coordinates or venue were invented to
  rescue those records. Provider failures/deferred requests and cache hits are
  reported, including a persistent Retry-After cooldown across jobs.
- GoOut intentionally stops at five pages even when later schedules exist.
  Current high yield does not justify an unbounded crawl far into the future.
- Docker external DNS was intermittently unavailable during validation. To
  remove redundant resolver load, the network guard now caches validated public
  IPv4 pins for five minutes (maximum 256 hosts), re-pins each actual connection,
  and always revalidates redirects and expired entries. A deterministic test
  reduces 100 same-host lookups to one while still rejecting private-address
  redirects and expired-cache rebinding. This does not claim to repair the
  laptop's DNS service; persistent resolver failure still fails closed/backoffs.
- Only the local development Compose services were restarted. No production
  deployment occurred. Proof databases/volumes and the checked snapshot remain
  available; none were deleted or committed. No dependencies changed.

Development recovery, final repository verification and the commit/push result
are reported with the final working-tree status. The new migrations are additive
and were applied to local development and the isolated PostgreSQL proof.


## Local development recovery and final verification

After the isolated checks, bounded operational passes ran against the local
application for SNG, City, GoOut, Stará Tržnica, Visit, Cvernovka and Karlova Ves,
plus genuinely due candidate inspections. These are real public-source imports,
not test fixtures. The normal worker was resumed; a failed intermediate Visit
run retried through its persisted scheduler and subsequently finished healthy.
All seven registered sources have zero consecutive failures at the snapshot;
six are healthy/complete and GoOut is honestly partial at its five-page cap.

At `2026-10-21T01:04:00Z` (03:04 Europe/Bratislava):

| Development measure | Count |
|---|---:|
| Total canonical records | 759 |
| Future starts / published future | 703 |
| Fresh / stale / expired | 744 / 0 / 15 |
| Cancelled / postponed | 0 / 0 |
| Ongoing | 34 |
| Explicit inclusive end date | 122 |
| Known location / location complete | 759 / 731 |
| Map eligible / future map eligible | 735 / 695 |
| Explore eligible / unmapped Explore | 744 / 9 |
| Home candidate eligible | 698 |
| Fixed-window published records `[2026-10-21, 2027-01-19)` | 698 |
| All-city viewport GeoJSON features, requested cap 500 | 500 |
| Pending / rejected outbox | 0 / 0 |

The fixed-window comparison is 152 original records versus 698 current records.
The later 703 future-start count uses the snapshot's own current time and no
upper bound; it must not be substituted for that matching-window comparison.
The 500 displayed GeoJSON features are an actual run of the mobile converter on
the viewport API response, not a claim to have visually inspected native map
rendering or to have returned all 735 eligible markers in one capped response.

Four productive local candidate hosts (A4, BKIS, panakrala.sk and
tickets.billybarman.sk) have 13 canonical references. Twelve have no registered
source provenance; eleven of those have future starts. These references are
traceable to actual candidate runs with positive accepted counts, rather than
merely counting domains that appeared as ticket links in the old registered
crawler's output. There are no forced live trust promotions.

Local acknowledgement reconciliation: 824 new enqueue observations coalesced
to 804 queue records and 804 acknowledgements. Add the 229 baseline API accepted
observations to obtain 1,033 cumulative accepted requests: **759 creates + 209
updates + 65 merges**. Relative to baseline, that is 578 creates, 209 refreshes
and 17 additional merges. All timestamps/provenance remain intact; the 22 legacy
Stará Tržnica groups noted above were not silently deleted to improve a metric.
SQLite integrity is `ok`. Current API/maintenance/worker processes were restarted
to load the final local code; the protected quality endpoint returns 401 without
admin authentication. No production service was deployed.

Intentional changes are limited to crawler extraction/navigation/state/worker,
HTTP retry and backup helpers; API ingestion/status/date/diagnostic fields and
migration support; isolated regression fixtures; the mobile event contract; and
these crawler runbooks. No package/requirements/lock dependency changes or live
database snapshots are included in the commit. The final commit SHA, remote
verification and clean working-tree result are supplied in the final report.

The final DNS-cache build also passed a fresh real SNG audit: three accepted
events, zero request/pipeline errors, 23.0 seconds.

### Files changed

Application-relative paths (38 files, including this report):

- `apps/mobile/src/types/event.ts`
- `docs/crawler-coverage-recovery.md`
- `docs/crawler-operations.md`
- `docs/crawler-v2.md`
- `services/api/alembic/versions/0015_event_end_date.py`
- `services/api/alembic/versions/0016_postponed_events.py`
- `services/api/app/api/routes/crawler.py`
- `services/api/app/crud/ingestion.py`
- `services/api/app/models/event.py`
- `services/api/app/schemas/crawler.py`
- `services/api/app/schemas/event.py`
- `services/api/tests/conftest.py`
- `services/api/tests/test_coverage_recovery.py`
- `services/crawler/crawler/backup.py`
- `services/crawler/crawler/discovery.py`
- `services/crawler/crawler/extraction/feeds.py`
- `services/crawler/crawler/extraction/goout_extractor.py`
- `services/crawler/crawler/extraction/jsonld_extractor.py`
- `services/crawler/crawler/extraction/source_html.py`
- `services/crawler/crawler/extraction/visit_extractor.py`
- `services/crawler/crawler/items.py`
- `services/crawler/crawler/middleware.py`
- `services/crawler/crawler/navigation.py`
- `services/crawler/crawler/pipelines.py`
- `services/crawler/crawler/processing/normalize.py`
- `services/crawler/crawler/processing/validate.py`
- `services/crawler/crawler/retry.py`
- `services/crawler/crawler/run.py`
- `services/crawler/crawler/settings.py`
- `services/crawler/crawler/sources.py`
- `services/crawler/crawler/spiders/bratislava_sources_spider.py`
- `services/crawler/crawler/spiders/discovery.py`
- `services/crawler/crawler/state.py`
- `services/crawler/crawler/worker.py`
- `services/crawler/tests/fixture_crawl.py`
- `services/crawler/tests/test_coverage_recovery.py`
- `services/crawler/tests/test_e2e.py`
- `services/crawler/tests/test_jsonld_extraction.py`
