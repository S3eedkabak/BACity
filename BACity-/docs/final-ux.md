# FINAL-UX — implementation ledger

## UX adjustments — 2026-10-06

This section supersedes the onboarding-card, hold-final-frame, Home premium-rail and Map-not-wired statements in the earlier media ledger. No backend, API, entitlement, billing, Map data/cache/marker or location-privacy behavior changed.

- Onboarding now uses the supplied optimized MP4 as a full-viewport, cover-cropped, muted looping background. It has no radius, border or controls. The existing four steps, login/providers, registration, guest skip, Back and progress remain above an SVG cinematic scrim that is lightest over the upper/middle image and becomes near-black/dark-magenta beneath the copy and actions. Focus/background and reduced-motion poster behavior remain.
- Home retains its featured hero and recommendation feed but replaces the five-card premium rail with one BACITÝ+ entry. The new `/plus-experience` route presents eight closable story pages for the actual implemented Tonight, Evening, Weekend, Event Chains, Groups, Area Watch and optional-location capabilities. Feature actions retain the existing fail-closed `PlusGateAction`; Groups participation remains free and Event Chains still begins from a real selected event. The existing `/plus` billing/paywall implementation is unchanged.
- BACITÝ+ uses segmented progress, left/right tap zones, forward/reverse spatial Reanimated transitions, stagger-free physical page continuity and an always-visible exit. Location uses the existing request-scoped/coarsened foreground flow; no coordinates or story preferences are persisted.
- The single root loading provider now also owns immediate branded major transitions. Map tab press starts the Expert character and MapLibre initializes behind it; native full-frame readiness ends it, Map failure also releases it, and an eight-second safety release prevents trapping. Web reveals after its coherent local map shell mounts. Home → BACITÝ+ uses Intermediate. Actual Evening generation uses Intermediate; actual Weekend generation uses Expert. No API delay was introduced and normal fast interactions remain immediate.
- Responsive browser QA at390×844 verified full-bleed onboarding/control bounds, settled BACITÝ+ pages, forward overlap during transition, consolidated Home entry, real Rive BACITÝ+ entry, real Rive Map entry and clean Map reveal. Complete mobile tests: **116 passed**; TypeScript and Expo public config passed. All-platform Expo export passed: web2.22MB, Android4.19MB, iOS4.14MB. Native Android `assembleDebug`: **BUILD SUCCESSFUL**,986 tasks (75 executed/911 up-to-date). No native iOS runtime build is available on Windows.

## Current media/loading integration — 2026-10-06

This section supersedes **only** the prior startup/vector/video-removal decisions below. The dark redesign remains. Branch FINAL-UX; existing uncommitted redesign preserved. No backend/API, authentication, location-consent, crawler, billing or entitlement changes.

### Audit and asset evidence

- Expo 51 / RN 0.74.5 / Router 3.5 / React Query 5 / Reanimated 3.10 remain. Root retains per-account query clients and login-to-Home acknowledgement. Home retains FeaturedEvent and recommendations. Map retains native sources/clustering, bounded viewport caching and SWR. Explore uses existing debounced requests; Saved/detail use existing Query hooks.
- Supplied MP4: 174,039,631 bytes; 3840x2160 H.264 High/yuv420p, 30fps, 75.03 seconds; no audio. Inspected six representative frames: continuous aerial movement around Bratislava Castle, not a seamless loop. Original Downloads file untouched. Full-duration derivative: **9,542,805 bytes**, 960x540 H.264 Main/level3.1/yuv420p, CRF24, fast-start, silent. Bundled first-frame JPEG: 41,710 bytes.
- Video belongs ONLY to onboarding. Intentional cover crop in a rounded landscape visual region; explicit inner video dimensions also fix Expo AV's web intrinsic-size behavior. Poster remains underneath until ready opacity reveal. Muted, inline, controls hidden; holds final frame rather than jumping back. Active navigation focus + foreground control playback; unmount unload is handled by Expo AV. Reduced motion uses poster without decoding video. Continue/Back/progress/provider/skip flows are unchanged and never await playback.
- Supplied Rive inspected with official `@rive-app/canvas` **2.44.0** WASM runtime, not filename guessing. Artboard **New Artboard**, bounds 800x1000. Looping timelines: **Beginner** 120 frames/60fps, **Intermediate** 240/60fps, **Expert** 120/60fps (loop=1). One-shot timelines Intermediate_press, Expert_press, Beginner_press: 60/60fps, loop=0. State Machine 1: one **number** input `level` (runtime type56); no triggers/booleans. Three character variants visually inspected. No invented jacket/keys/success states. Demo level buttons are cropped off the loader's noninteractive stage, without editing the binary.
- Rive SHA256: `D3347DD1E233F60909DD4F9F1C13455D5752D3719BD9AFD2D6843B85A47EC49D`; supplied file and bundled copies match.
- Native runtime pinned **rive-react-native 8.0.0** (Android Rive9.9.5, iOS Rive6.2.1, verified in build.gradle/podspec). Initial 9.8.5 attempt rejected by native AAR checks: SDK35/36 + newer AGP requirements. Version8 builds using existing SDK34/AGP8.2.1/Kotlin toolchain. No forced transitive dependency downgrades or Expo upgrade. Native iOS requires **iOS14+**, expressed through SDK51-compatible expo-build-properties. This raises Expo51's default iOS13.4 floor and must be considered before release.
- Small Expo config plugin bundles native `bacity_walk.riv` as Android raw resource and iOS build resource. No runtime native download/file-URL reliance. Web uses bundled Rive/WASM with CDN fallback disabled. Runtime unavailable (including Expo Go), asset failure or four-second initialization timeout -> branded Reanimated fallback. A new native development build is required; Expo Go does not include Rive.

