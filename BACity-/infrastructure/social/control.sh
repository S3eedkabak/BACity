#!/bin/sh
# Portable entry point for a provisioned BACity host. Does not provision a server.
set -eu
TASK_APP_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
TASK_APP_ENV=${BACITY_APP_ENV_FILE:-$TASK_APP_ROOT/.env}
TASK_SOCIAL_ENV=${BACITY_SOCIAL_ENV_FILE:-${HOME}/.config/bacity/social.env}
TASK_RUNTIME_OVERRIDE=${BACITY_RUNTIME_OVERRIDE_FILE:-$(dirname -- "$TASK_SOCIAL_ENV")/runtime.override.yml}
for TASK_REQUIRED_FILE in "$TASK_APP_ENV" "$TASK_SOCIAL_ENV" "$TASK_RUNTIME_OVERRIDE"; do
  if [ ! -f "$TASK_REQUIRED_FILE" ]; then
    printf 'Required configuration missing: %s\nSee docs/deployment.md.\n' "$TASK_REQUIRED_FILE" >&2
    exit 1
  fi
done
cd "$TASK_APP_ROOT"
exec docker compose \
  --env-file "$TASK_APP_ENV" --env-file "$TASK_SOCIAL_ENV" \
  -f "$TASK_APP_ROOT/docker-compose.yml" \
  -f "$TASK_APP_ROOT/compose.social.yml" \
  -f "$TASK_APP_ROOT/infrastructure/social/public-api-runtime.override.yml" \
  -f "$TASK_RUNTIME_OVERRIDE" \
  --profile social --profile social-retention "$@"
