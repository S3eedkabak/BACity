# Starting the BACity control panel

Use this guide for everyday startup after the database, credentials, HTTPS and first owner have been configured. For a new server or first installation, follow [deployment.md](deployment.md).

For durable buffering and recovery during database/worker outages, see [social_outage_recovery.md](social_outage_recovery.md).

The **private control panel** and **regular app API** are separate services sharing the same PostgreSQL database. The mobile app/development server is separate again. Starting the panel does not require starting the app API.

## Everyday publisher workflow

1. Open **Publishers → Add publisher**. Enter the Instagram profile/event link, name, type and a short description. Venue information is optional.
2. The publisher is saved **Awaiting approval**. No provider request runs yet.
3. An owner or staff member with approval rights opens **Review**, checks the displayed details and confirms **Approve & start daily checks**. That single reviewed action records approval and starts monitoring. No separate access form, manual post link, priority, score or schedule setting is needed.
4. The first check is due immediately and the collector normally picks it up within 30 seconds, subject to the provider, spending limits and any existing buffered work. Provider execution can take longer. Later checks run no more than once per 24 hours, with **at most two posts per publisher**. Failed checks do not trigger unlimited paid retries.
5. **Daily checks** shows results; publisher details show collected posts; **Events to review** contains extracted events. Publication remains separate and respects independent-review rules.

A publisher's approval does not override a login wall, blocked source, rate limit, provider outage or spending limit. These appear as actionable status messages. Existing approved-but-paused publishers stay paused through the upgrade; review and start them explicitly. Editing source details returns the publisher to approval. Pause/resume or switching providers cannot create a second daily allowance.

**Settings** contains team access, activity logs, passkeys, system pause and advanced provider/access diagnostics. Technical controls are not part of everyday publisher setup. Staff-reviewed collection approval lasts until edited/revoked/suspended; legacy explicit access reviews retain their existing expiry behavior.

Staff sessions now allow **two hours idle and eight hours total**. While you actively use the visible page, activity keeps the session current. A truly expired session or sensitive team/security/publication action opens an in-place passkey prompt and resumes the rejected request after verification, preserving the form. Revoked sessions and staff permissions remain enforced. Form contents are held only in the current page, not localStorage; refreshing/closing the tab can discard an unfinished form.

For private post images and free local poster OCR, see [post_images_ocr.md](post_images_ocr.md). Images and poster text appear automatically for collected posts; no new key or extra paid crawl is required.

For event filtering, giveaway dates, deduplication and legacy draft cleanup, see [social_event_filtering.md](social_event_filtering.md).

## Configuration files

| File | Purpose |
|---|---|
| Application root `.env` | Regular API/backend, normal app authentication, website crawler Levels 1–3, and migration configuration. |
| Private `social.env` | Panel service connections and worker secret, Apify/ScrapingAnt credentials, social acquisition settings, budgets and flags. |
| Private `runtime.override.yml` | Deployment-specific runtime settings; the configured local file runs social retention hourly. |
| `apps/mobile/.env` | Client settings such as the API address; never backend/provider secrets. |

On the current Mac, the private files are in `/Users/s3eed/.config/bacity/`. Only the social collector receives the provider token values; the panel receives configuration-presence hints.

## Current Mac: choose what to start

Run the commands below from the application directory using `./control`. It loads both backend environment files and the same Compose overlays for startup, shutdown and inspection. The existing `/Users/s3eed/.config/bacity/control` command delegates to this launcher and can still be used from any directory. `-d` keeps services running in the background; `--build` builds their current images before starting them.

### Two everyday start commands

```sh
./control up main
./control up panel
```

Both show build output, start services in the background and immediately stream live service logs (including the last 100 lines). **Ctrl+C closes the log stream; it leaves the backend running.** Use a second terminal for the other backend, or press Ctrl+C before starting it. `main` starts PostgreSQL, Redis, OpenSearch, the app API, website crawler and app maintenance. `panel` starts PostgreSQL, the private panel and HTTPS proxy, social gateway, collector, provider egress and hourly retention. Neither starts the mobile development server. Existing collection/publication settings and publisher approvals remain in force.

Run both commands, in either order, to run both sides. They share the same PostgreSQL configuration and persistent volumes. Starting one side leaves the other running. The longer service-specific commands below remain available.

### Everyday command reference

