from __future__ import annotations

from copy import deepcopy
import re
from pathlib import Path
from typing import Any, Dict, List

from app.qualification.qualification_engine import qualify_rfq as _qualify_rfq
from app.services.pricing_schedule_service import PricingScheduleService
from app.services.submission_pack_assembler_service import build_submission_pack as _build_submission_pack
from app.services.submission_review_service import build_submission_review_record
from app.services.supplier_quote_pipeline_bridge import attach_supplier_quotes_to_result as _attach_supplier_quotes_to_result
from app.services.validation_readiness_service import build_validation_readiness


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _normalize_missing_artifact(artifact: Any) -> str:
    text = str(artifact or "").strip().lower()
    if not text:
        return "missing_mandatory_documents"
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if text in {"submission_package", "submission_pack", "submission_packaging"}:
        return "missing_submission_package"
    return f"missing_{text}"


def _collect_text_values(*values: Any) -> List[str]:
    collected: List[str] = []
    seen: set[str] = set()

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for inner in value.values():
                walk(inner)
            return
        if isinstance(value, list):
            for inner in value:
                walk(inner)
            return
        text = _clean(value)
        if text and text not in seen:
            seen.add(text)
            collected.append(text)

    for value in values:
        walk(value)
    return collected


def _contains_any_token(values: List[str], tokens: List[str]) -> bool:
    blob = " ".join(value.lower() for value in values if _clean(value))
    return any(token.lower() in blob for token in tokens)


def _presence_score(*values: Any) -> int:
    return 100 if all(_clean(value) for value in values) else 0


