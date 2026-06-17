from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from app.qualification.qualification_engine import qualify_rfq as _qualify_rfq
from app.services.pricing_schedule_service import PricingScheduleService
from app.services.submission_pack_assembler_service import build_submission_pack as _build_submission_pack
from app.services.submission_review_service import build_submission_review_record
from app.services.supplier_quote_pipeline_bridge import attach_supplier_quotes_to_result as _attach_supplier_quotes_to_result


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _clean(value: Any) -> str:
    return str(value or "").strip()


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
    submission_ready = package_status == "ready" and bool(data.get("submission_ready", True))
    approval_ready = bool(data.get("approval_ready", submission_ready))
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
    enriched = attach_supplier_quotes_to_result({**payload, **qualification})
    review_ready_bundle = build_review_ready_bundle({**payload, **qualification, **enriched})
    submission_package = build_submission_package({**payload, **qualification, **enriched, **review_ready_bundle})

    recommendation = _clean(qualification.get("recommendation") or qualification.get("qualification_status")).upper()
    submission_ready = bool(submission_package.get("submission_ready")) and bool(review_ready_bundle.get("submission_ready"))
    approval_ready = bool(submission_package.get("approval_ready")) and bool(review_ready_bundle.get("review_ready"))
    healthy = recommendation == "GO" and submission_ready and approval_ready and bool(enriched.get("supplier_quotes_found"))
    status = "healthy" if healthy else "degraded"
    if qualification.get("rejected") or not qualification.get("qualified", False):
        status = "failing" if recommendation == "REJECT" else status

    summary = {
        "tender_id": tender_id,
        "recommendation": recommendation or _clean(qualification.get("readiness_state")).upper(),
        "readiness_state": _clean(qualification.get("readiness_state") or qualification.get("qualification_status") or ("READY" if submission_ready else "REVIEW_REQUIRED")),
        "submission_ready": submission_ready,
        "approval_ready": approval_ready,
        "quote_pack_quality_status": submission_package.get("quality_status") or ("healthy" if submission_ready else "degraded"),
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
    }