| Command | What it does |
|---|---|
| `./control up main` | Build/start the app backend and show its live logs. |
| `./control up panel` | Build/start the panel and social services and show their live logs. |
| `./control down main` | Stop app services; leave PostgreSQL and the panel running. |
| `./control down panel` | Stop panel/social services; leave PostgreSQL and the app running. |
| `./control prune main` | Stop and remove only main-backend containers; keep the shared database and panel. |
| `./control prune panel` | Stop and remove only panel/social containers; keep the shared database and main backend. |
| `./control down` | Stop/remove the entire stack's containers and networks, including PostgreSQL. Persistent data volumes remain. |
| `./control logs -f` | Reopen live logs for the running services. Ctrl+C only closes logs. |
| `./control ps` | Show which services are running. |
| `docker system prune` | Ask Docker to remove unused containers, networks, dangling images and build cache. This applies across Docker projects; volumes are retained by default. |

The named `down` commands intentionally use service-specific stops so they cannot remove the shared database. They preserve the saved collector outbox. Starting that side again resumes its services. `./control down` is the full shutdown command.

The group `prune` commands stop the selected services and remove their containers. They retain PostgreSQL, all persistent data volumes, saved collector results, images and build cache. They do not remove networks or run a global Docker prune. Use `./control up main` or `./control up panel` to rebuild/recreate that side afterward. Extra prune flags are rejected to keep cleanup scoped.

Global Docker pruning is optional disk cleanup, not a startup requirement or restart command. Docker asks for confirmation. It can make the next build slower because it removes cache. The command above does not request volume deletion; retain the PostgreSQL and social outbox volumes. No prune runs automatically.

### Panel and database only

```sh
./control up -d --build \
  postgres social-admin social-proxy
```

Open **https://localhost:8443** on this Mac and sign in with your staff passkey. This starts the panel UI, its HTTPS proxy and PostgreSQL. It allows publisher management and review of stored candidates; it does not start social acquisition.

### Panel plus social collection and cleanup

```sh
./control up -d --build \
  postgres social-admin social-proxy \
  social-gateway social-collector social-egress social-retention
```

This adds the staging gateway, isolated collector, restricted provider egress and retention worker. It does **not** start the regular app API, website crawler or normal app maintenance service.

For actual Apify acquisition, the private `social.env` must contain:

```dotenv
SOCIAL_L4_ENABLED=true
SOCIAL_L4_COLLECTION_ENABLED=true
APIFY_ENABLED=true
SCRAPINGANT_ENABLED=false
SOCIAL_L4_PUBLICATION_ENABLED=false
```

A valid token and a publisher confirmed through **Approve & start daily checks** are also required. The configured preferred provider is selected automatically; the system does not call both providers for the same check. Do not enable every setting merely because it is currently false.

### Entire configured backend, including the panel

```sh
./control up -d --build
```

This starts the regular app backend/website crawler and the social stack, including hourly retention. It does not enable acquisition flags, select publishers, start the mobile development server or select the separate publication profile.

Standard Docker commands remain available. From `BACity-`, `docker compose up --build` starts the main app backend with its normal foreground build output and logs. It does not start the panel. `docker compose down` retains its normal behavior, including stopping the shared PostgreSQL service. `./control` is optional convenience for the named groups and private panel configuration.

The base manifest and panel overlay share the same PostgreSQL network definition, so switching launchers does not change the database's network attachments. Unlike the named `./control` starts, a foreground `docker compose up --build` stops its selected services on Ctrl+C. Use `./control config --quiet` or `docker compose config --quiet` to validate either configuration.

### App API and panel together, without starting collection

```sh
./control up -d --build postgres redis api social-admin social-proxy
```

Starting the panel first and adding `api` later uses the same PostgreSQL configuration and container.

### Stop everything

```sh
./control down
```

This stops the app and panel, including their shared PostgreSQL database. To stop just one side, use the service-specific `stop` commands below. Retain the database and outbox volumes.

### Stable local panel network

`social-ingress` now uses subnet `172.30.41.0/28` and gateway `172.30.41.1`. The Mac's private `SOCIAL_ADMIN_NETWORKS` includes exactly `172.30.41.1/32`, plus loopback addresses. Docker recreating this bridge no longer changes the source address accepted by the panel. `SOCIAL_TRUSTED_PROXY_IP` stays `172.30.40.2`; it identifies the proxy on the separate internal network.

Other hosts can override `SOCIAL_INGRESS_SUBNET` and `SOCIAL_INGRESS_GATEWAY` if those ranges conflict, and must align their own source-IP allowlist. The proxy port remains bound to loopback on this Mac.

### Owner migrations and repairs

```sh
./control owner-run alembic upgrade head
./control owner-run python -m app.social.reconcile_candidates
```

`owner-run` uses the main app environment in a one-off owner container with `--no-deps`. It does not start/reconfigure PostgreSQL or change the regular API's restricted runtime identity. The reconciliation command remains a dry run unless `--apply` is supplied.