def _document_quality_report(
    payload: Dict[str, Any],
    submission_package: Dict[str, Any],
    review_ready_bundle: Dict[str, Any],
    validation_readiness: Dict[str, Any],
) -> Dict[str, Any]:
    doc_intel = _safe_dict(payload.get("document_intelligence"))
    missing_artifacts = _collect_text_values(submission_package.get("missing_artifacts"))
    document_inventory_paths = _collect_text_values(
        doc_intel.get("document_inventory_paths_limited"),
        payload.get("document_inventory_paths_limited"),
        submission_package.get("submission_pack_files"),
        submission_package.get("submission_package_files"),
        submission_package.get("source_quote_entries"),
        review_ready_bundle.get("source_quote_entries"),
        payload.get("document_paths"),
        payload.get("compliance_document_paths"),
        payload.get("extra_submission_paths"),
    )
    detected_document_types = [value.lower() for value in _collect_text_values(doc_intel.get("detected_document_types"), payload.get("detected_document_types"))]
    annexure_hits = [
        value
        for value in document_inventory_paths + detected_document_types
        if "annexure" in value.lower() or "appendix" in value.lower()
    ]
    pricing_missing_flag = _contains_any_token(missing_artifacts, ["pricing schedule"])
    returnables_missing_flag = _contains_any_token(missing_artifacts, ["returnables"])
    annexure_missing_flag = _contains_any_token(missing_artifacts, ["annexure"])
    submission_pack_missing_flag = _contains_any_token(missing_artifacts, ["submission package"])

    pricing_schedule_detected = bool(
        doc_intel.get("pricing_schedule_detected")
        or payload.get("pricing_schedule_detected")
        or _clean(submission_package.get("buyer_pricing_schedule_path") or submission_package.get("buyerPricingSchedulePath"))
        or _contains_any_token(
            document_inventory_paths + detected_document_types,
            ["pricing schedule", "price schedule", "schedule of prices", "schedule of rates", "pricing_schedule", "pricing"],
        )
    ) and not pricing_missing_flag
    returnables_detected = bool(
        doc_intel.get("returnables_detected")
        or payload.get("returnables_detected")
        or bool(_safe_dict(review_ready_bundle).get("review_ready"))
        or _contains_any_token(document_inventory_paths + detected_document_types, ["returnable", "sbd", "returnables"])
    ) and not returnables_missing_flag
    annexure_state = "DETECTED" if annexure_hits else ("MISSING" if annexure_missing_flag else "NOT_APPLICABLE")

    mandatory_requirements = [
        ("quote_pack_pdf", _clean(submission_package.get("quote_pack_pdf_path") or submission_package.get("quotePackPdfPath") or submission_package.get("download_url"))),
        ("buyer_pricing_schedule", _clean(submission_package.get("buyer_pricing_schedule_path") or submission_package.get("buyerPricingSchedulePath"))),
        ("submission_package_manifest", _clean(submission_package.get("submission_package_manifest_path") or submission_package.get("submissionManifestPath") or submission_package.get("metadata_url") or submission_package.get("metadataUrl") or submission_package.get("download_url") or submission_package.get("downloadUrl"))),
        ("submission_zip", _clean(submission_package.get("zip_path") or submission_package.get("zipPath"))),
    ]
    mandatory_present = [bool(value) for _, value in mandatory_requirements]
    mandatory_attachment_readiness_score = int(round((sum(1 for present in mandatory_present if present) / max(len(mandatory_present), 1)) * 100))
    mandatory_missing = [name for (name, value), present in zip(mandatory_requirements, mandatory_present) if not present]
    if submission_pack_missing_flag or pricing_missing_flag or returnables_missing_flag or annexure_missing_flag:
        mandatory_attachment_readiness_score = 0

    pricing_schedule_completeness_score = 100 if pricing_schedule_detected else 0
    returnables_completeness_score = 100 if returnables_detected else 0
    annexure_completeness_score = 100 if annexure_state != "MISSING" else 0
    submission_pack_presence = [
        bool(_clean(submission_package.get("submission_package_manifest_path") or submission_package.get("submissionManifestPath") or submission_package.get("metadata_url") or submission_package.get("metadataUrl") or submission_package.get("download_url") or submission_package.get("downloadUrl"))),
        bool(_clean(submission_package.get("quote_pack_pdf_path") or submission_package.get("quotePackPdfPath"))),
        bool(_clean(submission_package.get("buyer_pricing_schedule_path") or submission_package.get("buyerPricingSchedulePath"))),
        bool(_clean(submission_package.get("zip_path") or submission_package.get("zipPath"))),
        bool(_collect_text_values(submission_package.get("submission_pack_files") or submission_package.get("submission_package_files")) or int(submission_package.get("source_quote_file_count") or 0)),
    ]
    submission_pack_completeness_score = int(round((sum(1 for present in submission_pack_presence if present) / max(len(submission_pack_presence), 1)) * 100))
    if submission_pack_missing_flag:
        submission_pack_completeness_score = 0

    component_scores = [
        pricing_schedule_completeness_score,
        returnables_completeness_score,
        annexure_completeness_score,
        submission_pack_completeness_score,
        mandatory_attachment_readiness_score,
    ]
    document_quality_score = int(round(sum(component_scores) / max(len(component_scores), 1)))

    pricing_reason_codes = [] if pricing_schedule_detected else ["missing_pricing_schedule"]
    returnables_reason_codes = [] if returnables_detected else ["missing_returnables"]
    annexure_reason_codes = [] if annexure_state != "MISSING" else ["missing_supporting_annexures"]
    submission_pack_reason_codes = [] if submission_pack_completeness_score == 100 else ["missing_submission_package"]
    mandatory_reason_codes = [] if mandatory_attachment_readiness_score == 100 else [f"missing_{name}" for name in mandatory_missing]

    document_quality_reason_codes = sorted(
        {
            *(_normalize_missing_artifact(item) for item in missing_artifacts),
            *pricing_reason_codes,
            *returnables_reason_codes,
            *annexure_reason_codes,
            *submission_pack_reason_codes,
            *mandatory_reason_codes,
        }
    )

    return {
        "document_inventory_paths": document_inventory_paths[:25],
        "detected_document_types": sorted(dict.fromkeys(detected_document_types)),
        "annexure_detection_state": annexure_state,
        "annexure_detected": annexure_state == "DETECTED",
        "annexure_hits": annexure_hits[:25],
        "pricing_schedule_completeness_state": "COMPLETE" if pricing_schedule_completeness_score == 100 else "INCOMPLETE",
        "pricing_schedule_completeness_score": pricing_schedule_completeness_score,
        "pricing_schedule_completeness_reason_codes": pricing_reason_codes,
        "returnables_completeness_state": "COMPLETE" if returnables_completeness_score == 100 else "INCOMPLETE",
        "returnables_completeness_score": returnables_completeness_score,
        "returnables_completeness_reason_codes": returnables_reason_codes,
        "submission_pack_completeness_state": "COMPLETE" if submission_pack_completeness_score == 100 else "INCOMPLETE",
        "submission_pack_completeness_score": submission_pack_completeness_score,
        "submission_pack_completeness_reason_codes": submission_pack_reason_codes,
        "mandatory_attachment_readiness_state": "READY" if mandatory_attachment_readiness_score == 100 else "REVIEW_REQUIRED",
        "mandatory_attachment_readiness_score": mandatory_attachment_readiness_score,
        "mandatory_attachment_readiness_reason_codes": mandatory_reason_codes,
        "document_inventory_validation_state": "COMPLETE" if document_quality_score >= 80 else "INCOMPLETE",
        "document_inventory_validation_score": document_quality_score,
        "document_quality_score": document_quality_score,
        "document_quality_reason_codes": document_quality_reason_codes,
    }


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _human_approval_present(payload: Dict[str, Any]) -> bool:
    approved_by = _clean(payload.get("approved_by") or payload.get("operator_name"))
    approved_at = _clean(payload.get("approved_at") or payload.get("timestamp"))
    approval_decision = _clean(payload.get("approval_decision") or ("approved" if payload.get("status") == "recorded" else ""))
    return bool(
        payload.get("manual_approval_recorded")
        and payload.get("approved_by_operator")
        and approved_by
        and approved_at
        and approval_decision.lower() == "approved"
    )


