#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 - <<'PY'
from app.productivity.operator_workload_balancer import build_operator_workload_summary
import json
print(json.dumps(build_operator_workload_summary(limit=200), default=str, indent=2))
PY
