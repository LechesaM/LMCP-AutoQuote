#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
export LMCP_PROJECT_ROOT="${LMCP_PROJECT_ROOT:-$PROJECT_ROOT}"
export LMCP_RUNTIME_DIR="${LMCP_RUNTIME_DIR:-$PROJECT_ROOT/runtime}"
export LMCP_MANUAL_PRODUCTION_DIR="${LMCP_MANUAL_PRODUCTION_DIR:-$PROJECT_ROOT/runtime/manual_production}"
export LMCP_MANUAL_PRODUCTION_DB_PATH="${LMCP_MANUAL_PRODUCTION_DB_PATH:-$PROJECT_ROOT/runtime/manual_production/lmcp_operations.db}"
export CELERY_BROKER_URL="${CELERY_BROKER_URL:-${REDIS_URL:-redis://127.0.0.1:6379/0}}"
export CELERY_RESULT_BACKEND="${CELERY_RESULT_BACKEND:-$CELERY_BROKER_URL}"

GENERAL_CONCURRENCY="${GENERAL_CONCURRENCY:-2}"
EXECUTION_CONCURRENCY="${EXECUTION_CONCURRENCY:-2}"
OPERATIONS_CONCURRENCY="${OPERATIONS_CONCURRENCY:-1}"
BEAT_ENABLED="${BEAT_ENABLED:-1}"
OPERATIONS_WORKER_READY_TIMEOUT_SECONDS="${OPERATIONS_WORKER_READY_TIMEOUT_SECONDS:-45}"
OPERATIONS_WORKER_READY_POLL_INTERVAL_SECONDS="${OPERATIONS_WORKER_READY_POLL_INTERVAL_SECONDS:-1}"
REQUIRE_OPERATIONS_WORKER_READY="${REQUIRE_OPERATIONS_WORKER_READY:-1}"

echo "Starting LMCP production workers"
echo "Broker: ${CELERY_BROKER_URL}"
echo "General concurrency: ${GENERAL_CONCURRENCY}"
echo "Execution concurrency: ${EXECUTION_CONCURRENCY}"
echo "Operations concurrency: ${OPERATIONS_CONCURRENCY}"

python3 -m celery -A app.celery_app.celery_app worker \
  --loglevel="${CELERY_LOGLEVEL:-INFO}" \
  --concurrency="${GENERAL_CONCURRENCY}" \
  --queues=default,acquisition_queue,parsing_queue,pricing_queue,proof_queue,retry_queue \
  --hostname="lmcp-general@%h" &

GENERAL_PID=$!

python3 -m celery -A app.celery_app.celery_app worker \
  --loglevel="${CELERY_LOGLEVEL:-INFO}" \
  --concurrency="${EXECUTION_CONCURRENCY}" \
  --queues=execution_queue \
  --hostname="lmcp-execution@%h" &

EXECUTION_PID=$!

python3 -m celery -A app.celery_app.celery_app worker \
  --loglevel="${CELERY_LOGLEVEL:-INFO}" \
  --concurrency="${OPERATIONS_CONCURRENCY}" \
  --queues=operations_queue \
  --hostname="lmcp-operations@%h" &

OPERATIONS_PID=$!

if [[ "${BEAT_ENABLED}" == "1" ]]; then
  echo "Waiting for operations queue worker readiness"
  if ! python3 scripts/check_operations_worker_ready.py \
    --queue operations_queue \
    --timeout-seconds "${OPERATIONS_WORKER_READY_TIMEOUT_SECONDS}" \
    --poll-interval-seconds "${OPERATIONS_WORKER_READY_POLL_INTERVAL_SECONDS}"; then
    if [[ "${REQUIRE_OPERATIONS_WORKER_READY}" == "1" ]]; then
      echo "Operations worker did not become ready; refusing to start beat." >&2
      kill "${GENERAL_PID}" "${EXECUTION_PID}" "${OPERATIONS_PID}" 2>/dev/null || true
      exit 1
    fi
    echo "Operations worker not ready yet; starting beat anyway because REQUIRE_OPERATIONS_WORKER_READY=0"
  fi
  python3 -m celery -A app.celery_app.celery_app beat \
    --loglevel="${CELERY_LOGLEVEL:-INFO}" \
    --pidfile="" &
  BEAT_PID=$!
else
  BEAT_PID=""
fi

trap 'kill "${GENERAL_PID}" "${EXECUTION_PID}" "${OPERATIONS_PID}" ${BEAT_PID:+"$BEAT_PID"} 2>/dev/null || true' INT TERM EXIT

wait
