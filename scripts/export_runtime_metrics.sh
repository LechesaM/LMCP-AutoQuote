#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

python3 - <<'PY'
from app.api.observability_contracts import build_observability_prometheus_response

payload = build_observability_prometheus_response(limit=100)
print(payload["text"], end="")
PY
