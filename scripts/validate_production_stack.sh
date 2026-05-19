#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

for file in \
  .env.example \
  Dockerfile \
  docker-compose.yml \
  frontend/command-centre/Dockerfile \
  nginx/default.conf
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
  LMCP_OPERATOR_SESSION_COOKIE_SECURE
do
  if ! grep -q "$env_name" .env.example; then
    printf '%s\n' "Missing required environment variable in .env.example: $env_name" >&2
    exit 1
  fi
done

python3 -m pytest tests/test_deployment_stack.py -q

