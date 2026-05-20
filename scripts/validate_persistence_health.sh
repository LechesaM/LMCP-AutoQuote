#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 - <<'PY'
import json
from app.persistence.persistence_health import validate_persistence_health

payload = validate_persistence_health()
print(json.dumps(payload, default=str))
PY
