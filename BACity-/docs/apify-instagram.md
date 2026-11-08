# Official Apify Instagram integration

Implementation report, 2026-10-27. Selected Actor: **apify/instagram-scraper**. Work remains uncommitted on `crawl-L4-social`; HEAD remains `8e3dabc3a596e9131aae677ca68a59052aee7334`. No deployment, push or live Actor acquisition was performed. Existing Level 4/ScrapingAnt work and historical reports are preserved. The incremental file list is in `apify-instagram-files.txt`.

## Architecture

The existing private publisher registry, approval/access review, shared scheduler, worker gateway, observation staging, caption extraction, candidate review and publication relay are reused. No consumer mobile, public API, canonical event ingestion or crawler Levels 1–3 code changes are required.

The isolated collector calls a narrow Apify transport, and the existing staging gateway owns durable run state and a separate USD ledger. Only the collector receives `APIFY_API_TOKEN`; staff and gateway receive a presence hint. The browser subprocess environment excludes provider tokens, worker credentials and database credentials. API egress permits only `api.apify.com:443` in addition to existing destinations. Requests use Authorization headers, fixed paths, no redirects, bounded responses and sanitized errors. No Instagram credentials, CAPTCHA solving or fallback provider calls are used.

Migration **0026** adds `l4_apify_budget`, `l4_apify_runs`, persistent provider-independent `l4_instagram_items` dedup metadata, publisher limits/checkpoints and a collection-job run link. These are provider/staging metadata, not a separate event system. Terminal dataset-caption copies expire through the existing retention worker on the raw-observation schedule; run IDs, costs and caption-free dedup hashes remain. Downgrade deliberately retains evidence. Reapply the existing role-grants script after migration; public runtime access remains denied.

New observations enter existing caption parsing and candidate staging. Missing fields remain uncertain; publishing still requires the existing review/relay and publication flags. The inspected starting stack has **no working poster OCR pipeline**. This extension retains up to three safe image/thumbnail references; it does not implement OCR, download full videos, or infer events from images. This is a remaining functional limitation for poster-only announcements.

## Verified documentation and schemas

