# Compliance evidence index

API evidence is relative to services/api/app and services/api/tests; mobile evidence to apps/mobile. IMPLEMENTED and ALREADY SATISFIED describe bounded technical properties, not whole-law compliance. No row may be marked implemented merely because counsel was asked to review it.

| ID | Status | Code/test/config/document evidence | Operational/contract/legal follow-up |
|---|---|---|---|
| GDPR-001 | OWNER DECISION REQUIRED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Identity/address/contact still not supplied; blank configuration added; Supply approved controller/trader identity, address and public contacts |
| GDPR-002 | LEGAL REVIEW REQUIRED | docs/records-of-processing.md; actual-code inventory linked there | Counsel: Approve bases for each ROPA activity |
| GDPR-003 | IMPLEMENTED | docs/privacy-data-inventory.md; docs/records-of-processing.md; app/models/*.py | See related unresolved policy/deployment rows |
| GDPR-004 | LEGAL REVIEW REQUIRED | docs/records-of-processing.md; actual-code inventory linked there | Counsel: Approve factual notice before launch |
| GDPR-005 | IMPLEMENTED | api/routes/privacy.py; mobile/app/privacy.tsx; tests/test_privacy.py | See related unresolved policy/deployment rows |
| GDPR-006 | IMPLEMENTED | community.py:export_account; test_privacy.py:test_access_export_does_not_silently_truncate_messages | See related unresolved policy/deployment rows |
| GDPR-007 | LEGAL REVIEW REQUIRED | docs/records-of-processing.md; actual-code inventory linked there | Counsel: Approve portability vs access scope |
| GDPR-008 | ALREADY SATISFIED | community.py:edit_profile; users.py:update_interests; account.tsx; test_community.py | See related unresolved policy/deployment rows |
| GDPR-009 | LEGAL REVIEW REQUIRED | docs/records-of-processing.md; actual-code inventory linked there | Counsel: Decide subscription-block and shared-record policy |
| GDPR-010 | IMPLEMENTED | privacy.py:RequestInput; test_privacy.py:test_private_request_categories_owner_and_encryption | See related unresolved policy/deployment rows |
| GDPR-011 | ALREADY SATISFIED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Owner approved existing public/private controls; private behavior regression-tested; Preserve user choices; GDPR bases and notice review remain separate |
| GDPR-012 | OWNER DECISION REQUIRED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | No indefinite discretionary retention approved; exact category durations still missing; Approve justified category durations; keep unresolved categories POLICY_REQUIRED |
| GDPR-013 | ALREADY SATISFIED | worker.py:tick; core/mail.py:deliver_pending_mail; data-retention-policy-matrix.md | See related unresolved policy/deployment rows |
| GDPR-014 | PRODUCTION CONFIG REQUIRED | docs/records-of-processing.md; actual-code inventory linked there | Operations: Encrypted backups, retention and erasure replay on restore |
| GDPR-015 | LEGAL REVIEW REQUIRED | docs/records-of-processing.md; actual-code inventory linked there | Counsel: Assess profiling/location/chat risk and consultation need |
| GDPR-016 | LEGAL REVIEW REQUIRED | docs/records-of-processing.md; actual-code inventory linked there | Counsel: Determine actual establishment and appointment duties |
| GDPR-017 | LEGAL REVIEW REQUIRED | docs/records-of-processing.md; actual-code inventory linked there | Counsel: Assess event-interest inference without adding sensitive profiles |
| GDPR-018 | LEGAL REVIEW REQUIRED | docs/records-of-processing.md; actual-code inventory linked there | Counsel: Classify discovery ranking; no rights/credit adjudication found |
| GDPR-019 | OWNER DECISION REQUIRED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Configured channel supported; actual monitored public contact absent; Supply and monitor a non-account privacy contact |
| GDPR-020 | IMPLEMENTED | config.py:Settings; privacy.py:information; privacy.tsx; test_privacy.py:test_privacy_information_not_fake_policy_and_safe_config | See related unresolved policy/deployment rows |
| GDPR-021 | OWNER DECISION REQUIRED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Initial responsible role is BACity administrator/owner; retention/contact/review staffing not operational; Configure monitored contact, assign authorized administrators and approve case retention |
| LOC-001 | ALREADY SATISFIED | mobile recommendations/useRecommendationLocation.ts; core/recommendation_context.py; locationSecurity.test.mjs | See related unresolved policy/deployment rows |
| LOC-002 | ALREADY SATISFIED | api/routes/area_watches.py; test_area_watches.py; community.py export/deletion | See related unresolved policy/deployment rows |
| LOC-003 | ALREADY SATISFIED | locationSecurity.test.mjs; useRecommendationLocation.ts | See related unresolved policy/deployment rows |
| SOC-001 | ALREADY SATISFIED | community.py:_profile_access, collections; test_community.py | See related unresolved policy/deployment rows |
| SOC-002 | IMPLEMENTED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Owner approved surviving participant conversation retention; legal erasure review remains GDPR-009; Retain encrypted delivered history under existing expiry; reject deleted authentication and new sends |
| SOC-003 | ALREADY SATISFIED | community.py:conversation, can_message; core/encryption.py; test_adversarial_security.py | See related unresolved policy/deployment rows |
| SOC-004 | ALREADY SATISFIED | api/routes/groups.py; test_groups.py; test_adversarial_security.py | See related unresolved policy/deployment rows |
| SOC-005 | ALREADY SATISFIED | community.py:block, report; test_community.py; test_adversarial_security.py | See related unresolved policy/deployment rows |
| CRAWL-001 | ALREADY SATISFIED | core/source_learning.py; test_level3_discovery.py; docs/crawler-v2.md | See related unresolved policy/deployment rows |
| CRAWL-002 | LEGAL REVIEW REQUIRED | docs/privacy-data-inventory.md; actual-code inventory linked there | Counsel: Review source transparency, correction and reuse rights |
| CRAWL-003 | LEGAL REVIEW REQUIRED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Anonymous-by-default community event attribution implemented; submission retention still requires approval; Review retained internal submission/provenance duration and basis; no public event attribution |
| ORG-001 | ALREADY SATISFIED | community.py:organizations, claim; core/community.py:owned_organization; test_community.py | See related unresolved policy/deployment rows |
| ORG-002 | LEGAL REVIEW REQUIRED | docs/privacy-data-inventory.md; actual-code inventory linked there | Counsel: Separate B2B organization from consumer account |
| MINOR-001 | LEGAL REVIEW REQUIRED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Owner approved adults-only 18+ audience; consistent signup/OAuth eligibility mechanism awaits counsel; Approve proposed unselected versioned eligibility confirmation and legacy/OAuth enforcement; no DOB |
| MINOR-002 | LEGAL REVIEW REQUIRED | docs/legal-review-input.md; actual-code inventory linked there | Counsel: Review Slovak law and actual lawful bases; no invented age |
| EPRIV-001 | LEGAL REVIEW REQUIRED | docs/privacy-data-inventory.md; actual-code inventory linked there | Counsel: Assess necessary storage and Slovak implementation |
| EPRIV-002 | NOT APPLICABLE | docs/privacy-data-inventory.md; actual-code inventory linked there | See related unresolved policy/deployment rows |
| EPRIV-003 | NOT APPLICABLE | docs/privacy-data-inventory.md; actual-code inventory linked there | See related unresolved policy/deployment rows |
| EPRIV-004 | LEGAL REVIEW REQUIRED | docs/privacy-data-inventory.md; actual-code inventory linked there | Counsel: Classify chat service and confidentiality duties |
| CONSENT-001 | LEGAL REVIEW REQUIRED | docs/privacy-notice-facts.md; actual-code inventory linked there | Counsel: Do not present native permission as approved lawful basis |
| PROC-001 | PROCESSOR/CONTRACT REQUIRED | docs/privacy-processors.md; actual-code inventory linked there | Owner: Confirm actual vendors, roles and signed terms |
| PROC-002 | PROCESSOR/CONTRACT REQUIRED | docs/privacy-processors.md; actual-code inventory linked there | Operations: Assess provider-held data; no blind financial deletion |
| TRANSFER-001 | PROCESSOR/CONTRACT REQUIRED | docs/international-transfers-checklist.md; actual-code inventory linked there | Counsel: Confirm regions, subprocessors, adequacy/SCC/TIA as applicable |
| BREACH-001 | IMPLEMENTED | docs/data-breach-response.md: restricted register template and response procedure | See related unresolved policy/deployment rows |
| BREACH-002 | OWNER DECISION REQUIRED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Initial responsible role is administrator/owner; named contacts and rehearsal missing; Configure operations contact and rehearse incident assessment and notification |
| SEC-001 | PRODUCTION CONFIG REQUIRED | docs/security-verification-matrix.md; actual-code inventory linked there | Operations: Inject keys and offline-backfill before serving |
| SEC-002 | BLOCKED | docs/security-verification-matrix.md; actual-code inventory linked there | Engineering: Coordinate dependency upgrades recorded by security audit |
| SEC-003 | PRODUCTION CONFIG REQUIRED | docs/security-verification-matrix.md; actual-code inventory linked there | Operations: Apply redaction/retention/access policies to infrastructure |
| SEC-004 | ALREADY SATISFIED | api/deps.py; community.py moderation gates; test_adversarial_security.py | See related unresolved policy/deployment rows |
| SEC-005 | IMPLEMENTED | privacy.py:inspect, review; community.py audit minimization; test_privacy.py | See related unresolved policy/deployment rows |
| DSA-001 | LEGAL REVIEW REQUIRED | docs/dsa-checklist.md; actual-code inventory linked there | Counsel: Assess hosting/platform scope, size and Slovak duties |
| DSA-002 | OWNER DECISION REQUIRED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Contact placeholders supported; actual service/regulator contacts and terms missing; Supply legal contact and approved service terms after applicability review |
| DSA-003 | LEGAL REVIEW REQUIRED | docs/dsa-checklist.md; actual-code inventory linked there | Counsel: Assess Article 16 non-user form/contact and required fields |
| DSA-004 | LEGAL REVIEW REQUIRED | docs/dsa-checklist.md; actual-code inventory linked there | Counsel: Review existing reason-coded decisions and submission appeals scope |
| DSA-005 | LEGAL REVIEW REQUIRED | docs/dsa-checklist.md; actual-code inventory linked there | Counsel: Determine applicable obligations/exemptions and processes |
| DSA-006 | IMPLEMENTED | privacy.py:information; core/recommendations.py; privacy.tsx; test_privacy.py | See related unresolved policy/deployment rows |
| DSA-007 | LEGAL REVIEW REQUIRED | docs/dsa-checklist.md; actual-code inventory linked there | Counsel: Do not assume VLOP-specific duties apply |
| DSA-008 | LEGAL REVIEW REQUIRED | docs/dsa-checklist.md; actual-code inventory linked there | Counsel: No designation evidence; verify rather than assert exemption |
| DSA-009 | LEGAL REVIEW REQUIRED | docs/dsa-checklist.md; actual-code inventory linked there | Counsel: Inspect organization promotions; no BACity ticket marketplace |
| DSA-010 | LEGAL REVIEW REQUIRED | docs/dsa-checklist.md; actual-code inventory linked there | Counsel: Review deletion/payment asymmetry and audience |
| CONS-001 | OWNER DECISION REQUIRED | docs/compliance-owner-followup.md; test_privacy.py; public event serializer and existing authorization | Provider architecture preserved; trader identity, price and legal disclosures missing; Supply trader/address and approved price, renewal and withdrawal disclosures |
| CONS-002 | ALREADY SATISFIED | core/google_play_billing.py; core/consumer_billing.py; mobile/app/plus.tsx; test_google_play_billing.py; test_consumer_billing.py | See related unresolved policy/deployment rows |
| CONS-003 | LEGAL REVIEW REQUIRED | docs/consumer-subscription-checklist.md; actual-code inventory linked there | Counsel: Approve terms/confirmation and consumer remedies |
| CONS-004 | STORE/PROVIDER CONFIG REQUIRED | docs/consumer-subscription-checklist.md; actual-code inventory linked there | Owner: Verify actual products, pricing, confirmations and portal settings |
| STORE-001 | STORE/PROVIDER CONFIG REQUIRED | docs/store-privacy-inventory.md; actual-code inventory linked there | Owner: Verify SDK processing and submit accurate disclosures |
| STORE-002 | STORE/PROVIDER CONFIG REQUIRED | docs/store-privacy-inventory.md; actual-code inventory linked there | Owner: Provide public monitored deletion resource and listing URL |
| STORE-003 | IMPLEMENTED | mobile/app.json; AndroidManifest.xml; Info.plist; mobile privacy.test.mjs; actual Android merge/build | See related unresolved policy/deployment rows |
| LEGAL-001 | LEGAL REVIEW REQUIRED | docs/legal-review-input.md; actual-code inventory linked there | Counsel: Review privacy/ePrivacy/consumer/accessibility local rules |
| LEGAL-002 | IMPLEMENTED | privacy.tsx, privacy-admin.tsx; reused accessible CommunityUI; privacy.test.mjs; device accessibility unverified | See related unresolved policy/deployment rows |
| OPS-001 | PRODUCTION CONFIG REQUIRED | docs/compliance-launch-blockers.md; actual-code inventory linked there | Operations: Supply deployment values and validate launch config |
| LEGAL-003 | LEGAL REVIEW REQUIRED | docs/legal-review-input.md; actual-code inventory linked there | Counsel: Assess accessibility duties and screen-reader/release testing |
| CONSENT-002 | LEGAL REVIEW REQUIRED | docs/privacy-notice-facts.md; actual-code inventory linked there | Counsel: Decide legally consented purposes before building timestamp/version acceptance records |

## Validation / scope

Exact commands/results: compliance-validation.md. New privacy endpoint tests cover owner/admin gates, encrypted storage, calendar deadlines and extension bounds, immutable closed cases, export completeness/exclusions, deletion minimization, no content logs, block-decision privacy and moderation audit minimization. Mobile tests include source wiring plus executable mocked transport; not device E2E. Existing auth/recovery, messages, Groups, Area Watch, Level 3/source security and billing suites form regression evidence. No contracts, production regions, legal approval or live provider verification are inferred from passing tests.
