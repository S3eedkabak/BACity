# FINAL-UX — implementation ledger

Source: crawler-v2 at ad73924a67b22a2ccfbc14d2a66f5ba2f64c885e. FINAL-UX created from that clean, origin-verified baseline. No merge/deployment. This ledger distinguishes implemented presentation from runtime verification; exports and source-contract tests are not device acceptance tests.

## Audit and direction

Expo 51 / React Native 0.74.5, Expo Router 3.5, TanStack Query 5, Zustand sessions, existing Gluestack, Ionicons 14, Expo AV 14 and MapLibre 10.4.2. No platform upgrade is planned. Existing core palette is warm coral with system typography. Shared CommunityUI currently presents many identical boxed forms/buttons; social routes use SocialUI. Home repeats five equally weighted premium entry rows. Event cards are text-heavy horizontal thumbnails; hero and detail independently render imagery. Fallback category imagery currently makes external Unsplash requests unrelated to real events. Existing global startup blocks mounting navigation for a 950ms logo timer. Map native sources/cache/query policy must remain untouched. Existing backend billing, entitlements and privacy implementation is authoritative.

Visual direction: warm paper, near-ink text, energetic coral, large editorial type, real event media, category-based drawn fallback motifs (not external stock photos). Premium uses deep plum/ink, coral and spatial/timeline composition, not gold decoration. Core remains light; no unsupported theme-switch system. Ionicons only. System fonts avoid new font/network dependencies.

## Route / feature migration ledger

Existing route paths remain canonical; presentation and progressive disclosure change, not backend contracts.

| Existing capability/routes | Destination / preservation requirement |
|---|---|
| index, welcome, auth, oauth | Guest welcome remains; authenticated entry sequence overlays initialized shell; login/signup/provider exchange preserved |
| Home /(tabs)/discover | Editorial hero + existing personalized feed; explanation/save/location controls; compact premium rail, not five button rows |
| Explore /(tabs)/explore | Canonical search across events, places, people, organizers; filters disclosed contextually |
| event/[id] | Immersive event detail; save, source, discussion, collections, corrections, sharing and Event Chains preserved |
| /(tabs)/map, map.web | Spatial native map / web alternative; viewport, utilities, clustering, location, selected detail and caching preserved |
| /(tabs)/contribute, activity, correction | Staged contribution entry; own moderation status and correction remain reachable |
| /(tabs)/profile, member/[id], social/[type], following, blocked | Identity and role menus; social pagination/privacy/blocks preserved |
| /(tabs)/saved, collections, collection | Visual personal library and collection management; canonical Profile/menu access |
| messages/index, messages/[userId], notifications | Dedicated inbox/chat/activity; shared-record deletion semantics preserved |
| organizer, venue/[id], place/[id], utilities, utility/[id] | Public discovery/detail separate from role-authorized management/claims; confirmations and review actions retained |
| plus | Existing provider-authoritative purchases/status/restore/manage and reusable gate; no new billing |
| tonight, event-chains, evening-plan, weekend-plan | Premium temporal discovery and constrained visual itineraries; existing inputs/results/rules preserved |
| groups, group/[id] | Plus initiation/free invited participation; match/voting/hidden votes/lifecycle preserved |
| area-watches, area-watch/[id] | Private spatial watch controls/results; owner authorization and persisted-center semantics preserved |
| account, privacy, privacy-admin | Account/recovery/deletion and private rights workflow; administrative review remains role protected |
| moderator, community | Dedicated role tools plus compatibility route; no deletion of legacy capabilities without replacement |

Onboarding/interests and guide tools currently live inside existing account/community/profile flows, not invented new APIs. Organizer claims, role changes, reports, appeals, audit, source health and billing management must remain reachable through their existing gated destinations.

## Loading and motion contract

Entry: owner Squiggle Flow once per successful authenticated session entry, full natural playback, silent; hydrate and bounded query warmup run concurrently. Navigation stays mounted behind the overlay; account changes cancel stale entry. Tabs/back/save/follow/vote never trigger it. Reduced motion uses static branding rather than video. Errors/timeouts must release the overlay into recovery, not falsely authenticate.

Substantial real waits: one centralized Car Racing overlay, delayed reveal to avoid flashes; never hide usable cached content. Stop when work completes/cancels; no forced four-second delay, no audio, no simultaneous players. Content waits use layout-specific skeletons; inline actions use small state indicators; background refresh retains content. Native transforms/opacity only for modest interaction motion; reduced motion removes nonessential movement.

## Assets and verification ledger

Owner originals: squiggle_flow_text.mp4 (5,281,922 bytes), car_racing.mp4 (1,216,130 bytes), supplied in Downloads. Preserve originals; one bundled copy each under assets/motion. No stock imagery, new data or backend changes planned. Native AV already exists; playback requires actual native verification, not TypeScript alone.

Both supplied clips are bundled once, untranscoded: Squiggle 2.967 seconds / 1080×1920 AVC, Car Racing 3.967 seconds / 1080×1920 AVC. Metadata was checked from MP4 headers. Total additional media is 6,498,052 bytes. The original welcome clip/file and native splash configuration are unchanged. No new image, font, location, video, payment or UI dependencies were added. Existing image caching is retained; no new image-resizing backend or cache service is claimed.

