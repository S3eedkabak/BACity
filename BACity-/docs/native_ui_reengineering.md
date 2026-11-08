# Native UI reengineering — 2 November 2026

Implementation is local on `ui/spectrum-native-20261102`. All eleven requested native interaction patterns have production integration paths. Full application/device acceptance remains partial; this is not production approval.

## Architecture

`src/components/interactions` contains presentation primitives and feature wrappers. Feature hooks centralize save/follow state in the existing session-separated React Query cache. Synchronous per-entity gates prevent duplicate native events before rerender, reversible mutations roll back only their own entity, and existing authenticated response/session guards remain. Undo restores a desired saved state rather than toggling blindly.

`src/theme/appearance.ts` supports system/light/dark with a persisted device preference. Lazy per-theme sheets plus subscribed renders update existing screens without remounting routes or losing drafts. Original dark colors and brand primary `#A93468` remain. Reduced motion uses one shared live OS subscription; animations/haptics simplify accordingly.

Public event/place reviews use one FeedbackComposer/StarRating workflow. The backend still enforces verification, target eligibility, author identity, revisions and moderation. Password creation/reset guidance reflects the existing policy but is not an entropy estimator or breach check. Hold confirmation is a UX safeguard; account deletion still uses the original authorized endpoint and provider checks.

## Additive API contracts

- `GET /community/follow-state`: authenticated owner's relation for an existing supported target type/ID.
- `GET /community/review-summary/{type}/{id}`: visible/not-blocked per-dimension SQL aggregates and real count.
- `GET /community/notification-summary`: owner-scoped unread total/message subset.
- Existing `/community/notifications` adds bounded offset/limit while preserving its default response shape.

New read APIs share the existing 600/minute/account atomic budget. No model or migration was added. Deploy backend contracts before the updated client; roll back client/API contracts together. No push permission or new push infrastructure is introduced.

## Verification

Mobile: **185 passed** (baseline 162). API: **659 passed, 8 optional skips** (baseline 654/8). Separate security/auth/billing selection: **130 passed**. Dedicated disposable PostgreSQL migration/security regression: **1 passed**. TypeScript and production JavaScript/Hermes exports for iOS/Android/web pass. No configured lint pass, signed native build, real-provider/device or FPS/startup claim.

Run from `apps/mobile`:

```sh
npm test
npm run typecheck
./node_modules/.bin/expo export --platform all --output-dir /tmp/bacity-ui-export
```

API tests must run with isolated settings/storage, outside the directory that loads the live development `.env`. Do not point tests or migrations at the application database.

Current npm audit remains nonzero (3 critical, 24 high, 42 moderate, 3 low affected entries). Physical device/VoiceOver/TalkBack/performance and full screen-specific visual acceptance remain pending. Production readiness is **NOT READY**.

Full local artifacts (report, 44-screen inventory, 32-item checklist, eleven-component matrix, exact tokens, screenshots, measured bundle deltas and raw verification logs):

`/Users/s3eed/.codex/.chatgpt-projects/g-p-6a94b492f5088191920f3f48c7c9c29f/outputs/ui-reengineering/REPORT.md`
