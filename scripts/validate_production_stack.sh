#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

for file in \
  .env.example \
  .env.production.example \
  Dockerfile \
  docker-compose.yml \
  docker-compose.production.yml \
  frontend/command-centre/Dockerfile \
  nginx/default.conf \
  nginx/production.conf \
  scripts/generate_local_tls_certs.sh \
  deploy/systemd/lmcp-autoquote.service
do
  if [ ! -f "$file" ]; then
    printf '%s\n' "Missing required production artifact: $file" >&2
    exit 1
  fi
done

for env_name in \
  LMCP_DEPLOYMENT_PROFILE \
  LMCP_AUTH_REQUIRED \
  LMCP_ENABLE_LEGACY_ROUTERS \
  LMCP_OPERATOR_SESSION_COOKIE_SECURE \
  LMCP_DB_BACKEND \
  LMCP_QUEUE_BACKEND \
  LMCP_SECRET_KEY
do
  if ! grep -q "$env_name" .env.example; then
    printf '%s\n' "Missing required environment variable in .env.example: $env_name" >&2
    exit 1
  fi
done

for env_name in \
  LMCP_ENV \
  LMCP_PRODUCTION_MODE \
  STRICT_PRODUCTION_STARTUP \
  LMCP_DATABASE_URL \
  REDIS_URL \
  CELERY_BROKER_URL \
  CELERY_RESULT_BACKEND
do
  if ! grep -q "$env_name" .env.production.example; then
    printf '%s\n' "Missing required environment variable in .env.production.example: $env_name" >&2
    exit 1
  fi
done

STRICT_PRODUCTION_STARTUP=0 python3 -m pytest tests/test_deployment_stack.py -q
