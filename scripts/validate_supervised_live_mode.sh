#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "[cutover] Supervised-live mode validation"

python3 -B - <<'PY'
from app.core.runtime_config import get_runtime_config
from app.deployment.deployment_profiles import get_deployment_profile
from app.startup.startup_health_report import build_startup_health_report

runtime = get_runtime_config()
profile = get_deployment_profile()
startup = build_startup_health_report()

summary = {
    "runtime_mode": runtime.mode.value,
    "deployment_profile": profile.name,
    "strict_production_startup": runtime.strict_production_startup,
    "auth_required": profile.auth_required,
    "demo_users_enabled": profile.demo_users_enabled,
    "telemetry_fallback_enabled": profile.telemetry_fallback_enabled,
    "startup_status": startup.get("status", "unknown"),
    "blocker_count": len(startup.get("blockers", [])),
}

for key, value in summary.items():
    print(f"{key}: {value}")

healthy = (
    runtime.mode.value in {"manual_production", "supervised_live", "production"}
    and profile.auth_required
    and not profile.demo_users_enabled
    and startup.get("status") in {"healthy", "degraded"}
)
raise SystemExit(0 if healthy else 1)
PY
