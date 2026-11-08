# Native BACity+ receipt printer

## Access and scope

The printer appears inline after the existing **BACity+ → Build My Evening** or **Weekend Generator** action. No new route, tab, itinerary generator, persistence domain, API, entitlement or payment provider was added. Other Plus experiences retain their existing presentations. Expo 51, React Native 0.74.5, TypeScript 5.3, Reanimated 3.10 and SVG 15 versions are unchanged; there are no new dependencies.

The original generators own parameters, validation, ranking, alternatives, occurrence selection, sequencing, day groups and limited-result logic. Pure adapters render their responses without fetching, sorting, deduplicating or mutating them. Repeated canonical IDs remain when different returned occurrences require them. The ingestion, deduplication and MapLibre engines are untouched.

## Components and behavior

- `apps/mobile/src/components/receipts/ReceiptPrinterView.tsx`: native machine, recessed screen, aperture, procedural paper grain, serrated edge, bounded feed, accessibility and interruption lifecycle. It accepts content and cannot generate a plan or verify payment.
- `ReceiptPaper.ts`: shared paper typography/styles.
- `PrintedPlanResult.tsx`: existing result content, native text sharing, original-card fallback, existing canonical map-focus and event-detail actions.
- `apps/mobile/src/receipts/presentation.ts`: pure evening/weekend data adapters, Bratislava formatting, feed function and a separate payment presentation contract.
- `VerifiedPaymentReceipt.tsx`: separate payment-state presenter, with no checkout/purchase/entitlement side effects.
- Existing `app/evening-plan.tsx` and `app/weekend-plan.tsx`: keep their original forms and mutations. A synchronous guard prevents rapid duplicate submissions. No second generation action is added.
- Existing loading registry/provider: only the two generation contexts now render inline. Central hooks and all other Rive/major-route loading behavior remain.

The same screen stays mounted during lookup and printing. Processing is honest pending state, with no fake progress or mandatory preparation delay. Real, nonempty results start feeding after layout measurement. Empty/error results use the original recovery views. Paper advances with mechanical pauses for 1.25–1.85 seconds; UI-thread transforms handle feeding. The expanding result uses a small native layout transition. Long paper scrolls inside a viewport cap with a visible hint.

Reduced motion bypasses feed animation, including dynamic accessibility changes. “Show results now” skips printing. Backgrounding or losing focus settles already-ready content. Unmount cancels animations and stale completion callbacks are ignored. Up to 32 completed result identities are remembered per mounted printer to avoid replay on unrelated renders.

Use × or **Event cards** to restore the original result cards. **Show printed result** reopens that response without another lookup or replay. Adjusting preferences hides the still-mounted result; explicit regeneration remains the only new generation request. Alternatives retain the original backend selection semantics.

Time presentation uses Europe/Bratislava. Unknown/date-only starts, missing ends and locations are labelled honestly. Status, recurrence and multi-day metadata are retained. Valid locations reuse `useViewOnMap`; unverified locations fall back to event details. Native sharing sends the actual result text and clearly states that admission/reservations are not included.

Neither existing generator exposes durable plan-save/history endpoints or a save-plan action. This change preserves their in-memory persistence; it does not create a parallel save system. Existing event saving through details is unchanged. A full screen unmount/app restart retains the existing planning-state behavior.

## Payment integration gap

Current Stripe/Google Play subscription, entitlement and webhook-idempotency records do not expose an authenticated durable transaction receipt containing final amount, currency and payment timestamp. Active access, a subscription state, frontend callback or Checkout redirect cannot prove money was collected.

`VerifiedPaymentReceipt` is consequently a **presentation integration seam, not wired into production payment completion**. Existing billing verification, purchase listeners, entitlements, subscriptions, checkout and provider portal/invoice access are untouched. No paid-looking production receipt is emitted.

A future authenticated backend receipt must provide `payment_status: paid`, `verification_source: provider_confirmed`, stable `receipt_id`, `transaction_reference`, `product`, timezone-qualified `paid_at`, integer `amount_minor`, ISO `currency` and `currency_exponent`. Optional merchant identity must originate in that record. The client validator checks shape only; it is not verification or a security boundary. The provider/backend must establish authoritative success and durable identity first.

The seam supports pending, cancelled, failed, unavailable and verified states. Incomplete records fail closed. Sensitive extra fields are excluded. No taxes, invoice numbers or merchant identity are invented. A caller can retain an official-document action, and the confirmation explicitly does not replace a fiscal invoice. A real verified-payment manual path remains unavailable until this backend contract exists.

## Reference and licensing

The [reference interaction](https://www.dqnamo.com/experiments/receipt-printer) and supplied source appendix were inspected. No explicit commercial reuse license was established on the page. This is an original native implementation of the physical interaction; no website source, logo, artwork, texture, web Motion package, DOM component or WebView was copied. The attached source document remains unchanged.

## Manual verification

1. Generate in Build My Evening using the original preferences. Verify pending → feed → actual result, alternatives, dismiss/reopen, adjustment and explicit regeneration.
2. Generate in Weekend Generator. Check returned days, long content, recurring/multi-day metadata, empty days and map/detail actions. Returning should retain the same response.
3. Check reduced motion, skip-print, rapid taps, background/resume, narrow layout, long-paper scrolling, sharing/cancelling and original cards.
4. Payment states can be checked with isolated synthetic contract records. Do not substitute a frontend success flag or entitlement for a verified transaction.

Actual automated results and device observations are in the implementation report. Android device gestures, sustained frame-rate profiling and real-provider paid receipts were not verified. Visual tests use isolated render fixtures, with no live account or purchase mutation.
