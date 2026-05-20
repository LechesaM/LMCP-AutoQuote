#!/usr/bin/env bash
set -euo pipefail
python3 - <<'PY'
from app.productivity.operator_workload_balancer import build_operator_workload_summary
import json
print(json.dumps(build_operator_workload_summary(limit=200), default=str, indent=2))
PY

