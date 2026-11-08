# BACity+ consumer Stripe billing (web Phase 1)

This integration is separate from organization billing. It is disabled by default and supports Stripe-hosted Checkout and Customer Portal on the web only. Native Apple and Google purchasing are not implemented.

## Authority and lifecycle

The client never grants access. A success redirect only triggers a server reconciliation and displays a verifying state. Access follows this chain:

`verified Stripe state -> ConsumerSubscription -> EntitlementService -> bacity_plus`

Only `active` and `trialing` Stripe subscription states are eligible. `past_due`, `unpaid`, `canceled`, `incomplete`, `incomplete_expired`, `paused`, a wrong product/price, an environment mismatch, or an expired billing period do not grant access. No payment grace period is introduced. `cancel_at_period_end` remains eligible only while Stripe still reports an eligible status and the verified period has not ended. A separate valid `EntitlementGrant` continues to grant access independently.

Refunds and disputes do not directly mutate access in Phase 1. Stripe subscription state remains authoritative until a product/legal policy defines how a refund or dispute should affect an otherwise-active subscription. Operators should cancel or update the subscription in Stripe when access must end, then reconcile it.

## Configuration

Use placeholders from `.env.example`:

- `CONSUMER_BILLING_ENABLED`
- `STRIPE_CONSUMER_SECRET_KEY`
- `STRIPE_CONSUMER_WEBHOOK_SECRET`
- `STRIPE_CONSUMER_PLUS_PRICE_ID`
- optional `STRIPE_CONSUMER_PLUS_PRODUCT_ID`
- `STRIPE_CONSUMER_SUCCESS_URL`
- `STRIPE_CONSUMER_CANCEL_URL`
- `STRIPE_CONSUMER_PORTAL_RETURN_URL`
- `STRIPE_CONSUMER_LIVEMODE`
- `STRIPE_CONSUMER_API_VERSION` (deliberately pinned to `2024-06-20`)

Return URLs must use the configured public app or CORS origins; callers cannot supply redirects. Production additionally requires HTTPS, live mode, and an `sk_live_` key. Do not place Stripe secrets in Expo public variables.

When disabled, existing grants and BACity+ gates continue to work, while Checkout, Portal, reconciliation, and the consumer webhook return unavailable. The safe status endpoint still reports that web billing is disabled.

## Stripe test-mode setup

1. Create a recurring BACity+ Product and Price in Stripe test mode.
2. Configure test `sk_test_...`, Price/Product IDs, local web return URLs, and `STRIPE_CONSUMER_LIVEMODE=false`.
3. Start the API and Expo web app, then enable `CONSUMER_BILLING_ENABLED=true`.
4. Forward a dedicated webhook to `http://localhost:8000/billing/consumer/webhook`, for example with Stripe CLI: `stripe listen --forward-to localhost:8000/billing/consumer/webhook`.
5. Put the CLI-provided test signing secret in `STRIPE_CONSUMER_WEBHOOK_SECRET` and restart the API.
6. Configure/send only these consumer signals: `checkout.session.completed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.paid`, and `invoice.payment_failed`. Paused/resumed subscription signals are also accepted when emitted by the configured Stripe API behavior. Unsupported events are recorded as ignored and cannot grant access.
7. Sign in on web, open `/plus`, select **Subscribe on web**, and complete Stripe-hosted Checkout using an official Stripe test card. Never put test card data into BACity itself.
8. On return, BACity shows a verifying state and asks the backend to fetch current Stripe state. It does not trust the redirect or a Checkout Session ID as proof of payment.

Useful lifecycle checks:

- Open **Manage billing** to schedule cancellation; verify access remains through the current verified period and the cancellation date is shown.
- Use Stripe test clocks where supported by the chosen test Customer/subscription to advance renewal, failed-payment, and period-end scenarios. Reconcile after each state transition.
- Stop webhook forwarding temporarily, change the subscription in Stripe, then call `POST /billing/consumer/reconcile` as that authenticated user. Restart forwarding and verify retries are idempotent.
- Sign into a second browser with the same BACity account; server-side entitlement should appear without a device purchase flag.
- An active subscriber attempting Checkout again receives conflict/manage-billing behavior rather than another subscription.

## Operations, recovery, and privacy

- `POST /billing/consumer/reconcile` is an authenticated, repeatable recovery path for the current account. It fetches the Customer and all bounded current subscriptions from Stripe and converges local state.
- Webhooks are signals, not state snapshots: handlers fetch current provider state. A delayed event therefore cannot resurrect an already-canceled subscription.
- Provider event IDs are stored in `provider_event_receipts` for durable deduplication; raw webhook payloads are not stored.
- Customer association uses immutable BACity user UUID metadata, not email. Email changes retain the association; a recreated account with the same email receives a new UUID and does not inherit it.
- Checkout, Portal, and reconcile calls are rate-limited. Mutations use server-derived Stripe idempotency keys. Checkout is serialized by a database row lock and records a bounded pending session.
- Logs contain operation/event identity and outcome only. They exclude secrets, authorization headers, full payloads, Checkout URLs, payment methods, and card data.
- Account export includes safe provider/product/status/period/cancellation facts but excludes Stripe Customer/Subscription IDs and webhook receipts.
- Account deletion first reconciles and immediately cancels any blocking Stripe consumer subscription. If provider cancellation cannot be safely attempted, deletion fails before application data changes. The existing anonymized user row and billing records remain pending a formal legal/financial retention policy.

## Deliberate Phase 1 limits

- No Apple StoreKit or App Store server verification.
- No Google Play Billing or server verification.
- No automated fleet-wide reconciliation job; the canonical service and authenticated recovery endpoint are ready to be invoked by a future bounded job/admin workflow.
- No direct refund/dispute entitlement rule until product/legal policy is approved.
- No final tax, invoicing, chargeback, retention, or app-store compliance review.
- Real Stripe test-mode and live-mode E2E verification must be performed with deployment-owned credentials; automated tests use a deterministic provider double and never create fake local entitlement success.
