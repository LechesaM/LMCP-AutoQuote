#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

if [[ "${LMCP_USE_DOCKER:-0}" == "1" ]]; then
  CERT_DIR="${LMCP_TLS_CERT_DIR:-$ROOT/runtime/certs}"
  if [[ ! -f "$CERT_DIR/lmcp.crt" || ! -f "$CERT_DIR/lmcp.key" ]]; then
    bash "$ROOT/scripts/generate_local_tls_certs.sh" || true
  fi
  exec docker compose --env-file .env.production -f docker-compose.production.yml up -d --build --remove-orphans
fi

export PYTHONPATH="${PYTHONPATH:-$PWD}"
exec python3 -m uvicorn "${LMCP_APP_ENTRYPOINT:-app.main:app}" --host "${LMCP_HOST:-0.0.0.0}" --port "${LMCP_PORT:-8000}" --workers "${LMCP_WORKERS:-1}"
