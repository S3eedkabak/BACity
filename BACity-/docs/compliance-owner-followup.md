# Approved owner directions: focused compliance follow-up

Starting SHA 6b08cfbc50ada4414393cecfd4e4273fe844994f; branch crawler-v2. These are product decisions, not legal approval. No normal database or production configuration was changed.

## Eleven owner rows reviewed

| ID | Approved product direction / technical result | Remaining requirement |
|---|---|---|
| GDPR-001 | Blank environment-backed controller name/address and public contacts | OWNER: actual identity/address/contact absent |
| GDPR-011 | Existing discoverable profiles and private choices preserved and tested | Product control resolved; bases/notices remain separate legal rows |
| GDPR-012 | No indefinite discretionary retention | OWNER: approve purposes/durations; POLICY_REQUIRED stays open |
| GDPR-019 | Configurable privacy contact and documented alternative channel | OWNER: supply and monitor real address |
| GDPR-021 | Administrator/owner responsible role; existing ADMIN-only review | OWNER: assign reviewers, contact, approved retention and operating schedule |
| SOC-002 | Active counterpart retains delivered encrypted history; deleted authentication/profile blocked | Product implemented; GDPR-009 erasure/legal review remains open |
| CRAWL-003 | Public event contributor ID is null; other users cannot browse submitted-event history; internal provenance retained | LEGAL: submission/provenance retention and basis |
| MINOR-001 | Approved audience: adults 18+ | LEGAL: mechanism/wording/enforcement; age gate not deployed |
| BREACH-002 | Administrator/owner responsible role; configurable internal operations contact | OWNER: named escalation contacts, restricted register and rehearsal |
| DSA-002 | Configurable legal/support contacts and versioned terms links | OWNER: actual contacts/approved terms; classification separately open |
| CONS-001 | Provider-authoritative billing preserved | OWNER: actual trader/address, price/product/base-plan and disclosures |

Four product decisions are settled. Two rows become satisfied technical controls; two transition to LEGAL REVIEW REQUIRED rather than being closed. Seven remain OWNER DECISION REQUIRED. All 46 unresolved checklist IDs remain in the blocker register.

## Adults-only proposal — not implemented or legally certified

Password signup, Google/Apple first-login account creation, existing users and recovery do not share an age-eligibility decision. A password-only checkbox would leave inconsistent OAuth/legacy behavior. Counsel/product must approve existing-user treatment, refusal/appeals, declaration wording and evidence retention before enforcement.

Proposed minimum: unselected affirmative “I am 18 or older”, server-validated boolean plus server-owned version/timestamp; no DOB, identity documents or inferred age. All creation methods must share enforcement and existing users need an approved transition policy. This is product eligibility, not verified age or legal consent. Evidence must be owner-exportable, never public/crawler-visible, and deletion-aware subject to approved exceptions. Test absent/false/stale-version/spoofed declarations, OAuth/legacy paths, export and deletion before enabling. MINOR-001/MINOR-002 remain blockers. No auth or schema change was made prematurely.

## Conversation and attribution

Existing sends synchronously deliver into the recipient-accessible store, not queued drafts. Deletion retains both directions for an active counterpart under pair authorization and existing configurable expiry. Generic message notification links remain so the recipient inbox works; deleted private identity is cleared, old authentication and new sends denied. The UI uses “Unavailable member” for inaccessible profiles, not proof of deletion or cached private identity. A second participant's deletion erases the shared history. Stable pseudonymous participant IDs remain for authorization, not public profiles. No E2EE or delete-for-everyone feature.

Shared EventOut serialization preserves contributor_id as null across public event surfaces without mutating ORM provenance. Other users' profile contribution history excludes events; own history and private-profile behavior remain. Internal moderation, own export, canonical dedup and public-source-only Level 3 learning remain intact. Moderators must still assess identifying free text; structured suppression is not automatic text anonymization.

## Operations and retention

Initial responsible role: BACity administrator/owner. Intake/escalation uses monitored PRIVACY_CONTACT_EMAIL and internal OPERATIONS_CONTACT_EMAIL under documented procedures. Existing ADMIN role controls provide review, not an automatic incident mailer/assignment system. No personal ID/email is hardcoded. Missing actual contacts, retention and rehearsal remain blockers.

No indefinite discretionary “just in case” retention is approved. Existing cleanup defaults are preserved, not adopted as new legal periods. Each POLICY_REQUIRED category needs approved purpose/duration, accountable owner and enforceable deletion/exceptions before launch. Vendors, contracts, regions, transfers, provider pricing and production configuration remain unverified.
