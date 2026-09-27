# Account lifecycle policy and operations

## Export

An authenticated user can choose **Account → Export my data**. `GET /community/account/export` returns portable JSON containing the profile, linked provider names and link dates, saved events, authored events and submissions, social/activity records, collections, comments, messages, and notifications. Provider subjects/tokens, password hashes, action-token secrets, internal risk flags, reviewer identifiers, and security audit logs are excluded. Export creation is audited.

## Deletion and retention

Deletion is immediate and irreversible in the application:

- JWTs are revoked and the account is disabled.
- Email, password hash, profile, identity-verification state, location preferences, and messaging settings are anonymized.
- OAuth identity mappings, encrypted provider credentials, pending action tokens, queued email, saved events, messages, follows, blocks, notifications, memberships, votes, confirmations, reports, private collections, and account rate-limit keys are erased.
- Unpublished submissions are withdrawn and their payload, appeal, and decision text are erased.
- Published reviews, comments, public collections, approved/rejected moderation records, attributed places/utilities, and audit logs remain for public-record integrity, abuse prevention, and legal accountability. They reference only the anonymized user row (`Deleted account`) and contain no account email or profile data.
- Operational backups expire on the backup schedule and are not edited in place. Restores must immediately re-run deletion records captured after the backup; production operations must retain that deletion ledger outside the restored database.

BACity does not retain Google access or refresh tokens. Apple may issue a refresh token only on the first authorization; BACity stores it encrypted at rest solely to revoke the Apple authorization during deletion. The encryption key must be held outside the database. Deletion attempts Apple's revocation endpoint before erasing the credential and reports `manual_revoke_required` when the provider cannot be reached. The account is still deleted locally in that case, and the user should remove BACity from **Sign in with Apple** settings.

The product owner must approve the legal retention basis and duration for anonymized public contributions, rejected moderation records, audit records, backups, and the external deletion ledger before launch. The implementation intentionally does not invent a jurisdiction-specific retention period.

## Recovery

- Password account: request a reset from **Account**. The response never reveals whether the address exists. The emailed link is single-use and expires; request another after expiry.
- Social account: sign in through any linked provider. A user who still receives mail at the provider-verified address (including an Apple relay address) may use password reset to establish a BACity password.
- Lost provider but another linked provider/password remains: use the remaining method, then link a replacement provider while authenticated.
- Lost email and every provider: do not bypass authentication or manually set a password. Support may change an address only under an organization-approved identity-verification procedure, with an audit trail and second-person approval. Until that procedure exists, recovery is unavailable.
- Suspected compromise: increment `users.token_version`, unlink compromised OAuth identities, require password reset, and review audit logs.
- Disabled or moderated account: password reset does not reactivate it; use the moderation appeal/support process.
- After deletion: recovery is impossible. Do not reactivate the anonymized row. The user must register a new account; retained public contributions are not automatically reassigned.

Every support action requires the ticket ID, operator, timestamp, verification method, action taken, and a second-person review for email changes or identity-link changes.
