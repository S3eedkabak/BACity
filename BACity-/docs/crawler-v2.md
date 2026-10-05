# Crawler V2: architecture and operator runbook

Starting checkpoint: `b4494e8e30917835d715f4128bc1e8ff8c67c526`, branch `crawler-v2`.
This extends the existing worker, Scrapy subprocesses, SQLite scheduler/outbox,
canonical ingestion, EventSource provenance and role-protected crawler API.
No new service, dependency, billing feature, planner rule or mobile UI.

## Audit and scope

Seven existing registry sources remain: Visit Bratislava, Stará Tržnica, SNG,
Bratislava City, GoOut feeder, Nová Cvernovka and Karloveské centrum kultúry.
GoOut uses a public JSON feeder, not browser rendering. SND remains explicitly
deferred; no active registry source requires Playwright. Staré Mesto, A4 and
university sources are not enabled registry entries. Their historic restrictions
were not independently revalidated; no bypass or speculative source was added.

Original gaps: discovered domains became ordinary seeds without probation;
there were no RSS/Atom/ICS adapters or candidate controls; dedup could merge
performances three hours apart; temporal conflicts used whole-event confidence;
failure of one provenance source could cause premature removal; a DNS check
was followed by a second resolution at connection time. Discovery's async start
and middleware's coroutine also needed modern Scrapy compatibility.

## Flow and source lifecycle

Registry crawl → relevant public event/calendar/feed links → CandidateSource
→ bounded structured inspection → probation → trusted recurring inspection.

Worker SQLite is the durable scheduling authority. PostgreSQL mirrors candidate
state/metrics and owns admin enable/disable controls. Normalized domain identity
ignores `www`; tracking parameters/fragments are removed. Only one URL is retained
per domain, with a hard capacity of 250 candidates. Repeated evidence does not
create another candidate. Registry domains are not re-registered as candidates.
Legacy discovered seeds are quarantined into this queue on startup.

Only registered sources may discover external domains: no recursive expansion
from candidate domains, including trusted candidates. This deliberate one-hop
boundary avoids unrestricted crawling. Candidates use static structured extraction;
they cannot select code, endpoints, browser settings or an extraction implementation.

Every inspection records a reason and transitions deterministically:

- No validated events: inspected; rejected after three attempts.
- Robots exclusion or HTTP 403: blocked, without automatic retries.
- Three consecutive failed attempts: rejected.
- Positive yield: probation.
- Three consecutive successful runs with mean completeness ≥60/100 and
  validated/(validated+rejected) ≥80%: trusted.
- Degrading quality immediately returns a trusted candidate to probation;
  its qualifying-run streak resets. Repeated failure rejects it.
- Admin disable wins over stale worker snapshots. Re-enable restarts inspection,
  not trust, and can retry a blocked/rejected candidate only as an explicit action.

Counts describe crawler validation acceptance, not an assertion of API delivery.
Queued, delivered and pending outbox counters remain distinct. API outages retain
validated data in the durable outbox with the existing bounded delivery retries.
If candidate-control synchronization fails, previously validated local controls
remain in force; newly changed remote controls apply once synchronization resumes.

## Temporal extraction

Structured start/end dates remain preferred. JSON-LD additionally accepts explicit
ISO durations, organizer name and `previousStartDate` reschedule evidence.
Community adapters retain structured ends; Cvernovka clock ranges are preserved
instead of replaced with midnight. Visit Bratislava no longer invents `23:59`
when a multi-day listing supplies only an end date, not an end clock.

Intervals support explicit same-day/multi-day datetimes, ISO durations up to
31 days, Slovak clock ranges and midnight crossing. Clock-only ends use the
start's Bratislava calendar date and roll into the next day only when earlier
than the start clock. Unknown duration remains unknown. Description text,
door-opening times, category and venue hours never imply duration.

Naive Bratislava times use strict DST localization. Ambiguous/nonexistent starts
are rejected. An invalid end cannot discard a valid start or manufacture duration.
Explicit offset datetimes remain valid; canonical ingestion retains UTC normalization.

