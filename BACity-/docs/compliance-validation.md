# Compliance validation and implementation inventory

Branch crawler-v2; starting SHA 4d865ed2ac27153b186724df7ef9a6ef0b6ee361. Testing was local, mocked or isolated only. No deployment, provider attacks, contracts or real user-data changes.

## Initial pass results (historical baseline at 6b08cfb)

| Validation | Result |
|---|---|
| Complete API suite | 305 passed, 1 skipped, 12121 existing/deprecation warnings; final run 245.59 seconds |
| New privacy API properties | 19 new passing cases, included in complete suite |
| Focused development privacy/security | 53 passed before final two privacy tests were added; subsequent focused privacy/community 29 passed |
| Complete crawler suite | 112 passed; 10.60 seconds |
| Complete mobile tests | 77 passed, 0 failed (74 baseline plus 3 new privacy/permission tests) |
| TypeScript | npm run typecheck passed |
| Expo public config | passed |
| Web/Android/iOS JS export | passed; final export after account-keyed privacy form hardening |
| Native Android assembleDebug | BUILD SUCCESSFUL, 36 seconds; 915 tasks: 59 executed, 856 up-to-date |
| Real PostgreSQL/PostGIS migrations/security | 1 passed, 70 warnings; 10.17 seconds |
| Checklist/evidence/blocker integrity | 73 rows, valid statuses/columns, unique IDs, evidence for all rows; all 48 unresolved IDs in blocker register |
| Merged Android permission check | Camera/audio/background location/activity recognition absent; foreground coarse location retained |
| Development Compose | config validation passed |
| Production Compose | not validated: required API_DOMAIN/deployment environment unavailable |
| Diff whitespace | passed |

The normal full API run deliberately skips opt-in PostgreSQL. It was actually executed separately, not dismissed as an unavailable test. Native iOS compilation/device E2E, screen-reader testing, production proxy/provider/contract configuration and real store submission were not performed. Mobile source assertions and mocked transport are not rendered device UI tests.

## Commands

Run API in disposable container; mount source but keep SQLite test files under /tmp:

```powershell
docker run --rm --workdir /tmp -e PYTHONPATH=/app -e ENVIRONMENT=development -e DATABASE_URL=sqlite:////tmp/application-test.db -v C:/Users/saeed/Documents/BACity/BACity-/services/api:/app bacity--api python -m pytest /app/tests -q --disable-warnings

docker run --rm --workdir /repo/services/crawler -e ENVIRONMENT=development -e DATABASE_URL=sqlite:////tmp/crawler-test.db -v C:/Users/saeed/Documents/BACity/BACity-:/repo bacity--worker sh -c 'python -m pip install -q -r /repo/services/api/requirements.txt && python -m pytest tests -q --disable-warnings'
```

Mobile directory:

```powershell
$testFiles = @(rg --files src | Where-Object { $_ -match '\.test\.(mjs|cjs)$' })
node --experimental-strip-types --test $testFiles
npm run typecheck
npx expo config --type public --json
npx expo export --platform all --output-dir C:/Users/saeed/AppData/Local/Temp/bacity-compliance-final-export-20261005
```

Android directory with installed JDK17/SDK:
`gradlew.bat assembleDebug --console=plain`.

PostgreSQL instance: existing bacity--postgres-1, postgis/postgis:16-3.4, network bacity-_default. Created only bacity_privacy_test after verifying absence; existing integration test creates a second random bacity_test_UUID. TEST_POSTGRES_URL form:
`postgresql://<configured-user>:<PASSWORD-REDACTED>@postgres:5432/bacity_privacy_test`.

```powershell
docker run --rm --network bacity-_default --workdir /tmp -e PYTHONPATH=/app -e ENVIRONMENT=development -e DATABASE_URL=sqlite:////tmp/pg-runner.db -e TEST_POSTGRES_URL=$privacyTestUrl -v C:/Users/saeed/Documents/BACity/BACity-/services/api:/app bacity--api python -m pytest /app/tests/test_postgres_migrations.py -q --disable-warnings
```

Migration 0014 verified through actual chain to head, constraints/index/TEXT/FK SET NULL checks, AEAD raw storage and ORM decoding, existing security lock/concurrent deletion checks, downgrade and re-upgrade. Downgrade removes privacy-request records; test only in isolation, not a production erasure strategy. Both temporary databases dropped; final catalog check found zero test databases. Normal bratislava_events never targeted. Disposable containers --rm; exports remain in Windows Temp outside Git, not user data.

## Implemented behavior

/privacy/information exposes configured contact/document versions and factual location/message/recommender information, no fake policies or acceptance.
/privacy/requests provides authenticated own submit/list/detail; 5/day, 10 open, pages <=50.
/privacy/admin/requests provides admin-only metadata queue, audited detail read and locked assessed status/reply/extension workflow.
/privacy/portability reuses throttled complete account export to supply an explicitly described user-provided/observed subset, including sent messages only.
Account deletion redacts/detaches request data; account export adds only own cases. Inbound third-party blocks are no longer exported. Submission/report moderation audit entries no longer duplicate free-form evidence; existing role-change justifications remain for accountability.
New Privacy/Account routes expose existing controls and human review without redesign. Forms are keyed to account identity, private queries account-scoped, stale mutations/session-switched exports fail closed.
Native permissions are narrowed without removing foreground location/gallery capabilities; iOS checked-in purpose strings now match actual features.

