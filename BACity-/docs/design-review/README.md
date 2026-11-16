# BACity editorial design iteration

The proposed iteration makes the main discovery journey easier to scan: a shorter feature, compact event rows, explicit typography, consistent gutters and a shared brand foundation across native and staff UI. The recommendation is the refined **A — editorial guide** direction, implemented in the existing stack.

## Decision

Review the implemented screenshots first, then compare the Stitch concepts. Accept the editorial direction, request specific adjustments, or keep the baseline. This is a draft design decision, with no deployment or merge.

| Option | Evaluation |
| --- | --- |
| A: editorial guide | Recommended. Clear hierarchy, useful city imagery and a compact feed retain BACity's identity. |
| B: compact utility | Useful density, but generated variants truncate too much event context and introduce more repeated boxed surfaces. |
| A refined | Removes unsupported social/availability claims and repeated row surfaces. The native implementation retains real stateful saves and map access. |

These are qualitative design judgments, not invented user-research scores. Stitch-generated dates, venue claims and imagery are illustrative; only fixture data and existing app contracts were used in implementation.

## Good, bad, ugly — treatment

| Finding | Result |
| --- | --- |
| Good: theme lifecycle, real actions, shared components and test coverage | Retained; no framework, API contract, billing or crawler replacement. |
| Bad: repeated styles and mobile/staff drift | Canonical foundations with native adapters and generated staff CSS. Named control/card radii, shared gutters and end spacing. Staff CSS consolidated into one readable cascade. |
| Ugly: family names pretending to be font weights | `fontStyles` applies explicit weights across the existing callers. |
| Ugly: motion definitions with unclear ownership | One canonical source with compatible named interaction/navigation profiles. |
| Ugly: ten ambiguous card variants and an unused prop | Explicit presentation mapping, removed unused `entranceDelay`, shared event metadata and extracted featured composition. Existing bounded entrances are owned by ContentEntrance. |
| Ugly: screen/transport coupling | Extracted discovery and profile-activity hooks with cancellation/stale-response tests; map tray extracted without moving camera/query ownership. |
| Largest-text crowding found during review | Logo stays fixed; navigation labels scale within a bounded layout; photo-backed cards grow with their content rather than clipping fixed overlays. |

The initial scan mapped 702 tracked files and 531 code/config files (53,542 lines under its extension filter). Its 1,186 numeric style literals were candidates, not 1,186 verified defects. Illustration geometry, map coordinates and purposeful local measurements remain. A full line-by-line security or correctness review is not claimed.

## Implemented comparisons

Browser captures use the real exported app, synthetic API fixtures, matched data and viewports. They are not production activity. The city photo is the existing repository welcome-video poster; events and the account are explicitly synthetic.

| Home before | Home after |
| --- | --- |
| ![Before Home dark](screenshots/before-home-dark.png) | ![After Home dark](screenshots/after-home-dark.png) |

| Explore before | Explore after |
| --- | --- |
| ![Before Explore light](screenshots/before-explore-light.png) | ![After Explore light](screenshots/after-explore-light.png) |

| Staff review before | Staff review after |
| --- | --- |
| ![Before staff review](screenshots/before-staff-review-1440.png) | ![After staff review](screenshots/after-staff-review-1440.png) |

[Complete screenshot gallery](GALLERY.md) includes light/dark Home, Explore, detail, Map, Saved, Profile, account and auth; 320/768-wide layouts; empty/error/draft states; staff desktop/mobile; and native iOS captures. [Capture manifests](verification/) record exact browser viewports and overflow checks.

## Stitch evidence

Created with the official `@google/stitch` CLI **0.12.2** after the owner completed Google authentication and the Stitch notice/terms flow. No credentials are included here. [Private Stitch project](https://stitch.google.com/projects/13687655136657432701).

Two directions were generated for Home, Explore, event detail and staff review, followed by a refined Home recommendation. [Screen IDs, prompts and links](stitch/manifest.json), screenshots and exported HTML are versioned under `stitch/`. These are concept references; generated HTML is not mounted as native application code.

## Validation

| Check | Local result |
| --- | --- |
| TypeScript | Passed |
| Mobile Node tests | 211 passed, 0 failed/skipped (baseline 208) |
| Token synchronization | Passed; also covered by the Node suite |
| Expo exports | iOS, Android and web passed; these are JavaScript exports, not signed builds |
| Staff browser workflows with disposable real API/virtual passkey | 2 passed, including form/session recovery and private image/OCR gallery |
| Browser captures | 30 final views, zero captured page errors, no horizontal overflow at checked widths |
| iOS simulator | Actual rendering, tab navigation, independent save, detail/Back, Profile and light-theme selection exercised on the installed development client |

The added behavior tests cover late profile/tab/account responses and cancellation of superseded discovery requests. The third new test rejects stale generated staff tokens. Existing save/auth/billing/map tests remain in the suite.

Native content-size verification includes `accessibility-extra-extra-extra-large`. The full heading/content is scrollable at that size; it is not expected to fit one viewport. Navigation and logo crowding were corrected after observing the actual native render. This is not a complete VoiceOver/TalkBack, gesture, performance, physical-device or role-specific certification. Android runtime/SDK was unavailable. Remaining route-level gaps are explicit in [route coverage](route-coverage.csv).

The initial native developer client was opened before Metro was ready, then connected successfully after retry. A transient developer warning occurred during early hot refresh; settled final captures exclude that intermediate state. No native crash-free or unhandled-rejection-free certification is inferred from these smoke checks.

## Reproduction

From `apps/mobile`:

```sh
npm run typecheck
npm test
npm run design:check
EXPO_NO_DOTENV=1 EXPO_NO_TELEMETRY=1 EXPO_PUBLIC_API_URL=http://127.0.0.1:18741 npx --no-install expo export --platform all --output-dir /tmp/bacity-design-export
python scripts/capture-design-review.py --export /tmp/bacity-design-export --out /tmp/bacity-design-shots --phase after
```

The capture script requires Playwright Chromium and uses no live API or production account. It serves a local export on port 18742 and intercepts only its synthetic API destination on port 18741. Native smoke used a separate temporary fixture HTTP server and Metro with dotenv disabled. Staff browser tests ran with isolated databases/media and SMTP/provider keys disabled. Review evidence never requires production secrets.

## Boundaries

No deployed service, schema, crawler, payment, permission or real account data changed. Synced project `sources/` files were not edited. Existing source coverage is wider than runtime coverage: every route has an explicit review status, while screenshots and tests support only the stated journeys. This PR remains a reviewable iteration, with incomplete native/platform acceptance disclosed.
