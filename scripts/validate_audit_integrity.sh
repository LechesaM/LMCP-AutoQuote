#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 - <<'PY'
import json
from app.governance.audit_integrity_monitor import build_audit_integrity_monitor
print(json.dumps(build_audit_integrity_monitor(), indent=2, default=str))
PY
