#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

RUNTIME_DIR="${LMCP_RUNTIME_DIR:-/private/tmp/lmcp_runtime}"
HOST="${LMCP_PROOF_HOST:-127.0.0.1}"
PORT="${LMCP_PROOF_PORT:-8011}"
DATABASE_PATH="${LMCP_DATABASE_PATH:-/private/tmp/lmcp_autoquote.db}"
SERVER_LOG="${RUNTIME_DIR}/logs/controlled_runtime_uvicorn.log"
SEED_LOG="${RUNTIME_DIR}/logs/controlled_runtime_seed.json"
PROOF_LOG="${RUNTIME_DIR}/logs/controlled_runtime_proof.json"
ENDPOINT_LOG="${RUNTIME_DIR}/logs/controlled_runtime_endpoints.json"
REPORT_LOG="${RUNTIME_DIR}/logs/controlled_runtime_report.json"
HEALTH_URL="http://${HOST}:${PORT}/health"
EFFECTIVE_STATUS_URL="http://${HOST}:${PORT}/system/control/effective-status"
WORKFLOW_URL="http://${HOST}:${PORT}/health/workflows"

mkdir -p "${RUNTIME_DIR}/logs"

export LMCP_RUNTIME_DIR="$RUNTIME_DIR"
export LMCP_LOG_DIR="${RUNTIME_DIR}/logs"
export LMCP_HANDWRITING_RUNTIME_DIR="${RUNTIME_DIR}/handwriting_simulation"
export LMCP_TENDER_FORM_RUNTIME_DIR="${RUNTIME_DIR}/tender_form_intelligence"
export LMCP_CLICKABLE_NAVIGATION_RUNTIME_DIR="${RUNTIME_DIR}/clickable_navigation_v40"
export LMCP_SUBMISSION_PROOFS_DIR="${RUNTIME_DIR}/submission_proofs"
export LMCP_PORTAL_SUBMISSION_DIR="${RUNTIME_DIR}/portal_submission"
export LMCP_FINAL_SUBMISSION_DIR="${RUNTIME_DIR}/final_submission_v47_5"
export LMCP_PROOF_CENTER_DIR="${RUNTIME_DIR}/proof_center"
export LMCP_OPERATOR_AUTH_DB_PATH="${RUNTIME_DIR}/operator_auth/operator_auth.sqlite3"
export HEALTH_URL
export EFFECTIVE_STATUS_URL
export WORKFLOW_URL
export ENDPOINT_LOG
export REPORT_LOG
if [[ -z "${DATABASE_URL:-}" ]]; then
  export DATABASE_URL="sqlite:////${DATABASE_PATH#/}"
fi
export POSTGRES_USER="${POSTGRES_USER:-}"
export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-}"
export POSTGRES_DB="${POSTGRES_DB:-}"

server_pid=""

cleanup() {
  if [[ -n "${server_pid}" ]] && kill -0 "${server_pid}" 2>/dev/null; then
    kill "${server_pid}" 2>/dev/null || true
    wait "${server_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

echo "[1/4] Seeding controlled runtime state"
python3 app/scripts/run_controlled_runtime_proof.py --runtime-dir "${RUNTIME_DIR}" --seed-only | tee "${SEED_LOG}"

echo "[2/4] Starting backend"
nohup python3 -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" >"${SERVER_LOG}" 2>&1 &
server_pid=$!

wait_for_health() {
  local attempts=60
  local delay=1
  local attempt=1
  while [[ "${attempt}" -le "${attempts}" ]]; do
    if curl -fsS --max-time 5 "${HEALTH_URL}" >/dev/null 2>&1; then
      return 0
    fi
    sleep "${delay}"
    attempt=$((attempt + 1))
  done
  return 1
}

if ! wait_for_health; then
  echo "Backend did not become healthy."
  tail -n 200 "${SERVER_LOG}" >&2 || true
  exit 1
fi

python3 - <<'PY'
import json
import os
import sys
from urllib.request import urlopen

health_url = os.environ["HEALTH_URL"]
effective_url = os.environ["EFFECTIVE_STATUS_URL"]
workflow_url = os.environ["WORKFLOW_URL"]
runtime_dir = os.environ["LMCP_RUNTIME_DIR"]

def fetch(url: str):
    with urlopen(url, timeout=10) as response:
        return json.load(response)

health = fetch(health_url)
effective = fetch(effective_url)
workflow = fetch(workflow_url)

errors = []
if health.get("runtime_dir") != runtime_dir:
    errors.append(f"health.runtime_dir={health.get('runtime_dir')!r}")
if effective.get("effective_system_status") != "controlled":
    errors.append(f"effective_system_status={effective.get('effective_system_status')!r}")
if workflow.get("controlled_status") != "controlled":
    errors.append(f"workflow.controlled_status={workflow.get('controlled_status')!r}")

checks = workflow.get("workflow_checks")
if isinstance(checks, dict) and checks:
    failing = [name for name, passed in checks.items() if not bool(passed)]
    if failing:
        errors.append(f"workflow failing checks: {failing!r}")
else:
    errors.append("workflow.workflow_checks missing or empty")

print(json.dumps({
    "health": health,
    "effective_status": effective,
    "workflow_health": workflow,
}, indent=2))

if errors:
    raise SystemExit("Endpoint verification failed: " + "; ".join(errors))

with open(os.environ["ENDPOINT_LOG"], "w", encoding="utf-8") as handle:
    json.dump(
        {
            "health": health,
            "effective_status": effective,
            "workflow_health": workflow,
        },
        handle,
        indent=2,
        ensure_ascii=False,
        default=str,
    )
PY

echo "[3/4] Probing endpoints"
for url in "${HEALTH_URL}" "${EFFECTIVE_STATUS_URL}" "${WORKFLOW_URL}"; do
  echo "--- ${url}"
  curl -fsS --max-time 10 "${url}" | python3 -m json.tool
done

echo "[4/4] Running controlled RFQ proof"
python3 app/scripts/run_controlled_runtime_proof.py --runtime-dir "${RUNTIME_DIR}" --skip-seed | tee "${PROOF_LOG}"

echo "[5/5] Writing controlled proof report"
python3 scripts/show_controlled_proof_report.py --json | tee "${REPORT_LOG}"

echo "Controlled shared-runtime proof complete"
echo "Seed log: ${SEED_LOG}"
echo "Backend log: ${SERVER_LOG}"
echo "Proof log: ${PROOF_LOG}"
echo "Endpoint log: ${ENDPOINT_LOG}"
echo "Report log: ${REPORT_LOG}"
