# Deploying BACity and the private social panel

For everyday panel-only, collection and full-stack startup after provisioning, see [control_panel_start.md](control_panel_start.md).

This is the deployment entry point. The current running installation is **local to the owner's Mac**, not an Internet deployment. The application is a Docker backend plus a React Native mobile app and a private staff website; the social panel is not a static site that can be deployed by uploading HTML.

The Level 4 implementation and deployment files are currently uncommitted. A server cloning the existing remote branch will not receive uncommitted/untracked work. Review and explicitly authorize publishing the code before deploying from Git. No commit, push or remote deployment is implied by this guide.

## Where the secrets go

Secrets belong to each deployment, outside Git. They are supplied when the containers start. They are not hardcoded and do not travel with a Git clone.

| Purpose | Current Mac | Example server |
|---|---|---|
| Main app/migration environment | `BACity-/.env` | `/opt/bacity/BACity-/.env` |
| Panel/provider environment | `/Users/s3eed/.config/bacity/social.env` | `/etc/bacity/social.env` |
| Local runtime/retention override | `/Users/s3eed/.config/bacity/runtime.override.yml` | `/etc/bacity/runtime.override.yml` |
| Startup entry point | Mac-specific `/Users/s3eed/.config/bacity/control` | Repository `infrastructure/social/control.sh` |

The server paths above are examples, not directories already provisioned. The main `.env` contains the normal application configuration and migration connection. Put **all `APIFY_*`, `SCRAPINGANT_*`, `SOCIAL_*` and `INSTAGRAM_ACQUISITION_PROVIDER` settings in the separate social file**, not the main `.env`: the base API/crawler services receive the main file. The social Compose overlay maps only the actual collector's provider credentials into its environment; the staff/gateway receive configuration-presence hints.

Create the server social file from `infrastructure/social/environment.example`, then populate its real values. The example contains no working credentials. You can securely transfer the existing private file when deliberately moving an existing database installation, but do not blindly reuse its Mac-only addresses or database logins against a new database. Protect environment files/backups with mode 0600 and their parent secret directory with mode 0700. Never put them in Git, a frontend environment, a Docker image, or the report.

## Decide the deployment addresses first

There are separate destinations:

- **Public API:** the HTTPS backend address used by the mobile app/public clients.
- **Private staff panel:** a stable private hostname reachable over the administrative VPN/private network. The existing panel proxy uses HTTPS on port 8443 and a private CA.

The Mac's `https://localhost:8443` is not a remote-server address. On another device, localhost means that device. On a server, set `SOCIAL_ADMIN_HOST` to its final private DNS hostname, `SOCIAL_BIND_ADDRESS` to the private VPN interface address (or retain loopback for host-local access), and `SOCIAL_ADMIN_NETWORKS` to the actual allowed private source addresses. Do not copy the Mac's observed Docker forwarding address onto a different host. The exact source must be verified there. The overlay derives `SOCIAL_ADMIN_ORIGIN` from the hostname for the running staff container.

Trust the **server's own** Caddy CA on authorized staff devices through the private administrative connection. Do not bypass certificate verification. The CA trusted for the Mac installation is not automatically the server's CA.

## Prepare the host and configuration

Use a host capable of running the existing Docker/Compose services with persistent storage. A static-site-only host cannot run this stack. The selected host, public domain, private network and public HTTPS ingress have not been chosen or configured by this work.

For an example checkout at `/opt/bacity/BACity-`, create:

1. The normal app `.env`, populated from the normal template and configured for that deployment.
2. `/etc/bacity/social.env`, populated from `infrastructure/social/environment.example`.
3. `/etc/bacity/runtime.override.yml`, copied from `infrastructure/social/runtime.override.example.yml`.

Keep initial flags:

```dotenv
SOCIAL_L4_ENABLED=false
SOCIAL_L4_COLLECTION_ENABLED=false
SOCIAL_L4_PUBLICATION_ENABLED=false
APIFY_ENABLED=false
SCRAPINGANT_ENABLED=false
```

The social environment needs five real database URLs: staff, gateway, publication relay, retention and public runtime. Their LOGIN roles must exist in the same BACity database and inherit only their corresponding groups from `infrastructure/social/roles.sql`. Configure `SOCIAL_CONSUMER_DB_ROLE` to the actual public-runtime login. Use independent strong passwords and a distinct random `SOCIAL_WORKER_KEY`. These are different credentials from the Apify token and from the owner's passkey.

For a fresh database, provision fresh service logins. For a restored database, ensure its restored roles/passwords match the environment or deliberately provision new logins. A regular `pg_dump` of a database does not itself provision the server's global LOGIN roles. The detailed role mapping and private-network requirements are in [social-control-operations.md](social-control-operations.md).

## Database initialization or transfer

From the application directory, with the main `.env` pointing at that host's intended migration-owner connection:

```sh
docker compose up -d postgres redis opensearch
docker compose build api
```

