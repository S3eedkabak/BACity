# Verified privacy data flows

- Account -> Expo native/web -> bearer API -> users/PostgreSQL. Native auth material uses SecureStore; web uses sessionStorage. Logout/account change clears QueryClient; transient request responses use session revision guards.
- Recovery -> API -> hashed action token + encrypted mail body -> SMTP relay -> user's inbox. SMTP recipient leaves BACity; TLS does not stop relay access. Sent body becomes [Delivered]; provider retention independent.
- OAuth -> provider authorization -> verified callback/state -> account identity mapping. Google tokens are not retained; Apple revocation credential is separately encrypted.
- Purchase -> Stripe hosted web Checkout/Google Play Billing -> verified provider API/webhook/RTDN -> subscription -> server entitlement. BACity receives identifiers/status, not card input. Organization Stripe billing separate.
- Foreground location -> coarsened device memory -> optional recommendation/planner POST body -> bounded distance signal -> discarded request context. Map nearby/viewport APIs have geographic query parameters: reverse-proxy tracing must not create private location history.
- Area Watch input -> owner-private center/radius/categories persisted -> owner feed/seen -> delete. It is not transient GPS and not sent to crawler.
- Message -> authenticated sender -> AEAD body in DB -> authorized recipient response. Server can decrypt. Generic notification carries no message body; narrow reported-message moderation is separate.
- Contribution -> verified submission -> moderation publication -> canonical event/provenance -> bounded explicit public evidence outbox -> CandidateSource -> safe crawler inspection. Rejected/private text/messages/media/location never feed discovery. Non-crawlable contributed events remain valid.
- Group -> membership/private request preferences/votes -> deterministic aggregation -> intended reveal. Export returns own inputs, not other members' hidden data.
- Privacy request -> encrypted private case -> admin audited view -> assessed response/generic notification -> own status. Deletion redacts case text and detaches account, leaving metadata for a retention decision.
- Export -> authenticated own API -> JSON -> OS Share destination chosen by user. Warn before sharing; destinations are outside BACity control.
- Backups -> operator-selected storage; no deployed encrypted-backup infrastructure established. Restoring must reconcile erasures made after snapshot.

External boundaries: SMTP, OAuth providers, Stripe, Play, public source hosts, native OpenFreeMap style/vector-tile hosts, hosting/storage selected by owner. Basemap hosts receive request IP/tile coordinates; direct client requests cannot promise no third-party geographic inference. No external routing/geocoding or paid Google Maps map API is required by MapLibre. Web currently presents a discovery list rather than the native map.

No active Redis/OpenSearch private indexes, push provider, advertising/attribution SDK or external telemetry integration found. Production proxy/APM instrumentation must be separately inventoried.
