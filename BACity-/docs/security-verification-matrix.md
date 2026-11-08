# Security verification matrix

2026-10-05; `crawler-v2`; starting `3e6a49307622c4a8dab9b858d4f3eb8b8d8c98cb`.
This is a release evidence artifact. PASS means the named controlled property,
not proof that a subsystem has no vulnerabilities. REVIEW/UNVERIFIED is not PASS.
API tests below live in `services/api/tests`, crawler tests in `services/crawler/tests`.
All provider traffic was mocked; DNS/network attack fixtures did not attack public hosts.

| ASSET | ATTACKER | ENTRY POINT | ATTACK | CONTROL | TEST | RESULT | RESIDUAL RISK |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Session | Token forger | `/users/me` | Expired/empty subject/invalid version/missing expiry/wrong algorithm/signature | Signature/expiry/live version | `test_adversarial_security.test_malicious_jwt_claims_rejected_by_endpoint`, `test_token_structure_and_signature_at_actual_endpoint` + existing auth tests | PASS | Valid stolen bearer works until expiry/revocation |
| Admin/Plus rights | Normal user | Moderation, Tonight | Signed role/Plus claim spoof | Current DB role and entitlement | `test_stale_admin_role_claim_cannot_elevate_current_user`; `test_registration_cannot_assign_privilege` | PASS | Compromised signing key is a high-impact incident |
| Recovery | Bot/token thief | Reset/verify | Enumeration, replay, expired tokens, brute force | Uniform reset response, rate buckets, expiring purpose-bound single-use hash | `test_auth_recovery.py`, `test_community.py` | PASS existing regression | Registration still indicates existing email; no production timing study |
| Browser OAuth | Login-CSRF attacker | Provider callbacks | Transfer state/unsigned Apple email | Browser nonce binding, verified signed identity | `test_security_hardening.py` OAuth tests | PASS mocked provider | Real browser/cookie/device provider flow unverified |
| Private messages | User C/staff | GET pair history/report | IDs/pagination/sender spoof | Auth sender, pair query, party-only report | `test_message_endpoint_sender_identity_pagination_export_and_notifications` | PASS actual endpoints | Authorized recipients can copy content |
| Messaging consent | Blocked user | Send/read | Alternate endpoint bypass | Mutual follows/opt-in, current mutual block | Same new test; `test_mutual_follow_messages_blocking_and_private_profiles` | PASS | Old history remains accessible after unfollow unless blocked |
| Message availability | Spammer | POST messages | Oversized body/flood | 3000 characters, 30/hour/account | `test_message_flood_bound_and_deleted_account` | PASS | Distributed/new-account spam needs operator controls |
| Message deletion consistency | Concurrent sender | Send + account delete | Late insert after deletion | Ordered account locks/live checks | `test_postgres_migrations.py` concurrent actual HTTP test + shared-lock contention | PASS real PostgreSQL | Other account mutation/provider deletion races not exhaustive |
| DB message/purchase/action secrets | Snapshot reader | Raw SQL/dump | Read unencrypted fields | AEAD outside DB key ring | `test_private_storage_snapshot_and_legacy_backfill`; PG encrypted purchase assertion | PASS | Metadata/private JSON/coordinates still readable; deployment backfill mandatory |
| Encrypted data integrity | Storage attacker | GET messages | Corrupt ciphertext/cross-field substitution | AEAD tag/context, generic 503 | `test_tampered_private_data_fails_closed_without_disclosing_storage`; `test_aead_nonce_rotation_tampering_and_field_binding` | PASS | Same-field row replay/full DB-write compromise not prevented |
| Key lifecycle | Operator error | Settings/backfill | Missing/bad key, old-key removal, repeat backfill | Startup fail-closed, versioned ring, bounded utility | Encryption tests; `test_backfill_rotation_is_bounded_resumable_and_verified` | PASS | Secret-manager compromise/key loss/backup restore require operations |
| Private neighborhood | User | Follow targets | Infer private-only profile location | Public/active/unblocked user filter | `test_private_neighborhood_cannot_leak_via_discovery_targets` | PASS | Public event/place neighborhoods remain public by design |
| Private watches/library/export | User/guide/mod/admin | Watch CRUD/feed, collections/export | Cross-account object access | Owner filters, not staff bypass | `test_private_object_matrix_does_not_grant_staff_owner_bypass` | PASS four role cases | No universal read-only privileged export audit bypass exists |
| Organization ownership | Organizer B/mod | Org patch/role patch/claim | Cross-org takeover/admin escalation/race | Approved membership/admin role, shared org lock | New org boundary test; existing claim tests; PG contention | PASS | Compromised admin can exercise existing authorized capabilities |
| Public events | Malicious source | Ingestion | Weaker source overwrites shared venue | Only fill missing geography; correction moderation | `test_weaker_source_cannot_poison_shared_venue_coordinates` | PASS | First-write/source truth and stolen ingestion credentials remain risks |
| Canonical events | Malicious repost/source | Ingestion/maintenance | Duplicate, false removal, weak facts, reschedule | Conservative matching, quality/manual overrides, provenance/healthy-source removal | `test_ingestion.py`, `test_crawler_v2.py`, Level 3 dedup tests | PASS existing regression | Not a fact-verification service; ambiguous evidence needs moderation |
| Level 3 event/source privacy | Contributor | Submission -> approval -> learning | Draft/rejected/private data, retry amplification | Structured evidence, approval, durable bounded idempotent JSON outbox | `test_level3_discovery.py` | PASS | Allowed public URL may later fail qualification; event remains valid |
| Crawler/internal network | URL/DNS attacker | Every Scrapy request/redirect | localhost/private/mapped/integer/octal/hex/IDN/redirect/rebind | Syntactic policy; reject ANY private DNS answer; pinned resolver | New crawler `test_every_request_and_redirect_rejects_non_public_dns`; existing pin/rebinding test | PASS mocked DNS | Public-only browser firewall not provided by assertion flag |
| Candidate queue | Contributor/bot | Evidence/inspection | URL normalization/domain spam/trust bypass | Domain dedup, 250 queue cap, 3 evidence, 25 outbox batch, 5 attempts, qualification | Level 3/API/crawler V2 tests | PASS existing regression | Many independent public domains can exhaust bounded queue |
| Parser availability | Hostile website | JSON-LD/HTML | Deep recursion/event amplification | 5 MiB HTML, 2 MiB JSON total, 32 scripts, depth64/nodes10000/events100 | New `test_deep_json_and_wide_event_lists_are_bounded` | PASS | Native parser/library CPU bugs and aggregate concurrency still matter |
| Feed/worker availability | Hostile publisher | RSS/Atom/ICS/download | Entities, huge bytes/recurrence, redirects/outage | Feed2 MiB, DTD deny, occurrence32, source job/download/redirect bounds | New entity/recurrence test; `test_crawler_v2.py`; discovery worker tests | PASS fixtures | No comprehensive compressed-bomb/native parser fuzz campaign |
| Consumer purchase/entitlement | Payment fraudster | Play verify/restore/RTDN | Wrong account/package/product, replay, expired state | Provider authority, owner hash/binding, receipt dedup, locks, Plus dependency | `test_google_play_billing.py`, `test_entitlements.py` | PASS provider mocks | Real Play console/transport/outage behavior not end-to-end tested |
| Stripe consumer/org billing | Payment fraudster | Checkout/reconcile/webhooks | Forged signature/wrong owner/product/stale state | Signed webhook + current provider refetch + stable owner mapping | `test_consumer_billing.py`, `test_organization_billing_regression.py`, platform | PASS mocks | Provider secrets/console/real renewals need live authorized tests |
| Group private decisions | Invite holder/free participant | Detail/preferences/match/vote | Read others' preferences, impersonate host, gain Plus | Membership/private own inputs/host-only generation/server entitlement | New participant boundary test; `test_groups.py` | PASS | Legitimate stolen invite permits joining until rotation/expiry |
| Group lifecycle | Participant | Join/vote/remove/reveal | Duplicate joins/capacity/hidden votes/completed mutations | Unique constraints, group locks, lifecycle checks | `test_groups.py`, PG group lock test | PASS | True multi-HTTP lifecycle stress beyond message race not exhaustive |
| Area Watch privacy/availability | Nonowner/Plus client | CRUD/feed/cursor/seen | Guess IDs, huge radius, null update, old seen marker | Ownership, caps/radius/schema, row lock/monotonic seen | `test_area_watches.py`; new null/staff matrix; PG locks | PASS | Coordinates intentionally stored; expiry allows owner definition read/delete |
| Avatars/media | Malicious uploader | Avatar upload/media URL | MIME/executable/path/EXIF/image size | JPEG/PNG/WebP decode/re-encode, UUID paths, limits/EXIF strip | Community avatar test + body/UNC tests; code review | PASS limited fixtures / REVIEW | Not a full malformed-image fuzz corpus; private-profile avatars have public URLs |
| Mobile identity/private cache | Compromised account | Logout/hydrate/request | User A response appears under B | Session revision, serialized secure writes, QueryClient clear | `sessionSecurity.test.mjs`, `locationSecurity.test.mjs` | PASS executable mocks | Same-origin XSS/rooted device/screenshot handling require device testing |
| External links | Hostile source | Event/source opener | javascript/data/file/custom/credential URLs | Browser HTTP(S)-only opener | `externalUrl.test.mjs` | PASS pure code | Router malformed decoding advisory/device deep-link handling remains |
| Private notification content | Message sender | DB notification/inbox | Body preview leak | Generic message notice, owner read/mark-read | New message endpoint test | PASS | No push implemented; no lock-screen guarantee claimed |
| Logs/private requests | Log reader | Validation/SMTP/HTTPX/SQL | Body/password/token/coord leak | Sanitized validation, URL/SMTP redaction, no request body logging, hidden SQL params | Recovery/security-hardening/new message caplog tests | PASS fixtures / REVIEW | Operators must also redact reverse-proxy/crash/third-party logs |
| Search/server caches | User | Event/people SQL search | Private index/cache disclosure | Public SQL profile filters, no message search; no Redis/OpenSearch clients | Code inspection + profile/neighborhood tests | REVIEW + PASS relevant endpoints | Future search/cache integration needs a new security gate |
| Export/deletion | Cross-account attacker | Own account endpoints | Other pair/preferences/secrets; reuse deleted bearer | Auth-derived user, limited serialization, erasure/version bump | Community/billing/groups/watch/new chat tests | PASS | Rejected evidence/public tombstones/backups/provider cleanup are policy/operations gaps |
| Public HTTP | Abusive client | Forms/map/export | Oversized bodies/unbounded SQL/CSRF/Host attacks | 1 MiB body, form/map bounds, rate buckets, bearer auth, explicit CORS/Host | `test_platform.py`, `test_security_hardening.py` | PASS fixtures | Proxy/DDoS budgets, large account histories and exact client IP need deployment validation |
| Admin/internal actions | Compromised staff/key | Admin/crawler/ingestion | User -> admin; missing internal key | Current role/key checks and audit | Community/crawler-admin/Level3/production internal-key tests | PASS | Admin/ingestion credential compromise can still alter authorized data |
| Containers/storage | Dependency exploit | App container/volumes | Privilege escalation/host access | Prod capability drop/no-new-privileges; internal DB; no Docker socket | UID10001 read-only source/cap-drop platform tests: 7 passed | PASS isolated / UNVERIFIED production | Root defaults, volume UID migration, bootstrap DB role, backups need rollout |
| Web/TLS/CSRF | Network/web attacker | Caddy/public API/OAuth cookie | Plain HTTP, framing, cookie-CSRF | HTTPS config, HSTS/frame/no-store, bearer APIs, OAuth nonce | Production Settings + prior header review/config tests | PASS configuration / UNVERIFIED live TLS | Internal HTTP/DB plaintext; browser XSS/CSP/provider cookies not live tested |
| Toolchain | Supply-chain attacker | Expo archive/CSS/schema tooling | tar traversal, PostCSS/AJV advisories | Compatible major8 patches, archive compatibility/traversal regression | `toolchainSecurity.test.mjs`, exports/build, npm audit | PARTIAL | CRITICAL tar remains; tar7 override actually failed Windows CLI; no forced replacement |
| Secrets/history | Repository reader | Git/config | Committed production credentials | Read-only pattern scan all 312 local commits | `git log --all -G` provider/key/PAT and named-secret patterns | No real credential established | Not exhaustive entropy scan/remote history; generated tests/placeholders only |

