#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
from app.governance.regulatory_export_service import build_regulatory_export_bundle
print(json.dumps(build_regulatory_export_bundle(), indent=2, default=str))
PY

