# Pre-production security hardening

Audit date: 2026-10-05. Branch: `crawler-v2`. Starting commit:
`258de64944887e23bf2df9c7ed04ca6636e3d12b`.

This is a code/configuration and adversarial-test review, not a penetration-test
certificate, a claim of zero vulnerabilities, or legal/GDPR certification.
No production/development user database was modified. No schema migration was added.

## Reviewed boundaries

Reviewed authentication/JWT/logout/recovery/browser and native OAuth; user roles,
organization ownership, profile/social graph/messages/collections/moderation;
event/map/search queries and ingestion; Crawler V2 discovery, URL policy, DNS
pinning, redirects, robots, feed parsing, rendering, durable outboxes and Level 3;
mobile bearer storage, asynchronous sessions, query-cache clearing, location and
external links; consumer Stripe, organization Stripe, Google Play verification and
RTDN; BACity+ gates/planners, group membership/preferences/votes and Area Watches;
account export/deletion, avatars/media, logging/configuration, Docker/proxy and
dependency manifests. Redis/OpenSearch have development services but no active
application query path was found. ORM/raw queries reviewed use bound parameters.

## Findings and changes

Severity reflects the application context, not just a package advisory label.

| Severity | Finding | Change / disposition |
| --- | --- | --- |
| HIGH | Apple browser callback could use an unsigned form email when the signed identity had no email, then link an existing account | Removed unsigned email fallback; only verified identity claims can supply linking email. Apple JWT now requires expiry/subject and rejects an explicitly unverified email |
| HIGH | SMTP default TLS context did not explicitly require certificate/hostname verification | Both implicit TLS and STARTTLS receive `ssl.create_default_context()`; staging/production reject plaintext SMTP |
| HIGH, Windows only | Pinned Starlette StaticFiles has a UNC-path credential-disclosure advisory | Reject backslashes/NUL/malformed paths before filesystem resolution; normal deployment is Linux. Dependency upgrade and outbound SMB blocking still recommended |
| HIGH, development exposure | Default development PostgreSQL/Redis/OpenSearch ports listened on all interfaces, with development credentials/security settings | Bind those ports to loopback. API LAN/emulator access remains unchanged. Production Compose already keeps database ports internal |
| MEDIUM | Signed browser OAuth state was not bound to the initiating browser | Random 10-minute HttpOnly nonce cookie, hashed into provider-specific signed state; validate before provider exchange and clear on completion. Apple HTTPS form POST uses Secure/SameSite=None; Google uses Lax |
| MEDIUM | Default FastAPI validation responses echoed passwords/tokens; HTTPX logged Google identity-token URLs; SMTP server diagnostics could echo secrets | Return validation type/location/message only; redact outbound HTTPX request URLs; bound/sanitize SMTP diagnostics and redact configured credentials, AUTH encodings, recipients and action tokens. Settings errors hide input dictionaries |
| MEDIUM | Public following rows exposed metadata of now-private/inactive/blocked targets | Apply current target privacy/block/activity rules; owners retain a generic removable edge, not private metadata |
| MEDIUM | Negative viewport/nearby limits could remove SQL bounds; invalid coordinates reached queries | Positive bounded limits, geographic ranges and ordered viewport bounds; shared 600/minute/IP event-read budget |
| MEDIUM | Separate approved organization claims could race the ownership check | Lock the common organization before checking/adding membership; real PostgreSQL contention test verifies serialization |
| MEDIUM | An active Stripe consumer subscription without a usable end could become an unbounded entitlement | Reject malformed/missing/reversed eligible provider periods before reconciliation; retain existing entitlement architecture and provider authority |
| MEDIUM | Late authenticated responses/hydration could cross logout/account transitions; late location acquisition could restore discarded coordinates | Session revision guards, immediate local logout, serialized credential writes and stale hydration guard; location acquisition invalidation/session checks |
| LOW / defense in depth | Content link handling relied entirely on backend validation | Shared browser-only HTTP(S) opener for event/source/organizer/moderation/venue content, rejecting executable/custom/file schemes, credentials, controls and oversized links. Native directions/auth flows unchanged |
| LOW / defense in depth | Unbounded account input, repeated exports, permissive deployment config and raw default access logs | Bound names/interests; exports 10/hour/account without truncating content; require JWT expiry/subject and integral nonnegative version; HMAC algorithm allowlist; explicit CORS origins and production trusted hosts; fail closed if production ingestion key disappears; disable default Uvicorn URL access logs |
| LOW / defense in depth | Provider redirect and service-account endpoint validation was incomplete | Stripe redirects require expected HTTPS host, no credentials, normal TLS port; Google service-account token URI restricted to Google HTTPS endpoints |
| LOW / defense in depth | Static web response protections incomplete | Add web HSTS, anti-framing and CSP `frame-ancestors`, `object-src`, `base-uri`. No unsafe blanket script CSP that breaks Expo |