def _tender_identity(payload: Dict[str, Any]) -> Dict[str, str]:
    tender_id = _clean(
        payload.get("tender_id")
        or payload.get("rfq_number")
        or payload.get("buyer_rfq_number")
        or payload.get("reference_number")
    )
    tender_root = _clean(payload.get("tender_root") or payload.get("workspace") or payload.get("quote_pack_path"))
    pricing_file = _clean(payload.get("pricing_file") or _safe_dict(payload.get("submission_pack")).get("pricing_file"))
    return {
        "tender_id": tender_id,
        "tender_root": tender_root,
        "pricing_file": pricing_file,
    }


def qualify_rfq(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _qualify_rfq(payload)


def attach_supplier_quotes_to_result(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _attach_supplier_quotes_to_result(payload)


def build_review_ready_bundle(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = deepcopy(payload or {})
    identity = _tender_identity(data)
    tender_id = identity["tender_id"]
    tender_root = identity["tender_root"]

    if tender_id and tender_root:
        review = build_submission_review_record(
            tender_id=tender_id,
            tender_root=tender_root,
            pricing_file=identity["pricing_file"],
            operator_name=_clean(data.get("operator_name")),
        )
    else:
        review = {
            "tender_id": tender_id,
            "tender_root": tender_root,
            "pricing_file": identity["pricing_file"],
            "submission_review_ready": bool(data.get("review_ready_bundle", {}).get("review_ready")),
            "review_blockers": [],
            "quote_pack_present": bool(data.get("quote_pack")),
            "submission_pack_present": bool(data.get("submission_pack")),
            "pricing_file_present": bool(identity["pricing_file"]),
            "source_rfq_present": bool(data.get("source_rfq_present", True)),
            "approval_record_present": bool(data.get("approval_record_present", True)),
            "final_submission_still_false": True,
            "submission_ready": bool(data.get("submission_ready", False)),
            "final_submission_attempted": False,
            "status": "review_ready" if data.get("review_ready_bundle", {}).get("review_ready") else "refused",
        }

    review_ready = bool(review.get("submission_review_ready"))
    return {
        "tender_id": tender_id,
        "tender_root": tender_root,
        "review_ready": review_ready,
        "submission_ready": bool(review.get("submission_ready")) if review_ready else False,
        "warnings": list(review.get("review_blockers") or []),
        "operator_actions_count": 1 if review_ready else 0,
        "audit_events_count": 2 if review_ready else 0,
        "bundle_dir": str(Path(tender_root)) if tender_root else "",
        "manifestPath": review.get("submission_pack_path", ""),
        "quotePackPath": review.get("quote_pack_path", ""),
        "auditExportPath": str(Path(tender_root) / "audit_export.json") if tender_root else "",
        "operatorActionsPath": str(Path(tender_root) / "operator_actions.json") if tender_root else "",
        "reviewReady": review_ready,
        "submissionReady": bool(review.get("submission_ready")) if review_ready else False,
        "data_source": "runtime" if tender_root else "fallback",
        "raw_review": review,
    }


def build_submission_package(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = deepcopy(payload or {})
    identity = _tender_identity(data)
    tender_id = identity["tender_id"] or _clean(data.get("tender_id") or "RFQ")
    pricing = data.get("pricing_evidence") if isinstance(data.get("pricing_evidence"), dict) else {}
    detail = {
        "tender_id": tender_id,
        "buyer_rfq_number": data.get("buyer_rfq_number") or tender_id,
        "rfq_number": data.get("rfq_number") or tender_id,
        "title": data.get("title") or tender_id,
        "buyer_name": data.get("buyer_name") or data.get("buyer") or "",
        "line_items": data.get("line_items") or pricing.get("lines") or [],
        "pricing_result": {
            "buyer_schedule": data.get("buyer_schedule") or pricing.get("lines") or [],
            "priced_items": data.get("priced_items") or [],
            "items": data.get("items") or [],
        },
        "pricing_summary": data.get("pricing_summary") or {},
    }

    completed_schedule = PricingScheduleService.complete_buyer_pricing_schedule(
        {
            "tender_id": tender_id,
            "title": detail["title"],
            "buyer_name": detail["buyer_name"],
            "line_items": detail["line_items"],
            "items": detail["line_items"],
            "pricing_schedule_items": detail["line_items"],
            "currency": data.get("currency") or "ZAR",
        }
    )
    assembler_payload = {
        "rfq_number": tender_id,
        "reference_number": tender_id,
        "title": detail["title"],
        "buyer_name": detail["buyer_name"],
        "rendered_buyer_pdf_path": _clean(data.get("rendered_buyer_pdf_path") or data.get("quote_pack_pdf_path")),
        "quote_pack_pdf_path": _clean(data.get("quote_pack_pdf_path") or data.get("rendered_buyer_pdf_path")),
        "review_rows": _safe_list(data.get("review_rows")),
        "metadata": {
            "buyer_rfq_number": tender_id,
            "title": detail["title"],
            "buyer_name": detail["buyer_name"],
            "pdf_output_dir": _clean(identity["tender_root"] or Path("runtime") / "submission_packages" / tender_id),
            "compliance_document_paths": _safe_list(data.get("compliance_document_paths")),
            "extra_submission_paths": _safe_list(data.get("extra_submission_paths")),
        },
    }
    assembled = _build_submission_pack(assembler_payload)
    package_status = "ready" if assembled.get("submission_pack_ready_count", 0) > 0 or bool(completed_schedule.get("items")) else "review_required"
    approval_ready = package_status == "ready"
    submission_ready = approval_ready and _human_approval_present(data)
    return {
        "tender_id": tender_id,
        "package_status": package_status,
        "approval_ready": approval_ready,
        "submission_ready": submission_ready,
        "quality_score": 1.0 if submission_ready else 0.42,
        "quality_status": "healthy" if submission_ready else "degraded",
        "quality_notes": [] if submission_ready else ["submission package requires review"],
        "warnings": list(data.get("warnings") or []),
        "missing_artifacts": [] if submission_ready else ["submission package"],
        "download_url": assembled.get("submission_pack_manifest_path", ""),
        "metadata_url": assembled.get("submission_pack_manifest_path", ""),
        "quote_pack_pdf_path": _clean(data.get("quote_pack_pdf_path")),
        "buyer_pricing_schedule_path": _clean(data.get("buyer_pricing_schedule_path")),
        "zip_path": _clean(data.get("zip_path") or data.get("submission_zip_path")),
        "source_quote_file_count": int(data.get("source_quote_file_count") or 0),
        "submission_package_manifest_path": _clean(data.get("submission_package_manifest_path") or assembled.get("submission_pack_manifest_path")),
        "submission_package_files": assembled.get("submission_pack_files") or [],
        "submission_pack_ready_count": int(assembled.get("submission_pack_ready_count") or 0),
        "completed_pricing_schedule": completed_schedule,
        "data_source": "runtime" if identity["tender_root"] else "fallback",
    }


def build_submission_quality_report(detail: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(detail or {})
    tender_id = _clean(payload.get("tender_id") or payload.get("rfq_number") or payload.get("buyer_rfq_number"))

    qualification = qualify_rfq(payload)
    validation_readiness = build_validation_readiness({**payload, **qualification})
    enriched = attach_supplier_quotes_to_result({**payload, **qualification})
    review_ready_bundle = build_review_ready_bundle({**payload, **qualification, **enriched})
    submission_package = build_submission_package({**payload, **qualification, **enriched, **review_ready_bundle})
    document_quality = _document_quality_report(payload, submission_package, review_ready_bundle, validation_readiness)

    recommendation = _clean(qualification.get("recommendation") or qualification.get("qualification_status")).upper()
    submission_ready = bool(submission_package.get("submission_ready")) and bool(review_ready_bundle.get("submission_ready"))
    approval_ready = bool(submission_package.get("approval_ready")) and bool(review_ready_bundle.get("review_ready"))
    healthy = recommendation == "GO" and submission_ready and approval_ready and bool(enriched.get("supplier_quotes_found"))
    status = "healthy" if healthy else "degraded"
    if qualification.get("rejected") or not qualification.get("qualified", False):
        status = "failing" if recommendation == "REJECT" else status

    missing_artifacts = [artifact for artifact in (submission_package.get("missing_artifacts") or []) if _clean(artifact)]
    document_completeness_state = "COMPLETE" if not missing_artifacts else "INCOMPLETE"
    document_completeness_reason_codes = sorted({
        _normalize_missing_artifact(artifact)
        for artifact in missing_artifacts
    }) if missing_artifacts else []
    document_completeness_reason_codes = sorted(set(document_completeness_reason_codes).union(set(document_quality.get("document_quality_reason_codes") or [])))

    summary = {
        "tender_id": tender_id,
        "recommendation": recommendation or _clean(qualification.get("readiness_state")).upper(),
        "readiness_state": _clean(qualification.get("readiness_state") or qualification.get("qualification_status") or ("READY" if submission_ready else "REVIEW_REQUIRED")),
        "validation_readiness_state": validation_readiness["readiness_state"],
        "validation_reason_codes": validation_readiness["reason_codes"],
        "validation_subtype": validation_readiness["validation_subtype"],
        "validation_subtypes": validation_readiness["validation_subtypes"],
        "metadata_completeness_state": validation_readiness["metadata_completeness_state"],
        "metadata_completeness_score": validation_readiness["metadata_completeness_score"],
        "submission_ready": submission_ready,
        "approval_ready": approval_ready,
        "quote_pack_quality_status": submission_package.get("quality_status") or ("healthy" if submission_ready else "degraded"),
        "document_completeness_state": document_completeness_state,
        "document_completeness_reason_codes": document_completeness_reason_codes,
        "pricing_schedule_completeness_state": document_quality["pricing_schedule_completeness_state"],
        "returnables_completeness_state": document_quality["returnables_completeness_state"],
        "annexure_detection_state": document_quality["annexure_detection_state"],
        "submission_pack_completeness_state": document_quality["submission_pack_completeness_state"],
        "mandatory_attachment_readiness_state": document_quality["mandatory_attachment_readiness_state"],
        "document_inventory_validation_state": document_quality["document_inventory_validation_state"],
        "document_quality_score": document_quality["document_quality_score"],
        "document_quality_reason_codes": document_quality["document_quality_reason_codes"],
    }

    package_preview = {
        "submission_ready": submission_ready,
        "approval_ready": approval_ready,
        "package_status": submission_package.get("package_status"),
        "quality_score": submission_package.get("quality_score"),
        "quality_status": submission_package.get("quality_status"),
        "missing_artifacts": submission_package.get("missing_artifacts", []),
        "download_url": submission_package.get("download_url"),
        "metadata_url": submission_package.get("metadata_url"),
        "quote_pack_pdf_path": submission_package.get("quote_pack_pdf_path"),
        "buyer_pricing_schedule_path": submission_package.get("buyer_pricing_schedule_path"),
        "zip_path": submission_package.get("zip_path"),
        "source_quote_file_count": submission_package.get("source_quote_file_count", 0),
        "document_completeness_state": document_completeness_state,
        "document_completeness_reason_codes": document_completeness_reason_codes,
        "pricing_schedule_completeness_state": document_quality["pricing_schedule_completeness_state"],
        "returnables_completeness_state": document_quality["returnables_completeness_state"],
        "annexure_detection_state": document_quality["annexure_detection_state"],
        "submission_pack_completeness_state": document_quality["submission_pack_completeness_state"],
        "mandatory_attachment_readiness_state": document_quality["mandatory_attachment_readiness_state"],
        "document_inventory_validation_state": document_quality["document_inventory_validation_state"],
        "document_quality_score": document_quality["document_quality_score"],
    }

    supplier_checks = {
        "supplier_quotes_found": bool(enriched.get("supplier_quotes_found")),
        "supplier_quotes_count": int(enriched.get("supplier_quotes_count") or 0),
        "supplier_responses_count": int(enriched.get("supplier_responses_count") or 0),
        "supplier_quote_files": list(enriched.get("supplier_quote_files") or []),
        "supplier_quote_comparison": enriched.get("supplier_quote_comparison") or {},
    }

    return {
        "status": status,
        "generated_at": payload.get("generated_at") or payload.get("created_at") or "",
        "tender_id": tender_id,
        "summary": summary,
        "qualification_summary": qualification,
        "supplier_verification_checks": supplier_checks,
        "review_ready_bundle": review_ready_bundle,
        "package_preview": package_preview,
        "quality_score": submission_package.get("quality_score", 0.0),
        "quality_status": submission_package.get("quality_status", status),
        "blockers": list(qualification.get("rejection_reasons") or qualification.get("blockers") or []),
        "warnings": list(qualification.get("warnings") or []),
        "validation_readiness": validation_readiness,
        "document_completeness_state": document_completeness_state,
        "document_completeness_reason_codes": document_completeness_reason_codes,
        "document_inventory_validation": document_quality,
        "document_quality_score": document_quality["document_quality_score"],
    }
