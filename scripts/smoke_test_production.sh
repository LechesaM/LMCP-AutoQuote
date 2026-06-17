#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8011}"
RFQ_ID="${RFQ_ID:-REAL-PILOT-001}"

login_json="$(mktemp)"
trap 'rm -f "$login_json"' EXIT

curl -sS --max-time 10 -X POST "$API_BASE/operator-auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"operator_id":"operator@lmcp.local","password":"operator"}' \
  -o "$login_json"

token="$(python3 - <<'PY' "$login_json"
import json, sys
print(json.load(open(sys.argv[1]))["access_token"])
PY
)"

check() {
  local path="$1"
  local expected="$2"
  local body
  body="$(curl -sS --max-time 10 -H "Authorization: Bearer $token" "$API_BASE$path")"
  python3 - <<'PY_INNER' "$body" "$expected" "$path"
import json, sys
payload = json.loads(sys.argv[1])
expected = sys.argv[2]
path = sys.argv[3]

status = str(payload.get("status") or payload.get("verification", {}).get("status") or "").lower()
execution_status = str(payload.get("execution_status") or payload.get("executionStatus") or "").lower()
submission_status = str(payload.get("submission_status") or payload.get("submissionStatus") or "").lower()
receipt_signature_status = str(payload.get("receipt_signature", {}).get("status") or payload.get("receiptSignature", {}).get("status") or "").lower()
blockers = payload.get("blockers") or []

if expected == "ok" and status not in {"ok", "ready", "queued"}:
    raise SystemExit(f"{path}: unexpected status {status}")

if expected == "verified":
    if status != "ok" or execution_status != "executed" or submission_status != "submitted":
        raise SystemExit(f"{path}: verification failed")
    if receipt_signature_status != "ok":
        raise SystemExit(f"{path}: receipt signature not ok")
    if blockers:
        raise SystemExit(f"{path}: blockers present: {blockers}")

if expected == "ready":
    execution_ready = bool(
        payload.get("ready")
        or payload.get("execution_ready")
        or payload.get("executionReady")
    )
    status_ok = str(payload.get("status", "")).lower() == "ok"
    no_blockers = not (payload.get("blockers") or [])

    if not ((execution_ready or status_ok) and no_blockers):
        raise SystemExit(f"{path}: not ready")

print(f"{path}: {status}")
PY_INNER
}

check "/operations/rfqs/$RFQ_ID/submission-execution" "ok"
check "/operations/rfqs/$RFQ_ID/submission-execution/receipt-verification" "verified"
check "/operations/rfqs/$RFQ_ID/submission-execution/external-audit-export" "ready"

echo "smoke test passed"