No application-level CRITICAL exploit was established in this pass. npm still
reports a CRITICAL build-tool dependency finding; it is not dismissed below.

## Preserved security/product invariants

- Authorization uses the current database user/role/token version, not client flags.
  Registration cannot assign admin, verification, reputation or Plus entitlement.
- Recovery/verification tokens remain hashed, expiring and single-use. Reset
  requests keep anti-enumeration responses, shared SMTP outbox and bounded retries.
- Owner-scoped resources, moderator/admin gates and internal ingestion-key gates
  remain in place. Production configuration requires strong ingestion/JWT secrets.
- Stripe signatures and current provider reconciliation, Play account binding,
  purchase-token ownership, RTDN issuer/audience/email/signature checks, receipt
  deduplication, cross-provider conflict handling and subscription locks remain.
  Organization billing semantics were not changed.
- Premium generation remains server gated. Free invited group participants can
  participate/vote without acquiring entitlement to any unrelated premium feature.
  Private preferences/individual votes and owner-only Area Watches remain scoped.
  Host-controlled reveal remains the existing product behavior; no new early
  participant reveal access was added.
- Existing normal discovery/recommendations/maps/saves/follows/source links stay
  free. No recommendation/planner/crawler architecture or welcome screen redesign.
- Level 3 publication does not depend on successful crawling. Only explicit public
  evidence from accepted/published submissions enters existing bounded learning;
  source qualification is separate from event trust. No private/social scraping.
- Crawler policy still rejects local/private/internal/credentialed/unsupported URLs,
  checks all DNS answers, pins the validated public IPv4 resolver, rechecks redirect
  requests, respects robots, bounds downloads/jobs/candidates/ICS recurrence and
  rejects XML DTD/entities. Source failures remain isolated and durable/retryable.
- Native credentials remain OS-backed; web bearer tokens remain sessionStorage,
  not localStorage. Root QueryClient clearing on user change is preserved.
- For recommendation/planner current-location acquisition, only the enabled-location
  preference persists. Coarsened foreground coordinates
  stay in memory/request bodies, are not logged, and cannot be restored by a stale
  acquisition after disable/session change. No background location was added.
  Area Watch centers remain intentionally persisted private watch definitions,
  not a recorded position history; this feature's existing storage was not removed.
- Avatars retain image decoding/pixel limits/re-encoding/EXIF stripping and fixed
  UUID storage paths; no SVG/HTML upload capability was introduced.
- Account exports exclude password/security/provider-token fields; deletion retains
  existing anonymization/revocation/source-learning minimization behavior.

## Dependency audits and deferred upgrades

Commands: `npm audit --json --ignore-scripts` in `apps/mobile` and isolated
`pip-audit -r services/api/requirements.txt -r services/crawler/requirements.txt --format json`.
pip-audit was installed only in disposable containers, not the application manifest.

Python report: **22 advisory entries across 5 packages; 12 distinct advisory IDs**.
The combined requirements report repeats some entries. npm: **81 affected package
entries (1 critical, 52 high, 27 moderate, 1 low)**, including parent packages
affected transitively; this is not a count of 81 independently exploitable bugs.
Neither audit passed cleanly. Manifests/lockfiles were not force-upgraded. A targeted
`npm update @xmldom/xmldom` found no update within the existing resolved ranges;
there is no intentional lockfile change.

