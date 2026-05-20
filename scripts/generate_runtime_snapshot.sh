#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

python3 - <<'PY'
import json
from app.observability.metrics_registry import get_observability_overview

print(json.dumps(get_observability_overview(limit=100), indent=2, default=str))
PY
