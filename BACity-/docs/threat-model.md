# BACity threat model and adversarial release gate

Audit: 2026-10-05, `crawler-v2`, starting SHA
`3e6a49307622c4a8dab9b858d4f3eb8b8d8c98cb`. This supplements, rather than
replaces, `security-hardening.md`. Evidence is code inspection, local endpoint
tests, mocked providers, controlled malicious fixtures and isolated PostgreSQL.
It is not a production penetration-test certificate or proof of zero defects.

## Actual system and boundaries

Expo 51 / React Native 0.74 clients call a bearer-authenticated FastAPI API.
Production Caddy terminates public HTTPS; internal Docker API traffic is HTTP.
SQLAlchemy uses PostgreSQL/PostGIS in production and SQLite for local tests.
Alembic head is 0013. API/maintenance share models/configuration and mail outbox.
Scrapy worker maintains its own SQLite delivery/discovery state, calls ingestion
endpoints using an ingestion key, and fetches hostile public event websites.
The API owns canonical events, provenance and CandidateSource/public-evidence
records. SMTP, Google/Apple OAuth, Stripe and Google Play are external trust domains.

Redis and OpenSearch are development Compose services, but no live client/query,
private-message index, or cache integration was found. No push SDK/server sender,
WebSockets, chat attachments, conversation-membership model, private-message search,
or message-edit endpoint exists. Do not invent controls for absent subsystems.

| Boundary | Trusted authority | Hostile input / protected decision |
| --- | --- | --- |
| Client -> API | Current DB user/role/token version | Body IDs, bearer tokens, coordinates, flags, pagination; client cannot assert Plus or roles |
| API -> DB | Owner-scoped queries and transactions | SQL parameters, private object IDs, concurrency, dump/backup access |
| API -> provider | Verified TLS, signed identities/current provider state | OAuth forms, webhook/RTDN envelopes, purchase claims, redirects |
| Worker -> ingestion | Deployment ingestion key | Canonical-event writes, provenance and health reports; stolen key is a high-impact integrity capability |
| Human publication -> learning | Approved canonical event + explicit public fields | Unapproved text, identities, screenshots and arbitrary URLs must not become fetch targets |
| Scrapy -> public network | URL policy + all-answer DNS validation/pinning | Private/link-local IPs, aliases, redirects, rebinding, malicious HTML/feed contents |
| App process -> encryption keys | Deployment secret injection | DB-only attacker must not obtain decrypting keys; process compromise remains able to decrypt |
| Native/browser local storage -> session | SecureStore / sessionStorage + revision guards | Stale responses/hydration, account switches, same-origin script/device compromise |
| Admin/moderator -> privileged operations | Current role, object checks, audit logs | Compromised staff tokens; role is not ownership of private social objects |
| Docker -> host/volumes | Operator network/volume policy | Root process, dependency compromise, writable media/state, backups |

## Assets and confidentiality/integrity/availability

H = high, M = medium, L = low. These classify actual stored data, not blanket encryption.

| Asset | C/I/A | Protection and remaining exposure |
| --- | --- | --- |
| Email, password hashes, roles, token version | H/H/H | Passwords hashed; current-row auth; email/roles readable in DB dumps |
| JWT/signing/ingestion/provider/SMTP secrets | H/H/H | Injected configuration; never public/mobile; rotate after compromise |
| Reset/verification/exchange/invite tokens | H/H/M | Hashes, expiry and one-use where applicable; queued action links now encrypted |
| Pairwise message bodies | H/H/M | Participant queries, block rules; application AEAD at rest with configured keys |
| Message sender/recipient/read_at/timestamps | H/H/M | Private endpoint/export scoping; metadata remains plaintext in DB |
| Private profiles, follows, saves, collections | H/H/M | Visibility/owner checks; private JSON/relationships remain plaintext in DB |
| Foreground recommendation location | H/M/L | Consent, coarsened memory-only POST payloads; no location history |
| Area Watch centers/preferences/watermarks | H/H/M | Intentionally persisted private watch definition; owner checks and bounds; plaintext DB coordinates |
| Group membership/preferences/votes | H/H/M | Membership/own preference/vote checks, controlled aggregate reveal, expiry; plaintext DB JSON |
| Organization claims/submissions/report evidence | H/H/M | Verified contribution + moderation + ownership, audited decisions; retained DB evidence needs policy |
| Consumer/org subscriptions and provider IDs | H/H/H | Current-provider authority and owner binding; normalized IDs remain plaintext |
| Google Play purchase credentials / Apple refresh credentials | H/H/H | AEAD / existing Fernet respectively; separate secret-managed keys |
| Canonical events, venue geography, source facts | L/H/H | Conservative dedup/quality/manual overrides; source reliability is not proof of truth |
| CandidateSource, crawler network capability/state | M/H/H | Public-only policy, qualification, isolated jobs and bounded durable queues |
| Avatars/media | L/M/M | Public UUID URLs, decoded/re-encoded JPEG, EXIF stripping; not a private file service |
| Notifications, exports, backups, logs | H/H/H | Owner scoping/minimal message previews/no-store/redaction; access control and backup encryption operationally required |

