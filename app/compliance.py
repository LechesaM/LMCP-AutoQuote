from __future__ import annotations

from typing import Dict, List


DEFAULT_COMPLIANCE_DOCUMENTS: List[str] = [
    "Cover Page",
    "Quotation",
    "SBD1",
    "SBD4",
    "SBD6.1",
    "SBD9",
    "CIPC",
    "Tax Clearance",
    "CSD Registration Report",
    "B-BBEE",
    "Director IDs",
]


def list_required_documents() -> List[str]:
    return DEFAULT_COMPLIANCE_DOCUMENTS.copy()


def get_compliance_summary() -> Dict[str, object]:
    documents = list_required_documents()
    return {
        "ok": True,
        "count": len(documents),
        "documents": documents,
    }
