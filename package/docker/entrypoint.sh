#!/bin/sh
set -eu

runtime_env=/data/.env
bootstrap_env=/app/bootstrap.env

umask 077

if [ ! -s "$runtime_env" ]; then
  if [ ! -s "$bootstrap_env" ]; then
    echo "Missing runtime configuration: $runtime_env" >&2
    exit 1
  fi
  cp "$bootstrap_env" "$runtime_env"
fi

chmod 600 "$runtime_env" 2>/dev/null || true

exec "$@"
