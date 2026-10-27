# Instagram acquisition feasibility — 25 October 2026

## A. Acquisition verdict

**Actual Instagram posts retrieved: 0. No new Instagram-sourced event was proved.**

The acquisition gate did not pass. This is a partial feasibility result, not an
Instagram collector implementation and not proof that Instagram is universally
inaccessible. Neither a free, permitted collection route nor repeatable retrieval
was demonstrated in BACity's present configuration.

| Route | Fresh result |
|---|---|
| Official API | Offline check found no known app/token/account configuration. Zero authenticated requests. Grants and app eligibility remain unverified. |
| Logged-out Instagram content | Zero profile/post requests. Current terms/robots retrieval was restricted in the documentation reader, with no evidence of collection permission. Stopped before content collection; no retries or alternative identity. |
| Website account discovery | Works: four distinct declared Instagram profile candidates from eight existing BACity source websites considered. This is not Instagram acquisition. |
| Fixture event extraction | Not implemented or run. The existing 33 Instagram foundation tests use synthetic **website links**, not Instagram captions/posts. |

Recommendation: **option 3 — retain the small disabled foundation and stop
Instagram expansion while permitted acquisition remains unproven.**

## B. Live Instagram results

| Counter | Exact result |
|---|---:|
| Existing source websites considered | 8: seven active and one deferred |
| Website pages successfully returned | 6 |
| Website failures | 2 |
| Instagram account candidates considered | 4 |
| Instagram accounts tested by API/profile/post request | 0 |
| Accessible Instagram accounts demonstrated | 0; all four remain untested |
| Real Instagram posts / captions / media references | 0 / 0 / 0 |
| Usable upcoming Bratislava announcements from Instagram | 0 |

The documentation reader reported HTTP 429 for Instagram's terms and robots
URLs. These are policy-document retrieval observations, **not tests of the four
accounts**, nor independently captured raw-origin responses. No robots directives
were obtained; this report does not claim a confirmed `Disallow` rule. No Python
request to Instagram was made after those restrictions. HTTP 200 website pages
were not counted as successful Instagram access.

Fresh candidate provenance, produced by the existing `discover_profiles` and
`record_profiles` functions in a temporary private registry:

| Declared profile candidate | Website evidence | Interpretation |
|---|---|---|
| `novacvernovka` | https://novacvernovka.eu/program | Existing Bratislava community/cultural venue source; priority 88 |
| `staratrznica` | https://staratrznica.sk/sk/program | Existing Bratislava market/event venue source; priority 85 |
| `visitbratislava` | https://www.visitbratislava.com/events/ | Existing tourism/event source; priority 90 |
| `gooutcz` | https://goout.net/en/bratislava/events/ | Platform-wide account declared on its Bratislava page; priority 75. Not established as Bratislava-specific. |

Each normalized profile is `https://www.instagram.com/<handle>/`. Website links
establish declaration provenance, not verified Instagram existence, ownership,
professional account status, public accessibility or collection consent.

The sample is smaller than the requested 5–10 and lacks separately verified
nightclub/promoter accounts. It was not expanded through guessed handles.
Karloveské centrum kultúry's root returned no eligible profile link. The deferred
Slovak National Theatre page was fetched, but is not an eligible registered active
source in the foundation; no lead from it was admitted. Bratislava City's page
failed with `NoRouteError`, and the SNG page with `gaierror`. No workarounds or
extra website discovery graph were added.

Raw observations, normalized publisher evidence and measurements are in the
private artifact directory identified below. Website bodies were processed in
memory and not retained.

## C. Event discovery results

| Instagram-derived result | Count/status |
|---|---|
| Event-like announcements obtained | 0 |
| Verified upcoming Bratislava events | 0 |
| Events already in BACity | 0 classified; comparison not run |
| Potentially exclusive new events | 0 |
| Ambiguous/unverified event candidates | 0 |

There are four unverified **publisher** candidates, not four event candidates.
No extraction, relative-date inference, poster OCR, geolocation, canonical lookup
or identity ingestion was run. No absent-from-baseline or exclusivity claim is
made. Without real posts, a matching implementation or invented event fixture
would not resolve the sprint's main uncertainty.

## D. Technical implementation and existing-work audit

Initial branch: `crawl-L4-social`; initial HEAD:
`8e3dabc3a596e9131aae677ca68a59052aee7334`; initial working tree: clean.
The previous foundation is already committed in this HEAD. Its older report's
statement that its files are uncommitted is historical and no longer current.

| Existing component | Implemented behavior | Not implemented |
|---|---|---|
| `services/crawler/crawler/instagram_discovery.py` | Canonical profile normalization, bounded link extraction from eligible website responses, idempotent private SQLite publisher records with bounded provenance | Stable authorized platform IDs; collection history, scheduling, access-grant changes, cursors, posts |
| `services/crawler/crawler/spiders/discovery.py` | Isolated opt-in observation hook on already fetched website responses | Instagram network access or a separate worker |
| `.env.example` | `L4_INSTAGRAM_DISCOVERY_ENABLED=0` | Enabling content collection |
| `services/crawler/tests/test_instagram_discovery.py` | 33 foundation tests: normalization, separate accounts, source eligibility, bounds, rollback, disabled behavior, failure isolation and original spider outputs | Live post retrieval or social event extraction |

