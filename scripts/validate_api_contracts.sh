#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

echo "[cutover] API contract validation"

python3 -B - <<'PY'
from app.api.router_registry import iter_router_specs

required_modules = {
    "app.api.telemetry_routes",
    "app.api.operator_workflow_routes",
    "app.api.operator_ops_routes",
    "app.api.operations_runtime_routes",
    "app.api.persistence_ops_routes",
    "app.api.observability_routes",
    "app.api.operator_productivity_routes",
    "app.api.business_intelligence_routes",
    "app.api.governance_routes",
    "app.api.stabilization_routes",
    "app.api.auth_routes",
}

router_specs = list(iter_router_specs(include_legacy=False))
loaded_modules = {spec.module_path for spec in router_specs}
missing = sorted(required_modules - loaded_modules)

print(f"status: {'healthy' if not missing else 'failing'}")
print(f"loaded_router_count: {len(router_specs)}")
print(f"required_module_count: {len(required_modules)}")
print(f"missing_module_count: {len(missing)}")
for module in missing:
    print(f"missing_module: {module}")

raise SystemExit(0 if not missing else 1)
PY