## Implemented screen composition

Home retains the exact existing featured-event selector and hero exclusion rule. The large 408px hero now shares resilient EventMedia and a readable gradient with detail. The social header remains visible during loading/error; layout skeletons occupy the content region. The existing free personalized feed, pagination, reasons, saves and consent controls remain. Five premium entry buttons became a horizontal deep-plum discovery rail below the hero. Category/free chips actually forward existing filters to Explore.

Explore has an editorial search surface, four domain chips and a contextual filter sheet. Events use media cards, people use avatar/profile rows, places use category artwork plus address, organizers use organization rows with contextual ownership/claim management. Existing endpoint search limits are unchanged: event text search is bounded but does not support the same pagination/filter combination as browse. No unsupported search contract is invented. Errors retain the search and offer retry.

Event cards expose hero/feed/horizontal/compact/map/saved/planner/premium/organizer variants; actual route usage remains appropriate to existing data. Missing/failed media uses local category SVG motifs, never unrelated stock images. Price unknown remains distinct from free. Event Detail retains source links, venue, save, discussion and the premium Chains entry, with safe-area back and a contextual share/collection/correction menu. Reviews/discussion use content rows and disclosed compose/safety actions instead of permanent large action cards.

Map retains all native ShapeSource layers, clustering/filter expressions, press callbacks, viewport/nearby queries, bounded snapshots, debounce, stale-while-revalidate and ambient tile caching. Changes are the safe-area search button, wrapped layer tray, readable controls and status placement. Search opens Explore; markers still open canonical detail routes. Web remains the existing schematic overview, not a new geographic basemap; it now distinguishes network error/loading/empty and retries without erasing cached pins.

Create is a three-step find → when/where → review flow. All event/place/utility structured payload fields, public-source evidence and verified-email requirement are retained. Date/time steppers preserve editable input. The existing native MapLibre area picker is reused with contribution-specific copy; its initial city-centre preview is NOT written into the contribution unless tapped. Web/manual coordinates remain available. No device GPS is collected by this picker and no geocoder is added.

Profile has centred identity, larger typography, accessible social stats, wrapping content tabs and a compact role-aware menu. Privacy review is exposed only to admins. Saved uses library media cards; Collections has drawn album covers, visibility/count metadata, domain actions and retained data during failed refresh. Collection selection uses icon/check rows. Public members/followers/following/blocked use the unified social row/avatar system; existing follow targets, pagination, privacy and safety controls remain.

Messages keeps its dedicated inbox/chat routes, with larger readable conversation rows, unread dots, time-only today timestamps, accessible profile labels, refresh and retry of failed threads while retaining successful ones. Conversation retains keyboard-safe composer/safety actions and scrolls to incoming content. Inbox discovery remains notification-derived because the existing backend has no dedicated conversation-list endpoint; this work does not fabricate one. Activity retains existing notification read and contextual navigation behavior, using more readable rows.

Organizer management has disclosed registration, identity, publication and subscription tools. A date/time occurrence control fills the existing ISO occurrence list; advanced recurrence editing stays available. Claims, analytics, permissions and organization billing code are unchanged. Normal organizer discovery does not show the management form inline.

BACity+ uses deep plum, coral accents, orbit composition and chronological media rails, not gold variants of ordinary cards. Tonight uses premium decision cards and existing classifications/reasons. Chains uses an anchor-aware timeline. Evening/Weekend use practical parameter controls, real-generation waits, focused results, honest limited/empty results and an explicit adjustment action. Groups separates hosting from invited participation; group voting uses real event imagery. Only Group Match generation triggers the substantial wait. Area Watch puts its map first and discloses exact coordinates; persisted watch-centre behavior is unchanged. Existing server-authoritative gates and provider-specific paywall/purchase/restore/manage logic are retained.

Auth uses a larger editorial hierarchy, accessible primary/provider/back controls and keyboard-safe form; login/register/OAuth exchange is unchanged. Interest onboarding remains in account editing, now with drawn category tiles; no new mandatory onboarding is inserted. Account photo selection/crop, recovery, verification, deletion confirmations and export remain, with private operations progressively disclosed. Privacy rights and audited admin review have clearer controls without changing legal text or operational decisions. Moderator, activity, utilities, place, venue, utility detail, corrections and compatibility Community use the updated shared form/social primitives; not every secondary route was independently rebuilt.

## Shared architecture and safety

