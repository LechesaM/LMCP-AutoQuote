#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 -m pytest tests/test_supervised_live_operations.py -q
python3 -m pytest tests/test_runtime_observability.py -q
python3 -m pytest tests/test_backup_validation.py -q
python3 -m pytest tests/test_auth_rbac.py -q
python3 -m pytest tests/test_live_operator_operations.py -q

