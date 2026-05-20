#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"

python3 -m pytest tests/test_observability_monitoring.py tests/test_runtime_sla_monitoring.py tests/test_runtime_anomaly_detection.py -q