### Central loading policy

- One provider outside the session-keyed QueryClientProvider, one Rive instance maximum. Explicit missing-data foreground requests only: startup → Beginner; Event Details/initial unfiltered Explore → Intermediate; Saved → Expert. Registry includes map/search for future **genuine blocking** waits, but neither is wired to map gestures/filtering/typing/tab switches.
- Grace **500ms**. Below threshold: no loader, no manufactured request/navigation delay. Once visible: up to 200ms coherence allowance plus **180ms exit**, never multi-second presentation hold. Destination/error mounts independently behind presentation. Completion, error, route blur/unmount and background clean up timers; background unmounts character. Reduced motion uses static branded fallback with no stage movement. Back remains available and ordinary Android back remains owned by Router.
- Startup has no mandatory introduction. Actual auth/navigation readiness controls it; 15-second initialization presentation deadline offers retry. Existing API transport timeout10s and bounded Query retry1 remain; errors end missing-data loading and expose retry. No global Promise interception.
- Event-detail cache uses an already-loaded canonical EventOut from the public event-list cache when available, then refreshes normally. Cached detail remains visible on refresh error. Cards/hero guard repeat pushes for700ms and reset on return focus; first navigation is immediate. No source/detail/API contracts changed.
- Development only: start Expo with `EXPO_PUBLIC_LOADING_TEST_DELAY_MS=500`, `1500` or `3000` to delay uncached detail acquisition. No `.env` mutation; `__DEV__` forces production zero-delay regardless of variable. Development logs contain context/actual animation/threshold/completion/fallback only, not IDs, coordinates, tokens or request contents. Remove variable/restart Metro after testing.

### Validation

