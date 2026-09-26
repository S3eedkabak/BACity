# Production authentication runbook

## Required secrets

Production startup fails unless `.env.production` contains a real sender and all provider credentials:

```env
SMTP_HOST=smtp.provider.example
SMTP_PORT=587
SMTP_STARTTLS=true
SMTP_SSL=false
SMTP_USERNAME=...
SMTP_PASSWORD=...
MAIL_FROM=noreply@bacity.example

OAUTH_CALLBACK_BASE_URL=https://api.bacity.example
OAUTH_APP_REDIRECT_URI=bratislava-events://oauth
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
APPLE_OAUTH_CLIENT_ID=...
APPLE_TEAM_ID=...
APPLE_KEY_ID=...
APPLE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
```

Use port 465 with `SMTP_SSL=true` and `SMTP_STARTTLS=false`; use port 587 with the inverse. Verify SPF, DKIM, DMARC, the sender domain, and provider suppression/bounce settings before launch. Never commit `.env.production`.

Register these exact OAuth return URLs:

- Google: `https://api.bacity.example/auth/oauth/google/callback`
- Apple Service ID: `https://api.bacity.example/auth/oauth/apple/callback`

## SMTP acceptance test

Run each test with a new production test account and inspect the real recipient inbox (including headers and spam placement):

1. Register; confirm one verification message arrives and its HTTPS link opens `/account?action=verify`.
2. Verify once; confirm a second use is rejected and the account becomes verified.
3. Request a reset for both an existing and nonexistent email; confirm identical API responses and mail only for the existing account.
4. Reset once; confirm the old session and old password stop working and the link cannot be reused.
5. Temporarily set an invalid SMTP password, request another reset, and run the maintenance worker. Confirm `mail_outbox.attempts` increments, `sent_at` stays null, `error` is populated, and `next_attempt_at` advances exponentially. Restore the credential and confirm the same row is delivered once and its body becomes `[Delivered]`.

Useful database check:

```sql
SELECT recipient, subject, attempts, next_attempt_at, sent_at, error
FROM mail_outbox ORDER BY created_at DESC LIMIT 20;
```

## OAuth device matrix

Use production-signed builds, not Expo Go.

| Test | Android | iOS |
|---|---:|---:|
| Google new account and returning account | Required | Required |
| Apple new account and returning account | N/A | Required |
| Cancel/deny and retry | Required | Required |
| Deep link returns to BACity and creates a session | Required | Required |
| Existing password account with same verified email links without creating a second user | Required | Required |
| Google then Apple with same verified email resolves to one BACity user | Required | Required |
| Apple private-relay email and subsequent sign-in without an email reuse the provider identity | N/A | Required |
| Deleted account cannot be restored by signing in with the old provider subject | Required | Required |

Check `oauth_identities`: `(provider, subject)` and `(provider, user_id)` are unique. A provider-verified matching email links to the existing BACity account; an identity without an email is accepted only when its provider subject is already linked.

## Sign-off evidence

Record build versions, device/OS, provider console configuration screenshots, timestamps, message IDs, OAuth result, database row counts, and the tester. Do not paste tokens, passwords, authorization codes, private keys, or full email addresses into the report.
