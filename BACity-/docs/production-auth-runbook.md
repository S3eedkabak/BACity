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
MAIL_FROM_NAME=BACity

OAUTH_CALLBACK_BASE_URL=https://api.bacity.example
OAUTH_APP_REDIRECT_URI=bratislava-events://oauth
ACCOUNT_ACTION_BASE_URL=https://app.bacity.example
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
GOOGLE_ANDROID_CLIENT_ID=...
GOOGLE_IOS_CLIENT_ID=...
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=...
EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=...
EXPO_PUBLIC_GOOGLE_IOS_URL_SCHEME=com.googleusercontent.apps....
APPLE_OAUTH_CLIENT_ID=...
APPLE_IOS_CLIENT_ID=com.bratislavaevents.app
APPLE_TEAM_ID=...
APPLE_KEY_ID=...
APPLE_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----
OAUTH_TOKEN_ENCRYPTION_KEY=...
```

Use port 465 with `SMTP_SSL=true` and `SMTP_STARTTLS=false`; use port 587 with the inverse. Verify SPF, DKIM, DMARC, the sender domain, and provider suppression/bounce settings before launch. Never commit `.env.production`.

Register these exact browser OAuth return URLs:

- Google: `https://api.bacity.example/auth/oauth/google/callback`
- Apple Service ID: `https://api.bacity.example/auth/oauth/apple/callback`

Register Android package `com.bratislavaevents.app` with every production signing SHA-1 used to distribute the app. Register iOS bundle `com.bratislavaevents.app`, its reversed Google client URL scheme, and the Sign in with Apple capability. Keep web, Android, and iOS Google clients in the same Cloud project.

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
| Native provider sheet returns to BACity and creates a session | Required | Required |
| Existing password account with same verified email links without creating a second user | Required | Required |
| Google then Apple with same verified email resolves to one BACity user | Required | Required |
| Apple private-relay email and subsequent sign-in without an email reuse the provider identity | N/A | Required |
| Explicit linking while signed in does not move an identity from another BACity account | Required | Required |
| Deleted account creates a new account rather than restoring anonymized history | Required | Required |

Check `oauth_identities`: `(provider, subject)` and `(provider, user_id)` are unique. An unauthenticated provider-verified matching email links to the existing BACity account; an explicit signed-in link targets the current account and returns a conflict if that provider identity belongs elsewhere. An identity without an email is accepted only when its provider subject is already linked.

Delete an Apple test account and confirm the response says `revoked`. If it says `manual_revoke_required`, confirm local erasure, remove BACity in the Apple ID settings, then investigate provider connectivity/key configuration. Confirm the deletion message reaches the former address and that no provider token or subject appears in account exports.

## Sign-off evidence

Record build versions, device/OS, provider console configuration screenshots, timestamps, message IDs, OAuth result, database row counts, and the tester. Do not paste tokens, passwords, authorization codes, private keys, or full email addresses into the report.
