# Privacy request operations and logging policy

## Human rights workflow

Authenticated users use /privacy/requests and the Privacy & account rights screen. A live account session proves session access, not automatically legal identity. The server never accepts caller user IDs, coordinates, contact duplicates or identity documents. The administrator must proportionately assess identity and record the boolean only; sensitive supporting documents belong in an approved secure operational process if genuinely needed, not this form.

Requests cover ACCESS, RECTIFICATION, ERASURE, RESTRICTION, PORTABILITY, OBJECTION and OTHER_PRIVACY_REQUEST. They do not automatically freeze processing or delete public facts. Read/admin review is need-to-know, authenticated and audited. Account holders cannot read other cases; moderators cannot use the admin workflow. The admin queue omits content and account identifiers; opening case details is audited. Detail/response is AES-GCM encrypted through existing field encryption, maximum 2000 characters per field. No attachments are accepted.

Operational deadline is one calendar month from the UTC creation timestamp, clamping the day to the last valid day. A one-time assessed extension may set the deadline to three months from original receipt, only during the initial month and with a reason-bearing reply. Waiting for information does not automatically reset/pause the clock. Calendar/timezone interpretation and any lawful exceptions require counsel approval. Generic in-app notification is not proof the person actually received the communication: operators must ensure the approved communication channel meets applicable requirements and record independent delivery evidence where necessary.

Admin PATCH stores status, bounded response, reason code, identity-assessed flag and extension flag; closed cases are immutable. Fulfilling a request requires identity assessment. Mark complete only after actual reviewed fulfilment, not just because a button is available. A refusal must give the assessed reason and applicable approved complaint/remedy information; no authority contact is invented. Terminal statuses do not automatically execute underlying rights actions. Operators must perform and verify scoped corrections/exports/erasure/restriction under an approved procedure. Lost-account/non-account requests use the configured monitored privacy contact; without it, launch remains blocked.

Quota: five submissions/account/day and ten open requests/account; list pages 20 by default, maximum 50. Abuse safeguards are not a legal grounds decision to reject a rights request: use the monitored alternative channel for legitimate follow-ups. Deadline-based admin queue and overdue flags require staffed regular review; no unseen automatic legal approval or authority filing occurs.

## Data minimization / erasure

Account export includes own case records without a duplicated user ID. Deletion redacts case details/response and removes user linkage, without asserting fulfilment; metadata/audit retention remains POLICY_REQUIRED. Submission/report moderation audits now retain structured decision facts, not a second copy of free-text reasons; actual workflow decisions keep their assessed reason. Role-change audits retain their bounded operational justification because it is the sole decision record; staff must not include unrelated private content. Account exports no longer reveal another user's block decision. Privacy request preferences/content never feed crawler learning, ranking or ad profiles.

## Logging policy

Allowed: operation, route template, status/error TYPE, latency, internal case/object ID and privileged actor ID where needed for accountability. Forbidden: passwords, bearer/action/invite/provider tokens, keys, private message/request bodies, precise user/watch coordinates, private Group preferences or raw provider payloads. API request logs omit query strings/bodies and hide SQL parameters; outbound credential URLs are redacted. SMTP diagnostic recipient hash remains potentially linkable personal metadata, not proof of anonymization. Production proxy/CDN/APM logs must follow the same minimization policy and avoid geographic query/trace retention.

Retention: POLICY_REQUIRED for logs, audit records and privacy cases; do not introduce arbitrary periods. Owner assigns access roles, named responders and approved durations. Keep incident register/identity evidence outside public Git; use restricted operational storage. See data-retention-policy-matrix.md, data-breach-response.md and compliance-launch-blockers.md.

## Document configuration

PRIVACY_CONTACT_EMAIL, PRIVACY_NOTICE_URL/VERSION and TERMS_URL/VERSION describe owner-approved published resources. URLs require HTTPS outside development and no embedded credentials; contact rejects header injection. Blank values show honest pre-production unavailability, not a fabricated policy. Document version is not consent or forced privacy acceptance. If counsel selects legally consented purposes/Terms acceptance, define the evidence and withdrawal model separately before launch. Migrate 0014 before privacy routes; then follow encrypted-data backfill/key runbook with writers stopped. No production configuration or contracts were changed here.
