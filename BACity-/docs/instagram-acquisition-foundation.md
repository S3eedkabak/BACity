# Instagram acquisition: smallest discovery foundation

22 October 2026; branch `crawl-L4-social`; base revision
`952288bad1967dd49978a1d23f5f4bbc09d0faea`.

Labels: **Repository** = inspected implementation; **Experiment** = bounded live
probe/tests; **Documentation** = current official publisher material retrieved;
**Recommendation** = next step; **Unverified** = not established.

## A. Instagram acquisition verdict

**Experiment / user-confirmed prerequisite:** no working Instagram-content
acquisition path has been proved. BACity has no Meta developer app or authorized
Instagram professional account yet. No authenticated Instagram calls were made.
No anonymous Instagram scraping, private API, login workaround or paid service
was introduced. There is deliberately no content adapter in this change.

**Documentation:** Meta's official Instagram collection describes two professional
account products. Instagram Login supports business/creator account integrations
without requiring a linked Facebook Page, and lists `instagram_business_basic`.
Facebook Login requires a professional account linked to a Page; its collection
describes media access, hashtagged media and other professional-account metadata,
excluding consumer accounts. These are conditional integration routes, not proof
BACity qualifies or can collect arbitrary accounts.

Sources: [Meta Instagram Login collection](https://www.postman.com/meta/instagram/folder/6raa77c/instagram-api-with-instagram-login),
[Meta Facebook Login collection](https://www.postman.com/meta/instagram/documentation/6yqw8pt/instagram-api?entity=request-23987686-1ff01566-3509-48bd-a0f4-8571a91ccfdf).

**Unverified:** current exact Business Discovery target scope, hashtag quotas,
caption/media field permissions, app-review requirements for BACity's intended
use, general public account search, media processing rights, retention/deletion
rules, token lifetime and rate limits. Relevant Meta developer pages returned 429
to the documentation reader. The accessible collection is insufficient to assert
all these details. No remembered historical numeric quota was used.

| Method | Verdict for this phase |
|---|---|
| Authorized professional account, Instagram Login | Conditional; app, professional account and valid authorization are missing. Confirm current read scopes, allowed purpose and media/retention rules before implementing calls. |
| Professional account via Facebook Login | Conditional; linked Page and app/token prerequisites missing; no real read performed. This is an Instagram API route, not expansion into Facebook event collection. |
| Business Discovery / hashtags | Current broad capability is described in Meta's collection; exact endpoint eligibility and current quotas remain unverified. No discovery or post acquisition call performed. |
| oEmbed or other free content mechanisms | Not proved usable for this workload. No current caption/poster-processing entitlement verified. |
| Anonymous scraping / unofficial APIs / sessions | Excluded by scope; not an authorization substitute. |
| Declared website profile links | Working account-candidate discovery only; **not Instagram content acquisition**. |

**Recommendation:** keep all content collection disabled until a permitted route
retrieves real posts repeatedly. The foundation itself has no subscription or
hosted-service dependency. No claim of free production Instagram access is made.

## B. Actual Instagram evidence

**Experiment:** Instagram posts retrieved: **0**. There are no acquired captions,
post IDs or poster/media samples to show. Website HTML was used only to identify
declared account candidates, not to claim Instagram events.

## C. Autonomous account discovery

**Experiment:** two distinct account candidates emerged from two existing
registered BACity venue/community websites, without a hardcoded account list:

| Candidate profile | Actual declaration evidence | Registry state |
|---|---|---|
| `https://www.instagram.com/novacvernovka/` | [Nová Cvernovka program](https://novacvernovka.eu/program) | `authorization_required`, `not_attempted`; priority 88 |
| `https://www.instagram.com/staratrznica/` | [Stará Tržnica program](https://staratrznica.sk/sk/program) | `authorization_required`, `not_attempted`; priority 85 |

The probe did not request Instagram, so account existence, current ownership,
professional status, content accessibility and grants have not been independently
verified. Bratislava relevance comes from BACity's existing registered website
evidence; it does not prove every future post concerns Bratislava.

**Repository:** the opt-in hook reads only website responses already fetched by
`DiscoverySpider`, under existing public-address/redirect/robots/rate policies.
It accepts existing registered sources or probation/trusted candidates with at
least one qualified local observation; cross-domain response evidence is rejected.
It does not follow profile links, discover followers or enumerate Instagram.

Normalized exact profile URLs provide provisional identities until an authorized
stable platform ID is available. Case, host aliases and tracking parameters do
not create extra publishers; post/reel/story/system routes and deceptive hosts
are rejected. Two accounts on `instagram.com` remain distinct.

The single private SQLite table `instagram_publishers` stores profile URL/handle,
first/last seen, source-based priority, bounded website relationship/provenance,
access eligibility and collection status. It reuses existing crawler operational
storage, not the canonical PostgreSQL database or domain-based Source registry.
No stable account ID is invented. Priorities reflect website reliability, not
Instagram account authorization or verified account trust.

## D. Extraction results — separate product counters

**Experiment:**

| Counter | Result |
|---|---:|
| Instagram account candidates discovered | 2 |
| Accounts authorized for content collection | 0 |
| Actual Instagram posts retrieved | 0 |
| Real event candidates extracted from those posts | 0 |
| New verified Bratislava events found | 0 |
| Posts identified as requiring OCR | 0; no posts available to evaluate |
| Existing-vs-new canonical matches | Not evaluated; no post candidates |
| Date/venue/identity conflicts | Not evaluated; no post candidates |

No extraction, OCR, local model or canonical matching implementation was added.
With no real acquired content or cleared sample corpus, these would expand the
framework before proving the main acquisition prerequisite. Website events are
not substituted into any of the Instagram counters.

## E. Implementation and tests

**Repository:** exact files changed:

- Added `services/crawler/crawler/instagram_discovery.py`: `profile_url`, immutable
  `ProfileLead`, `discover_profiles`, and idempotent `record_profiles`.
- Modified `services/crawler/crawler/spiders/discovery.py`: an isolated optional
  `_observe_instagram_profiles` hook. Existing extraction/navigation still run.
- Modified `.env.example`: `L4_INSTAGRAM_DISCOVERY_ENABLED=0`.
- Added `services/crawler/tests/test_instagram_discovery.py`: synthetic website
  fixtures; these are not represented as real Instagram posts.
- Added this report under `docs/`.

Paths above are relative to `BACity-/` within the repository. No dependencies,
API routes/models, PostgreSQL migrations, mobile/map code, public event contracts
or scheduler were added/changed.

**Experiment:** new tests cover identity normalization, distinct accounts,
unsafe/post/system URLs, exact provenance, duplicate/repeated discovery, qualified
local-source eligibility, evidence/profile caps, transaction rollback, disabled
behavior without opening state, feature-failure isolation, no network calls or
public delivery queue changes, and preservation of existing parse results.
The full crawler suite also exercises existing worker, lifecycle, security and
HTTP→crawler→API regressions using disposable test data.

Final validation: **33 new discovery tests; 204 crawler tests passed in 7.45s**
(including those 33). `git diff --check` passed. No API-only or mobile suite was
rerun; this change does not modify those components.

**Deferred explicitly:** API errors/rate limits and incremental cursors for an
Instagram collector; caption-relative dates, poster-only or multi-event posts,
cross-post/event deduplication and canonical comparison. No collector/extractor
exists yet, so fabricated success tests for those paths would be misleading.

## F. Resource measurements and operating limits

**Experiment:** a separate scratch probe used the existing Scrapy settings and
`PublicNetworkMiddleware`, disabled all item pipelines/browser handlers, limited
requests and time, and used temporary state. It made four requests (two robots
and two website pages), never requested Instagram or BACity's API, and left the
public event outbox empty. Temporary state was removed afterward.

| Measurement | Result |
|---|---:|
| Probe wall time | 2.421 seconds |
| Measured probe CPU time | 0.090 seconds |
| Peak process RSS including Scrapy | 84,967,424 bytes (~81.0 MiB) |
| Scrapy HTTP response-byte counter | 35,396 bytes; includes HTTP headers/compressed bodies, excludes TLS overhead |
| Decoded website page bodies | 121,090 bytes combined |
| Scratch state including WAL | 226,416 bytes (~221 KiB), including the existing State schema |
| Additional scheduled network requests from hook | 0 by construction |

These are one local probe's measurements, not target-host performance guarantees.
CPU timing excludes interpreter/import startup. The RSS and scratch state numbers
are whole-process/whole-state measurements, not incremental registry overhead.

**Repository:** hard caps are 250 profiles, ten profiles/page, four provenance
entries/profile, 2 MiB input HTML and 2,000 inspected anchor attributes/page.
Identical discoveries refresh last-seen without multiplying records/evidence.
At capacity, new profiles are ignored; existing profiles can still refresh.
There is no raw HTML/media storage or post/extraction cache because none is
acquired. No background service, extra scheduler, video download, OCR or LLM.

Optional failures are isolated from L1–L3 and recorded as
`instagram/discovery_errors`; diagnostics omit exception details/page content.
`instagram/accounts_discovered` counts new private registry rows;
`instagram/profile_links_observed` counts bounded linked profiles, including
repeated observations. Neither is an event metric.

**Repository:** discovery is off by default. To enable the website-link hook in
the existing crawler configuration, set `L4_INSTAGRAM_DISCOVERY_ENABLED=1`.
That switch does not enable Instagram requests or public social-event writes.
Setting it back to `0` stops new lead recording without altering existing event
data. Existing Instagram network exclusions remain enforced even when enabled.

## G. Remaining acquisition blocker

**User-confirmed / Unverified:** there is no Meta app or organizer authorization.
The exact current approved API purpose, scopes and media/retention terms must be
verified for BACity. Account candidates cannot confer those permissions.

No method has yet satisfied the product success condition: repeatable,
authorized, zero-subscription-cost acquisition of genuinely new Bratislava event
announcements from Instagram content.

## H. Recommended next milestone

**Recommendation:** establish a Meta developer app and authorize one willing
Bratislava organizer's professional account. Confirm the current read scope,
test-account access versus external-organizer review requirements, retention and
poster-processing permissions. Then retrieve a small real media/caption batch
on two separated scheduled checks, recording actual fields, limits and rights.

Only after that proof, implement one bounded Instagram adapter and post-based
shadow extraction. Keep public publication disabled. Prioritize a real sample
and comparison with known BACity events over expanding the registry or database.
Creating a developer app alone does not establish arbitrary-account discovery
or a right to process images.

## I. Git and validation status

**Experiment:** branch remains `crawl-L4-social`; no commit, push, merge, deploy,
branch switch or production-data modification. All changes above are uncommitted.
No prior uncommitted changes existed at the start. Validation results are recorded
in E; no historical test count is presented as a fresh run.

The reproducible scratch probe and its JSON results are artifacts outside the
repository, under the chat project's `outputs/instagram-foundation/` directory.