- `theme/tokens.ts`: semantic spacing 4–48, radii 12–36, touch 48, content width 760, media ratios, 450ms substantial-wait reveal, premium palette and named text hierarchy. `colors.ts` retains coral identity with warm paper and near-ink contrast. System fonts have explicit weights; Ionicons is the single icon family.
- `EventMedia` and `MediaScrim`: stable fallback behind loading images, error recovery, drawn SVG category imagery, readable photo overlays. `PremiumUI`: intro and chronological PlanStop; no invented venue/activity/time/price facts.
- `CommunityUI` / `SocialUI`: keyboard-safe pages/sheets, contextual disclosures, primary/secondary/danger buttons, circular avatars with failure fallback, icon buttons, rows, stats, skeletons. Overflow sheets use no fade; detail stacks retain platform-style pushes and tab navigation remains tab navigation.
- `TemporalField` and `InterestPicker`: minimal local input/selection controls, no added framework or dependency. Date/time fields remain editable, not a full native calendar/time-picker implementation.
- `BACityMotion`: centralized silent AV lifecycle, reduced-motion preference, foreground pause, natural completion, static branding underneath video readiness and a bounded entry-error watchdog. A wait player is mounted only when its real job is visible, suppressed during entry and removed immediately when work ends. Users can continue in background; no forced minimum job duration or automatic route transition.
- Root QueryClient is scoped to session identity and cleared on cleanup, not after new child queries mount. Auth hydration and bounded public-event prefetch occur concurrently with entry. Existing centralized transport/session-revision defenses remain unchanged. No private coordinates/tokens/identity are logged or newly persisted.
- Home virtualizes the feed with initial/batch 6 and window 7. Native map memoization/cache/query logic is preserved. No measured FPS, memory or cold-start improvement is claimed without native profiling.

## Validation (2026-10-05)

Run from `apps/mobile` unless otherwise noted:

| Check | Exact command / result |
|---|---|
| Mobile regression baseline | Before implementation: 78 passed, TypeScript passed |
| All existing/new mobile tests | `$testFiles = @(rg --files src -g '*test.mjs' -g '*test.cjs'); node --experimental-strip-types --test --test-reporter=spec $testFiles` → **89 passed, 0 failed, 0 skipped** |
| Added tests | 11 UX policy/source-contract checks: entry accessibility/background/fallback, wait completion/dismissal, cached-content policy, single supplied silent player lifecycle, per-identity cache, retained hero/feed/routes, local media fallback, preserved contribution fields/gate, planner gating/navigation, free group participation, inbox/library refresh recovery |
| TypeScript | `npm run typecheck` → passed |
| Expo config | `npx expo config --type public` → passed, existing plugins/permissions unchanged |
| Web/Android/iOS export | `npx expo export --platform all --output-dir <temporary-artifact-directory>` → passed on all three platforms; owner clips included once each |
| Native Android | From `apps/mobile/android`: `./gradlew.bat assembleDebug --console=plain`, Microsoft JDK 17 / installed Android SDK → **BUILD SUCCESSFUL**, 915 tasks (54 executed, 861 up-to-date on the repeated build) |
| Whitespace/scope | `git diff --check`, intentional path review, protected backend/payment/config paths unchanged |
| Browser | Real local Expo web preview: Home/Explore API-unavailable state; guest Profile; registration; BACity+ paywall; inbox sign-in gate; existing web map. Checked 320×740 and 390×844 phone widths; sampled document width matched viewport with no overflow. Desktop viewport reset afterward. No fake events or bypassed authentication |
| Device availability | `adb devices` showed no connected emulator/device. No native playback, gestures, permission, keyboard or accessibility runtime testing claimed. Native debug assembly does not bundle JS; platform exports separately validate JS/assets |
| Backend/crawler tests | Not rerun: no backend/crawler/schema/API behavior or files changed. No normal database was started/modified for screenshots |
| iOS native build | Not available on Windows; iOS JavaScript export passed |

Node's experimental type-stripping/module-type warnings and existing Gradle warnings remain; tests were not weakened to remove warnings. No configured mobile lint script exists. Tests are deterministic pure-policy and source-contract tests, not rendered component/device tests.

## Remaining verification and UX boundaries

Authenticated live-data Home/hero/event media, social/member/history, chat send, notifications mark-read, organizer/moderation/admin, purchase/restore, native map markers/clusters/selection, all premium results, Group Match/votes, Area Watch creation and account recovery/privacy actions were inspected code-path-wise but NOT visually exercised with live accounts. The local API was unavailable; no normal DB, fake data, token-store editing or authentication bypass was used to manufacture screenshots.

Before release, use Free/active Plus/expired Plus plus authorized organizer/moderator/admin accounts. Verify entry video exactly once, background/resume and reduced motion; complete a genuinely slow planner request and a quick one; cancel/navigate away; verify no multiple players/audio/stale navigation. Test small Android/iPhone safe areas, keyboard-open chat/forms/sheets, large accessibility fonts, long event/profile titles, missing images, map clusters/utility presses and purchase cancellation/restore. Ensure existing Free discovery/location/source links remain free, and invited Free group members still vote.

Known limitations: existing schematic web map; notification-derived inbox; no new native calendar/time-picker dependency; some collection items expose only type/id from the existing payload; unchanged owner videos add approximately 6.5MB (no transcoding quality/performance claims). Secondary administrative/detail routes benefit from shared primitives rather than independent visual reconstructions. Native video decoding, fullscreen crop, large-font layout and screen-reader flow need device QA. No broader legal/billing/backend gap is implemented or hidden by this UX change.

Build outputs are outside the repository under the user's temporary directory. The initial repository-local export was moved intact to a checked temporary path; no user data was deleted. Only intentional mobile source, the two supplied assets and this document are committed.
