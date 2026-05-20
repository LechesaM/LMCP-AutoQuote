#!/bin/sh
set -eu

python3 - <<'PY'
import json
from app.orchestration.queue_recovery_service import detect_queue_recovery_needs

payload = detect_queue_recovery_needs()
print(json.dumps(payload, default=str))
PY
