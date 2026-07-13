#!/bin/sh
set -eu

if [ ! -f /data/.env ]; then
  cp /app/.env /data/.env
  chmod 600 /data/.env
fi

exec "$@"