| Python package | Advisory IDs / patched release reported | Application reachability and follow-up |
| --- | --- | --- |
| Starlette 0.38.6 | GHSA-f96h-pmfr-66vw (0.40.0), GHSA-2c2j-9gv5-cj73 (0.47.2), GHSA-86qp-5c8j-p5mr (1.0.1), GHSA-wqp7-x3pw-xc5r / GHSA-x746-7m8f-x49c (1.1.0), GHSA-jp82-jpqv-5vv3 (1.3.0), GHSA-82w8-qh3p-5jfq (1.3.1) | Form/media paths are reachable: existing 1 MiB actual-body cap plus new URL-encoded field/size and malformed-path guards contain specific vectors, not all future parser defects. Linux avoids Windows UNC exposure. No custom HTTPEndpoint dynamic dispatch found. Upgrade FastAPI and Starlette together: FastAPI 0.115.0 constrains Starlette below 0.39 |
| Scrapy 2.14.2 | GHSA-h7wm-ph43-c39p (legacy report, no fixed version in tool); GHSA-76g3-c3x4-crvx (2.17.0) | Downloads capped; no S3 requests/AWS credential/S3FilesStore path found and URL policy permits HTTP(S) only. Upgrade/test crawler stack rather than ignore advisory metadata |
| Twisted 24.11.0 | GHSA-grgv-6hw6-v9g4 (26.4.0) | Advisory is twisted.names TCP DNS decompression; inspected crawler uses socket/getaddrinfo/threaded resolver plus DNS pinning, not an exposed DNS server. Schedule tested Twisted upgrade |
| pytest 8.3.3 | GHSA-6w46-j5rx-g56g (9.0.3) | Local multi-user test temporary-directory issue, not a request handler. Tests here use disposable containers. Upgrade test tooling in an isolated compatibility change |
| ecdsa 0.19.2 | GHSA-wj6h-64fc-37mp (no patched version reported) | Signing side-channel advisory; JWT HMAC allowlist and cryptography-backed Apple signing avoid introducing direct pure-Python signing. Keep cryptography installed; reassess/remove transitive fallback during Python stack upgrade |

npm direct-advisory packages (other entries are largely framework/tool parents):

| Package / examples | Reachability / disposition |
| --- | --- |
| tar: GHSA-34x7-hfp2-rc4v, GHSA-8qq5-rm4j-mr97, GHSA-83g3-92jg-28cx, GHSA-qffp-2rhf-9h96, GHSA-9ppj-qmqm-q256, GHSA-r6q2-hw4h-h46w, GHSA-vmf3-w455-68vh, GHSA-w8wr-v893-vjvp, GHSA-23hp-3jrh-7fpw, GHSA-8x88-c5mf-7j5w, GHSA-gvwx-54wh-qm9j, GHSA-r292-9mhp-454m | Critical archive/tooling exposure: do not run old Expo CLI against untrusted downloaded projects/archives; isolate builders and credentials. Upgrade in the platform/toolchain phase, not `npm audit fix --force` (tool even proposes an incompatible Expo downgrade) |
| @xmldom/xmldom: GHSA-wh4c-j3r5-mjhp, GHSA-2v35-w6hq-6mfw, GHSA-f6ww-3ggp-fr8h, GHSA-x6wf-f3px-wcqx, GHSA-j759-j44w-7fr8, GHSA-6gmq-8vp8-gcm6, GHSA-w2rr-34g9-rvrj, GHSA-4w3w-2rp5-g8jm, GHSA-c7q8-3ch8-vqpv, GHSA-27p8-2357-5qqv, GHSA-6h8r-xr42-gp59, GHSA-8344-3jmq-59r6, GHSA-x4fp-j954-r2f4, GHSA-965w-775f-mr7g, GHSA-93r5-fhx6-vmg9 | Expo/plist XML tooling, not BACity feed XML parsing. Do not build untrusted project/plist inputs; upgrade parent toolchain/resolution together |
| postcss: GHSA-qx2v-qp2m-jg93, GHSA-6g55-p6wh-862q, GHSA-fxqj-rqcc-2cmp, GHSA-r28c-9q8g-f849 | CSS/source-map build inputs; no user CSS upload/rendering found. Untrusted build assets remain a risk |
| braces GHSA-vfj7-8cjw-p6xm; image-size GHSA-5p2g-fcmc-qvqq / GHSA-w3rx-r6r6-pgpr; node-forge GHSA-86w9-cpqp-85rv; ajv GHSA-2g4f-4pwh-qvx6 | Predominantly glob/image/config/certificate tooling. No public caller-controlled schema/glob/RSA verifier identified. Isolate tooling; upgrade compatible parent ranges |
| decode-uri-component GHSA-vcc3-ghjq-m6fr | Potential web/deep-link malformed-query client DoS; runtime reachability not conclusively excluded. Prioritize Router upgrade and malformed-link validation in the platform phase |
| fast-xml-parser GHSA-gh4j-gqv2-49f6; turbo-stream GHSA-rxv8-25v2-qmq8; send GHSA-m6fv-jmcg-4jfg; uuid GHSA-w5hq-g745-h8pq | XML builder/SSR single-fetch/dev server/supplied-buffer UUID paths not used in reviewed BACity consumer flow. Static production hosting is Caddy, not Metro/Remix. Transitive upgrades still required; no advisory suppression |

