#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from app.productivity.review_efficiency_analytics import build_review_efficiency_analytics
import json
print(json.dumps(build_review_efficiency_analytics(limit=200), default=str, indent=2))
PY

