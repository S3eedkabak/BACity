# BACity implementation checkpoint — 2026-09-25

This checkpoint implements the core community workflows on `new-impl-03`. It is **not the completed production launch or every feature in the roadmap**. Work was stopped at the owner's request to commit before the usage limit. No hosting, email or payment accounts have been supplied.

## Requirements separated by delivery area

| Area | Implemented in this branch | Still required |
| --- | --- | --- |
| 0. Foundation | PostgreSQL migration 0004 with rollback; production secret/HTTPS configuration validation; bounded request bodies; structured request IDs/logs; authentication and contribution rate limits; production Compose/Caddy and daily database backup configuration; CI API/crawler/mobile jobs | Select hosting/domain, configure real secrets and TLS/DNS, deploy and verify stack, off-site backup and restore drill, external monitoring/error reporting, deployment automation, performance/load/security review and additional spatial indexes |
| 0. Accounts | Email verification/reset with hashed single-use tokens; durable SMTP retries; Google/Apple OAuth; JWT revocation; complete JSON export; documented deletion retention, anonymization and recovery; provider-link erasure; blocking and role checks | Enter production secrets and execute the real-inbox/device acceptance matrix in `production-auth-runbook.md` |
| 1. Discovery | Existing scheduled crawler, bounded link discovery, persistent outbox, source health/run stats, stale detection, deduplication and provenance retained | Broader hyperlocal/university/neighborhood source onboarding and live extraction validation; source-health administration UI; advanced extraction for unsupported/JS-only sites. No claim of exhaustive internet coverage |
| 2. Submissions/trust | Event/place/utility forms; pending queue; approval/rejection, independent appeals, audit records and reports; source/date/coordinate validation; duplicate risk flag; verified email and velocity limits; trust labels | Automated source corroboration, richer spam/content/address checks, image upload/storage (HTTPS image URLs work), improved moderation evidence UI and duplicate merging |
| 3. Profiles/follows | Rich public profiles; cropped and server-sanitized avatar upload with persistent backup; paginated contributions, reviews, followers, following and people search; discoverable follow targets for users, guides, organizers, venues, neighborhoods and categories; blocking | Object storage/CDN migration if media volume outgrows a single host; advanced guide application and reputation abuse controls |
| 4. Guides | Separate identity flag, role permissions and computed reputation levels; admin-only role API; corrections API and collections API | Identity verification workflow, anti-gaming reputation rules, guide application process, complete correction/collection editing UI |
| 5. Reviews | Structured event/place dimensions; future-event review restriction; edit history; helpful votes; reporting/moderation; honest unverified attendance label | Attendance integrations, stronger anti-spam/reputation weighting, revision-history UI and finer review moderation |
| 6. Utilities | Official Bratislava public-toilet import and daily refresh; normalized utility data; native clustered toilet layer; viewport/nearby/detail queries; recency-weighted confirmation aggregation; confidence, freshness, conflicts and conservative stale handling | Add further official utility datasets as stable city feeds become available |
| 7. Recommendations | Explainable ranking from interests, saved categories, follows, time, freshness, location and real save counts; separate sponsored feed | Full feed UX, larger-scale ranking/evaluation, location consent/geolocation UI, popularity-abuse protection |
| 8. Organizers | Organization pages, evidence-based moderated claims, membership authorization, recurring event publication, in-app follower notifications and real aggregate analytics; dashboard | Complete editing/cancellation/update notification tools, ownership transfers, richer venue pages and recurring-series management |
| 9. Monetization | Optional hosted Stripe checkout and customer portal for organizations; signed/idempotent webhooks reconcile current provider state; disabled state without configuration; no invented prices; sponsored data model/feed separate from organic ranking | Stripe account/products/prices/webhooks, sandbox integration tests against Stripe, consumer Pro subscriptions, defined and enforced paid-feature entitlements, promotion purchase/moderation UI and affiliate integration. Do not enable charges until benefits and pricing are defined |
| 10. Messaging | Event comments; mutual-follow DMs; recipient opt-in for general DMs; block enforcement; message reporting; in-app notifications; configurable message retention maintenance | Real-time delivery/push, read-state/conversation inbox UX, advanced abuse controls, full messaging moderation UI |

## Validation performed

- 37 API tests passed, including community workflows, permission isolation, reset/revocation, billing signature/idempotency and SMTP retries.
- 36 crawler tests passed, including fixture-based HTTP end-to-end tests.
- Real PostgreSQL migration test passed: existing data → 0004 → rollback to 0003 → 0004.
- Mobile TypeScript type check passed. Two existing unsupported icon names were corrected.
- Web export passed with `npx expo export --platform web --max-workers 1` (785 modules). Production container deployment is unverified. No new native-device or browser interaction test has been completed for these screens.
- Existing running Docker services are not evidence that this new implementation is deployed. Migrate and restart deliberately after configuring your environment.

## Local setup

1. Copy `.env.example` to `.env`; generate a private ingestion key. For a local email inbox set `SMTP_HOST=mailpit`, `SMTP_PORT=1025`, `SMTP_STARTTLS=false`.
2. From `BACity-`, run `docker compose --profile dev-mail up -d --build`. API startup upgrades migrations; the maintenance service sends queued email and applies retention.
3. Read local verification/reset email at `http://localhost:8025`. Set `PUBLIC_APP_URL` to the actual Expo web address so links open `/account`.
4. Register and verify your administrator account, then run `docker compose exec api python -m app.admin your-email@example.com`. Sign in again. The CLI only bootstraps when no active admin exists; later role changes use the audited admin API.
5. In `apps/mobile`, run `npm ci`, then `npm run web`. Open Profile → Community, Account, or Organizer dashboard. Contributions require verified email.

## Production activation

Use the independent `compose.production.yml`, not the development file, with a private `.env.production` containing PostgreSQL connection settings, random JWT and ingestion secrets, `APP_DOMAIN`, `API_DOMAIN`, HTTPS `PUBLIC_APP_URL`/`CORS_ORIGINS`, and your SMTP settings. Set database hostname to `postgres`. Point both DNS names at the host, open ports 80/443, then run:

```sh
docker compose --env-file .env.production -f compose.production.yml up -d --build
```

The included backup service writes daily custom-format PostgreSQL dumps to a private Docker volume and retains fourteen days. This does not protect against losing the host: configure off-site copies and test restore before launch. Back up before schema changes; migration 0004 downgrade removes community data. Test rollback in staging instead of downgrading a populated production database casually.

Stripe is optional and disabled without credentials. Checkout uses configured recurring Price IDs and hosted checkout; webhook route is `/billing/webhook`. Subscribe to `checkout.session.completed` and subscription created/updated/deleted events. The implementation follows [Stripe Checkout](https://docs.stripe.com/api/checkout/sessions/create) and [raw-body webhook signature verification](https://docs.stripe.com/webhooks/signature). Existing tests mock provider responses; a real Stripe sandbox test remains required.

## Suggested next work order

1. Browser/native end-to-end QA, production container build and staging deployment.
2. Finish moderation evidence, organizer event management, deletion cleanup and abuse controls.
3. Expand crawler source coverage and utility map/data integration.
4. Complete guide/collection/profile workflows and messaging UX.
5. Define paid benefits, enforce entitlements, then activate and verify billing.
