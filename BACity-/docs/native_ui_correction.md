# BACity corrective implementation — updated 4 November 2026

The original image-led Home has been restored selectively from Git, retaining real photography, Spectrum interactions, dark/pink identity and navigation improvements. Earlier compact-Home and repeated tab-focus animation decisions are superseded.

Reported AppSheet rendering, restored deep-link and premature navigation failures are fixed. Additional audit fixes cover member-profile guest/error/stale-response states, review reaction precedence and ongoing programme date labels. Existing map control now inverts for active filters and names those filters inline; no extra map-screen block was added.

Motion uses controlled geometry profiles, a stationary tab frame, short root fades and small content entrances. Actual iOS recording exposed two further causes of apparent bounce: background query refetches expanding native refresh controls and delayed native safe-area layout. Manual refresh feedback is now separate from background fetching; content insets use stable route-scoped hook values. Login retains its native safe-area boundary. Login page/card/field hashes match the saved baseline.

The crawler repair separates candidate inspection from normal crawl budgets, preserves publisher locality, rejects foreign/centroid pins, resolves verified venue addresses and bounds A4 discovery. Reviewed duplicate reconciliation preserves every original alias/source observation and retargets references transactionally. No history or Docker volume purge was performed.

Final checks: **208 mobile tests, 217 crawler tests, 660 API tests passed**; eight optional API scenarios skipped. Two opt-in disposable PostgreSQL tests passed separately. TypeScript, all-platform Expo exports and whitespace checks passed. Actual iOS workflows and final motion recordings were reviewed; Android export is not native runtime verification.

All eleven Spectrum components remain functional production integrations. iOS evidence includes save/Undo, follow, feedback/star update, notifications, ticker state, Login, morph buttons, settings disclosure, password strength, and short-hold cancellation. Destructive completion was not submitted. Full source/demo parity, accessibility and physical-device performance acceptance remain open.

One development-launcher splash promise warning remains recorded and investigated at the Expo Router/expo-splash-screen boundary; it was not globally suppressed. Android runtime, full VoiceOver/TalkBack, physical-device profiling, configured OAuth/recovery and store-billing checks remain unverified. Full release acceptance is not declared.

The authoritative report contains root causes, changed files, count semantics, catalog repair preimages, native evidence and limitations:

[Recovery report](/Users/s3eed/.codex/.chatgpt-projects/g-p-6a94b492f5088191920f3f48c7c9c29f/outputs/regression-recovery-20261103/REPORT.md)

Real API/worker and normal preview remain running. QA simulator/services are isolated and cleaned up. Incoming uncommitted work and synced read-only project sources are preserved. No commit, push, merge or deployment was performed.
