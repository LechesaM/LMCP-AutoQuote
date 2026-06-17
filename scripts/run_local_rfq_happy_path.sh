#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

FRONTEND_DIR="$(cd "$SCRIPT_DIR/../frontend/command-centre" && pwd)"
API_BASE="${API_BASE:-http://127.0.0.1:8011}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8011}"
API_HEALTH_URL="${API_BASE%/}/health"
API_LOG="${API_LOG:-$SCRIPT_DIR/../runtime/logs/run_local_rfq_happy_path_api.log}"
API_BOOTSTRAP="${LMCP_API_BOOTSTRAP:-1}"
STARTED_API=0
API_PID=""

ensure_api_running() {
  if curl --max-time 3 -fsS "$API_HEALTH_URL" >/dev/null 2>&1; then
    return 0
  fi

  if [ "$API_BOOTSTRAP" != "1" ]; then
    echo "API at $API_HEALTH_URL is unhealthy and LMCP_API_BOOTSTRAP=0 prevents startup." >&2
    exit 1
  fi

  mkdir -p "$SCRIPT_DIR/../runtime/logs"
  nohup python3 -m uvicorn app.main:app --host "$API_HOST" --port "$API_PORT" >"$API_LOG" 2>&1 &
  API_PID=$!
  STARTED_API=1

  attempts=0
  while [ "$attempts" -lt 60 ]; do
    if curl --max-time 3 -fsS "$API_HEALTH_URL" >/dev/null 2>&1; then
      return 0
    fi
    attempts=$((attempts + 1))
    sleep 1
  done

  echo "API failed to become healthy at $API_HEALTH_URL" >&2
  echo "API log: $API_LOG" >&2
  if [ -f "$API_LOG" ]; then
    tail -n 100 "$API_LOG" >&2 || true
  fi
  exit 1
}

cleanup() {
  if [ "$STARTED_API" -eq 1 ] && [ -n "$API_PID" ]; then
    kill "$API_PID" >/dev/null 2>&1 || true
  fi
}

trap cleanup EXIT INT TERM

ensure_api_running

python3 "$SCRIPT_DIR/seed_demo_live_rfq_bundle.py"

LMCP_SMOKE_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-180}" bash "$SCRIPT_DIR/smoke_end_to_end.sh"

if (cd "$FRONTEND_DIR" && node -e "import('playwright').then(() => process.exit(0)).catch(() => process.exit(1))") >/dev/null 2>&1; then
  (
    cd "$FRONTEND_DIR"
    LMCP_FRONTEND_URL="${LMCP_FRONTEND_URL:-http://127.0.0.1:5173}" \
    LMCP_BACKEND_URL="${LMCP_BACKEND_URL:-http://127.0.0.1:8011}" \
    node "$SCRIPT_DIR/operator_workflow_browser_check.mjs"
  )
  browser_status=$?
  LMCP_SMOKE_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-180}" bash "$SCRIPT_DIR/rfq_quote_package_happy_path.sh"
  LMCP_SMOKE_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-180}" bash "$SCRIPT_DIR/blocked_rfq_submission_gate_check.sh"
  LMCP_SMOKE_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-180}" bash "$SCRIPT_DIR/fresh_rfq_import_discovery_happy_path.sh"
  python3 "$SCRIPT_DIR/supplier_quote_live_imap_happy_path.py"
  exit $browser_status
fi

LMCP_SMOKE_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-180}" bash "$SCRIPT_DIR/rfq_quote_package_happy_path.sh"
LMCP_SMOKE_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-180}" bash "$SCRIPT_DIR/blocked_rfq_submission_gate_check.sh"
LMCP_SMOKE_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-180}" bash "$SCRIPT_DIR/fresh_rfq_import_discovery_happy_path.sh"
python3 "$SCRIPT_DIR/supplier_quote_live_imap_happy_path.py"

printf '%s\n' '{"status":"playwright_missing","message":"Browser workflow check skipped because Playwright is not installed.","smoke":"passed"}'
