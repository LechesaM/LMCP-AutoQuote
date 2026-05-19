from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

from app.domain.quote import QuotePack, QuotePackArtifact


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


def _normalize_artifact_name(path: str) -> str:
    name = Path(path).name.lower()
    if "quote_pack" in name and name.endswith(".pdf"):
        return "quote_pack_pdf"
    if "quote_pack" in name and name.endswith(".json"):
        return "quote_pack_json"
    if "quote_pack_manifest" in name or "manifest" in name:
        return "quote_pack_manifest"
    if "pricing_schedule" in name or "pricing schedule" in name:
        return "pricing_schedule"
    return name


def _payload_view(payload: Dict[str, Any]) -> Dict[str, Any]:
    base = payload.get("quote_pack") if isinstance(payload.get("quote_pack"), dict) else payload
    base = base if isinstance(base, dict) else payload
    manifest = base.get("manifest") if isinstance(base.get("manifest"), dict) else {}
    merged = dict(base)
    merged.update(manifest)
    return merged


def _truthy(*values: Any) -> bool:
    for value in values:
        if isinstance(value, bool) and value:
            return True
        if isinstance(value, str) and value.strip():
            return True
        if value not in (None, "", [], {}, 0, 0.0):
            return True
    return False


def _artifact_names(payload: Dict[str, Any]) -> List[str]:
    names: List[str] = []
    for artifact in _artifacts(payload):
        path = _text(artifact.get("path"))
        if path:
            names.append(Path(path).name.lower())
    for key in ("generated_pdf_path", "generated_json_path", "completed_buyer_schedule_path", "manifest_path", "quote_pack_manifest_path", "pricing_schedule_path"):
        path = _text(payload.get(key))
        if path:
            names.append(Path(path).name.lower())
    return list(dict.fromkeys(names))


def _consistent_artifact_naming(payload: Dict[str, Any]) -> bool:
    tender_id = re.sub(r"[^A-Za-z0-9]+", "", _text(payload.get("tender_id")).lower())
    names = _artifact_names(payload)
    if not names:
        return False
    required_tokens = {"quote_pack", "manifest", "pricing"}
    for name in names:
        if not any(token in name for token in required_tokens):
            return False
        if tender_id and tender_id not in re.sub(r"[^A-Za-z0-9]+", "", name):
            return False
    return True


def _generated_artifacts_present(payload: Dict[str, Any]) -> bool:
    artifact_map = {str(item.get("artifact_type") or "").lower(): bool(item.get("present", False)) for item in _artifacts(payload)}
    return all(
        _truthy(payload.get(key))
        for key in ("generated_pdf_path", "generated_json_path", "completed_buyer_schedule_path", "manifest_path")
    ) and (
        artifact_map.get("pdf", False)
        and artifact_map.get("json", False)
        and artifact_map.get("manifest", False)
    )


def _quote_pack_schema_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    base = _payload_view(payload)
    return {
        "tender_id": _text(base.get("tender_id")),
        "company_name": _text(base.get("company_name")),
        "company_contact_person": _text(base.get("company_contact_person")),
        "company_email": _text(base.get("company_email")),
        "company_phone": _text(base.get("company_phone")),
        "buyer_name": _text(base.get("buyer_name")),
        "tender_reference": _text(base.get("tender_reference") or base.get("tender_id")),
        "pricing_schedule_path": _text(base.get("pricing_schedule_path") or base.get("completed_buyer_schedule_path")),
        "generated_pdf_path": _text(base.get("generated_pdf_path")),
        "generated_json_path": _text(base.get("generated_json_path")),
        "completed_buyer_schedule_path": _text(base.get("completed_buyer_schedule_path")),
        "manifest_path": _text(base.get("manifest_path") or base.get("quote_pack_manifest_path")),
        "validity_days": int(base.get("validity_days") or 0),
        "delivery_terms": _text(base.get("delivery_terms")),
        "vat_treatment": _text(base.get("vat_treatment")),
        "quote_pack_ready": bool(base.get("quote_pack_ready", False)),
        "company_details_present": bool(base.get("company_details_present", False)),
        "buyer_details_present": bool(base.get("buyer_details_present", False)),
        "tender_reference_present": bool(base.get("tender_reference_present", False)),
        "pricing_schedule_present": bool(base.get("pricing_schedule_present", False)),
        "vat_treatment_shown": bool(base.get("vat_treatment_shown", False)),
        "validity_period_present": bool(base.get("validity_period_present", False)),
        "delivery_terms_present": bool(base.get("delivery_terms_present", False)),
        "signature_placeholder_present": bool(base.get("signature_placeholder_present", False)),
        "missing_artifacts": base.get("missing_artifacts") if isinstance(base.get("missing_artifacts"), list) else [],
        "artifacts": base.get("artifacts") if isinstance(base.get("artifacts"), list) else [],
        "quality_score": float(base.get("quality_score") or 0.0),
        "quality_notes": base.get("quality_notes") if isinstance(base.get("quality_notes"), list) else [],
        "warnings": base.get("warnings") if isinstance(base.get("warnings"), list) else [],
    }


