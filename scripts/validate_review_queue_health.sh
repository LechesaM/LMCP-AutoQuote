#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from app.productivity.review_queue_optimizer import build_review_queue_optimization_summary
import json
print(json.dumps(build_review_queue_optimization_summary(limit=200), default=str, indent=2))
PY

