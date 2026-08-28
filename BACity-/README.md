# Bratislava Event Discovery Platform — v1

This is a first working slice of the platform, scoped deliberately around
the spec's own guidance (section 63 / Architectural Principle 8): **prove
the hardest part first** — the crawler's extraction pipeline — before
building the mobile UI on top of it.

## What's built and tested here

### `services/crawler` — the Event Discovery Engine core
The multi-stage extraction pipeline from spec section 18-27:
- `extraction/jsonld_extractor.py` — JSON-LD / schema.org Event parsing (priority 1-2)
- `extraction/generic_extractor.py` — OpenGraph + heuristic HTML fallback (priority 4, 7)
- `extraction/date_parser.py` — normalizes ISO, slash, English, and Slovak date formats
- `processing/normalize.py` — builds a clean `NormalizedEvent`, guesses category
- `processing/validate.py` — confidence-based accept/reject, flags low-confidence events for advanced extraction
- `processing/dedup.py` — fuzzy duplicate scoring (title + time + venue), conservative on purpose
- `crawler/sources.py` — 20 real seed Bratislava sources (major institutions + niche venues per section 15)
- `crawler/spiders/` — a generic JSON-LD spider usable against any source, plus one source-specific example
- **`crawler/run_proof.py`** — runs the full pipeline against fixture pages, no Docker/network needed. This is the "first technical proof" from section 63.

**28 passing tests** (`services/crawler/tests/`), covering extraction, date parsing, normalization, validation, and dedup — including two real bugs caught and fixed along the way:
1. `dateutil.parse(..., dayfirst=True)` was silently corrupting unambiguous ISO 8601 dates (`2026-12-01` → `2026-01-12`). Fixed by routing ISO-shaped strings through `isoparse()` first.
2. Category keyword dict iteration order caused "Nightlife" to match before "Student" on titles like "Student Welcome Party". Fixed by reordering keywords from most to least specific.

### `services/api` — FastAPI backend
- SQLAlchemy models for `Event`, `Venue`, `Source`, `User` (spec sections 13, 21, 22, 37)
- Dialect-aware `/events/nearby`: `ST_DistanceSphere` on Postgres, haversine bounding-box fallback on SQLite (so local dev/tests don't require Postgres+PostGIS running)
- JWT auth (`/auth/register`, `/auth/login`, `/users/me`)
- `/events`, `/events/{id}`, `/events/search`, `/events/nearby`, `/venues/{id}`, `/venues/{id}/events`
- Alembic migration for the Postgres schema (`alembic/versions/0001_initial_schema.py`)

**15 passing tests** (`services/api/tests/`), covering listing/filtering, search, nearby-radius (including a negative case), auth, and interests.

### Infrastructure
- `docker-compose.yml` — Postgres+PostGIS, Redis, OpenSearch, api, worker
- `infrastructure/postgres/init.sql` — enables the PostGIS extension

## Running it

```bash
# Crawler pipeline proof (no dependencies beyond `pip install -r requirements.txt`)
cd services/crawler
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m crawler.run_proof
python -m pytest tests/ -v

# API
cd services/api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest tests/ -v          # uses SQLite, no Docker needed
uvicorn app.main:app --reload       # http://localhost:8000/docs

# Full stack with real Postgres+PostGIS/Redis/OpenSearch
cp .env.example .env
docker compose up
```

## Deliberately not built yet

Per the phase plan in the spec (sections 62-63) and Architectural Principle 8
("build infrastructure incrementally"), these are the next slices, in order:

1. **OpenSearch indexing + search-ranked queries** (API currently does a
   plain SQL `LIKE` search as a stand-in — functionally fine for MVP scale,
   but not the ranked full-text search in section 33-34).
2. **Redis-backed background worker** wiring the crawler into scheduled,
   queued jobs instead of the one-off `run_proof.py` / manual spider runs.
3. **Mobile app** (React Native + Expo) — Home / Explore / Map / Saved / Profile,
   consuming the API above.
4. Running the spiders against real, live source pages (this sandbox's
   network access is restricted to package registries, so `run_proof.py`
   demonstrates the pipeline against realistic fixture HTML instead —
   the spiders in `crawler/spiders/` are real Scrapy code, just unexercised
   against the live internet from here).

## Repository structure

```text
bratislava-events/
├── services/
│   ├── api/          FastAPI backend (models, routes, migrations, tests)
│   └── crawler/       Extraction pipeline, spiders, source registry, tests
├── infrastructure/
│   └── postgres/      PostGIS init script
├── docker-compose.yml
├── .env.example
└── README.md
```