Public documentation and metadata were read; no Actor was started and no Instagram profile was retrieved. Actor identity is `shu8hvrXbJbY3Eb9W`; the observed latest build was `0.0.831`. Runtime preflight verifies identity, current pricing and the latest build, then pins that build for the run. Sources: [selected Actor](https://apify.com/apify/instagram-scraper), [public Actor metadata](https://api.apify.com/v2/acts/apify~instagram-scraper), [generated build schema](https://api.apify.com/v2/acts/apify~instagram-scraper/builds/default/openapi.json).

The generated input schema supports `directUrls`, `resultsType=posts`, `resultsLimit` per URL, `addParentData` and `onlyPostsNewerThan`. Profiles with the same limit share a run; different 1–2 limits form separate bounded batches. Search, comments, Stories, analytics and history modes are not requested. The Actor README documents `skipPinnedPosts=true`, but the generated input schema currently omits it. The adapter sends the README parameter; its effectiveness remains **unverified live**. See [input schema](https://apify.com/apify/instagram-scraper/input-schema) and [README](https://apify.com/apify/instagram-scraper).

Output normalization requires an approved owner username, stable shortcode/post URL and trustworthy timestamp. `Image`, `Sidecar` and `Video` records are accepted; `productType=clips` or a Reel URL distinguishes Reels. Carousel thumbnails are bounded. Wrong-owner, malformed and irrelevant records fail closed; dataset order never determines publisher attribution. Raw engagement/comment/video fields are discarded. See [output schema](https://apify.com/apify/instagram-scraper/output-schema).

**Coverage:** one posts-feed request is used. Reels returned in that feed are normalized, but the Actor separately exposes a Reels mode. Complete combined feed/Reels coverage and the independently newest Instagram item have not been verified. The adapter selects newest trustworthy timestamps only within returned eligible records; it never silently launches a second Reels run. The panel and live probe disclose this limitation. Pinned records explicitly flagged and older than 24 hours are skipped, as are records older than the publisher checkpoint. A one-second checkpoint overlap plus persistent shortcode/content-hash dedup prevents repeated staging. Missing pin flags, changing Actor behavior, multiple announcements between daily checks, truncated captions and feed omissions remain coverage risks.

## Pricing and strict local budget

Current Actor metadata reports PAY_PER_EVENT, a Free-tier `result` price of **$0.0027**, and no separate startup event in the current pricing record. An explicit future `actor-start` event is supported; unknown charge events or pricing models block acquisition. The advertised lowest price is not necessarily the Free-tier price. [Actor pricing](https://apify.com/apify/instagram-scraper/pricing), [current machine-readable prices](https://api.apify.com/v2/acts/apify~instagram-scraper).

The Free plan currently includes **$5 recurring monthly prepaid usage**. Account billing-cycle boundaries and current total usage come from `/users/me/limits`; the ledger does not assume calendar months. Provider-reported terminal `usageTotalUsd` is reconciled, and failures/empty runs are never assumed free. [Plan pricing](https://apify.com/pricing), [billing](https://docs.apify.com/account/billing), [account limits API](https://docs.apify.com/api/v2/users-me-limits-get), [run accounting](https://docs.apify.com/api/v2/actor-run-get).

Money is stored as integer micro-USD. The effective ceiling is the minimum of configured $4, $5 minus the configured reserve, and account limit minus reserve. PostgreSQL row locks serialize reservation and dispatch. Before every launch, fresh account usage/pricing must be verified. An atomic reservation includes all requested results, 10% result-price margin, documented startup charge if any, $0.001 charge-cap margin, and **$0.005 local API/storage uncertainty per run**. Reservations must fit before dispatch. No launches are permitted within ten minutes of the billing-cycle end. Unknown or pending charges prevent an unsafe period reset.

Actor parameters include a 300-second timeout, 1024 MB memory, pinned build, `restartOnError=false` and provider-side `maxTotalChargeUsd`. The current [Run Actor API](https://docs.apify.com/api/v2/actors-runs-post) documents this charge cap. Terminal local accounting retains the maximum of reported run cost and dataset result-price floor, plus the $0.005 uncertainty allowance. Unknown launches retain their full reservation as estimated spend; undispatched cancellations release it. Over-cap provider charges suspend new launches. Accounted spend uses the higher of local charges and provider usage plus charges since sync; ScrapingAnt credit accounting stays separate.

For illustration only, 600 results at today's result price equal $1.62 **before** run/API/storage uncertainty, retries, price changes or other account use. This is not a monthly cost guarantee. Provider caps, delayed usage reporting, charge granularity, external account activity and platform costs can exceed local assumptions. BACity never upgrades plans or intentionally exceeds its ceiling. Use a dedicated Free account, keep paid upgrades disabled, and set the provider account's monthly usage limit no higher than $5. The local ledger cannot guarantee external billing. Ordinary monitoring pauses when costs cannot be estimated or the reserve cannot be maintained.

## Scheduling and recovery

Maximum combined active Instagram profiles: **20**, across Apify and ScrapingAnt. Each publisher has one explicit method; switching providers does not reset last-attempt/daily limits. Default is one result every 24 hours, optionally 2–3 via the existing proposal form. Manual test/retry uses the same schedule, approval, permission and budget guards. No automatic increases and no automatic fallback.

The existing scheduler/coordination and collection jobs are reused. Due profiles of equal limit are batched, with one open Apify batch globally. PostgreSQL locks and durable job/run identifiers prevent overlapping claims. Run IDs, dataset IDs, page offsets, build, reservation, normalized partial results and terminal accounting persist across restarts. A new process waits out the previous 90-second lease, then resumes known-run polling or dataset pagination. Acknowledged pages are not downloaded again.

There is no documented Actor-run idempotency parameter: dispatch intent is committed before the single billable POST. If the launch acknowledgement is lost, the batch becomes `launch_uncertain`, is not automatically resubmitted and retains its full estimated charge. Review that state against Apify Console before further operator action; there is no unsafe automated replay. Transient known-run failures defer polling with Retry-After; access restrictions suspend the publisher. Failed batches are not counted as successful profile checks. A successful zero-item dataset is recorded as empty with `no_items_unverified`, without advancing last-success or claiming access was verified.

Disabling collection/provider or emergency stopping prevents new launches and staging; existing identified remote runs can still be aborted and reconciled through a key-authenticated cleanup path. Removing the token or taking the collector offline prevents remote cleanup, so retain it until pending runs settle. All control-plane flags, RBAC, CSRF, WebAuthn and network boundaries remain in force.

## Owner configuration

Use the existing private control-center environment file, owned by the operator and mode 0600, outside Git. Never put a token in a frontend file, URL or panel. These are the exact new settings:

```dotenv
APIFY_ENABLED=false
APIFY_API_TOKEN=
APIFY_INSTAGRAM_ACTOR_ID=apify/instagram-scraper
APIFY_MONTHLY_BUDGET_USD=4.00
APIFY_MONTHLY_RESERVE_USD=1.00
APIFY_MAX_ACTIVE_PROFILES=20
APIFY_DEFAULT_POSTS_PER_PROFILE=1
APIFY_COLLECTION_INTERVAL_HOURS=24
INSTAGRAM_ACQUISITION_PROVIDER=apify
```

`APIFY_TOKEN_CONFIGURED` is a Compose-generated presence hint for staff/gateway, not a secret. Direct local processes can use the hint without the token; only the collector needs the actual token. Budget cannot exceed $4, reserve cannot fall below $1, active-profile cap cannot exceed 20, interval cannot fall below 24 hours, and limits must be 1–2. Keep ScrapingAnt configured independently if desired; selecting Apify does not enable either provider automatically.

Existing required settings still apply: distinct least-privilege `SOCIAL_ADMIN_DATABASE_URL`, `SOCIAL_GATEWAY_DATABASE_URL`, `SOCIAL_RELAY_DATABASE_URL`, `SOCIAL_MAINTENANCE_DATABASE_URL`, `SOCIAL_CONSUMER_DB_ROLE`, independent `SOCIAL_WORKER_KEY`, final private HTTPS host/network and bind address. Follow [existing deployment gates](social-control-operations.md) for first installation, passkeys, WireGuard and the public API runtime privilege separation. This extension does not prove those target-host gates. Existing Level 4 is not production-ready solely because fixture tests pass.

### Exact upgrade/start commands

These are operator instructions, **not commands executed against a deployment**. From the `BACity-` application directory, with `SOCIAL_ENV_FILE` pointing to the configured secret file and `MIGRATION_DATABASE_URL` pointing to the migration-owner connection:

```sh
.venv/bin/python -m pip install -r services/api/requirements-social.txt
cd services/api
DATABASE_URL="$MIGRATION_DATABASE_URL" ../../.venv/bin/python -m alembic upgrade head
cd ../..
psql "$MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f infrastructure/social/roles.sql

docker compose --env-file "$SOCIAL_ENV_FILE" --profile social \
  -f docker-compose.yml -f compose.social.yml build \
  social-admin social-gateway social-collector social-egress

docker compose --env-file "$SOCIAL_ENV_FILE" --profile social \
  -f docker-compose.yml -f compose.social.yml up -d --no-deps \
  social-admin social-gateway social-collector social-egress social-proxy
```

Existing PostgreSQL/private networks must already be running. Do not start publication merely to enable acquisition. After adding the token, explicitly set `APIFY_ENABLED=true`, `SOCIAL_L4_ENABLED=true` and `SOCIAL_L4_COLLECTION_ENABLED=true`, while retaining `SOCIAL_L4_PUBLICATION_ENABLED=false` for initial review, then repeat the `up` command so changed environments are recreated. No host cron or second dashboard is needed. Billing remains unverified until an eligible approved batch performs its preflight.

In **Publishers**, add the profile link and basic details, then review and confirm **Approve & start daily checks**. The default is daily collection with at most **two posts**, using the configured preferred provider. No separate access form or example post link is required. Pending sources stay idle; pause/suspend controls remain available. Routine approvals use the staff session; sensitive team/security/publication actions retain in-place passkey verification. Budget checks, source restrictions and daily limits remain enforced. See [the current workflow](control_panel_start.md#everyday-publisher-workflow).

The screen shows combined active profiles, provider/limit, last attempt/success, job errors, discovered posts/Reels/candidates, Apify USD/uncertainty/run states and separate ScrapingAnt credits. Review observations and candidates in the existing workflow. A retrieved post does not imply an event or authorize publication.

## Explicit opt-in live validation

No token was supplied for live validation and **no live acquisition command was run**. The fixture results are not evidence of real Instagram accessibility, profile completeness, newest-item correctness or actual charges.

After explicit owner selection of 1–3 approved public profiles, run from `services/api` with the backend token available only to this process:

```sh
APIFY_ENABLED=true ../../.venv/bin/python -m app.social.apify_probe \
  --live \
  --approved-profile "$APPROVED_PROFILE_URL" \
  --permission-attestation "$VERIFIED_PERMISSION_AND_PURPOSE" \
  --state-path "$NEW_DISPOSABLE_STATE_PATH" \
  --max-test-budget-usd 0.10
```

Repeat `--approved-profile` for additional explicitly selected profiles. State path must be new; it is created mode 0600. No hardcoded or production-registry targets are selected. Without explicit opt-in, enabled provider and token, it makes no calls and creates no state. The same client/gateway and bounded reservation are used; a reservation above the test ceiling cancels before launch. It uses a disposable SQLite staging database with publication disabled, never production canonical writes.

JSON output includes profiles, selected normalized posts/Reels, captions/timestamps/media availability, raw dataset record count, run identities/states, reported versus estimated costs, empty/error status, one-item compliance, staging/candidate counts and request/byte totals. Selection means newest within returned validated records; independent Instagram newest verification and complete feed/Reels coverage explicitly remain false. A probe deadline can leave a pending run recorded in its local state; inspect/abort that run in Apify Console and preserve its state for accounting. Provider billing exposure described above still applies to a live probe.

## Verification

Baseline: API **504 passed, 3 skipped**; crawler **204 passed**. Focused Apify suite: **50 passed**. Social suite before final reporting refinements: **202 passed, 1 skipped**. **Final API including PostgreSQL/PostGIS: 557 passed, no skipped tests (186.50s); crawler: 204 passed (7.91s).** Apify plus retention focused checks: 54 passed; dedicated PostgreSQL end-to-end check: 1 passed. Existing dependency/SQLAlchemy/datetime deprecation warnings remain (38,091 reported in the complete API run). Final regression results and reproducible logs are recorded in the delivered `outputs/apify/test-results` evidence and `verification-summary.json`.

Coverage includes provider/token defaults, input limits, feed/Reel/carousel handling, publisher attribution, timestamps/pins/checkpoints, batch staging, empty/failed/malformed datasets, pagination/restarts, unknown-launch quarantine, atomic reserve/dispatch, budget exhaustion/rollover, billing reconciliation, cross-provider dedup after retention, shared cap/daily schedule, approval/suspension, RBAC, emergency cleanup and disabled acquisition. Disposable PostgreSQL/PostGIS tests exercise migration/grants, concurrent reservations, actual terminal accounting and preservation on downgrade. Ordinary tests use fixtures, not Apify calls.

Container checks build the collector, staff and egress images; the collector fixture runs non-root, read-only, with dropped capabilities, the existing sandbox/seccomp and **network none**. Compose is rendered with all optional profiles using synthetic secrets to verify token placement. JavaScript syntax/Python compilation and diff whitespace are checked. The UI screenshot is a loopback-only synthetic owner session with acquisition disabled; hardware WebAuthn and real network deployment are not validated by it.

## Collaboration posts and invalid-content recovery

Instagram profile feeds can contain collaboration posts whose original `ownerUsername` differs from the requested profile. The collector accepts that relationship only when `inputUrl` resolves to the approved profile and the same profile is explicitly present as a published `coauthorProducers` entry. Mentions and tagged users alone are insufficient. The original author and the owner/coauthor relationship are retained in private observation provenance; the other account is not automatically registered or crawled.

A successful Actor run can therefore be recoverable even if an older parser rejected its dataset. A host owner can reprocess the **existing, complete, already-settled dataset** using `python -m app.social.recover_apify --run-id RUN_UUID` with the migration-owner database connection and evidence JSON on stdin (`run`, `metadata`, `items`). This CLI is not exposed through the panel or gateway and performs no provider calls. It checks original run/dataset identity, approval, source restrictions, complete evidence, the two-post cap and absence of a newer collection. `--allow-paused` explicitly permits recovery of previously captured content while keeping a publisher paused. Suspension, withdrawn approval, access restrictions and emergency stops still block repair. Recovery is atomic, idempotent and audited; it preserves settled billing, provider run ID, last attempt and next due time, and never writes public events. Store any temporary evidence privately and remove it after verified repair.