If moving existing data, transfer and restore a protected database backup into the intended target database before enabling app writers. Back up the target before any upgrade. Do not replace a live target database without a separately reviewed migration plan. Keep all database, crawler-state and `social-outbox` volumes persistent. Back up the social outbox independently; see [social_outage_recovery.md](social_outage_recovery.md).

Run migrations separately from the public API, then install the group grants:

```sh
docker compose run --rm --no-deps api alembic upgrade head

docker compose exec -T postgres sh -c \
  'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < infrastructure/social/roles.sql
```

The current migration head is **0028**. Create the five non-owner LOGIN roles and assign the groups as described above; fill their connection URLs in the server social file. Verify all actual service identities and public-runtime denial of private `l4_` tables before enabling the panel. Do not run the public API as the migration owner.

## Start the configured stack

The repository wrapper is portable; it does not contain `/Users/s3eed` paths. Select the server's files explicitly:

```sh
cd /opt/bacity/BACity-
export BACITY_SOCIAL_ENV_FILE=/etc/bacity/social.env
export BACITY_RUNTIME_OVERRIDE_FILE=/etc/bacity/runtime.override.yml
# Optional when the main app file is somewhere else:
# export BACITY_APP_ENV_FILE=/path/to/app.env
```

After database roles and the private network/HTTPS origin are ready, set `SOCIAL_L4_ENABLED=true` in the social file, retaining acquisition/publication false. Then:

```sh
sh infrastructure/social/control.sh build
sh infrastructure/social/control.sh up -d
sh infrastructure/social/control.sh ps
```

The wrapper combines the base stack, social overlay, restricted-public-runtime overlay and hourly retention override. It does not select the publication profile. The public API runs without performing owner migrations at startup. The collector receives provider tokens; the panel receives no provider token values.

**Internet deployment still needs host-specific work:** the base Compose file is a development baseline, including API port 8000 and default development configuration. Set the real production app configuration, strong secrets/encryption settings, public HTTPS ingress/domain, correct frontend/mobile API URL, CORS and applicable OAuth callback URLs. Restrict database/Redis/search and administrative ports appropriately. Do not treat the startup command as proof of a production-ready deployment or expose the staff panel publicly to avoid setting up its private access.

## Enroll the owner on the final hostname

Passkeys are bound to their relying-party hostname. The current localhost passkey is **not portable to a different panel hostname**.

Replace the example identity with the intended owner. For a restored database, use its existing owner email. For a fresh staff database:

```sh
sh infrastructure/social/control.sh exec social-admin \
  python -m app.social.operator bootstrap-owner \
  --email 'you@example.com' --name 'Your name'
```

For a restored staff database containing the owner, do not bootstrap a duplicate. After confirming the target and final hostname, use the existing host-only recovery command:

```sh
sh infrastructure/social/control.sh exec social-admin \
  python -m app.social.operator recover-owner \
  --email 'you@example.com'
```

**Recovery revokes that owner's existing passkeys and sessions** and creates a new one-use 15-minute invitation. Run it only when deliberately re-enrolling on the new hostname, after backing up and verifying the deployment. Keep the invitation private. The owner completes registration with their device/security key on the trusted final private URL. Register a backup authenticator too.

## Activate acquisition after validation

Verify normal API/crawler health, actual database identities, private-panel access, trusted TLS, authentication, secret placement and backups on the target host. Choose the intended public Instagram profiles, review their details and confirm Approve & start daily checks in the panel.

Then explicitly enable Apify in the **server's** social file:

```dotenv
APIFY_ENABLED=true
SOCIAL_L4_COLLECTION_ENABLED=true
SOCIAL_L4_PUBLICATION_ENABLED=false
SCRAPINGANT_ENABLED=false
```

Apply environment changes:

```sh
sh infrastructure/social/control.sh up -d social-admin social-gateway social-collector
```

Validate one approved profile before adding more. Collection does not enable publication. Read [apify-instagram.md](apify-instagram.md) for budget behavior, Actor limitations and the optional explicit live probe. Do not operate the old Mac collector and a restored copy of its scheduler/database independently against the same account/targets during cutover: stop the old acquisition deployment and retain pending-run accounting before enabling the new one.

## What has and has not been done

The Mac installation is running, its token was checked through read-only account metadata, and LEAD enrolled a real passkey. The local report is in the chat's `outputs/panel-setup/setup-report.md`. No Instagram Actor acquisition or remote deployment was performed. No server has been provisioned, no public domain selected, and no final production ingress/VPN deployment has been validated. Those steps require the actual target configuration; they are not solved by copying a Mac filesystem path.

## Simplified publisher approval upgrade (0028)

Back up PostgreSQL, let existing collector work drain, apply migration 0028 as the owner, then rebuild/recreate social-admin, social-gateway, social-collector and social-retention together. The migration adds the reviewed collection approval marker and caps existing per-profile limits at two. It does not enable any publisher or change acquisition/publication flags or credentials. Reapply the normal role grants if provisioning a new installation. Existing publisher and staff data, passkeys, receipts and the independent outbox are retained. Keep the same outbox volume. See [control_panel_start.md](control_panel_start.md#everyday-publisher-workflow) for the new workflow and session behavior.
