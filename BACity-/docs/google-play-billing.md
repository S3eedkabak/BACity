# Google Play consumer billing

Branch: `payment-int`. Starting commit: `d8134428f7a6ddc40c5c2c3c822073560e0bc4fd`.

## Release status

Implemented with automated provider-boundary tests, not a real Play purchase.
Google Play Console credentials, products and sandbox verification are still required.
Billing is disabled by default; missing configuration never grants paid access.

**Production release blocker:** the preserved Expo 51 / React Native 0.74.5 /
Kotlin 1.9 stack uses `react-native-iap` 12.16.4 and Play Billing 7.0.0, with
Android target API 34. As of October 4, 2026, normal Play submissions require
Billing 8+ and target API 36. Extensions may be available until November 1,
2026, but are not assumed. A separately authorized/tested platform upgrade is
required before normal store release. Forcing Billing 8 into this old adapter
is unsafe: it still uses removed `queryPurchaseHistoryAsync` and no-argument
`enablePendingPurchases` APIs. No major dependency upgrade was performed.

Sources: [Billing deadlines](https://developer.android.com/google/play/billing/deprecation-faq),
[target API policy](https://support.google.com/googleplay/android-developer/answer/11926878).

## Architecture and contracts

Android paywall → Play subscription/base-plan UI → opaque purchase token →
authenticated BACity verification → Google Android Publisher subscriptionsv2 →
existing `ConsumerSubscription` → unchanged `EntitlementService` → existing
account-scoped `/users/me/entitlements` refresh. Local purchase callbacks do
not grant access or set entitlement cache entries.

Web retains consumer Stripe checkout/portal/reconciliation. Organization
Stripe endpoints, models and subscription tiers are unchanged and isolated.
iOS explicitly reports purchasing unavailable; existing verified access works.

Authenticated routes:

- `GET /billing/google-play/config`: configured flag, public package/product/
  base-plan IDs, obfuscated BACity account ID, safe subscription/entitlement
  state and whether another paid provider is active. No service-account data.
- `POST /billing/google-play/verify`: object body
  `{ "purchase_token": "<opaque Play token>", "product_id": "<configured product>" }`.
  Token length 10–4096; product ID 1–255 characters. Provider state, price,
  expiry, package and entitlement values supplied by a client have no authority.
  Response: `active`, `expires_at`, `management_channel`, `subscription_status`,
  `cancel_at_period_end`. No provider identifiers, scores or tokens.
- `POST /billing/google-play/reconcile`: refetches at most 10 current account
  records and returns safe aggregate entitlement plus reconciled count.

Provider/internal routes:

- `POST /billing/google-play/rtdn`: authenticated Pub/Sub push envelope;
  requires Google-signed RS256 OIDC JWT, expected audience, Google issuer,
  expiration/issued-at claims and verified expected service-account email.
  Signing keys come only from Google's fixed certificates endpoint. Package
  and product must match configuration. Authenticated Console test messages
  are accepted. Unbound purchases are ignored, never assigned from arbitrary
  notification account metadata. Replacement purchases are recovered by restore.
- `POST /billing/google-play/reconcile-batch?limit=50`: requires configured
  `INGESTION_API_KEY` via `X-Ingestion-Key`, including in development. Bound
  1–100, ordered by oldest reconciliation, excludes replaced/missing-token
  records, isolates provider failures and advances attempted timestamps so one
  failing record cannot starve the batch. This adds no automatic scheduler.
  Schedule this endpoint privately (e.g. limit 10 every 15 minutes), with an
  HTTP timeout allowing provider requests; never expose the ingestion secret
  in mobile or command logs.

## Ownership, idempotency and acknowledgement

Play purchase initiation supplies `obfuscatedAccountIdAndroid = SHA256(BACity
user UUID)` obtained from the authenticated backend. First registration of a
token requires Google's authoritative `obfuscatedExternalAccountId` to match.
An already-bound token cannot move to another BACity account; conflicts do
not disclose its owner. Purchases lacking binding metadata are not adopted
as new subscriptions; account recovery for legacy/out-of-app purchases needs
support and a separately defined verified ownership procedure.

The existing `(provider, external_subscription_id)` uniqueness constraint
stores SHA256(token) for Google; the token itself goes in the restricted
nullable TEXT `provider_purchase_token` column. This is required because an
opaque token may exceed the old indexed VARCHAR(255) field. Migration `0012`
adds only that column; existing Stripe identifiers/data remain unchanged.
Do not downgrade after real Google deployment without backing up/recovering
provider credentials: removing the column removes reconciliation tokens.

Provider-linked replacement tokens retire the old same-account record;
foreign-account replacement links are rejected. Replaced records cannot be
restored into active state. Account row locks serialize provider refetches,
and native duplicate callbacks are coalesced during verification.

Server acknowledgement uses the configured product only after Google has
verified product/base plan, binding and a purchased eligible state. Verified
state is committed before acknowledgement; acknowledgement failure is
retryable without another subscription row. RTDN changes and durable receipt
commit atomically; failed notifications can retry. PostgreSQL advisory locks
serialize receipt processing; replay uses existing `ProviderEventReceipt`.
Out-of-order notifications always refetch current Google state.

## State policy

| Google state | Stored state / BACity+ |
| --- | --- |
| ACTIVE, known future expiry | active, eligible |
| CANCELED, known future expiry | active, cancellation flag, eligible until expiry |
| ACTIVE/CANCELED with elapsed verified expiry | expired, ineligible |
| EXPIRED / PENDING_PURCHASE_CANCELED | expired, ineligible |
| IN_GRACE_PERIOD | grace_period, ineligible (no product grace policy invented) |
| ON_HOLD | on_hold, ineligible |
| PAUSED | paused, ineligible |
| PENDING | pending, ineligible, not acknowledged as purchased |
| Unknown/missing validity | unknown, ineligible |

Renewal/recovery/cancellation/refund/revocation notifications trigger current
provider refetch, not entitlement changes from their notification label.
Known expiration also stops access without awaiting a notification.
Any valid subscription/grant remains sufficient according to the unchanged
generic entitlement service; expired Google cannot override valid Stripe.

New Google token verification is blocked while another paid provider is
currently valid. Restoring an existing bound Google token remains possible.
Android also hides purchase initiation for any active entitlement. Provider
migration is possible after the previous paid subscription expires. There is
no automatic cross-provider cancellation, refund or prorating.

## Privacy and account lifecycle

Tokens are not in public responses, account exports, analytics or application
logs. Google token-bearing URLs in httpx INFO logs are redacted. Billing
validation errors do not echo submitted input. Provider errors are generic;
UI does not display raw Google errors. Service-account JSON stays server-only.
Stored tokens are restricted plaintext provider credentials (no new encryption
key infrastructure); protect database/backups and limit database operator access.

Account deletion refetches Google before erasure and fails closed on provider
outage or disabled verification. Active, grace, hold, paused, pending or unknown
subscriptions block deletion, since recurring billing could recover later.
User must manage/cancel through Google and wait for verified expiration.
Expired/replaced token records are erased before normal anonymization.
BACity does not claim to cancel Play subscriptions on the user's behalf.
Existing Stripe deletion behavior and safe export selection remain unchanged.

## Human configuration

1. Resolve the native release blockers above in a separate scoped upgrade.
2. Create/associate the Play app with `com.bratislavaevents.app`, matching
   `app.json` and the Android application ID. Configure signing and release
   version codes for your actual Play app; do not change package casually.
3. In Play Console Monetize → Products → Subscriptions, create your actual
   BACity+ subscription. Create and activate an auto-renewing base plan,
   configure prices/countries and select the identifiers below. V1 purchases
   a base plan without promotional/trial offers and displays the localized
   recurring price/period returned by Google, not hardcoded pricing.
4. Enable Google Play Android Developer API in Google Cloud. Create a dedicated
   backend service account; add/invite its email in Play Console Users and
   permissions with access to this app and permissions to view purchases/
   subscriptions and manage orders/subscriptions needed for verification and
   acknowledgement. Keep permissions app-scoped where possible. Provision
   credentials in your server secret manager; never paste them in chat.
5. For RTDN create a Pub/Sub topic. Grant
   `google-play-developer-notifications@system.gserviceaccount.com` Publisher
   access to that topic. Configure the topic in Play Console Monetization setup.
6. Create an authenticated HTTPS push subscription to your public
   `/billing/google-play/rtdn` URL. Select a dedicated push-auth service account,
   set the audience exactly, and give Pub/Sub's service agent the token-creation
   permission required for authenticated push. Configure retry/dead-letter
   handling; send a Console test notification and confirm HTTP 200.
7. Add Google accounts as Play license testers and internal-track testers.
   Publish/install an eligible signed build through the testing track, with
   the correct Play account logged in. Expo Go is not supported for purchases;
   use a native build. Product availability can take time to propagate.
8. Apply Alembic head before enabling billing. Set backend environment variables
   below, restart API and maintenance callers, configure private reconciliation.

Backend-only variables (`.env`/deployment secret configuration, never mobile):

| Variable | Value / classification |
| --- | --- |
| GOOGLE_PLAY_BILLING_ENABLED | `false` default; enable only after setup |
| GOOGLE_PLAY_PACKAGE_NAME | actual application ID; public-safe |
| GOOGLE_PLAY_SUBSCRIPTION_PRODUCT_ID | actual subscription ID; public-safe |
| GOOGLE_PLAY_BASE_PLAN_ID | selected base plan; public-safe, optional server filter |
| GOOGLE_PLAY_SERVICE_ACCOUNT_JSON | complete JSON credentials; SECRET |
| GOOGLE_PLAY_RTDN_AUDIENCE | exact authenticated push audience; public-safe |
| GOOGLE_PLAY_RTDN_SERVICE_ACCOUNT_EMAIL | expected push identity; server configuration |
| INGESTION_API_KEY | internal reconciliation authentication; SECRET |

RTDN audience/email are paired. No production product IDs were invented.
Mobile obtains public configuration from BACity; no new EXPO_PUBLIC secret
settings. Existing `EXPO_PUBLIC_API_URL` resolution stays unchanged.
Development grant settings/semantics remain independent of real billing.

## Manual Google sandbox E2E (not performed here)

1. Sign in as a Free BACity account in the eligible installed test build.
   Open `/plus`; confirm localized recurring price and period, then subscribe.
2. Choose a Google test payment method. Confirm local callback shows verifying,
   backend verification/acknowledgement completes, account-scoped entitlements
   refresh and BACity+ becomes active. Access a premium tool.
3. Restart app, logout/login, reinstall or use a second eligible device with
   the same BACity account. Server entitlement survives; Restore Purchases
   verifies provider tokens again. Repeat restore; no duplicate subscriptions.
4. Cancel the purchase sheet: no entitlement changes. Test declined/slow test
   payments where Google provides them; pending must not grant access.
5. Cancel renewal in Google: restore/reconcile, verify active until provider
   expiry and cancellation notice. Use accelerated sandbox renewal/expiry;
   confirm access disappears. Revoke/refund using available Console test tools.
6. Verify RTDN delivery/replay/retry and run private batch reconciliation after
   a temporarily disabled push delivery. Check provider state, not raw payloads.
7. Retry purchase/verification twice; one subscription row. Switch BACity
   accounts while requests are in progress; old results must not update the
   new account's UI. Try restoring the same Play purchase into a different
   BACity account: generic conflict, no premium access.
8. Open Android paywall as active Stripe subscriber: no second purchase offer.
   Confirm web Stripe checkout/portal still work and organization plans do not
   grant consumer Plus. Test active Google + expired Stripe and the reverse.
9. Export account: no tokens/provider transaction IDs. Attempt deletion with
   active/held/grace subscription: blocked. Cancel, wait for verified expiration,
   delete: token links erased. Provider outage must fail closed.

Normal purchase/cancel/restore/restart/accelerated expiry and selected payment
failure/revocation cases can be tested with Console/test payment facilities.
Forged products, ownership theft, out-of-order notifications, exact grace/hold/
paused mappings, provider outages and replay are also covered by automated
provider mocks; real lifecycle availability depends on Google testing tools.

## Verification

Results:

- Full API: **163 passed, 1 skipped** (optional PostgreSQL URL absent in that run).
- Latest focused Google + consumer Stripe + organization + entitlement: **35 passed**,
  comprising Google **15**, consumer Stripe **10**, organization **2**, entitlements **8**.
- Crawler: **53 passed** in the combined ephemeral test runtime.
- Mobile: **61 passed** across all existing/new package test scripts; Play **7**,
  premium request contracts **3**, map **5**, Home/recommendations **6** included.
- TypeScript and public Expo config: **passed**.
- Latest web and Android exports: **passed**.
- Native Android `assembleDebug`: **passed**, 619 tasks (63 executed, 556 up-to-date).
- Real isolated PostgreSQL migration test: **1 passed**, including downgrade/re-upgrade,
  long TEXT credentials and existing Stripe record preservation. Test-created databases
  and `bacity_migration_test` removed. Normal `bratislava_events` was untouched.
- No attached Android emulator/device; **no real Google purchase performed**.

The final completion report records commit/push status.
Tests exercise provider mocks at the external boundary, real BACity routes/DB/
entitlement logic, signed OIDC validation, httpx privacy, actual Android adapter
callbacks/offer selection and actual API object serialization. They are not
native-device purchase tests. No emulator/device was attached during validation.

Commands used from repository root (API in existing Python 3.12 API Docker image):

```powershell
docker run --rm --mount 'type=bind,source=<repo>\services\api,target=/app' -e DATABASE_URL=sqlite:////tmp/bacity-play-application.db -e ENVIRONMENT=development bacity--api python -m pytest tests -q --disable-warnings
```

Crawler runs in an ephemeral existing worker image with the existing pinned
API requirements installed for its HTTP ingestion integration test; the
host's crawler-only venv lacked uvicorn. No repository dependencies were
changed to repair that test-environment limitation.

From `apps/mobile`: all `test:*` package scripts, `npm run typecheck`,
`npx expo config --type public`, `npx expo export --platform web --output-dir <temporary-directory>`,
equivalent Android export, and `android\gradlew.bat --project-dir android :app:assembleDebug --console=plain`.

PostgreSQL test uses existing Compose PostGIS 16/3.4 through a test-only base
database `bacity_migration_test` and automatically created/dropped
`bacity_test_<uuid>` databases. URL form:
`postgresql+psycopg2://<compose-user>:<PASSWORD-REDACTED>@postgres:5432/bacity_migration_test`.
Command inside the API test container:
`python -m pytest tests/test_postgres_migrations.py -q --disable-warnings`.
Checks migration chain, TEXT storage, uniqueness/constraints/indexes,
PostgreSQL row locks, downgrade/re-upgrade and preservation of existing Stripe
records across migration 0012. Normal `bratislava_events` data is never targeted.

## Files changed

- Configuration: `.env.example`, `apps/mobile/.env.example`,
  `services/api/app/config.py`, `apps/mobile/app.json`,
  `apps/mobile/android/app/build.gradle`, mobile `package.json` and lockfile.
- Backend: `services/api/app/core/google_play_billing.py`,
  `services/api/app/api/routes/google_play_billing.py`, `services/api/app/main.py`,
  account-deletion guard in `services/api/app/api/routes/community.py`,
  `services/api/app/models/entitlement.py`,
  `services/api/alembic/versions/0012_provider_purchase_token.py`.
- Mobile: `apps/mobile/app/plus.tsx`, `apps/mobile/src/api/googlePlayBilling.ts`,
  `apps/mobile/src/billing/playBilling.ts`, `playBilling.android.ts`,
  `playPresentation.ts`.
- Tests: backend `test_google_play_billing.py`,
  `test_organization_billing_regression.py`, `test_postgres_migrations.py`;
  mobile `src/billing/playPresentation.test.mjs`, `playAdapter.test.mjs`,
  `src/api/premiumContracts.test.mjs`.
- This document. No crawler, map, premium-feature orchestration or organization
  billing implementation files changed. No secrets or real `.env` files committed.
