# ScrapingAnt Instagram integration — 27 October 2026

Implemented as an extension of the existing private Level 4 system on `crawl-L4-social`. Nothing committed, pushed or deployed. All acquisition/publication flags remain disabled by default. **Live Instagram acquisition remains unverified.** Fixtures and container checks are not evidence of successful live retrieval.

## Architecture and scope

The existing publisher registry, staff panel, scheduler, machine gateway, staging/extractor and canonical relay remain authoritative. There is no second production publisher database, scheduler or event pipeline. Levels 1–3, consumer authentication/entitlements, canonical identity/ingestion and mobile/map code are unchanged.

`acquisition/scrapingant.py` is a replaceable HTTPX transport/parser. It calls fixed HTTPS ScrapingAnt v2 endpoints with the key in the `x-api-key` header, never in a URL. Provider query parameters fix `browser=false`, `proxy_type=datacenter`, `timeout=5`; there are no cookies, custom JavaScript, residential upgrades, login accounts, challenge solvers or escalation retries. The response JSON's target status and HTML are checked independently of outer HTTP 200. Login/challenge/denied/private/empty-shell/mismatched identity responses fail closed. Redirects from the provider API are not followed.

The isolated collector parent receives the provider key and the existing narrow machine key. Its existing browser subprocess receives neither. The provider parser executes no returned scripts. Responses are capped at 2 MiB, request phases have deadlines, concurrency remains one global job, and at most one profile plus two direct-post documents are acquired in a check. An account-status request may also be needed. No full Reel video is downloaded. Source URLs are normalized and allowlisted; post ownership must match the approved handle. Content is always untrusted. Returned content containing an echoed provider key is rejected.

The parser handles structured profile/feed media nodes, `/p/` and `/reel/` shortcodes, caption text, trustworthy available timestamps and allowlisted Instagram/Facebook CDN thumbnail references. A generic video is not automatically labeled a Reel. It preserves absent fields instead of inventing them. Captions are bounded to 3500 UTF-8 bytes. The bounded feed window is not a complete historical crawl. New/edited content is deduplicated through the existing immutable observation hashes, staged with `method=scrapingant`, and passed to the existing deterministic caption extractor. The gateway records discovered/new posts and Reels, new candidates and collection metrics separately. Existing review, independent approval and publication flags remain mandatory. Collection never writes canonical events directly.

There was **no OCR implementation in the starting Level 4 code**. This integration preserves permitted thumbnail references but does not download them or claim poster OCR. Poster-only announcements remain unsupported; missing dates/locations remain private. No parallel OCR/event subsystem was added.

## Environment

Add these to the backend/operator environment consumed by the optional Compose overlay. Never put them in a frontend/mobile environment or commit a real key.

```dotenv
SCRAPINGANT_ENABLED=false
SCRAPINGANT_API_KEY=
SCRAPINGANT_MONTHLY_CREDIT_LIMIT=10000
SCRAPINGANT_MONTHLY_CREDIT_RESERVE=1000
SCRAPINGANT_MAX_ACTIVE_PROFILES=20
SCRAPINGANT_COLLECTION_INTERVAL_HOURS=24

SOCIAL_L4_ENABLED=false
SOCIAL_L4_COLLECTION_ENABLED=false
SOCIAL_L4_PUBLICATION_ENABLED=false
```

`SCRAPINGANT_KEY_CONFIGURED` is an internal presence-only boolean derived by Compose; the owner does not configure it separately. Staff/gateway receive policy and this boolean, **not the provider key**. Only `social-collector` receives `SCRAPINGANT_API_KEY`. The egress proxy adds only `api.scrapingant.com:443` to its exact host allowlist. Provider settings do not load arbitrary `.env` files themselves; Compose's `--env-file` supplies them. Existing private staff/gateway credentials and least-privilege URLs remain required, as documented in `social-control-operations.md`.

## Local installation / upgrade commands

These commands are instructions only; no deployment has been performed. Use a local/disposable development stack. Existing private-stack production security gates still apply: final private HTTPS origin, WebAuthn, WireGuard/firewall, separate database logins, public API deprivileged runtime and backup/restore validation.

From `/Users/s3eed/Documents/GitHub/BACity/BACity-`:

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
  -f docker-compose.yml -f compose.social.yml up -d \
  social-admin social-gateway social-proxy social-collector social-egress