## Exact validation and commands

From repository root, API suite in a disposable container:

```powershell
docker run --rm --workdir /tmp -e PYTHONPATH=/app -e ENVIRONMENT=development -e DATABASE_URL=sqlite:////tmp/application-test.db -v C:/Users/saeed/Documents/BACity/BACity-/services/api:/app bacity--api python -m pytest /app/tests -q --disable-warnings
```

Result: **286 passed, 1 skipped, 11369 warnings, 238.64 s**. Only skipped test is
the opt-in PostgreSQL test, executed separately below. New adversarial file adds
38 cases. Entire API suite runs with fresh test-only encryption keys, preserving
auth/recovery/chat/payment/premium/contribution/normal discovery behavior.
Focused development runs: adversarial + platform + community, 52 passed;
adversarial + entitlements, 41 passed. Full final suite is the authoritative count.

Crawler:

```powershell
docker run --rm --workdir /repo/services/crawler -e ENVIRONMENT=development -e DATABASE_URL=sqlite:////tmp/crawler-test.db -v C:/Users/saeed/Documents/BACity/BACity-:/repo bacity--worker sh -c 'python -m pip install -q -r /repo/services/api/requirements.txt && python -m pytest tests -q --disable-warnings'
```

Result: **112 passed, 8.32 s**. API requirements installation is confined to the
disposable worker container for cross-service fixture tests. New crawler file: 17 passed.