Compact EventSource facts store latest observation, method, confidence, organizer,
temporal evidence and the strongest observed end. End precedence is explicit end
> explicit duration > text range > unknown; source reliability × extraction
confidence breaks ties. Weaker refreshes/missing ends do not erase better evidence.
Legacy known ends without facts receive conservative protection. This is temporal
field-level conflict resolution, not a new general-purpose history database.

## Generic adapters

- Existing JSON-LD Event/ItemList/graph support is reused.
- RSS/Atom accepts explicit event start/end extensions or embedded JSON-LD.
  Publication timestamps are never event starts. A news-only feed yields no events.
- ICS supports VEVENT, UTC/IANA TZID, explicit DTSTART/DTEND/DURATION,
  cancellation, simple DAILY/WEEKLY/MONTHLY/YEARLY RRULE and EXDATE.
  Maximum 32 occurrences/event, 100 events/feed, one-year forward horizon;
  historical recurrence enumeration is limited to five years. Rules with sub-day
  expansion are rejected. Custom VTIMEZONE and RECURRENCE-ID overrides are
  intentionally unsupported rather than silently interpreted incorrectly.
- No universal arbitrary-HTML event guessing is enabled for candidates.
  Existing registered source-specific/static fallbacks remain unchanged.

Feeds are capped at 2 MiB. XML DTD/entity declarations are rejected. Structured
JSON endpoints are never traversed with HTML selectors.

## Completeness and observability

Deterministic completeness weights: title 10, description 5, start 20, end 25,
venue 10, coordinates 10, category 5, organizer 5, source URL 5, image 5.
`Other` is not considered a complete category. This measures completeness,
not truth. Reliability, extraction confidence, provenance and freshness remain
separate evidence; no synthetic fields improve scores.

Crawler source/run metrics report validated/future counts, score totals,
end/coordinate/venue/category/organizer coverage, rejection reason counts,
errors and duration. Existing run history is retained (50 runs/source).

Admin-only endpoints extend the existing surface:

- `GET /crawler/admin/sources` and `.../{id}/runs`: health and quality snapshots.
- `GET /crawler/admin/candidates`: qualification queue and reason codes.
- `PATCH /crawler/admin/candidates/{domain}`: `{ "enabled": false|true }` only.
- `GET /crawler/admin/quality`: total/future events, total ends, future coverage,
  multi-source count, events per source, last-run rejection rates and candidate states.
- `GET /crawler/admin/events/{id}/quality`: missing fields and source facts.

Quality metrics also report average crawl duration and cumulative created/updated/
merged ingestion outcomes; merges distinguish canonicalization from routine refreshes.
Metrics do not
assert a production improvement from fixture or dry-run data. The supplied
58/424 end-coverage snapshot has not been independently remeasured here.

## Deduplication and lifecycle

Exact occurrence keys remain idempotent. Cross-source matching is bounded to
500 candidates within ±15 minutes, with eager-loaded venues, near-identical
titles and compatible location. Conflicting explicit venue names veto proximity
matches. Different days, repeat performances hours apart and unrelated events
on a shared listing remain distinct. No full-event-database scan.

An explicit prior start from the same source/title may update the canonical event
on reschedule; recurring occurrences without that evidence remain separate.
Manual overrides retain protection. Existing cancellation/postponement handling
and browsing contracts remain intact.

Maintenance still expires finished events and marks unobserved events stale.
Quota/time/item-limited scans are reported as `partial`, never proof of upstream
absence. Removal additionally requires *every* provenance source to be active/healthy and
successfully crawled after that occurrence's last observation. Disabled/failing/
never-successful sources cannot turn absence into deletion. SQL EXISTS checks
avoid a per-event source-query loop. Canonical IDs and evidence are preserved.

## Security and resource limits

HTTP/HTTPS only; no userinfo, credential query strings, unsupported ports,
local/internal hosts or private/loopback/link-local/metadata addresses in candidates.
At every Scrapy request (including robots and redirects), all DNS answers must be
public. A validated IPv4 is pinned in Scrapy's actual CachingThreadedResolver
cache before connection. IPv6-only destinations fail closed in this implementation.
Do not replace the resolver with one that bypasses this cache.

