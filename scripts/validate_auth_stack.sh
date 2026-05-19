#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 -m pytest \
  tests/test_auth_rbac.py \
  tests/test_governance_integrity.py \
  tests/test_no_autonomous_execution.py \
  -q

