#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 - <<'PY'
import json
from app.stabilization.governance_consistency_validator import build_governance_consistency_report

payload = build_governance_consistency_report(limit=50)
print(json.dumps(payload, default=str))
PY