## Realistic threat actors

Anonymous attacker; malicious authenticated user; compromised consumer account;
malicious/compromised organizer; malicious contributor; Group participant or
stolen-invite holder; spam bot; payment fraudster; malicious public event site;
DNS/redirect controller; compromised moderator/admin; stolen ingestion/application
credential holder; database/snapshot/backup reader; log reader; compromised dependency;
abusive API client. Staff, workers and providers are trusted only for specific
capabilities, not as universal owners of other users' data.

## Role/object matrix

"Own" is derived from authentication, not a submitted ID. Moderator/admin requests
to another user's Area Watch or pairwise messages do not bypass ownership. Anonymous
may read public event/venue/discovery data, not private endpoints. A stale JWT role
claim cannot override the database role. Organization membership is separate from
global user role. The following is policy; tests/evidence are mapped separately.

| Resource/action | Anonymous | User A vs B | Organizer A vs B | Moderator | Admin | Plus/free/expired | Group host vs participant |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Public profile/social search | Visibility-filtered | Public/active/unblocked only | Same | Same | Same | No premium requirement | Same |
| Own saves/private collections | Denied | Own only | Own only | Own only | Own only | Free | Own only |
| Messages/read/report/send | Denied | Pair membership; send verified + opt-in/mutual follow + no block | Same | No unrestricted reads | No unrestricted reads | Free | Groups confer no chat access |
| Org management/billing | Denied | Approved membership | Own org only | No generic bypass | Existing explicit admin exception | Consumer Plus irrelevant | Irrelevant |
| Submission/appeal | Denied | Own submission; verified contribution | Own submitted event | Review others, no self-review | Same plus admin actions | Free | Irrelevant |
| Moderation/role assignment | Denied | Denied | Denied | Moderation, not admin role assignment | Audited admin actions | Plus grants no staff role | Irrelevant |
| Public event reads / ingestion writes | Read / key required outside dev | Read / no client write privilege | Contribution/moderation, not ingestion | Moderation | Moderation | Free reads | Irrelevant |
| Tonight/Chains/Evening/Weekend | Denied | Auth + active entitlement | Same | Same | Same | Free/expired rejected | Free participant gets no unrelated premium access |
| Group private detail/preferences/votes | Denied | Member only; own private inputs | Same | No staff ownership bypass | Same | Creation/generation require host Plus; invited free votes allowed | Host manages; participant cannot generate/invite/reveal |
| Area Watch | Denied | Own only | Own only | Own only | Own only | Active Plus for creation/edit/feed/seen; expired owner can list/read/delete locked definitions | No group-derived rights |
| Consumer billing/export/deletion | Denied | Own only | Own only | Own only | Own only | Existing account functionality remains free | Own private participation/votes only in export |
| Crawler admin/internal delivery | Denied | Denied | Denied | Limited learning/moderation visibility | Source control/audit | Plus irrelevant | Irrelevant |

## Attack chains, detection and recovery

1. User A -> guessed private object ID -> User B data. Pair-scoped messages,
   owner queries, membership checks and current roles reject it. New staff/user
   endpoint matrix tests exercise private watch/message/export boundaries. HTTP
   status/audit logs detect attempts without logging private bodies. Revoke a
   compromised user's token version and investigate affected object/audit IDs.
2. Stolen JWT -> altered role/Plus flags -> admin/premium. Signature/expiry/version
   validation plus live DB roles/entitlements stop tested spoofing. A still-valid
   stolen bearer works as its owner until logout/reset/version revocation/expiry:
   this is a residual risk, not a magical replay defense. No blanket recent-auth
   middleware was added; billing-provider management and high-impact admin actions
   merit a future MFA/re-auth design.
3. Group invite theft -> legitimate membership -> host generation/reveal takeover.
   Random hashed expiring invite grants join, not host/Plus. Capacity/unique member
   constraints and group locks serialize mutation. Host can rotate invite/remove
   participant. Host-controlled early aggregate reveal is existing product policy,
   not confidentiality against a malicious legitimate host after reveal.
