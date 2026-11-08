# Encryption and key management

Audit date: 2026-10-05. Messaging is **not end-to-end encrypted**. Authorized API
processes decrypt bodies; a compromised application process or key holder can read
them. Deployment must not market application encryption as E2EE.

## Decisions and threat coverage

| Model | Decision | Threats/tradeoffs |
| --- | --- | --- |
| A: HTTPS + infrastructure storage encryption only | Insufficient alone for these bearer-equivalent/private fields | TLS protects transit; volume encryption protects lost disks but not readable SQL dumps or DB-only credentials |
| B: server/application AEAD | Implemented for five unindexed TEXT fields | Protects DB-only snapshots without keys; API/export/SMTP/provider operations still decrypt legitimately |
| C: true E2EE | Separate product/architecture project, not implemented | Requires device enrollment, multi-device keys, recovery/lost-device design, backups, user-assisted reports and preview/search changes |

Encrypted via the existing cryptography library (now explicitly pinned 50.0.1):

- `messages.body`: private pairwise content.
- `consumer_subscriptions.provider_purchase_token`: provider credential needed for reconciliation.
- `mail_outbox.body`: pending verification/reset/exchange links contain usable action secrets.
- `privacy_requests.details` and `privacy_requests.response`: bounded rights-request text and assessed replies (migration 0014 adds the workflow).

The SQLAlchemy `EncryptedText` type preserves TEXT columns, API response shapes,
provider reconciliation and existing owner/member authorization. It encrypts every
ORM write and decrypts ORM reads. These fields are not indexed/searched by content;
Play ownership lookup still uses the separate SHA-256 purchase identity. No schema
migration was needed for the original three fields; migration 0014 adds encrypted privacy requests without changing that architecture. Raw SQL writers can bypass ORM encryption: restrict DB access,
use the operational verifier, and do not add raw writers to these fields.

Public events/venues are deliberately not encrypted. User email, message metadata,
private collection/profile/Group JSON, claim/submission evidence and private watch
coordinates remain plaintext in DB. They still require restricted DB/backup access
and infrastructure encryption. Encrypting indexed/queried JSON would require a
separate schema/query/operational design; this pass does not disguise that gap.
AEAD does not defend against full DB-write compromise (roles/ownership can be changed)
or an attacker also holding the app key. Associated data binds field + format/key ID,
not row identity: same-field ciphertext replay is not cryptographically prevented.

## Cryptography and format

