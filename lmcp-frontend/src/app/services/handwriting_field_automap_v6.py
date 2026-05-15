from __future__ import annotations

import re
from typing import Any, Dict, Optional


def _norm(value: Any) -> str:
    return " ".join(str(value or "").lower().strip().split())


FIELD_RULES = {
    "name": {
        "line_index": 1,
        "keywords": [
            "name",
            "full name",
            "bidder name",
            "authorised representative",
            "authorized representative",
            "representative name",
            "signatory name",
            "surname and name",
            "lechesa manaba",
        ],
    },
    "designation": {
        "line_index": 2,
        "keywords": [
            "designation",
            "capacity",
            "position",
            "title",
            "director",
            "capacity of signatory",
            "capacity under which signing",
        ],
    },
    "company": {
        "line_index": 3,
        "keywords": [
            "company",
            "company name",
            "name of bidder",
            "bidder",
            "enterprise",
            "supplier",
            "tenderer",
            "lechesa manaba consulting",
            "lechesa manaba consulting and projects",
        ],
    },
}


VALUE_HINTS = {
    "name": ["lechesa manaba"],
    "designation": ["director"],
    "company": [
        "lechesa manaba consulting",
        "lechesa manaba consulting and projects",
        "pty",
        "ltd",
    ],
}


def infer_handwriting_field_type(field: Dict[str, Any]) -> str:
    """
    Infers which handwriting line should be used based on field metadata/text.

    Supported returned values:
        name
        designation
        company
        unknown
    """
    candidates = [
        field.get("field_type"),
        field.get("field_name"),
        field.get("name"),
        field.get("label"),
        field.get("anchor"),
        field.get("placeholder"),
        field.get("text"),
        field.get("value"),
    ]

    haystack = _norm(" ".join(str(v or "") for v in candidates))

    if not haystack:
        return "unknown"

    # Strong value hints first
    for field_type, hints in VALUE_HINTS.items():
        for hint in hints:
            if hint in haystack:
                return field_type

    # Label/anchor rules
    for field_type, rule in FIELD_RULES.items():
        for kw in rule["keywords"]:
            if _norm(kw) in haystack:
                return field_type

    return "unknown"


def apply_auto_line_mapping(field: Dict[str, Any]) -> Dict[str, Any]:
    """
    Returns a copied field with mode/line_index filled automatically where possible.
    Manual line_index is respected.
    """
    updated = dict(field)

    if updated.get("line_index"):
        updated.setdefault("mode", "line_ink")
        updated.setdefault("auto_mapped", False)
        return updated

    field_type = infer_handwriting_field_type(updated)
    updated["auto_detected_field_type"] = field_type

    if field_type in FIELD_RULES:
        updated["line_index"] = FIELD_RULES[field_type]["line_index"]
        updated["mode"] = "line_ink"
        updated["auto_mapped"] = True
        return updated

    updated.setdefault("auto_mapped", False)
    return updated


def automap_payload_fields(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies handwriting auto-mapping to every field in a payload.

    Usage:
        payload = automap_payload_fields(payload)
    """
    copied = dict(payload)
    fields = copied.get("fields") or []

    copied["fields"] = [
        apply_auto_line_mapping(f) if isinstance(f, dict) else f
        for f in fields
    ]

    copied.setdefault("style", {})
    if isinstance(copied["style"], dict):
        copied["style"].setdefault("use_line_ink", True)
        copied["style"].setdefault("line_ink_job_id", "REAL-HANDWRITING")

    copied["auto_mapping"] = {
        "status": "applied",
        "engine": "handwriting_field_automap_v6",
    }

    return copied
