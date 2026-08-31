# BACity / Bratislava Event Discovery

## Current state: iOS Functional MVP

**Branch:** `ios-functional-mvp`  
**Status:** Working MVP baseline  
**Target:** Bratislava, Slovakia  
**Mobile:** React Native + Expo  
**Backend:** Python + FastAPI  
**Database:** PostgreSQL + PostGIS  
**Crawler:** Scrapy

This branch is the stable working baseline for continuing BACity development.

The recent Expo SDK migration work is intentionally **not part of this branch**. The goal here is to keep the known-working iOS MVP intact and improve the product from this point rather than repeatedly changing the foundation.

---

## What BACity is trying to prove

The original V0.1 specification defines one core loop:

```text
Public Web
    ↓
Crawler
    ↓
Event Extraction
    ↓
Event Normalization
    ↓
PostgreSQL / PostGIS
    ↓
FastAPI
    ↓
Expo Mobile App
    ↓
User
```

The prototype succeeds when real Bratislava events can be discovered automatically, stored, exposed through the API, displayed in the mobile app, searched/browsed, opened as event details, and represented geographically.

The current branch has the core pipeline and mobile MVP functioning, but the geographic presentation and event enrichment still need work before this can be considered a convincing end-to-end prototype.

---

# Current implementation

## Backend

The FastAPI backend is implemented with:

- Event API
- Event detail endpoint
- Search endpoint
- Nearby/geographic endpoint
- Venue endpoints
- Authentication endpoints
- User/profile endpoint
- PostgreSQL/PostGIS support
- SQLite fallback for local API tests
- JWT authentication
- Alembic database migration

The API and backend test suite are already in place.

## Crawler

The crawler contains:

- Scrapy project
- Generic JSON-LD extraction
- Generic HTML/OpenGraph fallback extraction
- Date parsing and normalization
- Event normalization
- Validation
- Category inference
- Duplicate detection
- Source-specific spiders
- Source registry

The crawler intentionally started with a single explicitly targeted website as the proof of concept.

That decision was correct for the first milestone. It is **not sufficient for the next phase**.

### Current crawler limitation

```text
ONE SPECIFIC WEBSITE
        ↓
crawler
        ↓
events
```

Next phase:

```text
SOURCE REGISTRY
        ↓
multiple source spiders
        ↓
normalization
        ↓
deduplication
        ↓
database
```

The crawler should eventually run automatically rather than requiring a manually selected spider.

---

# Mobile application

The mobile application is React Native + Expo + Expo Router.

The iOS MVP has been verified working on the simulator.

The app currently provides the main event-discovery experience and is visually improved compared with the initial prototype, but it is still deliberately barebones.

### Working

- App launches successfully on the iOS simulator
- API-backed event data can be loaded
- Event browsing/list presentation works
- Event details are available
- Authentication/login works
- Map screen loads
- Navigation between the main app areas works
- TypeScript typecheck passes on the current baseline

### Known issues / incomplete areas

#### 1. Map loads, but events do not render on it

This is the biggest current product defect.

The map itself is functional, but event markers are not currently being displayed.

The intended architecture from the original spec is:

```text
Current map viewport
        ↓
Bounding box / geographic query
        ↓
FastAPI
        ↓
PostGIS
        ↓
Events in viewport
        ↓
Map markers
```

The next implementation should make this path work end-to-end.

Do **not** solve this by downloading every Bratislava event and placing them all on the map. The viewport-based query is the intended architecture and should remain the target.

#### 2. Events have no useful images yet

Events currently load without their associated images or other visual enrichment.

The database model already supports `image_url`, so the next step is to make the full pipeline reliable:

```text
Source image
    ↓
Crawler extraction
    ↓
image_url
    ↓
API
    ↓
Mobile event card/detail
```

The UI should also have a sensible fallback when an event has no image.

This is a relatively small feature with a large visual payoff.

#### 3. The app still needs product polish

The app looks better than the initial prototype, but it is still a functional MVP rather than a finished product.

Priorities should be:

- Better event cards
- Better event detail presentation
- Image-driven visual hierarchy
- Clearer map event cards
- Loading states
- Empty states
- Error states
- Consistent spacing/typography
- Useful filtering and browsing interactions

Do not spend weeks polishing animations while the map has zero event markers. Fix functionality first.

#### 4. Authentication needs a security pass

