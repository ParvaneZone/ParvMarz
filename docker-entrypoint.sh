#!/bin/sh
set -e
mkdir -p /app/data
if [ "$(id -u)" = "0" ] && [ "${RUN_AS_ROOT:-0}" != "1" ]; then
  # Drop root, but only if every TLS certificate file stays readable by the app user (else keep working as before).
  chown -R app:app /app/data
  ok=1
  for f in $(find /etc/letsencrypt \( -type f -o -type l \) 2>/dev/null); do
    setpriv --reuid=app --regid=app --clear-groups test -r "$f" || ok=0
  done
  if [ "$ok" = "1" ]; then exec setpriv --reuid=app --regid=app --clear-groups "$0" "$@"; fi
  echo "WARNING: certificates in /etc/letsencrypt are not readable by the unprivileged user; staying root (RUN_AS_ROOT=1 hides this)" >&2
fi
if [ "${ENVIRONMENT:-production}" = "production" ]; then
  eval "$(python -m cli.bootstrap)"
  [ -f /app/data/initial-admin.txt ] && echo "Initial admin credentials: docker compose exec subhub cat /app/data/initial-admin.txt"
fi
alembic upgrade head
exec python -m app.serve
