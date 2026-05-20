#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "[cutover] Runtime dependency validation"

python3 -B - <<'PY'
from app.startup.dependency_validator import validate_dependencies

report = validate_dependencies()
checks = report.get("checks", [])
blockers = report.get("blockers", [])

print(f"status: {report.get('status', 'unknown')}")
print(f"check_count: {len(checks)}")
print(f"blocker_count: {len(blockers)}")
for item in checks[:10]:
    print(f"module: {item.get('module', '')} status={item.get('status', '')}")

raise SystemExit(0 if report.get("status") == "healthy" else 1)
PY
