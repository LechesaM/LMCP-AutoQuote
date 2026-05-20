#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

python3 - <<'PY'
import json
from app.observability.sla_monitor import build_sla_monitoring_report

print(json.dumps(build_sla_monitoring_report(limit=100), indent=2, default=str))
PY