```

`MIGRATION_DATABASE_URL` is an operator-supplied owner connection used only for migrations/grants. Runtime services must use their existing distinct least-privilege logins. `SOCIAL_ENV_FILE` is the absolute path to an operator-owned mode-0600 backend environment file. Do not copy credentials into shell history. Migration **0025** adds `l4_provider_budget` and `l4_provider_requests`; it does not alter existing event or publisher semantics. Downgrade preserves the ledger and repeated upgrade is idempotent, matching the existing L4 preservation policy. Apply updated grants after migrating. No base Compose startup behavior is changed.

For activation, put the key in that backend environment, set `SCRAPINGANT_ENABLED=true`, `SOCIAL_L4_ENABLED=true`, and `SOCIAL_L4_COLLECTION_ENABLED=true`, then recreate the affected services. Keep `SOCIAL_L4_PUBLICATION_ENABLED=false` for shadow mode. The separate publication relay is not started by the `social` profile.

## Co-founder workflow

1. Sign in to the existing private panel with a passkey. Open **Instagram collection** or **Publishers**.
2. Paste a profile URL or username (`@name` or `name`); provide its display name and Bratislava relevance. Add a verified venue association if applicable. Preview is URL-derived, not proof of account ownership or access.
3. An owner/social admin approves the proposal. An owner records verified current collection permission, expiry and **Instagram daily collection** as the acquisition method under **Review collection access**. Approval does not override technical access or platform restrictions.
4. Enable monitoring. Up to 20 enabled provider profiles are allowed by default. All pending Instagram proposals are visible in the new section, so they remain manageable before activation.
5. Routine checks run automatically. The permitted test action can bring the first check forward, but cannot bypass the daily interval, authorization, backoff or quota. Suspend cancels jobs immediately; pause removes a publisher from active monitoring without destroying evidence. Reactivation requires approval/current permission and explicit re-enabling.
6. Review extracted candidates through the existing Event candidates screen. A successful collection can yield no event. Missing evidence stays private. A distinct reviewer/authorized publisher and the separate relay/flag are still required before canonical publication.

No code, JSON, SQL or terminal commands are needed for routine publisher management. Staff WebAuthn, sessions, CSRF, recent-authentication requirements, role boundaries, audit and private network restrictions are preserved. The new read endpoint is `GET /api/instagram-collection`, guarded by the existing staff read permission. New machine endpoints are `/jobs/{id}/provider/status`, `/reserve` and `/settle`; they require the existing worker key and a valid provider job lease. They are not public staff APIs.

## Daily scheduling

The existing database job/lease scheduler persists all due times/checkpoints. Enabling a new provider profile assigns a stable hash-derived offset across the configured interval, spreading checks across the day. The default is a **rolling minimum 24 hours between actual attempts**, stronger than a calendar-day counter. Intervals can be increased up to seven days; profile caps can be configured from 1 to 100. The default cap is 20. A serialized control-row lock prevents concurrent activations from exceeding it. Lowering the configured cap also limits which active profiles the scheduler selects.

Existing unique job keys, queued/running checks and one global lease prevent duplicate/concurrent collections. Transient failures use existing exponential backoff, with the provider daily interval as an additional floor; there is no same-day retry storm. `429` retry guidance is retained and the existing restriction policy pauses the source for owner review. Login/CAPTCHA/explicit denials suspend that source without automatic unchanged retries. Global flags and emergency stop prevent further acquisitions. An already-started bounded provider request may finish before cancellation; late results cannot stage after suspension. Failure never cancels or deletes canonical events.

## Hard credit accounting

The gateway is the persistent quota authority. Before **every provider HTTP request**, including usage checks and manual tests, the collector must atomically reserve **125 credits** in the existing PostgreSQL database. This is the highest [documented v2 request mode](https://docs.scrapingant.com/credits-cost), used as a conservative safety bound even though the fixed simple/datacenter mode is documented as costing one credit. The application never assumes every request costs one credit. Missing or malformed `Ant-credits-cost` retains all 125 as **estimated** spending; timeout/crash/ambiguous requests are never refunded. A valid cost header records the actual reported cost. Replayed settlements cannot refund an existing charge. A reported cost above the reservation halts further provider use for operator review rather than upgrading or increasing spend automatically.

Before page acquisition, a successful [`/v2/usage` snapshot](https://docs.scrapingant.com/api-credits-usage) must establish the current provider subscription start/end, total credits and remaining credits. Snapshots refresh at least daily and at rollover. Naive ISO dates in the documented usage format are interpreted as UTC. Provider-reported period boundaries are used; there is no first-of-calendar-month reset. A changed period is accepted only after the old period expires and a coherent new period is returned. Regressing usage counters or contradictory periods fail closed.

Spend accounting uses the greater of (a) local charges, including unknown-cost estimates and (b) provider-reported account usage **plus local charges since that snapshot**, then includes in-flight reservations. This includes other account consumption visible in the last snapshot. The spending ceiling is the lower of the configured limit and reported provider allowance, minus the configured reserve. If the next 125-credit reservation does not fit, no page request is made. No manual endpoint bypass exists.

At an expired period, at most three bounded account-status probes may establish the next period; they have their own conservative reservations, limited by the next period's configured usable allowance. Their costs are carried into that period when confirmed. If renewal remains unverified, acquisition stops and requires operator investigation. A crashed in-flight reservation becomes a full estimated charge after 120 seconds; restart never grants a refund. Budget and request rows persist; old linked job rows are retained rather than deleting accounting evidence.

The panel shows the actual period, content/status request counts, provider-reported/estimated/reserved credits, accounted spend, usable allowance, last sync and suspension reason. Unverified allowance is shown as **Not verified**. Counted jobs are not billable-request counts: a check can consume one status request plus one profile and up to two post requests. Missing cost headers can substantially reduce practical capacity. There is no promise that 20 profiles will fit every provider response/cost scenario.

There is no purchase/upgrade/billing API, plan selection, paid proxy escalation or overage-enabling code. A key used outside this application, an independently configured provider billing policy, a compromised collector/key, or future provider pricing beyond the documented bound cannot be controlled by this local ledger. Use a dedicated key/account, disable provider overages in the provider account, monitor usage and review changed cost headers before reactivation. No software promise is made about a third party's billing behavior.

## Explicit live validation command

Ordinary tests use synthetic HTTPX fixtures and make no real calls. The opt-in command uses only the explicitly listed profiles, never the production registry. It creates a **new disposable SQLite validation database**, not a second production publisher store; it reuses the quota and staging code and cannot invoke publication. A supplied permission attestation is required. Do not run against a production publisher list or use a production state path.

From `services/api`, after exporting the backend key and explicit provider activation in a development shell:

```sh
../../.venv/bin/python -m app.social.scrapingant_probe --live \
  --approved-profile "$APPROVED_INSTAGRAM_PROFILE" \
  --permission-attestation "$COLLECTION_PERMISSION_ATTESTATION" \
  --state-path "$NEW_DISPOSABLE_VALIDATION_DB"