## Starting selected services does not stop other services

The commands above start/recreate only the selected services and applicable dependencies. If the app API was already running, starting “panel only” does not shut it down.

To stop the regular app API, website crawler and normal app maintenance while keeping PostgreSQL and the social stack running:

```sh
./control stop api worker maintenance
```

To stop social collection without stopping the panel or database, disable acquisition in `social.env` and apply it as described below. Keep the collector/token available until any existing remote runs finish or are aborted and reconciled. This allows cleanup rather than abandoning a billable run.

## If the app API is down

| State | Result |
|---|---|
| App API stopped; PostgreSQL and social services running | Panel and social acquisition can continue independently. |
| New social items collected | Observations and event candidates are stored in private database tables for review. They are not yet app-visible events. |
| Publication relay running, publication enabled, candidate approved and queued | Relay can write through the shared canonical ingestion code to regular event tables without the public API process running. |
| App API stopped | The app cannot fetch those events until its API returns. Stored candidates/events are retained subject to their normal retention rules. |
| PostgreSQL stopped | Panel/database operations pause. Already-authorized collection results are saved to the independent collector outbox and retried when PostgreSQL returns; new paid work waits for database authorization. |

The regular website crawler uses the public API for ingestion; unlike the social pipeline's separate gateway, it depends on the app API being available.

## Publication is a separate step

The pipeline is:

**Instagram → private observations → extracted event candidates → review/approval → publication relay → regular BACity events → app API → mobile app.**

Collection alone does not publish. Enabling publication alone does not approve or publish every candidate. The existing independent review, quality and queued-publication checks still apply.

After deliberately authorizing publication, set `SOCIAL_L4_PUBLICATION_ENABLED=true` in the private social file and start the separate relay, updating the panel's environment too:

```sh
./control --profile social-publication \
  up -d --build social-admin social-publication
```

Do not start this profile merely to collect posts or inspect candidates. Leave publication disabled for initial collection review.

## Edit settings and apply them

Open the private configuration in VS Code:

```sh
code /Users/s3eed/.config/bacity/social.env
```

If `code` is unavailable:

```sh
open -a "Visual Studio Code" /Users/s3eed/.config/bacity/social.env
```

Save, then apply provider/collection changes:

```sh
./control up -d \
  social-admin social-gateway social-collector
```

A plain container restart does not reload changed environment values; `up -d` recreates containers when their configuration changes. If changing database-role credentials, update/recreate each affected service too, including retention or publication where applicable. The generic `SOCIAL_DATABASE_URL` and `SOCIAL_TRUSTED_PROXY_IP` can be blank in the private file because Compose supplies the per-service connection and trusted proxy address directly.

## Status and logs

```sh
./control ps
./control logs --tail 50 \
  social-admin social-gateway social-collector social-proxy
```

The panel's Instagram collection screen shows provider configuration, active profiles, collection results and budget status. A running collector container does not itself mean acquisition is enabled or that any post was found.

## Mobile development server

Docker startup does not start Expo/Metro or launch a simulator. If Metro is not already running:

```sh
cd /Users/s3eed/Documents/GitHub/BACity/BACity-/apps/mobile
npx expo start --dev-client --localhost --port 8081
```

The mobile app still needs the regular app API to load events.

## On another machine or deployment server

Do not copy the Mac-specific command paths. From the application directory, use the portable repository entry point with that host's files:

```sh
export BACITY_SOCIAL_ENV_FILE=/etc/bacity/social.env
export BACITY_RUNTIME_OVERRIDE_FILE=/etc/bacity/runtime.override.yml

# Panel and database only:
sh infrastructure/social/control.sh up -d --build \
  postgres social-admin social-proxy

# Panel, collection infrastructure and cleanup:
sh infrastructure/social/control.sh up -d --build \
  postgres social-admin social-proxy \
  social-gateway social-collector social-egress social-retention

# Entire configured backend:
sh infrastructure/social/control.sh up -d --build
```

The `/etc/bacity` paths are examples of files you must provision on that host, not files transferred automatically with Git. The portable wrapper defaults the main app environment to the checkout's `.env`; use `BACITY_APP_ENV_FILE` if stored elsewhere. Its wrapper selects social and retention profiles, not publication.

Use the server's final trusted **private** panel hostname instead of localhost. Database provisioning, private networking, TLS trust, passkey enrollment on that hostname and public API HTTPS configuration must already be complete; see [deployment.md](deployment.md). These startup instructions do not turn the development Compose stack into a complete Internet deployment.
