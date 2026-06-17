#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8011}"
RFQ_ID="${RFQ_ID:-REAL-PILOT-001}"

login_json="$(mktemp)"
trap 'rm -f "$login_json"' EXIT

curl -sS --max-time 10 -X POST "$API_BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"supervisor@lmcp.local","password":"supervisor"}' \
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
  python3 - <<'PY' "$body" "$expected" "$path"
import json, sys
payload = json.loads(sys.argv[1])
expected = sys.argv[2]
path = sys.argv[3]
status = str(payload.get("status") or payload.get("verification", {}).get("status") or "").lower()
if expected == "ok" and status not in {"ok", "ready", "queued"}:
    raise SystemExit(f"{path}: unexpected status {status}")
if expected == "verified" and not payload.get("verification", {}).get("verified"):
    raise SystemExit(f"{path}: verification failed")
if expected == "ready" and not payload.get("ready"):
    raise SystemExit(f"{path}: not ready")
print(f"{path}: {status}")
PY
}

check "/operations/rfqs/$RFQ_ID/submission-execution" "ok"
check "/operations/rfqs/$RFQ_ID/submission-execution/receipt-verification" "verified"
check "/operations/rfqs/$RFQ_ID/submission-execution/external-audit-export" "ready"

echo "smoke test passed"
