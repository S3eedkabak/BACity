# Retention / deletion policy matrix

Durations below describe EXISTING technical behavior, not invented legal mandates. Every unresolved duration is POLICY_REQUIRED. Controller/counsel must approve purpose, exceptions and enforceability before production. The previous account-lifecycle document overstates anonymization: retained content and UUID linkage may still be personal data.

Owner direction: no indefinite discretionary "just in case" retention. This supplies no missing duration. Existing configurable cleanup remains; every POLICY_REQUIRED category needs an approved purpose, duration and enforceable mechanism before launch.

| Category / purpose | Trigger / existing mechanism | Duration | Erasure action | Exception / owner decision |
|---|---|---|---|---|
| Users/auth | Explicit deletion disables row/token version and substitutes email/hash/profile | Tombstone POLICY_REQUIRED | ANONYMIZE account fields; retained UUID is pseudonymous, not proven anonymous | Public/financial integrity and reidentification; Owner/Counsel |
| Reset/verification/exchange | Purpose expiry + worker deletes expired action tokens after additional day | Reset 30 min; verification 24h; existing cleanup grace 1 day | DELETE tokens immediately on account delete | Worker availability; expired bearer stays invalid |
| Email/outbox | Sent body becomes [Delivered]; worker deletes rows older than 7 days | Existing 7 days, POLICY approval needed | DELETE queued recipient rows; one deletion-confirmation email created | Provider retains independent copies; SMTP retries bounded at 10 |
| Messages/metadata | Worker deletes messages older than configured message_retention_days | Existing default 90 days; POLICY approval needed | Retain encrypted history for active counterpart; erase when both delete | Approved product direction; erasure/recipient rights/evidence/backups LEGAL REVIEW |
| Private profile/avatar | Explicit account deletion | Until deletion; POLICY_REQUIRED inactivity | DELETE photo file; ANONYMIZE profile | Public avatar URLs/cache copy may remain externally |
| Follows/saves/blocks/votes/confirmations | Explicit account deletion | POLICY_REQUIRED | DELETE own relations and incoming follow/block relationships | Hash rate buckets expire separately |
| Private collections | Explicit account deletion | POLICY_REQUIRED | DELETE private collections | Public collections retain tombstone author/content; legal review |
| Reviews/revisions/comments/public collections | Current published records retained | POLICY_REQUIRED | DETACH recognizable profile via tombstone, not guaranteed anonymous text | Own/third-party names in text need assessed erasure |
| Groups | purge_after = event window end + write grace + existing 90 days; cleanup currently API-triggered | Existing lifecycle; POLICY approval needed | DELETE own votes/preferences; cancel hosted session and clear invite | Shared host/category records remain; periodic cleanup uptime |
| Area Watches | Owner delete/account delete | POLICY_REQUIRED inactive/unmaintained account | DELETE definitions/coordinates | Expired Plus can still list/delete; no location-history claim |
| Pending/appealed submissions | Account delete withdraws and clears payload/reasons/appeal | POLICY_REQUIRED before delete | DELETE CONTENT/tombstone workflow | Approved AND rejected payloads currently retained |
| Published canonical events/provenance | Public facts remain independently useful | POLICY_REQUIRED personal fields | DETACH identifying account profile; assess personal text separately | Public availability does not remove rights; no automatic destruction of event truth |
| Candidate/source learning | Candidate URL/operational facts with no contributor identity | Operational POLICY_REQUIRED | Public source may remain after account deletion | Source URLs can identify public persons; no private source learning |
| Reports/moderation/audit | Reporter report rows deleted; other decisions/audit retain pseudonymous IDs | POLICY_REQUIRED | DELETE own reports; retained audit/content must be reviewed | Do not rewrite security evidence automatically |
| OAuth | Account delete removes provider mappings; Apple revoke attempted | Until unlink/delete | DELETE local encrypted credential/link | Provider connected-app and logs need separate action |
| Consumer payment/org billing | Provider-specific cancellation/reconciliation; retained financial references | POLICY_REQUIRED financial/fraud | Erase expired Play token; retain pseudonymous provider state | Active Play block; Stripe identifiers remain; provider obligations |
| Notifications | Account delete removes own notifications and non-message account targets | POLICY_REQUIRED general TTL | DELETE own; retain counterpart generic message inbox links | No deleted private profile fields; no invented universal TTL |
| Privacy requests | Account delete clears encrypted text and user linkage | POLICY_REQUIRED case metadata/audits | DELETE CONTENT and DETACH FROM IDENTITY | Do not declare request legally fulfilled; human follow-up needed before deletion |
| Rate buckets | Worker purges windows older than existing 172800 seconds | Existing 2 days | DELETE hashed buckets | Keys hashed; deletion .contains(raw UUID) does not match hashes; expiry limits residual |
| Logs/monitoring/search | No active Redis/OpenSearch private integration; operator logs | POLICY_REQUIRED | Restricted manual assessment | No new private logging; reverse proxy/APM separate |
| Backups | No implemented per-person physical rewrite | POLICY_REQUIRED | Restore must replay independent deletion ledger before access | PRODUCTION CONFIG REQUIRED encrypted storage/expiry/restore exercise |

Do not silently introduce DSAR/moderation/financial cleanup durations. Restriction/objection requests need assessed instructions; request submission does not automatically freeze all processing.

## Backup runbook requirements

Operations must choose encrypted storage, separate key/backup access, named administrators, approved retention, restore isolation and tested restore checks. A live deletion is not immediate physical deletion of snapshots. Keep a minimized, access-controlled erasure ledger outside restored databases, retain only what reconciliation needs, replay before serving restored data, and audit it. No such deployed ledger is claimed here. Whole-key destruction is not per-user erasure and could destroy other users' messages; retired keys are retained only per approved restore policy.
