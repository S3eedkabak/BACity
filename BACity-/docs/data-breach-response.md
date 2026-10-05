# Personal-data incident response and register

Operational draft; named incident lead, privacy owner, counsel, on-call contact and secure register location REQUIRED before launch. No real notification is sent by this repository.

DETECT -> CONTAIN -> PRESERVE MINIMIZED EVIDENCE -> ASSESS DATA/PEOPLE -> RISK ASSESSMENT -> RECORD -> ESCALATE -> AUTHORITY/USER NOTIFICATION DECISIONS -> REMEDIATE -> POSTMORTEM.

Record awareness timestamp immediately. A qualified decision maker assesses notification duties and the 72-hour authority-notification timeline; not every incident is automatically reportable. If delayed or information incomplete, document rationale and phased updates. Escalate without waiting for complete forensic certainty. [Commission breach guidance](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/obligations/what-data-breach-and-what-do-we-have-do-case-data-breach_en) and [GDPR Articles 33–34](https://eur-lex.europa.eu/eli/reg/2016/679/oj/eng).

## Restricted register template

| Case ID | Discovered/aware at UTC | Occurred at/unknown | Systems | Data categories | Approximate subjects/records | C/I/A effect | Consequences | Containment/mitigations | Notification decision/rationale | Authority sent at | User notice decision/sent at | Owner | Follow-up |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| TEMPLATE_ONLY | REQUIRED | UNKNOWN | REQUIRED | categories, not raw data | estimate + confidence | assess | assess individual risk | action references | human decision + basis | not sent/actual timestamp | not sent/actual timestamp | named lead | review date |

Keep register outside public Git and general moderator tools. Store references/hashes/scope, not message bodies, bearer tokens or unnecessary identifiers. Restrict access, record investigators, define approved retention; do not create a surveillance DB.

Scenarios/runbook: revoke leaked credentials and session versions; isolate compromised services/crawler sources; preserve relevant audit IDs; assess DB/key co-compromise; separately assess backup/token/provider exposure; notify processor contacts according to contracts; restore only after erasure reconciliation; confirm provider secret rotations and source integrity. Encryption does not excuse risk assessment: plaintext metadata remains and server keys may be compromised. Preserve evidence without re-logging secrets. Rehearse with synthetic tabletop incidents and record owner approvals.