Major Expo 51/React Native 0.74/Router/Gluestack compatibility upgrades are explicitly
deferred. Backend framework, crawler and test-tool upgrades need their own tested
dependency pass; current containment does not make their advisories disappear.
Audit tools do not cover OS images, native binaries, private registries or all logic bugs.

Primary references: [SMTP TLS](https://docs.python.org/3/library/smtplib.html),
[Starlette Windows advisory](https://github.com/Kludex/starlette/security/advisories/GHSA-wqp7-x3pw-xc5r),
[tar hardlink advisory](https://github.com/advisories/GHSA-34x7-hfp2-rc4v).

## Deployment and residual risks

1. Do not publish the development stack. Use the independent production Compose,
   real random secrets, PostgreSQL, explicit HTTPS/CORS URLs, TLS SMTP and separate
   provider environments. Default production trusted hosts derive from configured
   callback/application URLs plus local health hosts; set `TRUSTED_HOSTS` explicitly
   when additional legitimate API hosts are required. Never use a wildcard.
2. Supply `.env.production`, `APP_DOMAIN`, `API_DOMAIN` and provider credentials.
   Production Compose rendering was blocked here because `.env.production` is absent;
   production Settings validation is exercised by tests. `.env` files remain ignored.
3. TLS proxy must enforce header/body/read-timeout/concurrency/rate budgets, trust
   only the intended proxy's forwarded client address, and redact URL queries in
   any enabled access logs. Uvicorn currently defaults to loopback trusted proxy:
   Docker Caddy client addresses may therefore collapse to one proxy IP. Configure
   trusted proxy addresses deliberately; do not set wildcard trust on an exposed API.
4. Public API budgets are not distributed-DDoS protection. Broad nearby queries,
   large account exports/saved histories and cleanup jobs still need production-scale
   profiling, bounded/streamed processing where appropriate and monitoring.
   Post-pagination privacy filtering can produce sparse public social-graph pages;
   cursor-aware visibility pagination deserves a separate UX/query follow-up.
5. API/crawler containers still run as root. A safe non-root rollout must address
   existing media/state/backup volume ownership rather than break current workers.
   Harden capabilities, network segmentation, filesystem permissions, encrypted
   backups and image scanning/rebuilds before production deployment.
6. Keep browser rendering disabled unless actual public-only network/egress isolation
   is deployed and verified. `CRAWLER_RENDER_NETWORK_ISOLATED=1` is an operator
   assertion, not a firewall. Scrapy DNS pinning does not constrain browser subrequests.
7. Provider tokens required for Google Play reconciliation remain private database
   fields. Restrict DB/backup access and consider application-level encryption/key
   rotation separately. RTDN certificate fetching remains network-dependent; edge
   limits and provider-key caching merit follow-up. No live payment/SMTP/device
   security test was claimed here.
8. Before launch reconcile any historical eligible Stripe rows with absent period
   ends; this pass does not touch live/development billing data. Cross-provider
   deletion/concurrent-account-mutation races were not exhaustively stress-tested;
   transactional deletion coordination and external-provider crash recovery need
   dedicated testing. Do not claim exactly-once provider-side deletion.
9. Web sessionStorage is still readable by same-origin JavaScript. Targeted CSP is
   not a complete script-injection defense. Plan strict build-compatible script CSP,
   secure hosting and browser/deep-link penetration testing during the web/platform
   phase. Native device compromise/rooting and provider-console configuration are
   outside this code-only review. Avatar URLs remain public static resources.
10. Pattern inspection found no real tracked deployment secret; matches were
    documented placeholders or generated/test keys. This was not an exhaustive
    historical secret scan. Rotate credentials if previous logs captured tokens or
    SMTP authentication echoes; never paste those logs/values into an issue.

## GDPR/legal decisions deliberately deferred

Confirm retention/legal basis for public event/review/contribution tombstones,
moderation/audit records, billing receipts and backups; handling of anonymized
public attribution/avatar availability; provider-side deletion/revocation timelines;
blocked deletion during paid Play periods; group invite/result lifetimes; private
source/contribution evidence retention; and export/access request procedures.
Rate-bucket identities are hashed and age out through maintenance rather than being
matched by deletion's raw identifier search. No new retention policy or legal claim
was invented in this engineering pass.

## Validation

Baseline before edits: API **203 passed, 1 skipped**; crawler **95 passed**;
real PostgreSQL migration/locking test **1 passed**.

Focused security additions cover secret redaction, required JWT claims/versions,
map bounds, browser state transfer, unsigned Apple email/unverified claims, SMTP
verified contexts and echoed-secret diagnostics, graph privacy, malformed provider
periods/redirects, CORS/Host/config errors, form/UNC containment, internal-key
failure, mass assignment and shared read budgets. Mobile tests execute actual
transpiled client/store/location code with mocked platform/network/storage adapters,
including account switching, stale hydration, immediate logout and disabled-location
races; they are not native device tests.

Final complete API: **248 passed, 1 skipped** (baseline 203 passed, 1 skipped;
45 new security cases). Focused auth/platform/security/payment selection:
**77 passed**. Complete mobile: **73 passed** (9 new session/location/link cases).
TypeScript and Expo public configuration: **passed**. Web and Android exports:
**passed**. Native device/emulator/assemble tests were not performed in this pass.
Crawler **95 passed**; isolated real PostgreSQL/PostGIS migration and lock check
**1 passed**, including organization claim serialization. `bacity_migration_test`
and the test-created random database were dropped; `bratislava_events` untouched.
No native rebuild required: native dependencies/configuration were unchanged.
Production Compose check remains blocked by the missing environment file; development
Compose configuration validates. No tests or dependency findings were disabled.

Changed files (relative to the application root):

- API: `app/config.py`, `app/main.py`, `app/api/routes/auth.py`,
  `app/api/routes/community.py`, `app/api/routes/consumer_billing.py`,
  `app/api/routes/events.py`, `app/core/consumer_billing.py`, `app/core/http.py`,
  `app/core/mail.py`, `app/core/security.py`, `app/schemas/auth.py` (under `services/api/`).
- API tests: `services/api/tests/test_security_hardening.py`,
  `services/api/tests/test_postgres_migrations.py`.
- Mobile: `app/(tabs)/explore.tsx`, `app/activity.tsx`, `app/event/[id].tsx`,
  `app/moderator.tsx`, `app/venue/[id].tsx`, `src/api/client.ts`,
  `src/api/externalLinking.ts`, `src/api/externalUrl.ts`,
  `src/api/externalUrl.test.mjs`, `src/api/sessionSecurity.test.mjs`,
  `src/recommendations/useRecommendationLocation.ts`,
  `src/recommendations/locationSecurity.test.mjs`, `src/store/authStore.ts`,
  `src/store/tokenSession.ts` (under `apps/mobile/`).
- Deployment/docs: `apps/mobile/Caddyfile`, `services/api/Dockerfile`,
  `docker-compose.yml`, `docs/security-hardening.md`.
