from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict


def load_fixture(path: str | Path) -> Dict[str, Any]:
    source_path = Path(path)
    payload = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"items": payload if isinstance(payload, list) else []}
    if "real_pilot_rfqs" in source_path.as_posix():
        return {
            "tender_id": payload.get("tender_id"),
            "rfq_record": payload,
            "qualification_summary": {
                "expected_exclusion_status": payload.get("expected_exclusion_status"),
                "expected_minimum_profit_result": payload.get("expected_minimum_profit_result"),
                "expected_submission_ready": payload.get("expected_submission_ready"),
            },
        }
    return payload