- Complete mobile suite **114 passed, 0 failed, 0 skipped**; includes 13 new loading/asset tests, grace/completion/cancel/replacement/race/production-disable coverage. Prior media/startup assertions updated because explicitly superseded, not business/security tests removed. TypeScript and Expo public config passed. No lint script exists.
- Final all-platform Expo export passed (`bacity-media-export-releasecheck-20261006`): web2.21MB; Android4.17MB; iOS4.12MB. Native Android `assembleDebug`: **BUILD SUCCESSFUL**,986 tasks (initial151 executed/835 up-to-date; final77 executed/909 up-to-date after restoring the normal package build). Rive8 compiled natively without SDK/AGP upgrade. Temporary test servers stopped; preview app, its temporary Gradle override and ADB8083 reverse mapping removed. No commit created.
- Browser runtime: all onboarding pages/Continue/Back at320x568 and390x844; muted autoplay, no controls, decoded960x540, explicit measured video bounds, final-page CTA/provider/skip buttons within568px, no horizontal overflow. Supplied real Rive Intermediate rendered in uncached Event Details; unavailable API ended loader and exposed retry/back. Timer receiver bug found in web runtime and fixed by global timer wrappers.
- iOS native prebuild/compile is unavailable on Windows. Asset plugin independently executed twice against official Expo SDK51 bare-template Xcode project: **passed**, single file reference/build resource, unchanged binary bytes. iOS export is not an iOS native runtime claim.
- Windows emulator screen capture timed out twice; no Windows input automation continued. An isolated mediapreview Android package was built/installed/launched, not the user's normal package. First-launch Expo development-menu onboarding blocked visual validation. Metro subsequently confirmed native `[RiveCharacter] initialized Intermediate` and initial Explore loading completion; this verifies runtime initialization, NOT visual/FPS quality. The fresh isolated package also logged the existing Map location-permission warning; no permissions were granted/changed. Temporary preview package removed afterward; normal installed BACity/session untouched. Do not claim measured native FPS, Android Rive visual verification, physical iOS playback, successful real event detail data, offline decoder stress or all platform lifecycle scenarios. Normal API was unavailable; normal DB was not started/modified for this task.
- Still required before release: native Android/iOS foreground/background/back/reduced-motion checks, real cached/uncached event success, video fail/slow-decode checks, native Rive fallback, low-end-device FPS/memory/battery profiling; verify media distribution rights. No invented event fixtures were shipped.

## Current dark redesign — 2026-10-06

This section supersedes the warm/light and prerecorded-video design direction in the historical ledger below. Starting checkpoint: `1971ab3b9a25693691e81199a9ce656f94a5b22f`, branch FINAL-UX, clean tree. Changes are uncommitted pending final product acceptance.

- Retained Expo 51, RN 0.74.5, Expo Router, API client/contracts, session/auth store, recommendations/location hooks, premium policy, contribution/moderation payloads and all canonical routes. No backend, crawler, payment, entitlement or database changes.
- Central near-black/charcoal/muted-magenta semantic palette, readable warm-white/grey text, shared typography/spacing/radius/opacity/elevation/motion tokens. Normal-text semantic contrast pairs meet WCAG AA 4.5:1 in deterministic tests.
- All application UI icon imports now use the official Iconoir adapter. Existing semantic action keys are retained to avoid navigation regressions. Native map points use plain event/WC text labels, not emoji. Provider options remain intact.
- Iconoir is pinned to **7.10.1**: the latest release requires RN >=0.78. Its published `module` entry is invalid on Metro, so a package-scoped resolver uses valid official files. Per-icon imports avoid bundling the entire library. New wildcard declarations preserve the official identical SVG icon type; no `any` escape hatch.
- Reanimated **~3.10.1** is the installed Expo 51 recommendation (`expo/bundledNativeModules.json`). Expo's existing Babel preset automatically enables its plugin. Shared press feedback runs transform motion natively, resolves Pressable styles before attaching the animated style, preserves nested stopPropagation/disabled handlers and respects reduced motion. Skeleton opacity loops stop in background/unmount. Detail pushes retain platform slide hierarchy; reduced motion uses fade. Modal sheets use native slide/none and safe insets. No new UI framework.
- Startup is a single cold-launch overlay outside the account-keyed query provider: BOOTING → INTRO → WAITING/READY → EXITING → COMPLETE, with bounded failure and retry. Feed/API failure cannot hold startup; readiness is auth initialization plus mounted navigation. The 1.4-second coherent introduction is skipped for reduced motion; exit is 380ms. A curtain reveal keeps the underlying app mounted. Login resolves to Home without replaying the scene. Session cache separation and stale-account navigation protection are unchanged.
- Removed BACityMotion, all substantial-request full-screen wait hooks, Expo AV as a direct dependency and three unused MP4 assets (recoverable from Git). Requests now retain their screen and use existing contextual skeletons/results/errors. Removed vector-icons as a direct dependency; Expo may still bring it transitively, but no application UI uses it.
- Onboarding now has four connected discovery/personalization/city/readiness pages with vector scenes, progressive copy reveal, back/progress/skip/guest exploration and the existing registration/login/provider starts. No automatic location request, new auth persistence or API behavior.
- Home retains the exact FeaturedEvent component/data selection and hero/feed dedupe, existing personalized/free feed, filters, location controls and five premium entries. Dark editorial hierarchy, lighter chrome, bounded first-three-card entrances that do not repeat on recycled rows. Cached hero remains visible after a refresh error.
- Event cards retain real images, missing-price distinction, saves and detail routes; image reveal is state-driven and missing/failed images retain vector fallbacks. Detail uses its own hero/metadata skeleton. Saved has a character-led empty discovery action. Explore keeps all four domains and current filters/pagination, with a search-specific empty scene.
- Map keeps the existing Liberty basemap, source IDs/layer ordering, native clustering/press expansion, utilities, viewport/nearby calls and bounded local-first caches. Dark control chrome and readable native cluster labels change presentation only. No speculative basemap replacement or marker-renderer rewrite.
- Social, account, organizer, moderation, privacy and premium screens inherit the same icon/tactile/surface system; original authorization, forms and actions remain. Existing five tabs are retained (Home/Explore/Create/Map/Profile); Saved remains available via Profile, avoiding removal of working Create/Profile destinations.

