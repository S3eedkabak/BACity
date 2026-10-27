# Starting the BACity control panel

Use this guide for everyday startup after the database, credentials, HTTPS and first owner have been configured. For a new server or first installation, follow [deployment.md](deployment.md).

For durable buffering and recovery during database/worker outages, see [social_outage_recovery.md](social_outage_recovery.md).

The **private control panel** and **regular app API** are separate services sharing the same PostgreSQL database. The mobile app/development server is separate again. Starting the panel does not require starting the app API.

## Configuration files

| File | Purpose |
|---|---|
| Application root `.env` | Regular API/backend, normal app authentication, website crawler Levels 1–3, and migration configuration. |
| Private `social.env` | Panel service connections and worker secret, Apify/ScrapingAnt credentials, social acquisition settings, budgets and flags. |
| Private `runtime.override.yml` | Deployment-specific runtime settings; the configured local file runs social retention hourly. |
| `apps/mobile/.env` | Client settings such as the API address; never backend/provider secrets. |

On the current Mac, the private files are in `/Users/s3eed/.config/bacity/`. Only the social collector receives the provider token values; the panel receives configuration-presence hints.

## Current Mac: choose what to start

The configured `/Users/s3eed/.config/bacity/control` wrapper loads both backend environment files and the required Compose overlays. Commands below can be run from any directory. `-d` keeps services running in the background; `--build` builds their current images before starting them.

### Panel and database only

```sh
/Users/s3eed/.config/bacity/control up -d --build \
  postgres social-admin social-proxy
```

Open **https://localhost:8443** on this Mac and sign in with your staff passkey. This starts the panel UI, its HTTPS proxy and PostgreSQL. It allows publisher management and review of stored candidates; it does not start social acquisition.

### Panel plus social collection and cleanup

```sh
/Users/s3eed/.config/bacity/control up -d --build \
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

A valid token and approved publishers with current collection permission and monitoring enabled are also required. Choose one explicit provider per publisher. Do not enable every setting merely because it is currently false.

### Entire configured backend, including the panel

```sh
/Users/s3eed/.config/bacity/control up -d --build
```

This starts the regular app backend/website crawler and the social stack, including hourly retention. It does not enable acquisition flags, select publishers, start the mobile development server or select the separate publication profile.

**Plain `docker compose up --build` uses the base Compose file.** Without additional files/profiles selected, it starts the normal app stack and does not launch the private panel. For this configured installation, use the wrapper so the private settings and restricted public-runtime database connection are applied.

## Starting selected services does not stop other services

The commands above start/recreate only the selected services and applicable dependencies. If the app API was already running, starting “panel only” does not shut it down.

To stop the regular app API, website crawler and normal app maintenance while keeping PostgreSQL and the social stack running:

```sh
/Users/s3eed/.config/bacity/control stop api worker maintenance
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
/Users/s3eed/.config/bacity/control --profile social-publication \
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
/Users/s3eed/.config/bacity/control up -d \
  social-admin social-gateway social-collector
```

A plain container restart does not reload changed environment values; `up -d` recreates containers when their configuration changes. If changing database-role credentials, update/recreate each affected service too, including retention or publication where applicable. The generic `SOCIAL_DATABASE_URL` and `SOCIAL_TRUSTED_PROXY_IP` can be blank in the private file because Compose supplies the per-service connection and trusted proxy address directly.

## Status and logs

```sh
/Users/s3eed/.config/bacity/control ps
/Users/s3eed/.config/bacity/control logs --tail 50 \
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
