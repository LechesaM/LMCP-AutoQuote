#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 -m pytest tests/test_supervised_live_stabilization.py tests/test_runtime_reliability.py tests/test_governance_consistency.py -q
