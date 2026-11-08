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
# Owner-only migrations/repairs are one-off containers. Explicitly selecting
# the base file uses the migration-owner connection without starting
# dependencies or changing the regular API runtime role.
if [ "${1:-}" = owner-run ]; then
  shift
  if [ "$#" -eq 0 ]; then
    printf 'Usage: ./control owner-run COMMAND [ARGUMENTS...]\n' >&2
    exit 1
  fi
  exec docker compose --env-file "$TASK_APP_ENV" \
    -f "$TASK_APP_ROOT/docker-compose.yml" \
    run --rm --no-deps -T api "$@"
fi
task_compose() {
  exec docker compose \
    --env-file "$TASK_APP_ENV" --env-file "$TASK_SOCIAL_ENV" \
    -f "$TASK_APP_ROOT/docker-compose.yml" \
    -f "$TASK_APP_ROOT/compose.social.yml" \
    -f "$TASK_APP_ROOT/infrastructure/social/public-api-runtime.override.yml" \
    -f "$TASK_RUNTIME_OVERRIDE" \
    --profile social --profile social-retention "$@"
}

# Group cleanup removes containers only. The shared database and persistent
# volumes, including buffered social results, are deliberately outside it.
task_prune_group() {
  (task_compose stop "$@")
  task_compose rm -f "$@"
}
if [ "${1:-}" = prune ]; then
  if [ "$#" -ne 2 ]; then
    printf 'Usage: ./control prune main | ./control prune panel\n' >&2
    exit 2
  fi
  case "$2" in
    main) task_prune_group worker maintenance api opensearch redis;;
    panel) task_prune_group social-collector social-gateway social-retention \
      social-admin social-proxy social-egress;;
    *) printf 'Usage: ./control prune main | ./control prune panel\n' >&2; exit 2;;
  esac
fi

# Start detached, then attach only to logs. Ctrl+C closes the log stream,
# rather than stopping a PostgreSQL container shared by both backends.
TASK_STREAM_START_LOGS=true
for TASK_START_OPTION in "$@"; do
  case "$TASK_START_OPTION" in --dry-run|--dry-run=true) TASK_STREAM_START_LOGS=false;; esac
done
case "${1:-}:${2:-}" in
  up:main)
    shift 2
    (task_compose up -d --build "$@" postgres redis opensearch api worker maintenance)
    [ "$TASK_STREAM_START_LOGS" = true ] || exit 0
    task_compose logs --follow --tail 100 postgres redis opensearch api worker maintenance
    ;;
  up:panel)
    shift 2
    (task_compose up -d --build "$@" postgres social-admin social-proxy \
      social-gateway social-collector social-egress social-retention)
    [ "$TASK_STREAM_START_LOGS" = true ] || exit 0
    task_compose logs --follow --tail 100 postgres social-admin social-proxy \
      social-gateway social-collector social-egress social-retention
    ;;
  down:main)
    shift 2
    task_compose stop "$@" worker maintenance api opensearch redis
    ;;
  down:panel)
    shift 2
    task_compose stop "$@" social-collector social-gateway social-retention \
      social-admin social-proxy social-egress
    ;;
esac
# Keep raw Compose commands available for existing scripts and diagnostics.
task_compose "$@"
