#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
from app.business_intelligence.executive_dashboard import build_executive_dashboard
from app.business_intelligence.strategic_reporting import build_strategic_report

payload = {
    "executive_dashboard": build_executive_dashboard(limit=25),
    "strategic_report": build_strategic_report(limit=25),
}
print(json.dumps(payload, indent=2, default=str))
PY

