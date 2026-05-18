#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"

check() {
  local path="$1"
  curl -fsS "$BASE_URL$path" >/tmp/lmcp_check.json
  python3 -m json.tool </tmp/lmcp_check.json >/dev/null
  echo "OK $path"
}

check "/health"
check "/opportunities"
check "/rfq-lifecycle/mission-control"
check "/quote-compilation/packs"
check "/proof-center/scan"

python3 - <<'PY'
from app.main import app, health
report = getattr(app.state, "router_report", {})
payload = health()
assert payload.get("status") == "healthy"
assert len(report.get("loaded") or []) == 111, report
assert len(report.get("failures") or []) == 0, report
assert len(report.get("duplicates") or []) == 0, report
print("router integrity ok")
PY
