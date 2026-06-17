from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


BENCHMARK_NAME = "First Externally Verified Submission"

BENCHMARK_CHECKLIST = [
    {
        "key": "approved",
        "label": "Operator approval",
        "required": True,
        "evidence": ["operator identity", "approval timestamp", "rfq id"],
    },
    {
        "key": "submitted",
        "label": "Buyer submission",
        "required": True,
        "evidence": ["buyer channel used", "submission timestamp"],
    },
    {
        "key": "receipt_captured",
        "label": "Buyer receipt captured",
        "required": True,
        "evidence": ["email acknowledgement", "portal confirmation", "upload confirmation"],
    },
    {
        "key": "proof_attached",
        "label": "Proof attached",
        "required": True,
        "evidence": ["receipt linked to lifecycle record"],
    },
    {
        "key": "lifecycle_closed",
        "label": "Lifecycle closure",
        "required": True,
        "evidence": ["status changed to externally_submitted", "actor trace", "timestamps"],
    },
]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_external_submission_benchmark_template(rfq_id: str = "", title: str = "", buyer_name: str = "") -> Dict[str, Any]:
    return {
        "benchmark_name": BENCHMARK_NAME,
        "status": "pending",
        "created_at": _now_iso(),
        "rfq_id": rfq_id,
        "title": title,
        "buyer_name": buyer_name,
        "criteria": {row["key"]: False for row in BENCHMARK_CHECKLIST},
        "required_evidence": {
            row["key"]: list(row["evidence"]) for row in BENCHMARK_CHECKLIST
        },
        "notes": [
            "This template is for the first externally verified submission benchmark.",
            "All five criteria must be true before the benchmark is marked complete.",
        ],
    }


def is_external_submission_benchmark_complete(evidence: Dict[str, Any]) -> bool:
    if not isinstance(evidence, dict):
        return False
    return all(bool(evidence.get(row["key"])) for row in BENCHMARK_CHECKLIST)


def benchmark_required_keys() -> List[str]:
    return [row["key"] for row in BENCHMARK_CHECKLIST]