Login currently works well enough for the MVP and has been tested functionally.

Security hardening is a **next-phase task**, not something that should block the current product work.

The security pass should cover at minimum:

- JWT/token handling
- Token storage
- Expiration and refresh behaviour
- Password hashing
- Authentication error handling
- Authorization boundaries
- Input validation
- Rate limiting where appropriate
- Secrets/configuration handling

The original specification explicitly said full authentication was not required for the first technical prototype. Authentication exists now because it is useful for the product, but it should not become the next rabbit hole.

---

# OG specification checklist

The checklist below is evaluated against the original V0.1 specification.

## Core required functionality

| Requirement | Status | Notes |
|---|---|---|
| Event crawler | 🟡 Partial | Working source-specific crawler; needs multi-source/autonomous crawling |
| Event extraction | ✅ Done | JSON-LD + generic fallback extraction exists |
| Event normalization | ✅ Done | Normalization pipeline implemented |
| PostgreSQL database | ✅ Done | Database/API infrastructure exists |
| PostGIS | ✅ Done | Geographic backend support exists |
| FastAPI backend | ✅ Done | Core event/auth/venue routes exist |
| Expo mobile app | ✅ Done | iOS MVP verified working |
| Event list | ✅ Done | Events can be loaded/displayed |
| Event details | ✅ Done | Event detail flow exists |
| Search | 🟡 MVP | Basic API search exists; needs product-level refinement |
| Basic filtering | 🟡 MVP | Backend support exists; mobile UX can be improved |
| Map | 🟡 Partial | Map loads, but event markers are missing |
| Event markers | ❌ Not working | Highest-priority current defect |
| Event source links | 🟡 Verify end-to-end | API model supports source URLs; should remain part of detail flow |
| Duplicate control | ✅ MVP | Conservative fuzzy duplicate detection exists |

## Optional functionality

| Requirement | Status | Notes |
|---|---|---|
| Local saved events | 🟡 Partial | Keep simple; cloud sync is not a priority yet |
| User location | 🟡 Partial | Geographic architecture exists; improve only where useful |
| Categories | ✅ MVP | Category extraction/inference exists |
| Authentication | ✅ Functional | Login works; security hardening is next phase |

## Explicitly out of scope for now

These should **not** become distractions during the next phase:

- Social networking
- Local guides
- Restaurant recommendations
- Public toilet discovery
- AI recommendations
- Machine-learning recommendations
- Multi-city support
- Large administration dashboard
- OpenSearch
- Redis-heavy infrastructure
- Full OAuth/account-management suite
- Premature visual polish

The original specification is intentionally conservative about infrastructure. Keep it that way.

---

# Where we are

The project has moved past the "can we make the pieces work?" stage.

We now have:

```text
Crawler
   ↓
Event data
   ↓
API
   ↓
iOS app
   ↓
Login
   ↓
Map
```

The weak link is no longer basic infrastructure.

The weak link is **event quality + geographic presentation + automatic freshness**.

That is where development should go next.

---

# Next phase: logical development order

## 1. Make events render on the map

**Highest priority.**

Implement the complete map data flow:

1. Read the visible map region.
2. Convert it to a geographic bounding box.
3. Request only events inside that viewport.
4. Return coordinates from the API.
5. Render event markers.
6. Tap marker → event preview card.
7. Tap card → event details.
8. Re-query when the viewport changes, with sensible debouncing.

Acceptance test:

```text
Open Map
    ↓
Events appear as markers
    ↓
Move/zoom map
    ↓
Visible events update
    ↓
Tap marker
    ↓
Event card
    ↓
Event details
```

This is the most important missing part of the original prototype definition of done.

---

## 2. Get event images flowing

Once map rendering works, improve the event presentation.

Implement:

- Reliable image extraction from source pages
- `image_url` persistence
- API exposure
- Image rendering in event cards
- Image rendering on event details
- Placeholder/fallback image
- Broken-image handling

Acceptance test:

```text
Crawler finds event
    ↓
Image extracted
    ↓
image_url stored
    ↓
API returns it
    ↓
Mobile displays it
```

This should make the app feel substantially less like a database viewer.

---

## 3. Upgrade crawling from manual/source-specific to automatic

The current one-site crawler was the correct first step.

Now build the actual discovery engine.

Target:

