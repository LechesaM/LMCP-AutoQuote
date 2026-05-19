from __future__ import annotations

import re
from typing import Any, Dict, List

from app.qualification.rfq_language_intelligence import analyze_rfq_language


COMPLIANCE_ITEMS = [
    ("SBD4", True, [r"\bsbd\s*4\b", r"declaration of interest"]),
    ("SBD8", True, [r"\bsbd\s*8\b", r"supplier code of conduct"]),
    ("SBD6.1", True, [r"\bsbd\s*6\.1\b", r"preference points claim"]),
    ("SBD9", True, [r"\bsbd\s*9\b", r"certificate of independent bid determination"]),
    ("BBBEE", True, [r"\bbee\b", r"\bbbbee\b", r"b-bbee"]),
    ("CSD", True, [r"central supplier database", r"\bcsd\b"]),
    ("Tax PIN", True, [r"tax pin", r"sars pin", r"tax reference number"]),
    ("Director IDs", True, [r"director id", r"director ids", r"id copies", r"copy of id"]),
    ("Bank confirmation", True, [r"bank confirmation", r"bank letter", r"bank account confirmation"]),
    ("CIDB", False, [r"\bcidb\b", r"cidb registration"]),
    ("Local content", False, [r"local content", r"designated sector", r"local production"]),
    ("Supplier code of conduct", True, [r"supplier code of conduct", r"code of conduct"]),
    ("Company registration/CIPC", True, [r"\bcipc\b", r"company registration", r"certificate of incorporation"]),
    ("SARS tax clearance", True, [r"tax clearance", r"sars clearance", r"tax compliance status"]),
    ("Pricing schedule", True, [r"pricing schedule", r"price schedule", r"schedule of rates"]),
    ("Quotation on company letterhead", True, [r"company letterhead", r"letterhead quotation", r"quotation on company letterhead"]),
]


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _collect_text(payload: Dict[str, Any]) -> str:
    parts = [
        payload.get("title"),
        payload.get("description"),
        payload.get("submission_instructions"),
        payload.get("extracted_text"),
        payload.get("source_text"),
        payload.get("notes"),
    ]
    for document in payload.get("documents") or []:
        if isinstance(document, dict):
            parts.append(document.get("name"))
            parts.append(document.get("document_type"))
            parts.append(document.get("extracted_text"))
    return _normalize(" ".join(str(part or "") for part in parts))


def _find_source_phrase(text: str, patterns: List[str]) -> str:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return ""


def build_compliance_matrix(rfq_record_or_dict: Dict[str, Any], *, language_intelligence: Dict[str, Any] | None = None) -> Dict[str, Any]:
    payload = dict(rfq_record_or_dict or {})
    language_intelligence = language_intelligence or analyze_rfq_language(payload)
    text = _collect_text(payload)
    category = _normalize(payload.get("category"))
    rows: List[Dict[str, Any]] = []
    blockers: List[str] = []
    missing_required = 0

    for item_name, required, patterns in COMPLIANCE_ITEMS:
        source_phrase = _find_source_phrase(text, patterns)
        if not source_phrase:
            for detected_pattern in language_intelligence.get("detected_patterns", []):
                if detected_pattern.get("name") and item_name.replace("/", "_").replace(" ", "_").lower() in detected_pattern.get("name", "").lower():
                    source_phrase = ", ".join(detected_pattern.get("evidence_phrases", [])[:1])
                    break
        detected = bool(source_phrase)
        status = "required" if required else ("mentioned" if detected else "optional")
        blocker = bool(required and not detected)
        if blocker:
            blockers.append(f"{item_name} missing")
            missing_required += 1
        rows.append(
            {
                "item": item_name,
                "status": status,
                "detected": detected,
                "confidence": 0.95 if detected else (0.25 if required else 0.15),
                "source_phrase": source_phrase,
                "blocker": blocker,
            }
        )

    if category in {"building_materials", "technical_fabrication", "construction_execution"}:
        for row in rows:
            if row["item"] == "CIDB" and not row["detected"]:
                row["status"] = "required"
                row["blocker"] = True
                if "CIDB missing" not in blockers:
                    blockers.append("CIDB missing")
                missing_required += 1

    return {
        "items": rows,
        "blockers": blockers,
        "missing_required_count": missing_required,
        "compliance_complexity_score": min(100, missing_required * 12 + sum(1 for row in rows if row["detected"]) * 2),
        "status": "degraded" if blockers else "healthy",
        "language_confidence": float(language_intelligence.get("confidence", 0.0)),
    }