Robots remains mandatory. Crawl-Delay and Retry-After are honored. No CAPTCHA,
authentication or publisher restriction bypass. Fixed operator-configured geocoding
does not use candidate URLs, and geocoder redirects are now disabled.

| Limit | Existing sources | Candidate inspections |
| --- | --- | --- |
| Pages/job | 150 | 10 |
| Accepted items/job | 1,000 | 100 |
| Scrapy time | existing job allowance minus 30 s | 90 s |
| Process timeout | 900 s default | 120 s |
| Global concurrency | 8 | 2 |
| Per-host concurrency | 2 | 2 |
| Redirects | 3 | 3 |
| Response | 5 MiB | 5 MiB (structured feed 2 MiB) |
| Retries | 2 | 2 |

Depth ≤3, ≤50 followed links/page, ≤20 new domains/registry job; ≤5 inspections
per scheduler cycle and ≤250 candidates overall. Environment controls may lower
depth/link/discovery limits, not lift these hard caps. One worker/file lock remains
the supported deployment. Source failures back off to 24 h, no faster than their
configured interval; probation normally retries hourly and trusted sources every 6 h.

Candidate inspections never render. Optional manually configured Playwright now
fails closed unless `CRAWLER_RENDER_NETWORK_ISOLATED=1`: set that only after
verifying browser-container egress rejects all private/internal destinations, DNS
rebinding and private redirects for *subresources* as well as top-level navigation.
The browser resolves independently of Scrapy; this flag is an operator assertion,
not a firewall implementation. No native/browser infrastructure was added.

## Level 3 public-source evidence

`POST /crawler/evidence` accepts only `{ "event_id": "canonical-event-uuid" }`,
requires a configured ingestion key, and reads an already-published fresh/stale
canonical event's public source URL. Pending/private contributions, arbitrary
source URLs, private messages, group data and location are not inputs. An event
without a suitable public URL can remain a legitimate human contribution;
learning is separate and optional, never a condition of moderation/acceptance.

Internal candidate runtime/report endpoints also require the configured ingestion
key. Public discovery reads, subscriptions and consumer entitlements are untouched.

## Operations

1. Back up database and crawler volume; apply Alembic `upgrade head` (0013).
2. Configure the existing matching `INGESTION_API_KEY` on API and worker.
3. Start/restart the existing worker. No new service or dependency is required.
4. Inspect source/candidate health with an ADMIN token. Disable problematic
   candidates rather than deleting the state volume or bypassing robots.
5. Inspect missing end fields and provenance before changing a parser. Unsupported
   or missing source metadata must remain unknown, not inferred.
6. API outage: retain outbox, inspect rejected payload reason codes, restore API
   then recrawl corrected parsers; existing delivery resumes automatically.
7. Candidate rejection: examine reason/quality/robots status. Re-enable explicitly
   only after fixing the issue and confirming publisher permissions.

Manual sources still use `SourceSeed` in `crawler/sources.py`, a deterministic
adapter where necessary, source fixtures and policy verification. Never add
blocked sites merely to increase source count.

Safe live extraction without API/database/geocoder writes:

```sh
CRAWLER_STATE_PATH=/tmp/bacity-audit/state.db python -m crawler.run \
  --source '<existing SourceSeed JSON>' --stats /tmp/bacity-audit/stats.json \
  --inspection --audit
```

The audit still obeys robots, public-network checks and bounded inspection limits;
discovered candidate evidence is written only to the chosen temporary SQLite file.

## Verification scope and limitations

New tests cover intervals/DST, structured feeds/recurrence, candidate caps,
normalization/trust/demotion, credential/private IP/redirect/DNS guards, no unsafe
rendering, explicit reschedules, temporal conflicts, adversarial dedup, multi-source
failure survival, admin controls and public-learning authentication/privacy.
Existing real HTTP → Scrapy → API → map regression remains in the suite.

