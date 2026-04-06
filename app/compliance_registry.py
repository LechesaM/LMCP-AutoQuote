from __future__ import annotations

COMPLIANCE_REGISTRY = {
    "CIPC_REGISTRATION": {
        "document_name": "CIPC Registration Documents",
        "required_by_default": True,
    },
    "TAX_COMPLIANCE": {
        "document_name": "Tax Compliance Proof / TCS PIN Letter",
        "required_by_default": True,
    },
    "CSD_REPORT": {
        "document_name": "CSD Report",
        "required_by_default": True,
    },
    "BBEEE_CERTIFICATE": {
        "document_name": "B-BBEE Certificate",
        "required_by_default": True,
    },
    "DIRECTOR_IDS": {
        "document_name": "Director ID Copies",
        "required_by_default": True,
    },
}


def get_all_compliance_codes() -> list[str]:
    return list(COMPLIANCE_REGISTRY.keys())
