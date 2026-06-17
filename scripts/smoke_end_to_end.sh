#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8011}"
RFQ_ID="${RFQ_ID:-REAL-PILOT-001}"
CURL_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-60}"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

login_json="$tmp_dir/login.json"
curl --retry 3 --retry-all-errors --retry-delay 1 --max-time "$CURL_MAX_TIME" -sS -X POST "$API_BASE/auth/login" \
  -H 'Content-Type: application/json' \
  -d '{"email":"supervisor@lmcp.local","password":"supervisor"}' \
  -o "$login_json"

token="$(python3 - <<'PY' "$login_json"
import json, sys
print(json.load(open(sys.argv[1]))["access_token"])
PY
)"

request_json() {
  local path="$1"
  local output="$2"
  curl --retry 3 --retry-all-errors --retry-delay 1 --max-time "$CURL_MAX_TIME" -sS \
    -H "Authorization: Bearer $token" \
    "$API_BASE$path" \
    -o "$output"
}

check_json_status() {
  local file="$1"
  local expr="$2"
  python3 - <<'PY' "$file" "$expr"
import json, sys
payload = json.load(open(sys.argv[1]))
expr = sys.argv[2]
ns = {"payload": payload}
result = eval(expr, {"__builtins__": {}}, ns)
if not result:
    raise SystemExit(f"check failed: {expr}")
PY
}

request_json "/observability/uptime" "$tmp_dir/uptime.json"
check_json_status "$tmp_dir/uptime.json" "payload.get('status') == 'ok'"

request_json "/operations/rfqs" "$tmp_dir/rfqs.json"
check_json_status "$tmp_dir/rfqs.json" "payload.get('status') in {'ok', 'degraded'}"

request_json "/operations/rfqs/$RFQ_ID" "$tmp_dir/detail.json"
check_json_status "$tmp_dir/detail.json" "payload.get('tender_id') == '$RFQ_ID'"
check_json_status "$tmp_dir/detail.json" "payload.get('data_source') == 'runtime' and payload.get('summary', {}).get('title') and payload.get('harvest_enrichment', {}).get('matched') is True"

request_json "/supplier-quotes/intelligence/status" "$tmp_dir/intelligence_status.json"
check_json_status "$tmp_dir/intelligence_status.json" "payload.get('status') in {'ok', 'degraded', 'empty'}"

request_json "/operations/rfqs/$RFQ_ID/submission-package" "$tmp_dir/package.json"
check_json_status "$tmp_dir/package.json" "payload.get('zip_path') and payload.get('quote_pack_pdf_path') and payload.get('buyer_pricing_schedule_path')"

request_json "/operations/rfqs/$RFQ_ID/submission-execution" "$tmp_dir/execution.json"
check_json_status "$tmp_dir/execution.json" "payload.get('status') in {'ok', 'degraded'}"

approved="$(python3 - <<'PY' "$tmp_dir/detail.json"
import json, sys
payload = json.load(open(sys.argv[1]))
gov = payload.get("governed_submission") or {}
decision = (gov.get("governanceDecision") or {}).get("decision", "")
locked = bool(gov.get("submissionLocked"))
print("1" if decision == "approved" and locked else "0")
PY
)"

if [[ "$approved" != "1" ]]; then
  curl --retry 3 --retry-all-errors --retry-delay 1 --max-time "$CURL_MAX_TIME" -sS -X POST "$API_BASE/operations/rfqs/$RFQ_ID/governance-decision" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $token" \
    -d '{"decision":"approved","note":"Smoke test approval"}' \
    -o "$tmp_dir/governance.json"
fi

idempotency_key="smoke-${RFQ_ID}-$(date +%s)"
curl --retry 3 --retry-all-errors --retry-delay 1 --max-time "$CURL_MAX_TIME" -sS -X POST "$API_BASE/operations/rfqs/$RFQ_ID/submission-execution" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $token" \
  -H "Idempotency-Key: $idempotency_key" \
  -d '{"note":"Smoke test execution","idempotencyKey":"'"$idempotency_key"'"}' \
  -o "$tmp_dir/submit.json"

check_json_status "$tmp_dir/submit.json" "payload.get('status') in {'ok', 'blocked'}"

request_json "/operations/rfqs/$RFQ_ID/submission-execution/receipt-verification" "$tmp_dir/receipt.json"
check_json_status "$tmp_dir/receipt.json" "payload['verification']['status'] in {'ok', 'failed'}"

request_json "/operations/rfqs/$RFQ_ID/submission-execution/external-audit-export" "$tmp_dir/export.json"
check_json_status "$tmp_dir/export.json" "payload['export']['status'] == 'ok'"

echo "end-to-end smoke test passed"
