from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime

STORE = Path(os.getenv("LMCP_RUNTIME_DIR", "/tmp/lmcp_runtime")).expanduser().resolve() / "decision_learning.json"

def log_outcome(rfq, decision, outcome):
    data = []
    if STORE.exists():
        data = json.loads(STORE.read_text())

    data.append({
        "rfq": rfq,
        "decision": decision,
        "outcome": outcome,  # win/loss/no_response
        "timestamp": datetime.utcnow().isoformat()
    })

    STORE.write_text(json.dumps(data, indent=2))
