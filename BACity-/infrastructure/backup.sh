#!/bin/sh
set -eu
umask 077
while true; do
  target="/backups/bacity-$(date -u +%Y%m%dT%H%M%SZ).dump"
  pg_dump --format=custom --file="$target.partial"
  pg_restore --list "$target.partial" >/dev/null
  mv "$target.partial" "$target"
  media_target="/backups/bacity-media-$(date -u +%Y%m%dT%H%M%SZ).tar.gz"
  tar -czf "$media_target.partial" -C /media .
  tar -tzf "$media_target.partial" >/dev/null
  mv "$media_target.partial" "$media_target"
  find /backups -name 'bacity-*.dump' -mtime +14 -delete
  find /backups -name 'bacity-media-*.tar.gz' -mtime +14 -delete
  echo '{"service":"backup","status":"completed"}'
  sleep 86400
done
