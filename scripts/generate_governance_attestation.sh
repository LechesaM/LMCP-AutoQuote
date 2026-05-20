#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
python3 - <<'PY'
import json
from app.governance.governance_attestations import build_governance_attestation
print(json.dumps(build_governance_attestation(), indent=2, default=str))
PY

