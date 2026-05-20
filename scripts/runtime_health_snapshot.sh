#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT_DIR"

python3 -c 'from app.operations.health_snapshots import capture_health_snapshot; import json; print(json.dumps(capture_health_snapshot(), default=str))'

