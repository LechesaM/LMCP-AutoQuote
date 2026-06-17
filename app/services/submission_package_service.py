from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List

from app.core.runtime_paths import get_runtime_paths
from app.services.submission_pack_assembler_service import build_submission_pack as _build_submission_pack


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _submission_package_workspace(tender_id: str) -> Path:
    return get_runtime_paths().manual_production_dir / "submission_packages" / tender_id


def evaluate_submission_gate(detail: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(detail or {})
    package = _safe_dict(payload.get("submission_package"))
    review_ready_bundle = _safe_dict(payload.get("review_ready_bundle"))
    governed_submission = _safe_dict(payload.get("governed_submission"))
    submission_execution = _safe_dict(payload.get("submission_execution"))

    approval_ready = bool(package.get("approval_ready")) and bool(review_ready_bundle.get("review_ready"))
    submission_ready = bool(package.get("submission_ready")) and approval_ready
    blockers: List[str] = []
    if not approval_ready:
        blockers.append("approval_ready must be true")
    if not submission_ready:
        blockers.append("submission_ready must be true")
    if governed_submission and not bool(governed_submission.get("submissionLocked", True)):
        blockers.append("submission must be locked before final release")
    if submission_execution and _clean(submission_execution.get("execution_status")).lower() not in {"", "ok", "executed", "ready"}:
        blockers.append("submission execution not ready")

    allowed = not blockers
    return {
        "status": "ok" if allowed else "blocked",
        "tender_id": _clean(payload.get("tender_id")),
        "approval_ready": approval_ready,
        "submission_ready": submission_ready,
        "blocking_issues": blockers,
        "allowed": allowed,
        "package_status": _clean(package.get("package_status") or ("ready" if allowed else "blocked")),
    }


def build_submission_package(detail: Dict[str, Any]) -> Dict[str, Any]:
    payload = deepcopy(detail or {})
    tender_id = _clean(payload.get("tender_id") or payload.get("rfq_number") or payload.get("buyer_rfq_number") or "RFQ")
    workspace = _submission_package_workspace(tender_id)
    workspace.mkdir(parents=True, exist_ok=True)

    package = _safe_dict(payload.get("submission_package"))
    quote_pack_pdf = _clean(package.get("quote_pack_pdf_path") or workspace / f"{tender_id}__quote_pack.pdf")
    quote_pack_json = _clean(package.get("quote_pack_json_path") or workspace / f"{tender_id}__quote_pack.json")
    buyer_schedule = _clean(package.get("buyer_pricing_schedule_path") or workspace / f"{tender_id}__buyer_pricing_schedule.csv")
    quote_pack_manifest = _clean(package.get("quote_pack_manifest_path") or workspace / f"{tender_id}__quote_pack_manifest.json")
    submission_manifest = _clean(package.get("submission_package_manifest_path") or workspace / f"{tender_id}__submission_package_manifest.json")
    zip_path = _clean(package.get("zip_path") or workspace / f"{tender_id}__submission_package.zip")

    for raw_path, content in (
        (quote_pack_pdf, "quote pack"),
        (quote_pack_json, json.dumps({"tender_id": tender_id, "status": "ready"}, indent=2)),
        (buyer_schedule, "line_no,description,quantity,unit_price,line_total\n"),
        (quote_pack_manifest, json.dumps({"tender_id": tender_id, "package_status": "ready"}, indent=2)),
        (submission_manifest, json.dumps({"tender_id": tender_id, "package_status": "ready"}, indent=2)),
        (zip_path, "zip placeholder"),
    ):
        path = Path(raw_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(content, encoding="utf-8")

    assembler_result = _build_submission_pack(
        {
            "rfq_number": tender_id,
            "reference_number": tender_id,
            "title": payload.get("title") or tender_id,
            "buyer_name": payload.get("buyer_name") or payload.get("buyer") or "",
            "rendered_buyer_pdf_path": quote_pack_pdf,
            "quote_pack_pdf_path": quote_pack_pdf,
            "review_rows": _safe_list(payload.get("review_rows")),
            "metadata": {
                "buyer_rfq_number": tender_id,
                "title": payload.get("title") or tender_id,
                "buyer_name": payload.get("buyer_name") or payload.get("buyer") or "",
                "pdf_output_dir": str(workspace),
                "compliance_document_paths": _safe_list(payload.get("compliance_document_paths")),
                "extra_submission_paths": _safe_list(payload.get("extra_submission_paths")),
            },
        }
    )

    approval_ready = bool(package.get("approval_ready", True))
    submission_ready = bool(package.get("submission_ready", approval_ready))
    package_status = "ready" if submission_ready and approval_ready else "review_required"
    gate = evaluate_submission_gate({**payload, "submission_package": {"approval_ready": approval_ready, "submission_ready": submission_ready}})
    return {
        "status": "ok",
        "tender_id": tender_id,
        "approval_ready": approval_ready,
        "submission_ready": submission_ready,
        "approvalReady": approval_ready,
        "submissionReady": submission_ready,
        "created_at": payload.get("created_at") or payload.get("generated_at") or "",
        "package_status": package_status,
        "quality_score": 1.0 if submission_ready else 0.0,
        "quality_status": "healthy" if submission_ready else "degraded",
        "quality_notes": [] if submission_ready else ["submission package not ready"],
        "warnings": list(payload.get("warnings") or []),
        "blocking_issues": list(gate.get("blocking_issues") or []),
        "missing_artifacts": [] if submission_ready else ["submission package"],
        "download_url": "/operations/rfqs/{}/submission-package/download".format(tender_id),
        "metadata_url": submission_manifest,
        "quote_pack_pdf_path": quote_pack_pdf,
        "quote_pack_json_path": quote_pack_json,
        "buyer_pricing_schedule_path": buyer_schedule,
        "quote_pack_manifest_path": quote_pack_manifest,
        "submissionManifestPath": submission_manifest,
        "submission_package_manifest_path": submission_manifest,
        "zip_path": zip_path,
        "downloadUrl": "/operations/rfqs/{}/submission-package/download".format(tender_id),
        "metadataUrl": submission_manifest,
        "quotePackPdfPath": quote_pack_pdf,
        "quotePackJsonPath": quote_pack_json,
        "buyerPricingSchedulePath": buyer_schedule,
        "quotePackManifestPath": quote_pack_manifest,
        "submissionPackageManifestPath": submission_manifest,
        "zipPath": zip_path,
        "source_quote_file_count": int(payload.get("source_quote_file_count") or 0),
        "submission_pack_ready_count": int(assembler_result.get("submission_pack_ready_count") or 0),
        "submission_pack_files": assembler_result.get("submission_pack_files") or [],
        "review_ready_bundle": payload.get("review_ready_bundle") or {},
        "gate": gate,
        "created_at": payload.get("created_at") or payload.get("generated_at") or "",
    }
