#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "[cutover] Production cutover validation"

python3 -B - <<'PY'
from app.startup.startup_health_report import build_startup_health_report

report = build_startup_health_report()
status = report.get("status", "unknown")
blockers = report.get("blockers", [])
warnings = report.get("warnings", [])

print(f"status: {status}")
print(f"strict_production_startup: {report.get('strict_production_startup', False)}")
print(f"blocker_count: {len(blockers)}")
print(f"warning_count: {len(warnings)}")
for item in blockers[:5]:
    print(f"blocker: {item}")
for item in warnings[:5]:
    print(f"warning: {item}")

raise SystemExit(0 if status == "healthy" else 1)
PY