```text
Source Registry
       ↓
Scheduled crawl jobs
       ↓
Multiple spiders
       ↓
Extraction
       ↓
Normalization
       ↓
Validation
       ↓
Deduplication
       ↓
Geocoding
       ↓
PostgreSQL
       ↓
API
       ↓
Mobile
```

The important part is not simply "scrape more websites."

The system should be able to:

- Run multiple sources
- Schedule crawls
- Detect failures
- Avoid duplicate events
- Update changed events
- Expire/remove stale events
- Preserve source URLs
- Keep crawl history/metadata
- Continue operating when one source fails

### Background crawling

The desired behaviour is:

```text
User opens app
       ↓
Fresh event database already exists
       ↑
Background crawler keeps updating it
```

This is where a worker/queue becomes useful.

Do not add infrastructure just because the spec mentions Redis. Introduce it when scheduled crawling actually needs it.

---

## 4. Improve event quality

After multiple sources are running, event quality becomes more important than raw volume.

Focus on:

- Better date/time extraction
- Better venue extraction
- Better category inference
- Better image extraction
- Better address/geocoding
- Duplicate detection across sources
- Stale-event cleanup
- Confidence scoring

The target is not:

> "We scraped 10,000 events."

The target is:

> "The app consistently shows useful, accurate Bratislava events."

100 good events beat 10,000 garbage records.

---

## 5. Product polish

Once the core data loop is reliable:

- Improve home feed
- Improve Explore filters
- Improve event cards
- Improve event details
- Improve map cards
- Add proper loading/empty/error states
- Improve saved events
- Tighten navigation
- Improve visual hierarchy

The app should start feeling like an actual local event product rather than an engineering demo.

---

## 6. Security hardening

After the event-discovery loop is solid:

- Audit authentication
- Review token storage
- Review API authorization
- Review password handling
- Review secrets
- Add rate limits where appropriate
- Add security-focused tests

Authentication should support the product, not hijack the roadmap.

---

# Recommended roadmap

The most efficient sequence from this branch is:

```text
CURRENT
  │
  ├── iOS MVP works
  ├── API works
  ├── Events load
  ├── Login works
  └── Map loads
        │
        ▼
PHASE A
  Fix map event markers
        │
        ▼
PHASE B
  Event images + visual enrichment
        │
        ▼
PHASE C
  Multi-source automatic crawling
        │
        ▼
PHASE D
  Background scheduling + freshness
        │
        ▼
PHASE E
  Event quality + dedup + geocoding
        │
        ▼
PHASE F
  Product/UI polish
        │
        ▼
PHASE G
  Authentication/security hardening
```

This order is intentional.

There is little value in polishing the login screen while the map cannot show an event. There is also little value in building a sophisticated crawler scheduler before the mobile app can correctly consume and display the data.

Fix the core loop first.

---

# Definition of done for the next milestone

The next milestone should be considered complete when this works:

```text
Crawler
  ↓
Real event with image + coordinates
  ↓
Database
  ↓
API
  ↓
Home/Explore
  ↓
Map marker
  ↓
Map event card
  ↓
Event details
  ↓
Source link
```

And the crawler should be able to refresh that event without manually invoking a single source-specific spider.

At that point BACity stops being merely a functional shell and starts proving the actual product thesis.

---

# Development principles

Keep these from the original specification:

1. **Functionality before polish.**
2. **Quality before event count.**
3. **Use deterministic extraction first.**
4. **Use Playwright only when a source actually requires JavaScript rendering.**
5. **Do not introduce OpenSearch until PostgreSQL search becomes a real limitation.**
6. **Do not introduce Redis until background jobs genuinely require it.**
7. **Do not make the mobile app depend on an LLM.**
8. **Keep the map viewport-based instead of downloading the entire city.**
9. **Build infrastructure incrementally.**
10. **Do not turn the MVP into a production platform prematurely.**

---

# Local development

From `BACity-/apps/mobile`:

```bash
npm install
npm run typecheck
npx expo start
```

For the iOS MVP, use the simulator workflow that is already verified on this branch.

Backend and crawler setup remain documented in the existing service directories.

---

# Final status

**BACity is currently at a functional iOS MVP baseline.**

The foundation is good enough to continue building.

The next job is not another migration, another framework upgrade, or another pile of infrastructure.

It is:

**make the events appear on the map → make the events look good → make the crawler keep the database fresh automatically.**

That is the shortest path from the current state to a convincing product prototype.
