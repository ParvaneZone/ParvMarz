#!/bin/sh
set -e
mkdir -p /app/data
if [ "${ENVIRONMENT:-production}" = "production" ]; then
  eval "$(python -m cli.bootstrap)"
  [ -f /app/data/initial-admin.txt ] && echo "Initial admin credentials: docker compose exec subhub cat /app/data/initial-admin.txt"
fi
alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers
