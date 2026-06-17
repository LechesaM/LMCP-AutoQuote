#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8011}"
RFQ_ID="${RFQ_ID:-REAL-PILOT-001}"
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
result = eval(expr, {"__builtins__": {"len": len}}, ns)
if not result:
    raise SystemExit(f"check failed: {expr}")
PY
}

request_json "/operations/rfqs/$RFQ_ID" "$tmp_dir/detail.json"
check_json_status "$tmp_dir/detail.json" "payload.get('tender_id') == '$RFQ_ID'"
check_json_status "$tmp_dir/detail.json" "payload.get('data_source') == 'runtime' and payload.get('summary', {}).get('title')"
check_json_status "$tmp_dir/detail.json" "payload.get('harvest_enrichment', {}).get('matched') is True"
check_json_status "$tmp_dir/detail.json" "len(payload.get('harvest_enrichment', {}).get('supplier_quote_comparison', {}).get('supplier_quotes') or []) >= 2"
check_json_status "$tmp_dir/detail.json" "payload.get('harvest_enrichment', {}).get('supplier_quote_comparison', {}).get('comparison_status') == 'ready'"

curl --retry 3 --retry-all-errors --retry-delay 1 --max-time "$CURL_MAX_TIME" -sS -X POST "$API_BASE/operations/rfqs/$RFQ_ID/submission-package/generate" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $token" \
  -d '{"note":"Generate the buyer pricing schedule and final quote package for the demo RFQ"}' \
  -o "$tmp_dir/generated.json"
check_json_status "$tmp_dir/generated.json" "payload.get('status') == 'ok'"
check_json_status "$tmp_dir/generated.json" "payload.get('approval_ready') is True and payload.get('submission_ready') is True"

request_json "/operations/rfqs/$RFQ_ID/submission-package" "$tmp_dir/package.json"
check_json_status "$tmp_dir/package.json" "payload.get('status') == 'ok'"
check_json_status "$tmp_dir/package.json" "payload.get('approval_ready') is True and payload.get('submission_ready') is True"
check_json_status "$tmp_dir/package.json" "payload.get('package_status') == 'ready'"
check_json_status "$tmp_dir/package.json" "payload.get('quote_pack_pdf_path') and payload.get('buyer_pricing_schedule_path') and payload.get('zip_path')"

curl --retry 3 --retry-all-errors --retry-delay 1 --max-time "$CURL_MAX_TIME" -sS -L \
  -H "Authorization: Bearer $token" \
  "$API_BASE/operations/rfqs/$RFQ_ID/submission-package/download" \
  -o "$tmp_dir/submission_package.zip"

python3 - <<'PY' "$tmp_dir/submission_package.zip" "$RFQ_ID"
import csv
import io
import json
import sys
import zipfile

zip_path = sys.argv[1]
rfq_id = sys.argv[2]
required = {
    f"{rfq_id}__quote_pack.pdf",
    f"{rfq_id}__buyer_pricing_schedule.csv",
    f"{rfq_id}__submission_package_manifest.json",
}

with zipfile.ZipFile(zip_path) as archive:
    names = set(archive.namelist())
    missing = sorted(required - names)
    if missing:
        raise SystemExit(f"missing expected package files: {missing}")

    with archive.open(f"{rfq_id}__buyer_pricing_schedule.csv") as handle:
        rows = list(csv.DictReader(io.TextIOWrapper(handle, encoding="utf-8")))
    if not rows:
        raise SystemExit("buyer pricing schedule csv is empty")
    if not any(str(row.get("recommended", "")).strip().lower() in {"1", "true", "yes"} for row in rows):
        raise SystemExit("buyer pricing schedule csv has no recommended row")

    with archive.open(f"{rfq_id}__submission_package_manifest.json") as handle:
        manifest = json.load(handle)
    if manifest.get("package_status") != "ready" or manifest.get("approval_ready") is not True:
        raise SystemExit("submission package manifest is not marked ready")

print(
    json.dumps(
        {
            "stage": "rfq_quote_package_happy_path",
            "rfq_id": rfq_id,
            "zip_entries": len(names),
            "pricing_rows": len(rows),
            "submission_ready": True,
            "approval_ready": True,
        },
        indent=2,
    )
)
PY

echo "rfq quote package happy path passed"
