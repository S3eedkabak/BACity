# DPIA engineering draft — not legal approval

Based on [EDPB-endorsed DPIA guidance](https://www.edpb.europa.eu/documents/guideline/data-protection-impact-assessments-high-risk-processing_en). Counsel must determine whether formal DPIA/authority consultation is required, evaluate scale/audience and approve residual risk. Controller, reviewers and consultation date: REQUIRED. This is a risk-assessment input, not formal approval.

| Processing / necessity question | Risk to people | Current safeguards | Additional measure / residual / owner |
|---|---|---|---|
| Authentication/recovery supports access; are all identifiers needed? | Account takeover/exclusion | Hashes, one-use tokens, anti-enumeration, encrypted mail links | Recovery procedure, provider retention and privileged authentication review; Owner/Operations |
| Location helps discovery but is optional | Home/work inference, stalking, proxy history | Foreground/coarsened/request-scoped; no persistent GPS history | Audit tile/proxy/APM flows, approve location basis; Counsel/Operations |
| Area Watch needs stored definition | Persistent sensitive center inference | Owner-only/export/delete/bounds | Review inactive retention and backup access; Owner |
| Profile/social graph supports social discovery | Unwanted disclosure/contact; sensitive associations | Private controls, block, general-message default off, collections private default | Public-profile default/age safeguards unresolved; Product/Counsel |
| Private messages require body storage | Confidential communication exposure/recipient erasure conflict | AEAD, pair checks, scoped reports, no push previews | Servers decrypt; metadata plaintext; approve shared retention/deletion; Counsel |
| Groups need participants/preferences/votes | Hidden preference disclosure/coercive reveal | Own inputs, member gates, host-scoped actions, aggregates | Host can reveal within existing product policy; approve notice and retention; Product |
| Ranking needs preferences, not sensitive traits | Sensitive event-interest inference/filter bubbles | Deterministic factual reasons/diversity; no explicit sensitive trait model | Profiling basis/objection and minors evaluation; Counsel |
| Moderation needs evidence | Reporter exposure, overbroad staff access | Role-scoped workflow, minimal new audit, report-party checks | Review existing retained free-text and redress scope; Counsel |
| Public source/Level 3 promotes event coverage | Unwanted publication of names/contact data | Event-focused extraction/public-only allowlist/trust separation | Public availability is not exemption; notice/correction/reuse review; Counsel |
| Billing needs authoritative IDs | Subscription misbinding/account deletion obstruction | Provider authority/owner binding/AEAD purchase token | Active Play deletion block and financial retention policy unresolved; Owner/Counsel |
| DSAR/export/delete enable rights | Wrong-person release, private third-party disclosure | Authentication/admin assessment, scoped exports, encrypted cases | Proportionate identity checks, staffing, lost-account/public request contact; Owner |
| Backups/logs support availability | Reappearance of erased data/snapshot disclosure | Minimized app logs, encryption framework | Encrypted backups/key separation/external deletion ledger not verified; Operations |

Risk review: location, private communication, inferred interests, minors uncertainty and unverified infrastructure are HIGH unresolved launch topics. No assertion that residual risk is acceptable. If counsel finds unmitigated high risk, review prior consultation before launch.

Proportionality: no background location, no new DOB/document collection, no tracking SDK, no new behavioral surveillance, no LLM profiling. New request text is bounded and encrypted; identity evidence is not uploaded. User controls are necessary but do not alone establish lawful bases.
