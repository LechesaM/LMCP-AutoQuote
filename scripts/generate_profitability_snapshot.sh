#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
from app.business_intelligence.profitability_analytics import build_profitability_analytics

print(json.dumps(build_profitability_analytics(limit=25), indent=2, default=str))
PY

