#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 - <<'PY'
import json
from app.stabilization.runtime_stability_engine import build_runtime_stability_report

payload = build_runtime_stability_report(limit=50)
print(json.dumps(payload, default=str))
PY
