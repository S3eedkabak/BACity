# Social collection during API and PostgreSQL outages

Social collection now has an **independent, durable collector outbox**. PostgreSQL is the destination for staging and publication, rather than the only place where collection progress/results can survive. No external queue service or new provider credentials are required.

## Delivery flow

1. PostgreSQL authorizes a job and reserves its provider budget before new paid work.
2. The collector journals the work to SQLite on the separate `social-outbox` Docker volume.
3. Already-authorized capture can finish while PostgreSQL or its staging gateway is unavailable. Apify launch responses/run IDs, normalized dataset pages, ScrapingAnt responses/settlements and collection completions are persisted locally.
4. The collector retries pending gateway deliveries every 30 seconds. New work waits behind the existing journal.
5. The gateway validates the original owner/lease and current permissions, then commits each operation and its delivery receipt **in one PostgreSQL transaction**.
6. Only the committed receipt acknowledgement marks the local message delivered. Once terminal work and all messages are acknowledged, raw local payloads are cleared.

A lost acknowledgement replays the same stable message ID and hash. PostgreSQL returns the stored result instead of staging another observation or charging another reservation. Capturing and redelivering never bypasses candidate review or writes directly to public event tables.

## What works during each outage

| Outage | Behavior |
|---|---|
| Regular BACity app API unavailable | Social acquisition/staging can continue through its separate gateway. The mobile app cannot load API-backed content. |
| PostgreSQL or social gateway unavailable | Buffered results stay on the collector volume. An authorized Apify run can finish and its results can be captured without waiting for PostgreSQL. An already-running bounded browser/HTTP capture can finish. |
| No PostgreSQL authorization/budget reservation available | No new paid requests or new collection jobs start. Cached permission/budget information is not used to authorize additional spend. |
| Collector process crashes or container is replaced | The same named volume restores owner identity, active work, provider responses and pending messages. It resumes or replays rather than repeating a known billable launch. |
| PostgreSQL comes back | Pending delivery retries automatically. Expired transport leases can be renewed for the same durable owner; buffered legacy jobs are protected from ordinary timeout/retention cleanup. |
| Publication relay faces a database outage | Previously queued publication remains in PostgreSQL; the relay's existing retry loop resumes after recovery. The API process itself is not required for the relay's direct canonical ingestion. |
| Publisher suspended, permission expired, emergency stop, owner mismatch or invalid payload | Delivery is blocked and the local data stays queued. It is not discarded or silently published. An operator must resolve the policy/conflict. |

While online, an active Apify collector refreshes cancellation state before each capture cycle, so emergency stops and publisher restrictions still reach a known remote run. During a database outage, the collector can finish bounded capture of already-authorized work; it cannot obtain a new spending grant.

A database outage is not permission to continue discovering indefinitely from stale approvals. The change protects authorized work and collected results while preserving budget and security checks.

## Storage and safety boundaries

- Persistent named volume: `social-outbox`, normally Docker project name plus `_social-outbox` (the current Mac uses `bacity-_social-outbox`).
- Container path: `/var/lib/bacity-outbox/outbox.sqlite3`.
- SQLite uses full synchronous commits, rollback journaling, secure deletion of acknowledged payloads and a process lock. A second collector cannot concurrently own the same journal volume.
- File mode is 0600. The collector is non-root, its root filesystem remains read-only, and only the outbox mount is writable persistent storage. Browser subprocesses do not receive the outbox configuration, machine key or provider tokens in their environment.
- The journal stores original lease capabilities and source content, **not provider API tokens or database credentials**. Treat volume backups as private data.
- Work is bounded to 12 MiB per active journal, 128 messages, a 64 MiB SQLite page budget and a 32 MiB free-disk safety threshold. Exhaustion fails closed and pauses new capture. Pending messages are never automatically evicted or expired to free space.
- Pending raw data can outlive the normal PostgreSQL observation-retention window during an outage/conflict. It remains until delivery acknowledgement or an explicitly reviewed operator action. Normal database raw-evidence retention applies after staging.
- PostgreSQL migration **0027** adds delivery receipts and the durable-job marker. Receipts contain body hashes and operation results, not raw captions. Receipt capacity is bounded at 100,000; if reached, deliveries pause with the local queue retained. Upgrade/maintenance planning must address receipt growth before that bound; there is no silent receipt deletion that could weaken replay protection.

This protects against PostgreSQL/gateway downtime, collector process crashes, and container recreation **while the outbox volume survives**. It does not guarantee survival of a destroyed Docker volume, disk/host failure, deliberate deletion, or loss of both database and queue backups. Back up the PostgreSQL data and collector volume independently. Do not use `docker compose down -v` to restart the stack.

An external request whose response/run ID was never received or durably saved remains inherently ambiguous. In particular, Apify provides no run-creation idempotency key in the implemented interface. A recorded launch intent with no known response is not blindly resubmitted; it retains estimated budget accounting and requires provider-side reconciliation. The outbox is not a guarantee that an unreachable source or an unreceived provider response can be reconstructed.

## Upgrade an existing installation

Back up the existing PostgreSQL database first. Let current work finish before replacing a pre-outbox collector. Apply migration 0027 as the database owner, reapply grants, then rebuild/recreate the social services. On the current configured Mac, from the application directory:

```sh
# Owner migration connection comes from the base app environment.
docker compose run --rm --no-deps api alembic upgrade head

docker compose exec -T postgres sh -c \
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < infrastructure/social/roles.sql

/Users/s3eed/.config/bacity/control up -d --build \
  social-admin social-gateway social-collector social-retention
```

The outbox volume is created automatically with the collector's writable directory ownership. Existing acquisition/publication flags and provider credentials do not need changing. This feature does not turn acquisition or publication on. For another host, use the portable wrapper and that host's environment paths from [deployment.md](deployment.md).

## Check pending deliveries

On the current Mac:

```sh
/Users/s3eed/.config/bacity/control exec -T social-collector \
  python -m app.social.acquisition.outbox status

/Users/s3eed/.config/bacity/control logs --tail 50 social-collector social-gateway
```

Status reports `work_pending`, `messages_pending`, `oldest_pending_seconds` and integrity, without captions, lease values or provider keys. No pending messages can still mean an active remote job is waiting; check `work_pending` too. A generic “delivery paused; local outbox retained” log means inspect gateway/database availability, storage capacity and current publisher permissions. A nonempty queue during a database outage is expected; once the database and permissions are available it should drain automatically.

Do not delete the journal or switch to an empty volume to clear an alert. Do not run multiple collector replicas with separate outboxes against the same single-worker schedule. Restart/recreate the existing collector with the same volume. A permanent permission conflict intentionally requires review; transient outages need no manual resubmission.

## Verification

Tests exercise independent on-disk persistence, process termination, container replacement with a retained volume, gateway outage after provider response, actual disposable PostgreSQL stop/start, expired leases, rollback before receipt commit, lost acknowledgements after commit, concurrent duplicate delivery, provider response reuse, disk-pressure backpressure and rejection of changed message bodies/owners. Provider calls in tests use fixtures; no real Instagram run is needed.

The existing website crawler (Levels 1–3) and canonical publication approval flow are preserved. This change targets the social collector's missing independent recovery journal.
