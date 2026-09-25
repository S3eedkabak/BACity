# Scheduled event ingestion

The worker is a long-running service. It crawls due sources on startup, checks
the schedule every 30 seconds, and keeps its schedule, discovered sources,
crawl history, geocoding cache and delivery queue in the `crawlerdata` volume.
The application reads the canonical PostgreSQL events through the existing
`/events` endpoints; `/v1/events` is an equivalent versioned route.

## Start

From `BACity-`:

```sh
cp .env.example .env
# Set JWT_SECRET and INGESTION_API_KEY to separate random secrets in .env.
docker compose up --build -d postgres api worker
docker compose ps
docker compose logs -f worker
```

The API waits for Postgres, applies Alembic migrations, and becomes healthy
after a database query succeeds. The worker waits for the API. Both restart
automatically. `/events` writes and freshness maintenance require
`X-Ingestion-Key` when `INGESTION_API_KEY` is set. Browsing remains public.

The first crawl takes several minutes. Partial results survive a restart in
the delivery queue. Keep `crawlerdata` and `pgdata` when recreating containers;
back up both volumes. No external search service or paid API key is needed.

## Scheduling and discovery

Defaults: GoOut every 2 hours, Visit Bratislava every 6 hours, other trusted
sources every 12 hours, discovered domains every 24 hours. Set
`CRAWLER_INTERVAL_MINUTES` to override the trusted-source intervals (minimum
15 minutes), then recreate the worker. `0` keeps individual source schedules.
Changing an interval affects the next completed crawl; existing due times are
preserved. Source-specific defaults live in `crawler/sources.py`.

Each job runs in its own subprocess, with a 900-second hard timeout and a
graceful Scrapy time limit before that. Failures retry with exponential backoff,
capped at one hour. Three consecutive failures emit `CRAWLER_ALERT` at ERROR
level for your log monitoring system. A filesystem lock prevents two workers
sharing the same state volume from overlapping. This is a single-worker
deployment; do not deploy replicas with separate state volumes.

Discovery scans event/program/calendar links and next-page/load-more URLs.
Trusted sources can add new public domains automatically, with the parent URL
recorded. Newly discovered domains are not allowed to expand the trust graph
again without being promoted into the trusted registry. This prevents unlimited
off-topic crawling. Defaults bound each job to 150 pages, depth 3, 50 links per
page and 20 discovered domains, with 250 sources overall. Adjust
`CRAWLER_MAX_DEPTH`, `CRAWLER_MAX_LINKS`, `CRAWLER_MAX_NEW_SOURCES` and
`CRAWLER_MAX_SOURCES` as needed. A bounded crawl is marked successful only if it
processed at least one validated event and had no parser exceptions.

`CRAWLER_ALLOW_DOMAINS` optionally limits destinations; `CRAWLER_BLOCK_DOMAINS`
excludes domains and subdomains. Private-network destinations and non-web URLs
are rejected, including on redirects. Scrapy obeys robots.txt, server crawl
delays, retry limits, response-size limits and throttling. The crawler does not
bypass site blocks or CAPTCHAs. Zero-event sources are visible as failures and
retry; a blocked website does not stop other sources.

## Extraction and quality

The extraction order retains site adapters and prefers JSON-LD, including
Event nodes nested inside ItemList/graphs, then microdata and structured HTML.
Visit Bratislava has an adapter for its separate date/clock fields. GoOut uses
its public feeder. Ordinary HTML pagination works without a browser. Arbitrary
JavaScript-only interactions require a source adapter; enabling the existing
optional Playwright handler also requires installing Chromium and its OS
dependencies. Default images do not install a browser.

Normalization cleans HTML, whitespace and tracking parameters, converts local
dates using Europe/Bratislava, extracts images/prices and classifies categories
and tags deterministically. Incomplete, past, malformed, low-confidence or
out-of-area records are rejected before submission. Coordinates must be inside
the Bratislava bounding box (48.0–48.35 latitude, 16.9–17.35 longitude). Unknown
locations remain unmapped; no fallback city-centre coordinates are invented.
New sources need explicit local evidence. Known venues and a persistent
geocoding cache avoid repeated lookups; successful results do not expire,
negative results retry after a day. The geocoder is bounded to Bratislava and
requests are spaced at least 1.1 seconds apart.

PostgreSQL stores canonical events, normalized venue rows, sources, and every
event/source reference with its last-seen time and deduplication confidence.
Exact occurrences are idempotent. Cross-source merging requires similar titles,
a shared venue/address, and compatible times or supporting descriptions.
Different simultaneous events on the same listing remain separate. Better
sources win conflicting fields; manual overrides are preserved. UTC storage
and explicit UTC API timestamps avoid losing the Bratislava UTC offset.

Cancellation updates remain accessible by event ID (including saved events)
but disappear from discovery and map results. Postponed events are withheld
until a dated update arrives. Maintenance expires events a day after their end,
marks unobserved events stale after 3 days and removes them from discovery after
14 days. It preserves event IDs and provenance.

## Operations

```sh
docker compose exec worker python -m crawler.worker --status
docker compose exec worker python -m crawler.worker --health
# For a one-off run, first stop the continuous worker to release its lock:
docker compose stop worker
docker compose run --rm worker python -m crawler.worker --once
docker compose start worker
```

Status reports due times, failure counts, discovery parents, recent runs and
delivery queue totals. Crawl statistics include duration, extracted, rejected,
queued and delivered counts. API outages retain pending events on disk and
retry with backoff. Non-retryable invalid payloads are retained as `rejected`
instead of blocking healthy events. Inspect their `error`/`payload` in the
SQLite `outbox` table before correcting the parser and recrawling. Recrawling
requeues the corrected occurrence. Do not delete the state volume to clear an
individual error.

## Verification

Install both services' requirements, then run their suites separately:

```sh
python -m pip install -r services/crawler/requirements.txt -r services/api/requirements.txt
python -m pytest services/crawler/tests -q
python -m pytest services/api/tests -q
```

The deterministic end-to-end test starts real local HTTP and FastAPI servers,
runs Scrapy three times, and verifies robots exclusion, a transient 503 retry,
pagination, normalization, durable delivery, source merging, UTC timestamps,
map queries, idempotency and cancellation. Additional tests cover persistent
scheduling/cache state, locks, domain policy and rejected delivery payloads.
The PR workflow fails on test failures. The manual `Crawler E2E` workflow builds
the real Docker/PostGIS stack and verifies live source ingestion. Live sources
are not required to be available for deterministic PR tests.

The wider mobile UX roadmap (recommendations, saved-event notifications,
interactive map controls and search UI) is separate from this ingestion service.