def assess_quote_pack_quality(payload: Dict[str, Any]) -> Dict[str, Any]:
    base = _payload_view(payload)
    artifacts = _artifacts(base)
    checklist_results: List[Dict[str, Any]] = []
    satisfied = 0
    missing_artifacts: List[str] = []
    quality_notes: List[str] = []
    warnings: List[str] = []

    field_checks = (
        ("company_details_present", _truthy(base.get("company_details_present"), base.get("company_name"), base.get("company_email"), base.get("company_phone")), "missing_company_details", "company details present"),
        ("buyer_details_present", _truthy(base.get("buyer_details_present"), base.get("buyer_name"), base.get("rfq", {}).get("buyer_name") if isinstance(base.get("rfq"), dict) else None), "missing_buyer_details", "buyer details present"),
        ("tender_reference_present", _truthy(base.get("tender_reference_present"), base.get("tender_reference"), base.get("rfq_reference"), base.get("quote_number")), "missing_tender_reference", "tender reference present"),
        ("pricing_schedule_present", _truthy(base.get("pricing_schedule_present"), base.get("pricing_schedule_path"), base.get("completed_buyer_schedule_path")), "missing_pricing_schedule", "pricing schedule present"),
        ("vat_treatment_shown", _truthy(base.get("vat_treatment_shown"), base.get("vat_treatment"), base.get("vat_rate")), "missing_vat_treatment", "VAT treatment shown"),
        ("validity_period_present", _truthy(base.get("validity_period_present"), base.get("validity_days"), base.get("valid_until"), base.get("quote_valid_until")), "missing_validity_period", "validity period present"),
        ("delivery_terms_present", _truthy(base.get("delivery_terms_present"), base.get("delivery_terms")), "missing_delivery_terms", "delivery terms present"),
        ("signature_placeholder_present", _truthy(base.get("signature_placeholder_present"), base.get("signature_placeholder"), base.get("approval_placeholder")), "missing_signature_placeholder", "signature/approval placeholder present"),
    )

    for field_name, present, warning_code, label in field_checks:
        checklist_results.append({"field": field_name, "label": label, "present": present})
        if present:
            satisfied += 1
        else:
            warnings.append(warning_code)
            quality_notes.append(f"missing {label}")

    artifact_missing: List[str] = []
    for artifact in artifacts:
        if not artifact.get("present", False):
            missing_artifacts.append(_normalize_artifact_name(_text(artifact.get("path"))))
    if not _truthy(base.get("generated_pdf_path")):
        artifact_missing.append("quote_pack_pdf")
    if not _truthy(base.get("generated_json_path")):
        artifact_missing.append("quote_pack_json")
    if not _truthy(base.get("manifest_path"), base.get("quote_pack_manifest_path")):
        artifact_missing.append("quote_pack_manifest")
    if not _truthy(base.get("pricing_schedule_path"), base.get("completed_buyer_schedule_path")):
        artifact_missing.append("pricing_schedule")
    missing_artifacts.extend(artifact_missing)
    missing_artifacts = list(dict.fromkeys([item for item in missing_artifacts if item]))
    artifact_naming_ok = _consistent_artifact_naming(base)
    generated_artifacts_ok = _generated_artifacts_present(base)
    if not artifact_naming_ok:
        warnings.append("inconsistent_artifact_naming")
        quality_notes.append("inconsistent artifact naming")
    if not generated_artifacts_ok:
        warnings.append("missing_artifacts")
        if "missing artifacts" not in quality_notes:
            quality_notes.append("missing generated artifacts")
    satisfied += int(artifact_naming_ok) + int(generated_artifacts_ok)
    quality_score = round(satisfied / 10.0, 4)
    quote_pack = QuotePack.validate_payload(
        _quote_pack_schema_payload(
            {
                **base,
                "tender_id": _text(base.get("tender_id")),
                "missing_artifacts": missing_artifacts,
                "quality_score": quality_score,
                "quality_notes": quality_notes,
                "warnings": warnings,
                "quote_pack_ready": quality_score >= 0.8 and not missing_artifacts and artifact_naming_ok,
                "artifacts": [QuotePackArtifact.validate_payload(item).to_jsonable_dict() for item in artifacts],
            }
        )
    ).to_jsonable_dict()
    return {
        "quote_pack": quote_pack,
        "checklist_results": checklist_results,
        "missing_artifacts": missing_artifacts,
        "quality_notes": quality_notes,
        "warnings": warnings,
        "quality_score": quality_score,
        "status": "healthy" if quality_score >= 0.8 and not missing_artifacts and artifact_naming_ok else "degraded",
    }


def build_quote_pack_quality_report(payload: Dict[str, Any]) -> Dict[str, Any]:
    return assess_quote_pack_quality(payload)
