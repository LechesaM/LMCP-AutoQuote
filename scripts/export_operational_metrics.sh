#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
from app.business_intelligence.report_exporter import build_report_export_bundle

print(json.dumps(build_report_export_bundle(limit=25), indent=2, default=str))
PY

