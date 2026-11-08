
# BACity

[![Python](https://img.shields.io/badge/Python-3.x-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![React Native](https://img.shields.io/badge/React%20Native-0.74-61DAFB?logo=react&logoColor=black)](https://reactnative.dev/)
[![Expo](https://img.shields.io/badge/Expo-51-000020?logo=expo&logoColor=white)](https://expo.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.x-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Scrapy](https://img.shields.io/badge/Scrapy-2.11-60A839?logo=scrapy&logoColor=white)](https://scrapy.org/)
[![Playwright](https://img.shields.io/badge/Playwright-1.x-2EAD33?logo=playwright&logoColor=white)](https://playwright.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![PostGIS](https://img.shields.io/badge/PostGIS-geospatial-336791?logo=postgresql&logoColor=white)](https://postgis.net/)


**BACity is a work-in-progress event discovery platform for Bratislava, Slovakia.**

The project is being built around one simple idea: make it easier to discover what is happening in Bratislava by automatically collecting real events from public sources, normalizing them into a common format, and presenting them through a mobile application.

> **Status:** Active prototype development  
> **Target:** Bratislava, Slovakia  
> **Mobile:** React Native + Expo + TypeScript  
> **Backend:** Python + FastAPI  
> **Database:** PostgreSQL + PostGIS  
> **Crawler:** Scrapy  
> **JavaScript rendering:** Playwright, only where required

BACity is **not finished and is not intended to be production-ready yet**. Development will continue as the crawler, API, geographic features, data quality, and mobile experience are progressively connected and improved.

---

## What BACity is

Bratislava has events spread across many different websites, calendars, cultural institutions, venues, and ticketing platforms. These sources use different page structures, date formats, naming conventions, and levels of data quality.

BACity is intended to provide a single place to discover those events.

The core system is:

~~~
Public Web
    ↓
Scrapy Crawler
    ↓
Event Extraction
    ↓
Normalization & Validation
    ↓
Deduplication & Geocoding
    ↓
PostgreSQL + PostGIS
    ↓
FastAPI
    ↓
Expo Mobile App
    ↓
User
~~~

The mobile application is only one part of the system. The real product challenge is keeping the event dataset useful, accurate, geographic, and fresh.

---

## The goal of the prototype

The project is based on a deliberately focused prototype objective:

> **Can BACity automatically discover real events happening in Bratislava, store them, expose them through an API, and let users search, browse, view details, and find those events geographically?**

The prototype does not need to solve every problem a finished event platform would.

It needs to prove the core loop.

A successful prototype should allow a user to:

1. Open the mobile application.
2. Discover real Bratislava events.
3. Search or browse events.
4. Open an event and see its details.
5. See where the event is located.
6. Open the original source.
7. View events geographically on a map.

The project will continue beyond this milestone. Features that are not necessary to prove the core concept are intentionally kept secondary.

---

# Current status

BACity is currently in **active development**.

The repository contains the foundations for the mobile application, API, database layer, and crawler. The system is being developed incrementally rather than attempting to build a production platform in one pass.

The current development focus is on connecting and hardening the complete event-discovery pipeline:

~~~
Crawler
   ↓
Real event data
   ↓
Database
   ↓
API
   ↓
Mobile application
   ↓
Search / Details / Map
~~~

There are still areas that need further implementation, integration, testing, and refinement. That is expected at this stage.

### What is intentionally still in progress

- Expanding and hardening the crawler across multiple real sources
- Improving extraction quality across different website structures
- Normalizing Slovak and English date/time formats
- Duplicate detection across sources
- Reliable geocoding and coordinate handling
- Keeping event data fresh
- Completing geographic event loading and map presentation
- Improving event images and visual enrichment
- Refining mobile browsing, search, details, and map interactions
- Improving loading, empty, and error states
- Testing the full crawler → API → mobile pipeline
- Hardening authentication and configuration where appropriate
- Establishing reliable automated development and testing workflows

The project is therefore best understood as a **working prototype under active construction**, not a finished application.

---

# Architecture

The planned architecture is intentionally straightforward.

~~~
                         PUBLIC WEB
                             │
                             ▼
                    ┌─────────────────┐
                    │      SCRAPY     │
                    │     CRAWLER     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ EVENT EXTRACTION│
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │  NORMALIZATION  │
                    │   VALIDATION    │
                    │   DEDUPLICATION │
                    │    GEOCODING    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   POSTGRESQL    │
                    │    + POSTGIS    │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │     FASTAPI     │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │   EXPO / RN     │
                    └────────┬────────┘
                             │
                 ┌───────────┼───────────┐
                 ▼           ▼           ▼
              Browse       Search       Map
                 │           │           │
                 └───────────┼───────────┘
                             ▼
                            User
~~~

The architecture is deliberately small. New infrastructure should be introduced only when the project actually needs it.

---

# Crawler

The crawler is one of the most important parts of BACity because the quality of the application depends directly on the quality of the event data.

The first crawler milestone is intentionally small:

~~~
ONE SOURCE
    ↓
REQUEST PAGE
    ↓
EXTRACT EVENTS
    ↓
NORMALIZE
    ↓
VALIDATE
    ↓
STRUCTURED DATA
~~~

Once that works reliably, additional sources can be added incrementally.

The long-term prototype target is approximately **5 to 10 real sources**, with different website structures so that the extraction pipeline is tested against more than one page format.

### Extraction strategy

The crawler should prefer structured information before falling back to increasingly generic techniques:

~~~
1. JSON-LD
2. Schema.org Event
3. Microdata
4. Structured HTML
5. Meta information
6. Source-specific parser
7. Generic heuristics
~~~

This keeps extraction deterministic and explainable.

The project should not depend on an LLM just to parse ordinary event pages.

### Event validation

An extracted event should not enter the database simply because some text looked event-like.

The minimum validation requirements are:

- A title exists
- A parseable date exists
- A location exists, or the event is explicitly online
- A source URL exists
- The resulting event data is structurally valid

Invalid records should be rejected rather than polluting the database.

### Normalization

Different websites describe the same concepts in different ways.

For example:

~~~
28 August 2026, 20:00
28/08/2026 20:00
Aug 28 @ 8 PM
28. 8. 2026 o 20:00
~~~

should ultimately become a consistent event timestamp.

The same principle applies to venue names, addresses, categories, prices, and other fields.

### Deduplication

The same event may appear on multiple websites.

The initial duplicate signals are intentionally simple:

~~~
Similar title
+
Same date/time
+
Same venue
~~~

This is sufficient for a prototype starting point. More sophisticated matching can be introduced if real data demonstrates that it is necessary.

### Geocoding

Where an event has an address but no coordinates:

~~~
Address
   ↓
Geocoder
   ↓
Latitude + Longitude
   ↓
PostGIS
~~~

Geocoding should be cached so that the same address is not repeatedly requested.

---

# Backend

The API is built with **FastAPI**, with PostgreSQL and PostGIS providing the primary data and geographic storage layer.

The API is responsible for exposing normalized event data to the mobile application rather than making the mobile client understand how individual websites work.

The intended core API surface includes:

~~~
GET /events
GET /events/{id}
GET /events/search
GET /events/nearby
~~~

Basic filtering can include concepts such as:

- Date
- Category
- Price
- Location
- Distance

Search starts with PostgreSQL rather than introducing a separate search platform prematurely.

---

# Geographic architecture

The map should not download every event in the city.

Instead, the mobile application should request events relevant to the currently visible geographic area:

~~~
Current Map Viewport
        ↓
Bounding Box
        ↓
FastAPI
        ↓
PostGIS
        ↓
Events inside viewport
        ↓
Map Markers
~~~

This keeps the mobile payload focused and establishes the correct architecture for future growth.

The map is not a separate data source. It is another presentation of the same event dataset.

---

# Mobile application

The mobile application is built with:

- React Native
- Expo
- TypeScript
- Expo Router

The intended product areas are:

~~~
Home
Explore
Map
Saved
~~~

The exact UI will continue to evolve while the underlying event pipeline becomes more reliable.

### Event discovery

The application should make it possible to:

- Browse upcoming events
- Search for events
- Filter by useful attributes
- Open event details
- See event location
- Open the original event source
- View events on a map

### Event details

A useful event detail screen should eventually provide:

~~~
Event image

Title
Date / time
Venue
Address
Category
Price

Description

[ View on Map ]
[ Open Source ]
~~~

The source URL is important. BACity aggregates discovery information, but the original event source remains the authoritative destination for the user.

### Saved events

Basic local saving is optional for the initial prototype.

A more complete account-backed saved-events system can be introduced later if it becomes useful.

---

# Database

The prototype database is intentionally small.

The core event data includes concepts such as:

~~~
id
title
description
start_time
end_time
venue
address
latitude
longitude
category
price
currency
image_url
source_url
source_name
created_at
updated_at
~~~

PostGIS provides the geographic capabilities required for nearby searches and viewport-based map queries.

A dedicated venue model can be introduced later if the real dataset justifies it. The prototype does not need a complicated venue-management system on day one.

---

# Technology decisions

The project intentionally avoids solving problems that do not exist yet.

### Playwright

Use Playwright when a target website genuinely requires JavaScript rendering.

Default:

~~~
HTTP request
~~~

Fallback:

~~~
Playwright
~~~

This keeps the crawler faster and lighter where JavaScript is unnecessary.

### PostgreSQL before OpenSearch

Search begins with PostgreSQL.

OpenSearch should only be introduced when real dataset size or search requirements demonstrate that PostgreSQL is no longer sufficient.

### Simple workers before unnecessary infrastructure

Background crawling will eventually need scheduling and reliable execution.

Infrastructure should be added when that requirement becomes real rather than because a particular technology happens to be available.

### No LLM dependency

The core crawler should remain functional without an LLM.

LLM-based extraction may be considered later as a fallback for genuinely difficult pages, but deterministic extraction remains the preferred first layer.

---

# Development roadmap

Development will continue in stages.

## Phase 1: Core data pipeline

~~~
Crawler
  ↓
Extraction
  ↓
Normalization
  ↓
Validation
  ↓
Database
~~~

The goal is reliable structured event data.

## Phase 2: Multiple sources

Expand from the initial source to approximately 5 to 10 real Bratislava sources.

The important objective is not simply collecting more URLs. It is proving that the extraction architecture can handle genuinely different website structures.

## Phase 3: API integration

Connect the normalized event database to FastAPI.

~~~
Database
   ↓
FastAPI
   ↓
Mobile client
~~~

## Phase 4: Mobile event discovery

Complete the primary user flow:

~~~
Open app
   ↓
Browse events
   ↓
Search / filter
   ↓
Open event
   ↓
View details
   ↓
Open source
~~~

## Phase 5: Geographic discovery

Complete:

~~~
Map
 ↓
Viewport query
 ↓
PostGIS
 ↓
Markers
 ↓
Event preview
 ↓
Event details
~~~

## Phase 6: Data quality and freshness

Once multiple sources are running, focus on:

- Duplicate control
- Event updates
- Stale event cleanup
- Better dates and times
- Better venues and addresses
- Better category inference
- Image extraction
- Geocoding reliability
- Crawl failure handling

## Phase 7: Background crawling

The desired long-term flow is:

~~~
User opens app
       ↓
Fresh event database
       ↑
Background crawler
       ↑
Scheduled source updates
~~~

The implementation can remain simple until scheduling and job volume justify additional infrastructure.

## Phase 8: Product refinement

After the core loop is reliable:

- Improve event cards
- Improve event details
- Improve map event previews
- Add better loading states
- Add empty states
- Add error states
- Improve filtering
- Improve saved events
- Improve navigation
- Improve visual consistency

## Phase 9: Security hardening

Authentication is not the reason BACity exists, but any authentication that remains in the application should eventually receive a proper security review.

That includes:

- Token handling
- Token storage
- Expiration and refresh behaviour
- Password handling
- Authorization boundaries
- Input validation
- Configuration and secrets
- Rate limiting where appropriate

Security hardening should support the product rather than delay the core event-discovery pipeline.

---

# Prototype definition of done

The core prototype is proven when this complete flow works:

~~~
Real event source
      ↓
Crawler
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
FastAPI
      ↓
Expo mobile app
      ↓
Browse / Search
      ↓
Event details
      ↓
Map marker
      ↓
Source link
~~~

The event should originate from an actual public source and should not require manual database insertion just to appear in the application.

---

# Minimum success criteria

The prototype should demonstrate:

- Real Bratislava event sources
- Automatic event extraction
- Structured and normalized event data
- PostgreSQL storage
- Geographic coordinates
- FastAPI access
- Mobile API consumption
- Event browsing
- Search
- Event details
- Map markers
- Source links
- Reasonable duplicate control

The most important metric is not the raw number of records.

> **Can BACity consistently discover useful, accurate events that a person in Bratislava would actually want to attend?**

A smaller dataset of reliable events is more valuable than a large dataset full of duplicates, stale records, or malformed dates.

---

# What is deliberately out of scope

The prototype is not trying to become a complete city platform yet.

The following are intentionally secondary or out of scope for the initial product thesis:

- Social networking
- Local guides
- Restaurant recommendations
- Public toilet discovery
- AI recommendations
- Machine-learning recommendations
- Multi-city support
- Large administration dashboards
- Complex analytics
- Premature search infrastructure
- Unnecessary distributed infrastructure
- Extensive account-management features
- Excessive visual polish before the core data loop works

These ideas may become useful later. They simply should not distract from proving event discovery first.

---

# Development principles

BACity is being developed around a few simple rules:

1. **Functionality before polish.**
2. **Data quality before raw event count.**
3. **Deterministic extraction before AI extraction.**
4. **Use Playwright only when a source actually requires JavaScript.**
5. **Use PostgreSQL search until real requirements justify something else.**
6. **Add infrastructure when the system needs it, not because it is available.**
7. **Keep the map viewport-based.**
8. **Build incrementally and test the complete pipeline.**
9. **Do not turn a prototype into a production platform prematurely.**
10. **Keep the core product thesis visible throughout development.**

The goal is not to build the largest possible system.

The goal is to build the smallest system that convincingly proves the idea, then improve it based on what the real data and real usage reveal.

---

# Local development

The repository is organized as a monorepo:

~~~
BACity/
├── apps/
│   └── mobile/
│
├── services/
│   ├── api/
│   └── crawler/
│
├── database/
├── docs/
├── docker-compose.yml
├── .env.example
└── README.md
~~~

### Mobile

From apps/mobile:

~~~
npm install
npm run typecheck
npx expo start
~~~

Android and iOS development builds can be run through the Expo native workflows when the local environment is configured.

### Backend and crawler

The API and crawler each have their own service directory and dependency configuration.

Local environment variables should be configured from the provided .env.example files rather than committed secrets.

For Android emulator development, the mobile API URL normally needs to point at the host machine rather than emulator localhost:

~~~
Android emulator → http://10.0.2.2:8000
iOS simulator   → http://localhost:8000
Physical device → http://<computer-lan-ip>:8000
~~~

The exact local setup may evolve as the development environment is standardized.

---

# Repository structure

A simplified view:

~~~
BACity/
│
├── apps/
│   └── mobile/          # Expo / React Native application
│
├── services/
│   ├── api/             # FastAPI backend
│   └── crawler/         # Scrapy event ingestion
│
├── database/            # Database-related files and migrations
│
├── docs/                # Project and prototype documentation
│
├── docker-compose.yml   # Local service orchestration
│
└── README.md            # Project documentation
~~~

As development continues, individual services may gain additional modules, tests, parsers, migrations, and configuration. The overall architecture should remain understandable.

---

# Why the project is still a work in progress

BACity is intentionally being built as a prototype first.

There are several hard problems hidden inside what initially sounds like a simple application:

- Websites do not expose event data consistently.
- Dates and times appear in many formats.
- The same event can exist on several sources.
- Event pages can change or disappear.
- Some websites require JavaScript rendering.
- Addresses need reliable geographic coordinates.
- Event data becomes stale.
- Mobile map queries need to remain efficient.
- The API and crawler need to agree on a stable event model.
- The UI needs to remain useful even when scraped data is incomplete.

These are normal engineering problems for this type of system.

The project will therefore continue through multiple iterations rather than pretending that the first working build is the final product.

---

# Long-term direction

The long-term direction is a simple user experience backed by a much more interesting data pipeline:

~~~
Many public event sources
          ↓
Reliable ingestion
          ↓
Clean event dataset
          ↓
Fast geographic/search API
          ↓
Simple mobile experience
          ↓
Useful local discovery
~~~

The complexity should live where it provides value: collecting, cleaning, updating, and serving useful event information.

The user should not have to care which website originally published an event.

---

# Project status

**BACity is actively under development.**

The foundation is being built now, and development will continue through crawler expansion, API integration, mobile refinement, geographic discovery, data-quality improvements, automated freshness, and eventual product hardening.

There will be unfinished features, changing implementation details, and temporary prototype decisions along the way. That is intentional.

The immediate objective is to keep tightening the core loop:

~~~
Discover
   ↓
Extract
   ↓
Normalize
   ↓
Store
   ↓
Serve
   ↓
Search
   ↓
View
   ↓
Map
~~~

Once that loop is dependable, the rest of BACity becomes an engineering and product refinement problem rather than an unanswered prototype question.

---

## License

This project is currently under active development. Licensing and distribution terms may be finalized as the project progresses.
