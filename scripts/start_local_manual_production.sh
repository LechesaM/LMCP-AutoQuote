#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

export LMCP_ALLOW_DEGRADED_STARTUP=true

mkdir -p runtime/logs

BACKEND_PORT="$(python3 scripts/check_local_system.py --select-backend-port)"
if [[ -z "${BACKEND_PORT}" ]]; then
  echo "No available backend port found in 8000/8001/8002." >&2
  exit 1
fi

BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
FRONTEND_PORT="${LMCP_LOCAL_FRONTEND_PORT:-5173}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"

BACKEND_LOG="runtime/logs/local_manual_production_backend.log"
FRONTEND_LOG="runtime/logs/local_manual_production_frontend.log"

echo "Starting backend at ${BACKEND_URL}"
nohup python3 -m uvicorn "${LMCP_APP_ENTRYPOINT:-app.main:app}" --host 127.0.0.1 --port "${BACKEND_PORT}" >"${BACKEND_LOG}" 2>&1 &
BACKEND_PID=$!

echo "Starting frontend at ${FRONTEND_URL}"
nohup bash -lc "cd frontend && npm run dev -- --host 127.0.0.1 --port '${FRONTEND_PORT}' --strictPort" >"${FRONTEND_LOG}" 2>&1 &
FRONTEND_PID=$!

STATUS_FILE="runtime/local_system_status.json"

python3 scripts/check_local_system.py \
  --backend-url "${BACKEND_URL}" \
  --frontend-url "${FRONTEND_URL}" \
  --status-path "${STATUS_FILE}" \
  --wait-seconds "${LMCP_LOCAL_STARTUP_WAIT_SECONDS:-30}" >/dev/null

echo "Backend URL: ${BACKEND_URL}"
echo "Frontend URL: ${FRONTEND_URL}"
echo "Status file: ${STATUS_FILE}"
echo "Backend PID: ${BACKEND_PID}"
echo "Frontend PID: ${FRONTEND_PID}"