The existing registry's `access_eligibility` and `last_collection_status` CHECK
constraints allow only `authorization_required` and `not_attempted`. It is a
lead registry, not a functioning acquisition frontier. It must not be portrayed
as already supporting successful collection/checkpoint replay.

**Only new repository file in this sprint:**
`docs/instagram-acquisition-feasibility-2026-10-25.md` (this report).
No existing repository file was modified. No production adapter, scheduler,
staging table, dependency, migration, LLM, OCR stack, API integration or public
write path was added. Website crawlers, mobile/map code, canonical IDs and
lifecycle behavior remain unchanged. `FINAL-UX` was not checked out or modified.

Development artifacts outside the repository:

`/Users/s3eed/.codex/.chatgpt-projects/g-p-6a94b492f5088191920f3f48c7c9c29f/outputs/instagram-feasibility-2026-10-25/`

- `eligibility_check.py`, `eligibility-results.json`, `eligibility-check.log`:
  repeatable offline presence check; known variable names/booleans only, no
  credentials or authentication. Checks process environment and existing root
  and mobile `.env` files; crawler/API `.env` files were absent. No matching
  configuration was present. This cannot establish whether an unconfigured Meta
  app exists elsewhere or verify any authorization.
- `website_probe.py`, `probe-results.json`, `website-probe.log`: bounded,
  development-only reuse of the existing discovery foundation and public-network
  middleware. One concurrent request, one per domain, retries disabled, 24-request
  ceiling, ten-second request timeout, two-MiB response cap, two redirects and
  55-second crawl ceiling; robots enforcement retained. No event extraction or
  item pipelines, browser handlers, API requests or publication queue delivery.
- `live-evidence.json`: separate acquisition counters, documentation restrictions
  and decision record; no simulated post objects.
- `crawler-tests.log`, `api-tests.log`: fresh regression results.

The probe's operational SQLite database was temporary and removed automatically.
Only small JSON/log artifacts remain. It did not open or mutate the actual worker
state, canonical database or production API. No social staging exists because
there are no posts to stage. Existing private lead recording is idempotent;
post-level change detection, checkpoints, partial collection and suspension are
explicitly unimplemented, rather than claimed through fabricated fixtures.

## E. Resource measurements

Measured for the fresh website-only Python/Scrapy probe, not Instagram collection:

| Measurement | Result |
|---|---:|
| Wall time | 30.627 s |
| Process CPU time after imports/startup | 0.299 s |
| Peak process RSS, including Scrapy | 84,623,360 bytes; 80.70 MiB |
| Scrapy downloader requests | 14; includes robots and failed attempts |
| Downloader response count | 12; six source pages plus policy responses |
| Downloader exception count | 3; includes a robots-fetch failure |
| Scrapy request bytes | 4,149 |
| Scrapy response bytes | 94,632; excludes TLS overhead |
| Decoded successful page bodies | 427,483 bytes |
| Temporary state including WAL | 242,896 bytes; removed after probe |
| Public event outbox records | 0 |
| Instagram API/profile/post requests from Python | 0 |

Documentation/search-tool bandwidth, CPU and memory are not exposed and are not
included. No Instagram throughput, extraction accuracy or deployment performance
was measured. Artifacts before this Markdown report totalled 53,025 bytes;
these are evidence files, not a retained media archive.

## F. Platform access and legal limitations

### Official API: confirmed setup and unresolved requirements

