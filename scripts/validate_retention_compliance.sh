#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
from app.governance.retention_enforcement import build_retention_enforcement_report
print(json.dumps(build_retention_enforcement_report(), indent=2, default=str))
PY