```

Repeat `--approved-profile` for at most three explicitly approved public profiles. `NEW_DISPOSABLE_VALIDATION_DB` must not exist and is created mode 0600. There are no hardcoded production handles. The report includes profile accessibility, actual posts/Reels, caption/date/media availability, requests, bytes, accounted/reported/estimated credits, restrictions and staged candidate counts. It reports zero canonical writes. The absence of key/activation/`--live` stops before any request or database creation.

## Verification and remaining limits

Baseline for this extension: **457 API passed, three PostgreSQL skips**, 129.30 seconds; **204 crawler passed**, 7.67 seconds. The prior full 460-pass PostgreSQL run is retained in the earlier L4 report. New tests exercise configuration/key redaction, URL/username normalization, malformed/oversized/login/private/challenge content, metadata and identity checks, real staging/deduplication with mocked provider responses, budget exhaustion, shared-account baseline accounting, concurrency, actual cost/uncertainty, billing renewal, daily limits, cap/spread, RBAC/audit, suspension and secret-safe Compose wiring. PostgreSQL tests additionally prove real row-lock reservation serialization and private ledger grants. Existing canonical integration/publication tests remain in the full suite.

Final verification: **507 API tests passed, zero failures, zero skips**, in 169.31 seconds, including all 47 new ScrapingAnt tests and real PostgreSQL/PostGIS tests. **204 crawler tests passed**, zero failures, in 7.55 seconds. The full run retained 38091 existing/library warnings. Current-code container builds passed for staff, collector and egress. Network-disabled, non-root staff default-off checks and sandboxed Chromium fixture checks passed. Compose validation used a synthetic key and verified it appears only in the collector environment. Python compilation, JavaScript syntax and whitespace checks passed. A desktop UI fixture verified username preview/proposal creation, pending/paused visibility and unverified budget presentation; this was not live acquisition or physical passkey testing.

Exact incremental file manifest: `scrapingant-instagram-files.txt` (**18 modified, eight created**). This comparison includes the pre-existing uncommitted L4 implementation rather than treating all its files as new work. Earlier reports and the pre-existing feasibility report were preserved. HEAD remains `8e3dabc3a596e9131aae677ca68a59052aee7334`. The only existing migration test change is the expected head advancing to 0025; no old assertions were removed. The PostgreSQL L4 test additionally validates the new ledger privileges and concurrent reservations. No commit, push, branch switch, merge, reset, cleanup or deployment was performed.

Durable [test logs](/Users/s3eed/.codex/.chatgpt-projects/g-p-6a94b492f5088191920f3f48c7c9c29f/outputs/scrapingant/test-results), [verification summary](/Users/s3eed/.codex/.chatgpt-projects/g-p-6a94b492f5088191920f3f48c7c9c29f/outputs/scrapingant/verification-summary.json) and [synthetic UI screenshot](/Users/s3eed/.codex/.chatgpt-projects/g-p-6a94b492f5088191920f3f48c7c9c29f/outputs/scrapingant/instagram-panel-fixture.jpg) accompany this report. Synthetic panel screenshots and test logs are saved in this task's project outputs. No real Instagram posts or Reels have been retrieved in this task, and no provider API requests have been made. Actual Instagram delivery, current HTML/schema coverage, permission suitability, provider reliability and account billing remain unverified until an explicitly approved live probe succeeds. Browser-rendered/residential fallback is deliberately unavailable; a page requiring it fails rather than escalating. There is no OCR or exhaustive history/pagination guarantee.

Primary provider contracts checked: [v2 request format](https://docs.scrapingant.com/request-response-format), [extended JSON response](https://docs.scrapingant.com/json-response), [credit costs/header](https://docs.scrapingant.com/credits-cost), [usage/billing period](https://docs.scrapingant.com/api-credits-usage), [error classifications](https://docs.scrapingant.com/errors). The provider's API key does not grant Instagram collection permission. Follow the existing authorization review before monitoring.