The retrieved/cached **Meta-owned** collection documents professional-account
integration, an app and authorized token. It describes Facebook Login with a
linked professional-account Page and Instagram Login without that Page
requirement. The former describes hashtagged media and metadata about other
professional accounts; neither statement proves BACity's arbitrary publisher
acquisition is authorized. [Meta's Facebook Login collection](https://www.postman.com/meta/instagram/folder/u4g5a2a/instagram-api-with-facebook-login),
[Instagram Login collection](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login).

Concrete setup still needed:

1. Create/configure a Meta developer app for the permitted Instagram use case;
   select a supported API version and login product.
2. Obtain organizer authorization for a business/creator account. With Facebook
   Login, link its Facebook Page and authorize the appropriate Page role.
3. For Instagram Login, the collection identifies `instagram_business_basic`.
   For Facebook Login, it lists `instagram_basic`, `pages_show_list` and
   `pages_read_engagement` among its permissions. These are **not a freshly
   validated minimum grant set for Business Discovery/hashtags**. Its publishing
   and comment-management scopes are unnecessary for this read-only proof and
   should not be requested merely because the larger collection lists them.
4. Verify the exact app-review/Advanced Access/business-verification and
   Instagram Public Content Access requirements for BACity's intended external
   publisher discovery in the current dashboard. No such approval was verified.
5. Verify current Business Discovery username targeting, allowed media fields,
   attribution, hashtag-ID endpoint and whether `recent_media`/`top_media` are
   presently supported for the approved use case. Obtain a real response before
   implementing against remembered examples.
6. Verify live request/hashtag quotas, response usage headers, pagination and
   token expiry. The collection describes cursor pagination; that does not prove
   incremental post collection. No historic numeric quota or fixed Graph version
   is asserted as current.
7. Establish permitted media processing, storage purpose, attribution, retention,
   deletion/revocation handling and token protection before persisting posts or
   downloading posters. No blanket media licence or retention duration was
   established.

Business Discovery and hashtag documentation URLs returned 429 in the reader.
The exact current feature-specific requirements, fields, limits, review rules
and retention obligations therefore remain **unresolved**, not silently inferred
from older documentation or third-party implementation guides. No authenticated
eligibility test was possible without configuration. Broad account search and
consumer-account access are not demonstrated.

### Logged-out investigation and EU processing

Meta's primary statements describe automated collection as permission-dependent,
including an Instagram public-profile enforcement example. They do not grant
BACity collection rights. Current detailed terms could not be retrieved; no
written permission was found in the checked configuration. This combination and
the policy-fetch restrictions prevent a permitted collection proof here.
[Meta on scraping](https://about.fb.com/news/2021/04/how-we-combat-scraping/),
[Instagram enforcement example](https://about.fb.com/news/2020/11/combating-clone-sites/).

Technical reachability, robots permission, platform authorization, copyright and
GDPR lawfulness are separate questions. Under the European Commission's guidance,
personal-data processing needs an applicable legal basis; public availability
alone does not establish one. BACity would need purpose limitation, necessity,
minimization, appropriate transparency and rights/deletion handling. A claimed
legitimate interest requires its own assessment. CNIL's scraping guidance also
calls for honoring opposition mechanisms; that guidance is framed around AI
training and is not a legal authorization for BACity's event service.
[European Commission](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/legal-grounds-processing-data_en),
[CNIL guidance](https://cnil.fr/en/legal-basis-legitimate-interest-focus-sheet-measures-implement-case-data-collection-web-scraping).

No reliance was placed on Meta v. Bright Data as a general permission. No login
cookies, bot account, authentication spoofing, private endpoints, proxy, CAPTCHA
bypass, browser farm, paid service or fingerprint evasion was used. No post
images, comments, follower lists or private content were collected. Poster OCR
was not attempted because no permitted image was available.

## G. Tests

Run from `/Users/s3eed/Documents/GitHub/BACity/BACity-/services/crawler`:

```sh
DATABASE_URL=sqlite:////tmp/bacity-l4-sprint-tests/crawler-import.db CRAWLER_STATE_PATH=/tmp/bacity-l4-sprint-tests/crawler-state.db ../../.venv/bin/python -m pytest tests -q
```

**204 passed in 7.79 s**, including the 33 existing Instagram foundation tests
and disposable HTTP→Scrapy→queue→API integration fixtures. Their fixture event
writes are isolated test activity, not social acquisition or production writes.

Run from `/Users/s3eed/Documents/GitHub/BACity/BACity-/services/api`:

```sh
DATABASE_URL=sqlite:////tmp/bacity-l4-sprint-tests/api-import.db CRAWLER_STATE_PATH=/tmp/bacity-l4-sprint-tests/api-crawler-state.db ../../.venv/bin/python -m pytest tests/test_event_identity.py tests/test_event_maintenance_lifecycle.py tests/test_ingestion.py tests/test_crawler_v2.py tests/test_level3_discovery.py tests/test_adversarial_security.py -q
```

**113 passed in 21.06 s**, with 2,981 existing deprecation warnings. API tests use
their own disposable SQLite fixture database; import-time/worker paths also point
to scratch storage. These are relevant regressions, not the full API suite or
PostgreSQL/PostGIS integration verification.

No post collector/extractor was implemented, so API 401/403/429 parsing, login-wall
recognition, edited-post hashing, post-ID replay, date/DST extraction, multi-event
posts and shadow matching have no new implementation coverage. This is an honest
coverage gap behind the failed acquisition gate, not a fixture-based success.
`git diff --check` passes; no mobile tests were required for a documentation-only
repository change.

## H. Next recommended action

**Choose 3: retain the small disabled foundation and stop Instagram expansion
because permitted acquisition remains unproven.**

A justified next experiment would require current approved API requirements and
one willing professional organizer's authorization, then a small real read on
two separate runs. Do not assume that creating an app guarantees approval,
Business Discovery access or novelty. Do not expand schemas, crawling, OCR or AI
until actual permitted posts cross the acquisition gate. Only then extract and
compare candidates through a read-only canonical query path.

## I. Git safety

Branch and HEAD remain `crawl-L4-social` at
`8e3dabc3a596e9131aae677ca68a59052aee7334`.
Initial working tree was clean. Final change: this untracked Markdown report only;
all prior foundation and map files are untouched. Evidence scripts/results live
outside the Git checkout.

No commit, push, merge, rebase, reset, clean, branch switch or deployment in this
sprint. No production data mutation and zero public social-event writes.
The earlier map commit predates this request and is not a sprint action.
