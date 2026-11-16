# BACity design system

BACity is a local city guide: events, places and useful plans should lead the experience. The recommended direction is an editorial guide with a restrained rose identity, compact event rows, clear metadata and one bounded photographic feature.

## Source of truth

`apps/mobile/src/theme/foundations.ts` owns both palettes, typography, spacing, radii, layout, accessibility thresholds and the purpose-specific motion profiles. `colors.ts`, `tokens.ts`, `fonts.ts` and `navigation/motion.ts` are compatible native adapters. `themedStyles` and appearance subscriptions retain their existing lifecycle and cache behavior.

The staff panel keeps its existing HTML/JavaScript and desktop density. Its `tokens.css` is generated from the same foundations. From `apps/mobile`, run `npm run design:tokens` after changing shared foundations; `npm run design:check` verifies the committed CSS. The Node test suite checks synchronization too. Do not hand-edit generated CSS.

## Foundations

| Role | Dark | Light |
| --- | --- | --- |
| Background | `#100E12` | `#FFF8FB` |
| Surface | `#1C191F` | `#FFFFFF` |
| Alternate surface | `#28232C` | `#F4EAF0` |
| Text | `#F6F1F3` | `#24141E` |
| Muted text | `#B7ADB9` | `#6F5664` |
| Brand primary | `#A93468` | `#A93468` |
| Readable brand accent | `#E69ABB` | `#8B2452` |

Use `onBrand` and `onMedia` for light foregrounds on brand/photo surfaces; these do not invert with the page theme. `primaryDark` remains a compatible alias for the readable brand accent. Status colors describe actual state, and category illustration colors remain local artwork rather than generic product actions.

System is the font family. `fontStyles` applies real regular/medium/semibold/black weights; the legacy family aliases alone cannot specify a weight. Prefer complete `tokens.type` roles, including line height. Page titles use 30/36/700, event rows 17/23/600, body 16/24/400 and metadata 13/19/500.

The spacing primitives remain 4/8/12/20/28/40/48, with named 16-point control and 24-point inset values. Screen gutters are 20. Cards and fields use named 16-point corners; circular and pill controls retain their distinct geometry. The tab navigator reserves its own height, so tab content uses a 24-point end-of-content gap rather than reserving the navigation bar twice. Existing safe-area ownership stays intact.

## Composition and behavior

- `EventCard` supports actual row, feature, rail and editorial presentations. Existing variant names map explicitly to those layouts during migration. Home uses compact rows below its separate `FeaturedEvent`.
- Event titles, real dates, locations, prices and the save state come from the existing data contracts. Free and unknown price are distinct. `EventMetadata` owns shared price/category presentation.
- `useDiscoveryResults` owns result identity, cancellation and pagination. `useProfileActivity` rejects stale tab/account responses. Screens compose those results rather than owning transport details.
- `MapBrowseTray` presents the map entry point. MapScreen retains viewport queries, filters, camera state, caching and geometry.
- Use filled actions for a meaningful commit; use plain contextual actions for navigation. Save, follow and feedback keep their existing state and mutation owners.
- Keep loading, empty, error and retry states truthful. Missing artwork uses the existing local fallback. Concept artwork and fixture content must never become fabricated production listings.

## Motion and accessibility

The canonical source retains named press, surface, badge and sheet profiles. Distinct timings are intentional; a single universal spring is not the goal. Preference and interruption handling stay in the existing interaction layer. Theme changes do not remount routes or intentionally reset drafts.

Photo-backed feature/detail cards size from their text in the normal layout flow rather than clipping copy into a fixed-height overlay. Content remains scalable and scrollable, including live native text-size changes. Repeated photo badges scale within a bounded header; their full data is also available in the body. Primary action labels scale up to 1.5 so a persistent footer cannot consume the screen. The wordmark is a logo and does not scale with Dynamic Type. Bottom-navigation labels scale up to 1.3 to stay legible within five fixed destinations; their accessible labels remain available.

Keep at least 48-point touch controls, readable focus and error states, and non-gesture alternatives where already supported. SVG/photo geometry and map coordinates are intentional local dimensions; do not blindly substitute every numeric value with a token.

## Design decision and evidence

See [the design review](docs/design-review/README.md) for the good/bad/ugly assessment, alternatives, before/after screenshots, Stitch concepts, route coverage and validation limits. The proposal is delivered for a PR decision; it is not a release-readiness certification.
