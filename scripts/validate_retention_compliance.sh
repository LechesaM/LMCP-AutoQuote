#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 - <<'PY'
import json
from app.governance.retention_enforcement import build_retention_enforcement_report
print(json.dumps(build_retention_enforcement_report(), indent=2, default=str))
PY
