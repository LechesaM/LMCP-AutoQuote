#!/bin/sh
set -eu

python3 - <<'PY'
import json
from app.persistence.backup_scheduler import create_runtime_backup

payload = create_runtime_backup(prefix="manual")
print(json.dumps(payload, default=str))
PY
