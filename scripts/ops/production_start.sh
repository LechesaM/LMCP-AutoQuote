#!/usr/bin/env bash
set -euo pipefail

cd /Users/Shared/LMCP-AutoQuote-Server

if [[ "${LMCP_USE_DOCKER:-0}" == "1" ]]; then
  exec docker compose up -d --build
fi

export PYTHONPATH="${PYTHONPATH:-$PWD}"
exec python3 -m uvicorn "${LMCP_APP_ENTRYPOINT:-app.main:app}" --host "${LMCP_HOST:-0.0.0.0}" --port "${LMCP_PORT:-8000}" --workers "${LMCP_WORKERS:-1}"