PostgreSQL instance: existing `bacity--postgres-1`, PostGIS 16-3.4, private Docker
network `bacity-_default`. Bootstrap `bacity_migration_test` was created only after
checking absence. URL form (credentials not printed):
`postgresql://<configured-user>:<PASSWORD-REDACTED>@postgres:5432/bacity_migration_test`.
The test creates/drops its own additional `bacity_test_<uuid>` DB.

```powershell
docker run --rm --network bacity-_default --workdir /tmp -e PYTHONPATH=/app -e ENVIRONMENT=development -e DATABASE_URL=sqlite:////tmp/pg-runner.db -e TEST_POSTGRES_URL=$isolatedUrl -v C:/Users/saeed/Documents/BACity/BACity-/services/api:/app bacity--api python -m pytest /app/tests/test_postgres_migrations.py -q --disable-warnings
```

Result: **1 passed, 66 warnings, 9.04 s**. Full migrations to 0013, downgrade/re-upgrade, JSONB/constraints/
indexes/FKs/provenance/learning, group/watch/org/user lock contention, encrypted Play
token and actual concurrent HTTP message-send/account-delete verified. Bootstrap and
random DBs dropped; cluster check showed no remaining test DBs. `bratislava_events`
was never a test URL or mutation target. No migration added.

Mobile directory:

