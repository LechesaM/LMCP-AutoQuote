#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 -m pytest \
  tests/test_governance_integrity.py \
  tests/test_no_autonomous_execution.py \
  tests/test_production_readiness_validation.py \
  tests/test_deployment_stack.py \
  -q

python3 - <<'PY'
import importlib

modules = [
    "app.main",
    "app.api.router_registry",
    "app.deployment.production_startup",
    "app.auth.auth_service",
]

for module_name in modules:
    importlib.import_module(module_name)
PY