### Character assets and compatibility

The official current Rive runtime requires RN >=0.78 / Expo >=53 ([requirements](https://rive.app/docs/runtimes/react-native/react-native)). No editable `.riv` artwork or onboarding reference screenshots were supplied. An Expo/native upgrade solely for illustration is outside the safety boundary. **CharacterScene is explicitly development SVG artwork, not a finished authored jacket/pocket/keys film.** It has a reusable mood adapter and small editable SVG tree, subtle waiting motion and expressive states; final authored vector animation and exact screenshot matching remain pending asset/design review. No raster frame sequence/video or dozens of RN limb views.

### Validation and remaining acceptance work

- Pre-change baseline: **93 mobile tests, TypeScript passed**.
- Current suite: **101 passed, 0 failed/skipped**; TypeScript and Expo config validation passed. Includes startup fast/slow/failure/retry/one-shot behavior, cache identity/login routing, contrast, icon/dependency migration, bounded entrance, contextual states and all existing mobile policy/security/map tests.
- Web/Android/iOS final per-icon exports passed (`bacity-dark-ux-export-reviewed-20261006` in the system Temp directory): web **1.94 MB**, Android **4.10 MB**, iOS **4.05 MB**. Compared with the initial full Iconoir barrel, web decreased from 5.04 MB and Android from 7.76 MB; this is a measured bundle reduction, not an FPS claim. Native Android `assembleDebug`: **BUILD SUCCESSFUL, 916 tasks (118 executed / 798 up-to-date)**. No native iOS build on Windows.
- Browser checked four-page onboarding, 320×568/390×844 layouts, guest navigation and dark Home/offline UI. Only existing RN-web shadow/pointerEvents deprecation warnings were observed; no new runtime errors in those checks.
- Normal API was unavailable at localhost:8000; no normal development DB/service was started for screenshots. Real-data/authenticated/planner/payment/moderation E2E, populated lists, live map markers and frame-rate measurements are **not verified**.
- The user stopped Computer Use during emulator preparation; no further browser/emulator inputs were sent. Native emulator playback was not completed. An isolated-package Gradle QA attempt failed in an included build before app compilation (`:app` absent in `:gradle-plugin`); temporary init file was removed. The normal package was not overwritten, no stored session was cleared and no test APK installed.
- No claim of measured FPS improvement or completed full visual acceptance. Finish real-data/native/reduced-motion QA and author the final character scene before calling the complete redesign production-approved. No configured mobile lint command exists. Existing npm audit findings were not broadly auto-fixed.

## Historical warm/light implementation (superseded)

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

## Login-entry regression fix

The initial entry overlay dismissed without acknowledging Home. The per-identity navigator remount could race with the auth screen's replace, exposing the previous route. Root now owns completion: it waits for a mounted navigator, replaces with Home and releases the final frame only after `/discover` is acknowledged. Completed entry no longer redirects subsequent navigation, and old-account completions are ignored.

The initial video started while hidden behind a separate static brand view. Entry media is now warmed using the existing Expo Asset dependency and a deduplicated local download; native playback uses the local file, begins only after display readiness, and contains the full portrait frame rather than cropping it. The normal entry preparation is transparent over the existing page instead of an additional BACity logo screen. Static branding remains only for reduced-motion/error recovery. Public-feed prefetch moves after entry completion to reduce competing work during playback. No auth/backend/session-storage behavior or supplied video file was changed.

Regression checks: **93 mobile tests passed**, TypeScript passed, web/Android/iOS exports passed and native Android assembleDebug passed (915 tasks; 63 executed, 852 up-to-date). Four added entry safeguards cover Home routing from prior routes, logout/account-switch cancellation, route acknowledgement/one-shot navigation, and local preparation/display-ready playback. A connected emulator was discovered during this follow-up, but it was on the launcher with no running packager; authenticated login playback was not visually exercised and no claim of measured frame-rate improvement is made.

## Session greeting (facial Rive)

The root presents one process-local greeting after resolved authentication, with
Home navigation and data preparation running underneath. Successful email
registration sets an in-memory `new` marker atomically with the resolved user;
login/hydration/OAuth are returning entries. OAuth has no authoritative new-account
flag, so it is deliberately not guessed. No greeting flag or identity is persisted.
Claim/deadline survive StrictMode and root remounts. Navigation, another login and
foregrounding cannot replay a claimed greeting. Logout/account change hides it.
The total deadline is 2.2 seconds (including a 220ms Reanimated exit). Background
entry completes the presentation. Reduced-motion users get an immediate exit at
the same deadline. The greeting currently uses ONLY the brand/text fallback.

`greeting.riv` is the supplied facial asset unchanged. Inspection with local Rive
canvas 2.44.0 found four 500×500 artboards: `animation_color`, `import`, `rig`,
`animation`. The color artboard has `idle` (5s loop), `blink` (3s loop),
`changeEye-1`…`changeEye-7` (3s one-shots), `changeEye-idle`, touch/cursor timelines
(1s), and `particle1`…`particle7` (1s). `State Machine 1` exposes only four triggers:
`touchUp-cursor`, `touchDown-cursor`, `touchUp`, `touchDown` (no boolean/numeric inputs).
This asset is no longer used or packaged for greeting. Its opaque demo backdrop
and cursor presentation were rejected; the original binary remains as an unused
reference. The separate walk asset remains exclusive to loading/navigation.

Replacement inspection: the supplied 20,532-byte expressive showcase has ONE
500×500 artboard, `New Artboard`, with `Idle` (4s loop), `Hello` (4s one-shot),
`Walk` and `Angry` (5s one-shots). `State Machine 1` has three trigger inputs:
`Hello`, `Walk`, `Angry`. Actual local runtime playback confirms the cheerful wave,
but also an opaque gray stage (not canvas/container CSS). There is no alternate
clean artboard, background toggle, or supported cross-platform background-removal
API in the installed runtimes. Per the task's strict rule it is NOT integrated.
Supply an editor-exported `.riv` with the artboard/background fill removed or made
transparent, retaining `Hello`; do not fake transparency with masks/overlays.

Onboarding visibility correction: the full-screen cover layout and composition
are unchanged. The scrim uses explicit 0%→100% coordinates and seven stops:
0%/12%, 20%/6%, 45%/10%, 60%/32%, 75%/72%, 90%/96%, 100%/100% opacity.
The upper/central footage stays visible while copy/CTA get progressively stronger
contrast. The 960×540 ~1Mbps encode was replaced from the original 4K source with
1920×1080 H.264 High, 30fps, CRF20, yuv420p/bt709 and fast-start; no color/brightness
filters, audio, stretching or footage replacement. Runtime file is 55.8MB (~5.95Mbps)
for the original 75.03 seconds. The bundled poster is a sharp unfiltered frame from
the same encode. Device capture timed out twice through the computer-use skill:
Android visual acceptance remains blocked, not claimed as passed.

Current correction validation: 125 mobile tests passed, TypeScript and Expo config
passed; web/Android/iOS exports passed without either greeting demo asset bundled.
Android `assembleDebug` passed: 986 tasks (84 executed, 902 up-to-date). The real
exported onboarding was visually checked at 393×852: visible castle/sky, readable
headline/CTA, full-bleed video and gradual lower scrim. This is WEB visual QA, not
native QA. The connected emulator's capture failed twice, so native visual/runtime
acceptance remains unverified. There is no lint script in this app.
Manual check: rebuild/install the development client, cold-open an authenticated
account, then navigate/background/foreground; greet only once. In a fresh process,
finish email registration and verify only “Welcome to BACITÝ”, then Home. In another
fresh process sign in an existing account and verify only “Welcome back”. Both
currently use the plain brand/text fallback while awaiting a transparent asset.
