#!/bin/sh
set -eu

python3 - <<'PY'
import json
from app.persistence.backup_scheduler import get_backup_status
from app.persistence.restore_validator import validate_restore_readiness

backup = get_backup_status()
payload = validate_restore_readiness(backup.get("latest_backup_dir", ""))
print(json.dumps(payload, default=str))
PY
