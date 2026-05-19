from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from app.domain.quote import QuotePack, QuotePackArtifact

CHECKLIST = (
    ("company_details_present", "company details present"),
    ("buyer_details_present", "buyer details present"),
    ("tender_reference_present", "tender reference present"),
    ("pricing_schedule_present", "pricing schedule present"),
    ("vat_treatment_shown", "VAT treatment shown"),
    ("validity_period_present", "validity period present"),
    ("delivery_terms_present", "delivery terms present"),
    ("signature_placeholder_present", "signature/approval placeholder present"),
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_artifact_name(path: str) -> str:
    name = Path(path).name.lower()
    if "pricing_schedule" in name or "pricing schedule" in name:
        return "pricing_schedule"
    if "quote_pack" in name and name.endswith(".pdf"):
        return "quote_pack_pdf"
    if "quote_pack" in name and name.endswith(".json"):
        return "quote_pack_json"
    return name


def _artifacts(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = payload.get("artifacts") or []
    return [item for item in items if isinstance(item, dict)]


def _quote_pack_schema_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    base = payload.get("quote_pack") if isinstance(payload.get("quote_pack"), dict) else payload
    base = base if isinstance(base, dict) else payload
    return {
        "tender_id": _text(base.get("tender_id")),
        "generated_pdf_path": _text(base.get("generated_pdf_path")),
        "generated_json_path": _text(base.get("generated_json_path")),
        "completed_buyer_schedule_path": _text(base.get("completed_buyer_schedule_path")),
        "quote_pack_ready": bool(base.get("quote_pack_ready", False)),
        "missing_artifacts": base.get("missing_artifacts") if isinstance(base.get("missing_artifacts"), list) else [],
        "artifacts": base.get("artifacts") if isinstance(base.get("artifacts"), list) else [],
        "quality_score": float(base.get("quality_score") or 0.0),
        "quality_notes": base.get("quality_notes") if isinstance(base.get("quality_notes"), list) else [],
    }


def assess_quote_pack_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = _artifacts(payload)
    checklist_results: List[Dict[str, Any]] = []
    satisfied = 0
    missing_artifacts: List[str] = []
    quality_notes: List[str] = []
    for field_name, label in CHECKLIST:
        present = bool(payload.get(field_name))
        checklist_results.append({"field": field_name, "label": label, "present": present})
        if present:
            satisfied += 1
        else:
            quality_notes.append(f"missing {label}")
    for artifact in artifacts:
        if not artifact.get("present", False):
            missing_artifacts.append(_normalize_artifact_name(_text(artifact.get("path"))))
    if not payload.get("generated_pdf_path"):
        missing_artifacts.append("quote_pack_pdf")
    if not payload.get("generated_json_path"):
        missing_artifacts.append("quote_pack_json")
    if not payload.get("completed_buyer_schedule_path"):
        missing_artifacts.append("pricing_schedule")
    missing_artifacts = list(dict.fromkeys([item for item in missing_artifacts if item]))
    quality_score = round(satisfied / max(len(CHECKLIST), 1), 4)
    quote_pack = QuotePack.validate_payload(
        _quote_pack_schema_payload(
            {
                **payload,
                "tender_id": _text(payload.get("tender_id")),
                "missing_artifacts": missing_artifacts,
                "quality_score": quality_score,
                "quality_notes": quality_notes,
                "quote_pack_ready": quality_score >= 0.75 and not missing_artifacts,
                "artifacts": [QuotePackArtifact.validate_payload(item).to_jsonable_dict() for item in artifacts],
            }
        )
    ).to_jsonable_dict()
    return {
        "quote_pack": quote_pack,
        "checklist_results": checklist_results,
        "missing_artifacts": missing_artifacts,
        "quality_notes": quality_notes,
        "quality_score": quality_score,
        "status": "healthy" if quality_score >= 0.75 and not missing_artifacts else "degraded",
    }


def build_quote_pack_quality_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    return assess_quote_pack_quality(payload)