```powershell
$testFiles = @(rg --files src | Where-Object { $_ -match '\.test\.(mjs|cjs)$' })
node --experimental-strip-types --test $testFiles
npm run typecheck
npx expo config --type public --json
npx expo export --platform all --output-dir C:/Users/saeed/AppData/Local/Temp/bacity-threat-model-final-20261005
```

**74 passed, 0 failed**; TypeScript/config/export passed. Exports include web,
Android and iOS bundles; iOS export is NOT a native Xcode/device validation.
Native Android `android/gradlew.bat assembleDebug --console=plain` with installed
JDK17/Android SDK: **BUILD SUCCESSFUL, 915 tasks (54 executed, 861 up-to-date), 22 s**
on final dependency state. No emulator/device testing was performed.

Non-root/cap-dropped API smoke/regression:

```powershell
docker run --rm --user 10001:10001 --cap-drop ALL --security-opt no-new-privileges --workdir /tmp -e PYTHONPATH=/app -e ENVIRONMENT=development -e DATABASE_URL=sqlite:////tmp/application-test.db -v C:/Users/saeed/Documents/BACity/BACity-/services/api:/app:ro bacity--api python -m pytest /app/tests/test_platform.py -q --disable-warnings -p no:cacheprovider
```

**7 passed, 8.36 s**. This proves those isolated paths, not production volume ownership.
Docker build secret/data exclusion patterns: **12 checks passed**. Development
`docker compose config --quiet` passed. Production rendering is blocked
by missing deployment domains/environment file, not bypassed with invented secrets.

`npm audit --json --ignore-scripts`: nonzero, **82 affected package entries**
(1 critical/54 high/26 moderate/1 low); PostCSS and AJV absent from final advisory map.
`pip-audit -r services/api/requirements.txt -r services/crawler/requirements.txt --format json`
inside disposable API image: nonzero, **22 entries / 12 distinct IDs / 5 packages**.
No advisory suppression; registry metadata can change between runs.

## Gate disposition

No new P0 application bypass was established within these tested paths. Confirmed
P1/P2 defects were fixed and tested; known critical toolchain and deployment risks
remain. This is NOT unconditional production approval. Before release: perform
encrypted backfill/key/backup rehearsal, coherent tar/framework upgrades, proxy/TLS/
egress/non-root/least-privilege rollout, real provider/device testing and the separately
scoped legal retention decisions. Re-run/update this matrix after those changes.