AES-256-GCM through `cryptography.hazmat.primitives.ciphers.aead.AESGCM`, a 32-byte
key, independent OS-random 12-byte nonce per write, full 16-byte authentication tag.
No custom cipher/KDF/MAC was implemented. The textual envelope is
`bacity:aead:v1:<key-id>:<base64(nonce || ciphertext-with-tag)>`.
The envelope header and fixed `table.column` context are authenticated associated
data, preventing cross-field substitution. Nonces are never reused intentionally.
Random nonces require sensible per-key usage limits and periodic rotation at scale.
See the [library's AEAD contract](https://cryptography.io/en/latest/hazmat/primitives/aead/).

Authentication failure, unknown key, malformed envelope or encrypted-mode plaintext
does not return a body/token. API read failures return a generic 503. No diagnostic
includes the body/ciphertext/key. SQLAlchemy production engine suppresses parameter
values in SQL errors. Keys never enter DB rows, mobile builds or images.

## Configuration and injection

`PRIVATE_DATA_KEYS`: JSON map of key IDs to standard-base64 random 32-byte keys.
`PRIVATE_DATA_ACTIVE_KEY`: one configured ID for new writes. Up to ten keys, IDs
restricted to 1-32 letters/digits/underscore/hyphen. IDs are public metadata, not keys.
Generate/inject key material through deployment secret management; do not paste
values into tickets, terminal logs, source, `.env.example` or Git. The examples
contain empty settings only. Keep production/staging/development keys separate.

Staging/production Settings fail startup without a valid ring and active ID.
Configured encryption also rejects legacy plaintext in development. Development
with BOTH encryption settings empty retains plaintext compatibility explicitly;
never use that mode for real private data or deploy it as production. The complete
API test suite injects fresh disposable keys and exercises encrypted storage.

API, maintenance and backfill process need the same key ring. The crawler does not
need these keys to discover public events. Existing environment files may inject
more secrets than a service needs; use service-specific secrets at deployment.
Keys are environment-injected here, not KMS envelope-encrypted. This protects DB-only
theft, not someone with container/deployment-secret access.

## Safe initial rollout / legacy backfill

Do not activate keys on a populated database while API/maintenance are running.
This audit did not backfill any real database.

1. Take an encrypted, access-restricted backup and verify recoverability. Keep keys
   separately from dumps; existing plaintext backups remain sensitive.
2. Stop API/maintenance and all writers of these fields. Migrations/DB schema remain unchanged.
3. Inject the new ring and active ID into the offline application environment.
4. Run `python -m app.private_data` to authenticate existing envelopes and count
   legacy rows. It is verify-only; legacy data produces a nonzero exit.
5. Run `python -m app.private_data --apply` to encrypt legacy rows.
6. Run `python -m app.private_data` again; require zero legacy rows and no failures.
7. Start API/maintenance with identical keys. Verify conversation reads, exports,
   mail dispatch and Play reconciliation through authorized test accounts.

The utility uses whitelisted identifiers and keyset pages of 100 records, commits
each page, emits counts only and is resumable/idempotent. It authenticates encrypted
rows, does not silently reinterpret corrupt ciphertext, and never deletes records.
Use an isolated copied DB for rehearsal. For unusually large individual legacy
records, memory is bounded by page size, not a universal byte limit.

Backward compatibility is explicit offline backfill, not a production plaintext
fallback. Unknown envelope versions/reserved-prefix collisions require investigation
against the backup, not automatic plaintext acceptance. Do not roll back to an old
binary that expects plaintext after applying backfill. Restore an isolated matched
backup/version/key set if rollback is necessary; never expose ciphertext as content.

## Rotation and recovery

1. Add a newly generated key under a new ID to all API/maintenance rings; retain old keys.
2. Switch the active ID consistently. Old envelopes still decrypt; new writes use new ID.
3. During a stopped-writer maintenance window, run
   `python -m app.private_data --apply --rotate`, then verify-only.
4. Retain old keys securely for backups still needing them. Retire only after
   verifying live rows and approved backup lifecycle. Never overwrite a key under
   an existing ID or delete it simply because new writes use another ID.
5. Rehearse restore into an isolated DB. Lost keys mean lost encrypted data; a
   same-ID wrong key fails authentication. There is no plaintext recovery shortcut.

Compromised keys require incident scoping, rotation/re-encryption and revocation of
exposed provider/action secrets. Rotation cannot make copies already decrypted by
an attacker secret again. No online/destructive bulk re-encryption was performed.

## Other tokens/passwords and TLS

Passwords use passlib bcrypt_sha256 (default cost 12) with secure legacy bcrypt
verification; they are hashed, never reversibly encrypted. Reset/verify/exchange
tokens and Group invite tokens are random, hash-stored and expiring; action tokens
are single-use. JWTs are signed, not encrypted, carry no private message/location
payload, and require expiry/subject/live account token version. Signing/ingestion/
SMTP/Stripe/Google credentials belong in deployment secrets, not database backups.
Apple refresh credentials retain existing Fernet protection with the independently
injected `OAUTH_TOKEN_ENCRYPTION_KEY`; it has no key-ID rotation utility in this pass.

Public clients use HTTPS via Caddy; staging/production configured app/CORS/API
callback/action URLs are HTTPS. OAuth/payment clients use provider HTTPS; SMTP
STARTTLS/implicit TLS verifies certificates/hostnames. Internal Docker HTTP and
default DB connections are NOT claimed encrypted. Browser/device TLS, network
segmentation, PG TLS if required, disk/backup encryption and secret-manager recovery
must be validated operationally. No key is embedded in an Expo export.

Tests cover snapshot bytes, endpoint decrypt/export, corrupt storage returning 503,
randomized envelopes, field substitution, old-key reads, missing-key failures,
legacy backfill and 205-row multi-page rotation/idempotence. Real PostgreSQL checks
encrypted purchase storage plus unchanged schema/migration chain. No E2EE/device
key recovery or real production backup restore was tested.
