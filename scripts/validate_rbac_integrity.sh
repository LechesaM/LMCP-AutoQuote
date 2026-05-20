#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "[cutover] RBAC integrity validation"

python3 -B - <<'PY'
from app.auth.rbac import ROLE_PERMISSIONS

prohibited = {
    "autonomous_submit",
    "auto_approve",
    "bypass_review_ready",
    "bypass_proof_capture",
}

violations = []
for role, permissions in ROLE_PERMISSIONS.items():
    overlap = prohibited.intersection(permissions)
    if overlap:
        violations.append((role, sorted(overlap)))

print(f"status: {'healthy' if not violations else 'failing'}")
print(f"role_count: {len(ROLE_PERMISSIONS)}")
print(f"violation_count: {len(violations)}")
for role, permissions in violations:
    print(f"violation: role={role} permissions={','.join(permissions)}")

raise SystemExit(0 if not violations else 1)
PY
