# Account lifecycle policy and operations

## Export

An authenticated user can choose **Account → Export my data**. `GET /community/account/export` returns JSON containing the profile, linked provider identifiers, saved events, contributions, moderation history involving the user, social/activity records, collections, comments, messages, and notifications. Password hashes and action-token secrets are excluded. Export creation is audited.

## Deletion and retention

Deletion is immediate and irreversible in the application:

- JWTs are revoked and the account is disabled.
- Email, password hash, profile, identity-verification state, location preferences, and messaging settings are anonymized.
- OAuth identity mappings, pending action tokens, queued email, saved events, messages, follows, blocks, notifications, memberships, votes, confirmations, reports, private collections, and account rate-limit keys are erased.
- Unpublished submissions are withdrawn and their payload, appeal, and decision text are erased.
- Published reviews, comments, public collections, approved/rejected moderation records, attributed places/utilities, and audit logs remain for public-record integrity, abuse prevention, and legal accountability. They reference only the anonymized user row (`Deleted account`) and contain no account email or profile data.
- Operational backups expire on the backup schedule and are not edited in place. Restores must immediately re-run deletion records captured after the backup; production operations must retain that deletion ledger outside the restored database.

BACity exchanges OAuth authorization codes only for verified identity claims and does not retain Google/Apple access or refresh tokens. Deletion removes the local provider subject mapping; there is therefore no provider-hosted BACity data or live provider token to revoke. Users may separately remove BACity from their Google Account connections or Apple **Sign in with Apple** settings.

## Recovery

- Before deletion: use password reset. OAuth users can sign in again through any linked provider.
- Lost email/provider access: support may restore access only after documented identity verification; support must never set or disclose a password. Issue a password reset to a newly verified address and audit the address change.
- Suspected compromise: increment `users.token_version`, unlink compromised OAuth identities, require password reset, and review audit logs.
- After deletion: do not reactivate the anonymized row. The user must register a new account; retained public contributions are not automatically reassigned.

Every support action requires the ticket ID, operator, timestamp, verification method, action taken, and a second-person review for email changes or identity-link changes.