## Intentional changed files

- .env.example (blank owner document/contact configuration; no secrets)
- apps/mobile/app.json
- apps/mobile/android/app/src/main/AndroidManifest.xml
- apps/mobile/ios/BratislavaEvents/Info.plist
- apps/mobile/app/account.tsx
- apps/mobile/app/auth.tsx
- apps/mobile/app/privacy.tsx
- apps/mobile/app/privacy-admin.tsx
- apps/mobile/src/api/privacy.ts
- apps/mobile/src/api/privacy.test.mjs
- services/api/app/config.py
- services/api/app/main.py
- services/api/app/models/__init__.py
- services/api/app/models/privacy.py
- services/api/app/api/routes/privacy.py
- services/api/app/api/routes/community.py
- services/api/app/private_data.py
- services/api/alembic/versions/0014_privacy_requests.py
- services/api/tests/test_privacy.py
- services/api/tests/test_postgres_migrations.py
- docs/account-lifecycle.md
- docs/encryption-and-key-management.md
- New compliance documentation: master checklist, evidence index, blockers, validation, data inventory, ROPA, flows, DPIA draft, notice facts, retention matrix, processors, transfers, breach response/register, DSA checklist, consumer subscription checklist, store privacy inventory, legal-review input, privacy operations.

Billing/entitlement/planner/crawler logic, welcome/splash and existing historical migrations were not modified. Existing security dependency risks remain unresolved rather than being silently waived.

## Manual follow-up (not performed)

Configure approved document URLs/versions/contact; migrate isolated staging and inject keys. Sign in A/B/admin/moderator, submit a case as A and verify B/moderator denial, admin metadata/detail and review, A generic notification/status/export, account-switch form clearing and deletion redaction. Test OS gallery/location with camera absent, denied permission/citywide mode, screen readers/small screens. Exercise signed-off erasure/subscription/provider operations with deployment-owned accounts. Rehearse incident and restored-deletion reconciliation with synthetic data before production.

## Owner-direction follow-up starting at 6b08cfb

See compliance-owner-followup.md for all eleven reviewed owner rows and the age-enforcement deferral. Product approval is not legal approval. Updated current checklist: 73 total; IMPLEMENTED 11, ALREADY SATISFIED 14, NOT APPLICABLE 2, OWNER 7, LEGAL 28, PROCESSOR 3, PRODUCTION 4, STORE 3, BLOCKED 1. All 46 unresolved IDs remain in the evidence/blocker registers; two resolved product controls remain in the blocker table for traceability, marked nonblocking.

Validation on final application code:

- Complete API: 308 passed, 1 skipped, 12237 existing/deprecation warnings in 263.47 seconds. Command as above, with disposable DATABASE_URL=sqlite:////tmp/owner-followup.db. Includes privacy (22 cases), auth/recovery, account deletion, messaging/security, Level 3 and all other API regressions. Opt-in PostgreSQL skipped intentionally: no schema changes; prior isolated migration evidence remains historical, not a new run.
- Focused development: privacy/community/security initially 71 passed, 1 failed; failure was obsolete public event-history expectation. Updated to require public suppression plus preserved own history; complete suite then passed. No tests disabled.
- Mobile: 78 passed, 0 failed, 1231.441 ms using existing node test command. Focused privacy tests: 4 passed, 0 failed. New test executes transpiled conversation-profile fallback and checks 404 anonymized identity versus 401/403/500 propagation and UI wiring; not rendered device testing.
- npm run typecheck passed.
- Checklist columns/status/evidence/unresolved-blocker integrity passed; whitespace and staged scope reviewed.
- No schema changes/migration verification, native rebuild, exports or device E2E in this follow-up; none claimed. No crawler logic changed; API Level 3 regressions included, separate crawler suite not rerun.
- Disposable --rm test container removed automatically; test SQLite remained inside container /tmp. No real user/development database targeted or temporary PostgreSQL database created.

Intentional code/config files: .env.example; mobile app/messages/index.tsx, app/messages/[userId].tsx, app/privacy.tsx, src/api/community.ts, src/api/privacy.ts, src/api/privacy.test.mjs; API app/config.py, app/api/routes/privacy.py, app/api/routes/community.py, app/schemas/event.py; tests/test_privacy.py, test_community.py, test_adversarial_security.py and test_postgres_migrations.py (existing concurrency expectation follows the approved shared-record semantics).
Intentional documentation: compliance-owner-followup.md (new); account-lifecycle.md, compliance-master-checklist.md, compliance-evidence-index.md, compliance-launch-blockers.md, compliance-validation.md, data-breach-response.md, data-retention-policy-matrix.md, legal-review-input.md, privacy-data-inventory.md, privacy-notice-facts.md and privacy-operations.md.
Billing/planners/crawler/native configuration/dependencies/welcome screens untouched. No personal owner details or secrets added; blank environment-backed contacts require owner configuration. Production deployment not performed.
