# Compliance launch blocker register

This is not release approval. Every unresolved master-checklist ID appears here. BLOCKER means launch-blocking in this engineering register, including unconfirmed applicability; HIGH requires documented remediation/acceptance. Do not fabricate policy/contract answers to turn this register green.

| ID | Severity | Category | Reason | Owner | Required action | Blocks launch? |
|---|---|---|---|---|---|---|
| GDPR-001 | BLOCKER | OWNER | Identity/address/contact still not supplied; blank configuration added | Owner | Supply approved controller/trader identity, address and public contacts | Yes |
| GDPR-002 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Approve bases for each ROPA activity | Yes |
| GDPR-004 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Approve factual notice before launch | Yes |
| GDPR-007 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Approve portability vs access scope | Yes |
| GDPR-009 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Decide subscription-block and shared-record policy | Yes |
| GDPR-011 | RESOLVED PRODUCT CONTROL | CODE | Owner approved existing public/private controls; private behavior regression-tested | Product | Preserve user choices; GDPR bases and notice review remain separate | No |
| GDPR-012 | BLOCKER | OWNER | No indefinite discretionary retention approved; exact category durations still missing | Owner | Approve justified category durations; keep unresolved categories POLICY_REQUIRED | Yes |
| GDPR-014 | BLOCKER | PRODUCTION | Deployment values/infrastructure unavailable | Operations | Encrypted backups, retention and erasure replay on restore | Yes |
| GDPR-015 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Assess profiling/location/chat risk and consultation need | Yes |
| GDPR-016 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Determine actual establishment and appointment duties | Yes |
| GDPR-017 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Assess event-interest inference without adding sensitive profiles | Yes |
| GDPR-018 | HIGH | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Classify discovery ranking; no rights/credit adjudication found | No |
| GDPR-019 | BLOCKER | OWNER | Configured channel supported; actual monitored public contact absent | Owner | Supply and monitor a non-account privacy contact | Yes |
| GDPR-021 | BLOCKER | OWNER | Initial responsible role is BACity administrator/owner; retention/contact/review staffing not operational | Owner | Configure monitored contact, assign authorized administrators and approve case retention | Yes |
| SOC-002 | RESOLVED PRODUCT CONTROL | CODE | Owner approved surviving participant conversation retention; legal erasure review remains GDPR-009 | Product | Retain encrypted delivered history under existing expiry; reject deleted authentication and new sends | No |
| CRAWL-002 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Review source transparency, correction and reuse rights | Yes |
| CRAWL-003 | BLOCKER | LEGAL | Anonymous-by-default community event attribution implemented; submission retention still requires approval | Product | Review retained internal submission/provenance duration and basis; no public event attribution | Yes |
| ORG-002 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Separate B2B organization from consumer account | Yes |
| MINOR-001 | BLOCKER | LEGAL | Owner approved adults-only 18+ audience; consistent signup/OAuth eligibility mechanism awaits counsel | Owner | Approve proposed unselected versioned eligibility confirmation and legacy/OAuth enforcement; no DOB | Yes |
| MINOR-002 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Review Slovak law and actual lawful bases; no invented age | Yes |
| EPRIV-001 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Assess necessary storage and Slovak implementation | Yes |
| EPRIV-004 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Classify chat service and confidentiality duties | Yes |
| CONSENT-001 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Do not present native permission as approved lawful basis | Yes |
| PROC-001 | BLOCKER | PROCESSOR | Vendor roles, regions and signed terms unverified | Owner | Confirm actual vendors, roles and signed terms | Yes |
| PROC-002 | BLOCKER | PROCESSOR | Vendor roles, regions and signed terms unverified | Operations | Assess provider-held data; no blind financial deletion | Yes |
| TRANSFER-001 | BLOCKER | PROCESSOR | Vendor roles, regions and signed terms unverified | Counsel | Confirm regions, subprocessors, adequacy/SCC/TIA as applicable | Yes |
| BREACH-002 | BLOCKER | OWNER | Initial responsible role is administrator/owner; named contacts and rehearsal missing | Owner | Configure operations contact and rehearse incident assessment and notification | Yes |
| SEC-001 | BLOCKER | PRODUCTION | Deployment values/infrastructure unavailable | Operations | Inject keys and offline-backfill before serving | Yes |
| SEC-002 | BLOCKER | CODE | Known critical dependency upgrade requires coordinated platform work | Engineering | Coordinate dependency upgrades recorded by security audit | Yes |
| SEC-003 | BLOCKER | PRODUCTION | Deployment values/infrastructure unavailable | Operations | Apply redaction/retention/access policies to infrastructure | Yes |
| DSA-001 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Assess hosting/platform scope, size and Slovak duties | Yes |
| DSA-002 | BLOCKER | OWNER | Contact placeholders supported; actual service/regulator contacts and terms missing | Owner | Supply legal contact and approved service terms after applicability review | Yes |
| DSA-003 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Assess Article 16 non-user form/contact and required fields | Yes |
| DSA-004 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Review existing reason-coded decisions and submission appeals scope | Yes |
| DSA-005 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Determine applicable obligations/exemptions and processes | Yes |
| DSA-007 | HIGH | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Do not assume VLOP-specific duties apply | No |
| DSA-008 | HIGH | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | No designation evidence; verify rather than assert exemption | No |
| DSA-009 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Inspect organization promotions; no BACity ticket marketplace | Yes |
| DSA-010 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Review deletion/payment asymmetry and audience | Yes |
| CONS-001 | BLOCKER | OWNER | Provider architecture preserved; trader identity, price and legal disclosures missing | Owner | Supply trader/address and approved price, renewal and withdrawal disclosures | Yes |
| CONS-003 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Approve terms/confirmation and consumer remedies | Yes |
| CONS-004 | BLOCKER | STORE | Release/console/provider configuration unverified | Owner | Verify actual products, pricing, confirmations and portal settings | Yes |
| STORE-001 | BLOCKER | STORE | Release/console/provider configuration unverified | Owner | Verify SDK processing and submit accurate disclosures | Yes |
| STORE-002 | BLOCKER | STORE | Release/console/provider configuration unverified | Owner | Provide public monitored deletion resource and listing URL | Yes |
| LEGAL-001 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Review privacy/ePrivacy/consumer/accessibility local rules | Yes |
| OPS-001 | BLOCKER | PRODUCTION | Deployment values/infrastructure unavailable | Operations | Supply deployment values and validate launch config | Yes |
| LEGAL-003 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Assess accessibility duties and screen-reader/release testing | Yes |
| CONSENT-002 | BLOCKER | LEGAL | Applicability, basis or legal policy cannot be concluded from code | Counsel | Decide legally consented purposes before building timestamp/version acceptance records | Yes |

## Concrete limitations / rollout

Active Google Play subscriptions still block deletion until the paid period ends. Retained free text/UUIDs are not proven anonymous. Owner-approved profile choices, anonymous event attribution, shared-message product behavior and adults-only audience do not settle legal bases, age enforcement or retention. Actual contacts, non-account channels, classification, contracts, store and production actions remain unresolved. No marketing/tracking SDK or Apple IAP added. Critical dependency advisories remain open. Two resolved product controls are retained above for traceability; 46 unresolved IDs remain.

Before release: migrate to 0014; inject keys and offline-backfill legacy private text with writers stopped; staff monitored privacy/contact channels; approve and publish URLs/versions; implement operational backup/deletion reconciliation; sign/review relevant processor terms/transfers; verify provider purchase/cancellation disclosures, release permissions/store declarations and accessibility. New controls are not production deployment proof.
