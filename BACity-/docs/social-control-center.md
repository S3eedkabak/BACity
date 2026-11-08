> Current workflow: [Add → review → approve and start](control_panel_start.md#everyday-publisher-workflow). Approval now combines daily collection authorization and activation. Advanced legacy access controls remain under Settings; the sections below also document those boundaries.

# Level 4 social control implementation report — 26 October 2026

Local implementation on `crawl-L4-social`, starting and ending HEAD `8e3dabc3a596e9131aae677ca68a59052aee7334`. Nothing committed, pushed or deployed. This is not production-ready: live social acquisition, physical passkey onboarding and target-host deployment gates remain unverified. All new flags default false.

## Repository audit and implementation decisions

The existing stack is FastAPI/SQLAlchemy/Alembic with PostgreSQL/PostGIS canonical events, Redis/crawler workers, a mobile consumer client and existing Level 1–3 discovery/ingestion. Existing consumer JWT/password/Plus authorization does not provide the required staff assurance. The committed Level 4 foundation already supports a disabled website-to-Instagram lead registry; it is preserved, not represented as completed social acquisition. The pre-existing untracked feasibility report is also preserved.

Baseline before changes: crawler **204 passed** (7.06s); API **352 passed, 2 skipped** (109.76s), with PostgreSQL tests initially skipped because no test server was configured. No baseline failure. These included the existing foundation tests. The plan was to add the narrow staff boundary first, then a separate approved publisher/staging workflow, bounded collectors, canonical relay, additive migration, private UI and deployment overlay; finally run real cryptographic, isolated browser, PostGIS and baseline regressions.

A buildless frontend served by the private FastAPI app avoids coupling staff assets to the public mobile app or adding a frontend toolchain. PostgreSQL implements atomic shared rate buckets and job leases rather than adding a second queue/database. A single collector lease globally is deliberately conservative and isolates L4 capacity from existing workers. The canonical relay invokes existing `app.crud.ingestion.ingest`; it does not implement a competing event store or identity algorithm. Read-only duplicate suggestions use the existing pure comparator because the ingestion finder may mutate identity fields. Review is mandatory until measured quality supports anything more automatic.

Protected files remain unchanged: existing spiders, discovery, schedules, ingestion/identity/qualification/reconciliation, public API routes, consumer authentication/entitlements, mobile/map code, base Compose and `FINAL-UX`. Two existing files changed: Alembic env imports the additive model metadata, and the migration test expects head 0024 instead of 0023. No existing assertions were removed. Everything else is additive. See the exact file manifest in `social-control-files.txt`.

## A. Implemented components

- Private control panel: dashboard, URL proposals and publisher details, separate approval/access/monitoring states, candidate evidence/corrections/review/duplicate suggestions, per-platform collection health, owner staff controls, audit, passkey/security settings and emergency stop. Responsive desktop/390px fixture UI reviewed; no horizontal document overflow. Screenshot is explicitly synthetic UI QA, not live collection.
- Maintained py_webauthn 3.0.1 verifies real WebAuthn signatures, RP/origin, challenge, user presence and user verification. Invite-only staff, backup authenticators, revocation, owner recovery, server-side roles and opaque revocable sessions.
- Publisher normalization, uniqueness, types/relevance, verified venue association, priority/conservative interval, immutable observation versions, caption extraction, private candidates/reviews and separate canonical publication relay.
- HTTP and real sandboxed Playwright/Chromium acquisition paths. Direct-post adapters for Instagram/Facebook/TikTok, explicit event-site adapter, safe network mediation and isolated process/container. Profile monitoring is unsupported, never silently substituted with a successful fixture.
- Jobs: lease-driven schedule/reclaim/backoff/cancel; short-lived acquisition subprocess; staged completion and extraction; separately gated reviewed publication; bounded retention; host-only bootstrap/recovery/audit export.
- Optional Docker/Caddy/private-network overlays, least-privilege SQL groups and consumer-runtime override. No new public API router, no deployment and no second production database.

New tables (14), in the existing database:

`l4_staff`, `l4_credentials`, `l4_invitations`, `l4_challenges`, `l4_sessions`, `l4_rate_buckets`, `l4_audit_head`, `l4_audit_events`, `l4_publishers`, `l4_collection_jobs`, `l4_observations`, `l4_event_candidates`, `l4_candidate_reviews`, `l4_control`.

Migration 0024 adds only L4 tables/indexes, canonical reference with ON DELETE SET NULL, immutable audit/staging triggers and foreign keys. PostgreSQL roles are applied separately by an operator. Downgrade intentionally preserves L4 evidence and audit data; repeated upgrade is idempotent. It is not a destructive rollback or uninstall.

Private routes, separate from the consumer app:

- `POST /api/auth/register/options`
- `POST /api/auth/register/verify`
- `POST /api/auth/login/options`
- `POST /api/auth/reauth/options`
- `POST /api/auth/login/verify`
- `GET /api/auth/session`
- `POST /api/auth/logout`
- `POST /api/auth/logout-all`
- `GET /api/auth/credentials`
- `DELETE /api/auth/credentials/{credential_id}`
- `GET /api/dashboard`
- `GET /api/publishers`
- `POST /api/publishers/preview`
- `POST /api/publishers`
- `GET /api/publishers/{publisher_id}`
- `PATCH /api/publishers/{publisher_id}`
- `POST /api/publishers/{publisher_id}/decision`
- `POST /api/publishers/{publisher_id}/access`
- `POST /api/publishers/{publisher_id}/monitoring`
- `POST /api/publishers/{publisher_id}/retry`
- `POST /api/publishers/{publisher_id}/evidence`
- `GET /api/candidates`
- `PATCH /api/candidates/{candidate_id}`
- `POST /api/candidates/{candidate_id}/review`
- `POST /api/candidates/{candidate_id}/publish`
- `GET /api/health`
- `GET /api/staff`
- `POST /api/staff`
- `PATCH /api/staff/{staff_id}`
- `POST /api/staff/{staff_id}/recover`
- `GET /api/audit`
- `POST /api/emergency`
- `GET /api/candidates/{candidate_id}/matches`
- `POST /lease` (machine gateway only)
- `GET /jobs/{job_id}/active` (machine gateway only)
- `POST /jobs/{job_id}/complete` (machine gateway only)

The staff root and static assets are private too. Machine routes expose staging-only operations, no staff session or canonical ingestion endpoint.

## B. Security verification and limits

Real signed P-256 fixture authenticator ceremonies exercise the actual WebAuthn library, including UP/UV rejection, signature/origin rejection, challenge expiry/replay and credential revocation. These are cryptographic integration tests, not physical-device certification. Consumer signed JWTs, including real test Plus grants, never confer staff access. OWNER, SOCIAL_ADMIN, SOCIAL_EDITOR, SOCIAL_REVIEWER and SOCIAL_VIEWER are checked on each endpoint; L4_WORKER has a separate bearer boundary and no human role. Editors cannot manage staff. Independent review/publication identities are enforced and rechecked at relay execution; edits invalidate approval.

Sessions store only SHA-256 digests of random opaque IDs; __Host- cookies are Secure/HttpOnly/SameSite=Strict with no Domain, idle two hours/absolute eight hours. Recent passkey authentication is required for sensitive operations; reauthentication rotates sessions. Suspension/version changes invalidate sessions immediately. CSRF, exact origin/host, private client network, trusted-proxy-only source IP, strict CSP, request-size bounds, atomic database rate limits and bounded pagination are covered by tests. No social passwords, persistent browser cookies, localStorage tokens or external analytics are used.

SSRF tests cover supported URL normalization, private/IP/DNS destinations, pinned public connection addresses, redirects, robots/login/access denial, TLS, response/time/request budgets and no unsafe fallback. Actual Chromium tests cover dynamic fixture extraction, blocked navigation and process cleanup. A real Docker verification passed with no network, non-root uid 10001, read-only filesystem, dropped capabilities, no-new-privileges and default-deny seccomp with Chromium sandbox enabled. The vendored Playwright seccomp policy adds only `chroot` needed inside Chromium's user namespace; upstream/license/hash rationale is recorded. This synthetic container proof is not a live social result or proof of the target host's firewall/VPN.

PostgreSQL tests verify append-only audit permissions and update-denied observations, gateway credential/user/canonical-write denial, staff canonical-delete denial, consumer session denial, deployment role guards and preserving migration downgrade/re-upgrade. The collector has no DB URL or staff code. Runtime guards reject owner/superuser roles and declared public roles with private-table access. The actual public API must be moved off its historical migration-owner credential before enabling staff. Declaring a safe role alone does not prove the deployed API uses it.

Audit records contain actor/time/action/resource/result/request/source IP, chained SHA-256 digests and a locked head. Notes are hashed; secrets are not logged. Row updates/deletes are denied by both grants and PostgreSQL triggers. Chain/tail tampering and capacity rollback tests pass. A compromised DB administrator can forge the full local chain; use protected independent exports as described in `social-control-operations.md`. Backup scheduling/restoration is documented, not deployed. Row-count caps, retention and process limits reduce resource exposure but do not replace disk monitoring and host security review.

## C. Platform acquisition matrix

| Platform | Profile URLs | Direct targets | Implemented method | Authentication/permission | Live observations | Live candidates | Restriction |
|---|---|---|---|---|---:|---:|---|
| Instagram | Registry accepted; enumeration unsupported | `/p/`, `/reel/` | Permitted public HTTP metadata or isolated browser | No account cookies; permission basis required; login wall stops | 0 | 0 | Actual live collection unverified; fixture parsing is not proof |
| Facebook | Page registry accepted; enumeration unsupported | Post/event URL patterns | Permitted public metadata or isolated browser | No account cookies; written permission/access policy must be established | 0 | 0 | Robots/access restrictions; no bypass |
| TikTok | `@handle` registry accepted; enumeration unsupported | `@handle/video/id` | Public item hydration with matching ID/author, HTTP/browser | No account cookies; current permission required | 0 | 0 | Actual live collection unverified; no following sync |

No successful live social acquisition is claimed. No platform credentials or permission grant were supplied. This task made no live social-post fetches; previous Instagram documentation/robots requests were rate-limited and not bypassed. Facebook robots states automated collection needs written permission; TikTok robots is not an authorization grant. Official API acquisition/following-list synchronization is not implemented without a verified usable grant. Manual URL proposals work independently; permitted submitted text is a functioning clearly labeled fallback, not automatic profile acquisition.

One bounded **ordinary event website**, not a social platform, produced a real observation through the new event adapter: [Nová Cvernovka event page](https://novacvernovka.eu/program/ak-raz-pride-vojna-k-nam-prirucka-prezitia). Explicit event-site allowlists also include staratrznica.sk, visitbratislava.com and goout.net; those hosts are not claimed live-validated here. The final successful probe used four requests including robots checks, 122551 decoded bytes and 2.558 seconds (Python peak RSS approximately 37.6 MB). Two preceding bounded website probes returned invalid content before the visible-page fallback was completed; there were 12 website requests across the three probes. No login, credentials, CAPTCHA, paid proxy or stealth used.

## D. Event pipeline and measured counts

The real website observation produced **one private candidate, zero qualified candidates, zero publications**. Its text says “zajtra 18:00” with no trustworthy publication timestamp; missing fields include unambiguous_date and verified_bratislava_location. Collection time is not used to invent a date, and coordinates are not guessed. The JSON evidence artifact records this result. No non-test canonical event was inserted.

Deterministic SK/EN and common CZ text parsing extracts titles, explicit/relative dates with original publication context, times, venue/address from verified association, organizer, price and ticket URL. DST gaps/folds, ambiguous timezone labels, past events, non-events and multiple announcements are quarantined or split conservatively. Explicit timezone offsets are honored. JSON-LD and visible event-page text preserve provenance. Captions and optional media are untrusted; no media is downloaded. OCR/poster extraction is **not implemented** because no verified permitted media path was established; poster-only announcements remain unsupported.

Immutable observation hashes provide replay idempotency and edited-content versions. Candidates preserve field/hash/review provenance. The canonical integration test calls the existing ingestion contract; two different publishers announcing the same event produce one canonical event and two source-attribution rows. Shadow comparison does not mutate existing identity. Publication requires complete future Bratislava evidence, fresh valid review, a distinct active authorized requester, explicit publication flag and separate relay. Collection failures never imply cancellation/deletion. Unattended automatic publication remains intentionally unavailable pending measured quality.

## E. Non-regression evidence

Final verification: **460 API tests passed, zero failed, zero skipped** in 161.12 seconds, including 106 new social tests and all 354 existing API/PostgreSQL tests. There were 38091 existing/new-library deprecation warnings; see the full log. **204 crawler tests passed, zero failed** in 7.28 seconds. The isolated PostgreSQL privilege/migration check passed, as did the canonical deletion-reference check. The current collector build passed the real sandboxed Chromium container fixture again. The rebuilt staff image ran non-root, with no network and all flags false, and returned 404 while disabled. Compose configuration validation, Python compilation, JavaScript syntax and `git diff --check` passed.

During development, a PostgreSQL test-harness `%I` driver-escaping error and a new ORM deletion-fixture error were corrected; the final complete rerun is green. No existing production behavior was modified to satisfy those checks. Durable logs: [test-results](/Users/s3eed/.codex/.chatgpt-projects/g-p-6a94b492f5088191920f3f48c7c9c29f/outputs/social-control/test-results). Website evidence: [JSON](/Users/s3eed/.codex/.chatgpt-projects/g-p-6a94b492f5088191920f3f48c7c9c29f/outputs/social-control/live-website-acquisition.json). Synthetic UI QA: [screenshot](/Users/s3eed/.codex/.chatgpt-projects/g-p-6a94b492f5088191920f3f48c7c9c29f/outputs/social-control/control-room-fixture.jpg). Baseline API had 352 passed/2 PostgreSQL skips; enabling the disposable PostGIS test server runs those two plus the new PostgreSQL security test. The final API collection includes 106 additive social tests and the 354 existing tests. Crawler remains 204 tests. Existing deprecation warnings remain; they are not suppressed to claim a clean warning count.

All three new feature flags default false. Disabled staff and gateway requests are rejected, the publication relay does nothing, and no new router is mounted in the public app. Existing test suites run against unchanged public contracts. Full diff review confirms no mobile/map, existing crawler or canonical implementation edits. No changes to FINAL-UX. Disposable PostGIS migration/security tests and sandbox-container results are separate from fixtures and live acquisition.

## F. Remaining work and release gates

- Obtain and verify platform-specific permission and actual accessible social announcements. All social live counts are zero; automated profile enumeration, official APIs and following sync remain unsupported.
- Validate physical passkeys/backup-key recovery and private final-origin HTTPS, WireGuard onboarding/revocation, host firewall/public reachability and target-kernel sandbox behavior.
- Provision production least-privilege logins and move the actual public API away from migration-owner credentials. Review/test the explicit runtime overlay on the deployment before enabling staff. No production privileges or migrations have been applied here.
- Configure protected off-process audit backups, capacity monitoring, evidence-retention timer and restore exercises. Test emergency shutdown on the target host.
- Perform release dependency/image vulnerability scans, independent security review and a measured extraction-quality corpus. No unattended publication until justified. No production-ready or complete social-monitoring claim.
- Optional permitted-media/OCR extraction is not implemented. Hosting/hardware/bandwidth costs remain; no paid SaaS/LLM/GPU dependency is required.

See `social-control-operations.md` for onboarding, role setup, recovery, secret rotation and shutdown. Local fixture screenshot and website evidence are in the project outputs; the fixture screenshot is never evidence of live platform success.

Primary references used for implementation/constraints: [py_webauthn registration](https://duo-labs.github.io/py_webauthn/registration.html), [Playwright Docker guidance](https://playwright.dev/python/docs/docker), [Facebook robots](https://www.facebook.com/robots.txt), [TikTok robots](https://www.tiktok.com/robots.txt). Access policy and authorization must be revalidated for the actual proposed collection; these references do not confer permission.

Verification commands and operator setup are in `social-control-operations.md`. Final repository diff: only Alembic metadata registration and expected migration head modified among tracked files; 56 additive files listed in the manifest. HEAD and branch unchanged. The pre-existing feasibility report remains outside this implementation manifest.