4. Contribution -> URL -> CandidateSource -> DNS/redirect -> internal service.
   Approval is required before durable learning; only bounded structured public
   evidence is queued. Candidate creation does not trust a source. Worker validates
   every request/redirect and pins public DNS; blocked source never unpublishes a
   legitimate human event. Disable/reject source, rotate stolen ingestion key,
   inspect provenance and restore canonical facts via existing moderation.
5. Malicious website -> giant/deep JSON-LD -> extraction exhaustion. A reproduced
   recursion/event-amplification gap is now bounded by bytes/scripts/nodes/depth and
   event count. Feed/XML/ICS/download/job limits remain. Source failures are isolated.
   Bounded parsers are not a sandbox against every native/parser-library defect.
6. Weaker source -> shared venue update -> poison otherwise trusted event geography.
   Previously venue coordinates changed before event-quality merging. Ingestion now
   only fills missing coordinates; established venue geography requires correction
   moderation. Canonical quality/manual override/provenance behavior stays intact.
   First-write misinformation and compromised ingestion credentials still need
   operator evidence review; source quality is not factual verification.
7. Account A purchase -> Account B restore -> stolen entitlement. Server-configured
   products/packages, verified current provider state, stable owner binding, hashed
   purchase identity, receipt idempotence and locks reject tested mock attacks.
   Provider outage fails closed for new grants, not client-side entitlement claims.
8. User A logout -> User B -> stale request/cache exposes A. Existing revision
   guards, serialized credential storage and root QueryClient clear are exercised
   in executable mocked-client tests. Device compromise and same-origin script
   injection remain outside those protections.
9. Message send checks consent -> recipient deletes/blocks -> late insert survives.
   Shared ordered account locks now serialize send/block/deletion, with live sender
   checks. Real PostgreSQL HTTP test holds a send while deletion reaches its lock,
   verifies deletion waits, then erases the committed message. Subsequent deleted
   session/recipient writes fail. Other cross-subsystem deletion races/provider
   crash recovery are not claimed exhaustively tested.
10. Dump/backup theft -> read private message/action link/purchase token. Configured
    application AEAD now protects these unindexed TEXT fields; keys are outside DB.
    Metadata, private JSON, user email and watch centers remain visible. Rotate
    provider/action credentials after plaintext backup exposure; app-key rotation
    alone cannot revoke secrets already decrypted by an attacker.
11. Untrusted archive -> old Expo tar -> developer/CI filesystem write. Critical
    advisory remains. Tested tar 7.5.22 override broke actual Windows Expo extraction
    (`default.extract` undefined); it was not retained. Isolate builders/credentials,
    do not extract untrusted projects, and upgrade CLI coherently before launch.

## Messaging and privacy decisions

Each Message has sender_id, recipient_id, body, read_at and timestamps. Sender is
always authenticated; there is no caller-selectable conversation membership.
GET returns only the viewer's pair with the requested user, at most 100 rows per
page. Unfollowing does not erase access to one's existing message history; blocking
does deny pair reads/sends. There is no read-receipt mutation or message editing API.
Notifications say "You received a new message", never the body. Reports of messages
require the reporting user to be a party; moderators may resolve an existing report
without an unrestricted message-content browser. Account export includes own sent/
received messages, not unrelated pairs. Deletion removes both directions of chats.
Messages are plain text in React Native, not executable HTML/link actions.

Application-level encryption is NOT E2EE. See `encryption-and-key-management.md`.
Profile discovery now excludes private/inactive/blocked neighborhood values.
Public avatars can still be retrieved by anyone who knows the URL even for a
private profile. No device lock-screen/screenshot policy was invented.

## Infrastructure, dependencies, secrets and release blockers

Production app services now drop capabilities and disallow privilege escalation.
API/crawler build ignores now cover environment variants and SQLite sidecars;
API media is excluded as well, so local secret/data files are not copied into images.
A disposable non-root UID 10001 API test with read-only source mount passed, but
existing production media/state/backup volume ownership is not verified. Default
Dockerfiles remain root rather than silently break existing volumes. Provision
ownership and separate migration/runtime DB roles before a coordinated non-root
rollout. Default Compose PostgreSQL uses the bootstrap superuser; least-privilege
runtime role and encrypted backup/storage deployment remain operator requirements.
Redis/OpenSearch development security settings must never be published as production.

