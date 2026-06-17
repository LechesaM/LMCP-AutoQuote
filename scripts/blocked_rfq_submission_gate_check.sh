#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8011}"
RFQ_ID="${RFQ_ID:-T-OPS-1}"
CURL_MAX_TIME="${LMCP_SMOKE_MAX_TIME:-180}"

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

response_file="$tmp_dir/blocked.json"
http_code="$(
  curl --retry 3 --retry-all-errors --retry-delay 1 --max-time "$CURL_MAX_TIME" -sS -o "$response_file" -w '%{http_code}' \
    -X POST "$API_BASE/operations/rfqs/$RFQ_ID/submission-package/generate" \
    -H 'Content-Type: application/json' \
    -H "Authorization: Bearer $token" \
    -d '{"note":"verify gate blocks not-ready RFQ"}'
)"

if [[ "$http_code" != "409" ]]; then
  echo "expected 409 from blocked RFQ package generation, got $http_code" >&2
  cat "$response_file" >&2
  exit 1
fi

python3 - <<'PY' "$response_file"
import json, sys

payload = json.load(open(sys.argv[1]))
detail = payload.get("detail") or {}
blocking_issues = detail.get("blocking_issues") or []

if detail.get("status") != "blocked":
    raise SystemExit("blocked RFQ response missing blocked status")
if detail.get("approval_ready") is not False:
    raise SystemExit("blocked RFQ response must report approval_ready false")
if detail.get("submission_ready") is not False:
    raise SystemExit("blocked RFQ response must report submission_ready false")
if not blocking_issues:
    raise SystemExit("blocked RFQ response missing blocking issues")
if "readiness gate" not in str(detail.get("message", "")).lower():
    raise SystemExit("blocked RFQ response missing readiness gate message")

print(json.dumps({
    "stage": "blocked_rfq_submission_gate_check",
    "rfq_id": detail.get("tender_id"),
    "blocking_issue_count": len(blocking_issues),
    "status": "blocked",
}, indent=2))
PY

echo "blocked rfq submission gate check passed"