Real PostgreSQL/PostGIS migration validation uses an isolated
`bacity_migration_test` connection; the existing test creates/drops its own UUID
database and tests upgrade/backfill/downgrade/re-upgrade plus JSONB/constraints/indexes.
Normal `bratislava_events` is never a migration-test target.

Live bounded, non-ingesting checks performed on 2026-10-05:
Cvernovka 12 validated records (no explicit ends in that sample);
Karlova Ves 9 validated records, all with explicit end and coordinates;
Visit Bratislava 2 validated detail records in a 10-page sample, with many
incomplete listing cards rejected. These are extraction counts, not unique
canonical production-event gains. Existing JSON traversal and compatibility
bugs found by these checks were fixed and regression-tested.

Deferred: authenticated/blocked sources, universal HTML scraping, complex ICS
overrides/timezone definitions, automatic recursive trust expansion, browser egress
sandbox implementation, and production before/after coverage measurements.
Generated/planner duration inference and private-data discovery remain prohibited.

## Change manifest and validation

All paths below are relative to `BACity-/`:

- Documentation: `docs/crawler-operations.md`, `docs/crawler-v2.md`.
- API migration: `services/api/alembic/versions/0013_crawler_v2.py`.
- API routes: `services/api/app/api/routes/crawler.py`, `community.py`
  (community change only excludes crawler metadata from its existing ORM constructor).
- API ingestion/learning: `services/api/app/crud/ingestion.py`,
  `services/api/app/core/source_learning.py`.
- API models: `services/api/app/models/__init__.py`, `candidate_source.py`,
  `event_source.py`, `source.py`.
- API schemas: `services/api/app/schemas/crawler.py`, `event.py`.
- API tests: `services/api/tests/test_crawler_v2.py`, `test_ingestion.py`,
  `test_postgres_migrations.py`.
- Crawler: `services/crawler/crawler/discovery.py`, `items.py`, `middleware.py`,
  `pipelines.py`, `quality.py`, `run.py`, `settings.py`, `state.py`, `worker.py`.
- Extraction: `services/crawler/crawler/extraction/community_extractors.py`,
  `date_parser.py`, `feeds.py`, `jsonld_extractor.py`, `temporal.py`, `visit_extractor.py`.
- Normalization: `services/crawler/crawler/processing/normalize.py`.
- Spiders: `services/crawler/crawler/spiders/bratislava_sources_spider.py`, `discovery.py`.
- Crawler tests: `services/crawler/tests/test_crawler_v2.py`, `test_discovery_worker.py`.

Verified results:

- Full API suite: **170 passed, 1 skipped** (optional PostgreSQL test skipped
  only in the SQLite run; separately executed successfully below).
- Full crawler suite, including real HTTP/API end-to-end test: **88 passed**.
- Real isolated PostgreSQL/PostGIS migration and ORM verification: **1 passed**;
  upgrade/backfill, downgrade/re-upgrade, JSONB, candidate constraint/index,
  existing subscription/group constraints, row locks and ingestion/lifecycle SQL.
- Focused V2/admin API suite: **10 passed** (7 V2 + 3 existing admin tests).
- Python compilation and `git diff --check`: passed.
- Worker CLI/imports and bounded live spider startup: verified.

Commands used in the existing API/worker Docker images:

```sh
python -m pytest /app/tests -q --disable-warnings
python -m pytest tests -q --disable-warnings  # services/crawler, API deps installed
TEST_POSTGRES_URL=postgresql+psycopg2://USER:REDACTED@postgres:5432/bacity_migration_test \
  python -m pytest /app/tests/test_postgres_migrations.py -q --disable-warnings
```

Both the migration test's UUID database and its test-only connection database
were removed. Normal development data was untouched. No mobile/native validation
was claimed: mobile, billing and planner code were not changed. Existing framework
warnings remain; the two targeted Scrapy lifecycle deprecations were migrated
without a dependency upgrade, retaining Scrapy 2.11 compatibility.