PostCSS 8.4.49 -> 8.5.28 and AJV 8.11.0 -> 8.20.0 use major-8-only npm overrides;
Expo/RN versions and native modules are unchanged. All installed copies are covered.
Current npm audit: 82 affected package entries (1 critical, 54 high, 26 moderate,
1 low), versus 86 before this pass (1/57/27/1); PostCSS/AJV direct advisories gone.
Parent/transitive metadata is not a count of independently reachable exploits.
tar 6.2.1, xmldom 0.7.13, node-forge 1.4.0, malformed deep-link decoding and other
tool/platform advisories remain. Python audit: 22 advisory entries, 12 unique IDs,
across pytest/Scrapy/Twisted/Starlette/ecdsa; existing report details applicability.
No major platform upgrade or unsafe audit-force downgrade was made.

Read-only git-history pattern scans covered all 312 locally available commits for
provider/PAT/AWS/private-key patterns and secret assignments. Hits were generated/
fake test keys, the documented PEM placeholder and explicit development placeholders
in `.env.example`; no real production credential was established. This is not
entropy-based detection of every secret or a scan of unavailable remote history.
No values were printed, no history rewritten, and no deployment secrets changed.

Production Compose cannot be fully rendered here: required deployment domains and
`.env.production` are absent. TLS certificates/egress firewall/proxy client-IP trust,
browser rendering isolation, encrypted backups/restore, real provider setup and
mobile OS/device behavior require production-like testing. Internal Docker HTTP
and DB links are not encrypted; restrict the network or add standard mTLS/PG TLS
when the deployment threat requires it. Public staging/API callbacks now require HTTPS.

Public HTTP budgets are not DDoS protection. Broad nearby/export histories, malformed
link decoding, uncached RTDN certificate fetches, root containers, DB privilege
scope and known framework advisories remain release risks. Do not enable browser
rendering merely by setting its isolation assertion without actual egress controls.

## Validation and policy deferrals

Complete API: 286 passed, 1 skipped (248 + 38 new cases). Complete crawler: 112 passed
(95 + 17). Mobile: 74 passed (73 + archive compatibility/traversal). TypeScript,
Expo public config and final web/Android/iOS JS exports passed. Android assembleDebug
passed: 915 tasks, 54 executed, 861 up-to-date on final validation. No native iOS
build or emulator/device penetration test. Isolated PostgreSQL migration/locking/
encrypted-storage/send-delete test: 1 passed. Non-root/cap-dropped API platform
checks: 7 passed. Development Compose and diff whitespace checks passed.
Exact commands and per-boundary evidence are in `security-verification-matrix.md`.

## Intentional changed-file inventory

Paths below are relative to the application root. No billing route, premium planner,
welcome/auth-screen, database migration, or feature UI was changed.

- `docs/threat-model.md`, `docs/security-verification-matrix.md`, `docs/encryption-and-key-management.md`.
- `.env.example`, `compose.production.yml`, `services/api/.dockerignore`, `services/crawler/.dockerignore`.
- `services/api/app/core/encryption.py`, `services/api/app/private_data.py`.
- `services/api/app/config.py`, `services/api/app/database.py`, `services/api/app/main.py`.
- `services/api/app/api/routes/community.py`, `services/api/app/crud/ingestion.py`.
- `services/api/app/models/community.py`, `services/api/app/models/entitlement.py`, `services/api/app/schemas/area_watch.py`.
- `services/api/requirements.txt`, `services/api/tests/conftest.py`, `services/api/tests/test_platform.py`, `services/api/tests/test_postgres_migrations.py`, `services/api/tests/test_adversarial_security.py`.
- `services/crawler/crawler/extraction/jsonld_extractor.py`, `services/crawler/crawler/spiders/discovery.py`, `services/crawler/tests/test_adversarial_security.py`.
- `apps/mobile/package.json`, `apps/mobile/package-lock.json`, `apps/mobile/src/api/toolchainSecurity.test.mjs`.

No schema migration: encrypted fields remain TEXT. Normal `bratislava_events` and
all development/production user data were untouched. Disposable databases were
dropped. Export build artifacts are under the host temporary directory, not Git;
their deletion was blocked by the environment policy. No real data was removed.

Legal/retention decisions are deferred: public anonymized contributions/reviews,
rejected submissions/claim evidence/audit retention, message/backup copies, exports
containing a correspondent's messages, shared Group reveal, paid-period deletion,
provider-side erasure and deletion-confirmation email retention. Existing maintenance
durations were not presented as a new legal policy. This audit is evidence, not
confidence theater; passing tests does not prove the absence of vulnerabilities.
