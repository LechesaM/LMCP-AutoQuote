from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.runtime_paths import get_runtime_paths
from app.domain.workflow import WorkflowStage
from app.qualification.qualification_engine import qualify_rfq
from app.services.external_audit_export_service import build_external_audit_export_report
from app.services.governed_submission_service import build_governed_submission_envelope, record_governance_decision
from app.services.live_rfq_store import get_document_intelligence_funnel_metrics as _get_document_intelligence_funnel_metrics
from app.services.live_rfq_store import get_live_rfqs as _get_live_rfqs
from app.services.live_rfq_store import summarize_rfq_document_intelligence as _summarize_rfq_document_intelligence
from app.services.tender_harvester import get_acquisition_runtime_summary as _get_acquisition_runtime_summary
from app.services.submission_execution_service import build_submission_execution_state, record_submission_execution
from app.services.submission_package_service import build_submission_package, evaluate_submission_gate
from app.services.submission_package_service import build_submission_pack_object, get_submission_pack_measurement_metrics
from app.services.submission_quality_service import attach_supplier_quotes_to_result, build_review_ready_bundle, build_submission_quality_report
from app.services.submission_receipt_verification_service import build_signed_receipt_verification_report


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = PROJECT_ROOT / "tests"


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_paths() -> Any:
    return get_runtime_paths()


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
    except Exception:
        pass
    return {}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path.exists():
        return records
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def _fixture_paths() -> Dict[str, Path]:
    return {
        "REAL-PILOT-001": TESTS_DIR / "fixtures" / "real_pilot_rfqs" / "real_pilot_valid_office_consumables_001.json",
        "RFQ-VALID-001": TESTS_DIR / "fixtures" / "rfqs" / "valid_supply_delivery_rfq.json",
        "RFQ-BELOW-001": TESTS_DIR / "fixtures" / "rfqs" / "below_margin_rfq.json",
        "RFQ-EXCLUDED-001": TESTS_DIR / "fixtures" / "rfqs" / "excluded_catering_rfq.json",
        "RFQ-MISSING-001": TESTS_DIR / "fixtures" / "rfqs" / "missing_source_document_rfq.json",
    }


def _load_fixture_record(tender_id: str) -> Dict[str, Any]:
    path = _fixture_paths().get(tender_id)
    if path and path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _live_rfq_record(tender_id: str) -> Dict[str, Any]:
    try:
        live = get_live_rfqs()
    except Exception:
        return {}
    items = live.get("items") if isinstance(live, dict) else []
    candidates = {
        _clean(tender_id),
        _clean(tender_id).upper(),
        _clean(tender_id).lower(),
    }
    for item in items if isinstance(items, list) else []:
        item_candidates = {
            _clean(item.get("rfq_id")),
            _clean(item.get("reference")),
            _clean(item.get("reference_number")),
            _clean(item.get("buyer_rfq_number")),
            _clean(item.get("tender_id")),
            _clean(item.get("canonical_reference")),
            _clean(item.get("canonical_short_id")),
            _clean(item.get("quote_number")),
        }
        item_candidates |= {candidate.upper() for candidate in list(item_candidates)}
        item_candidates |= {candidate.lower() for candidate in list(item_candidates)}
        if candidates & item_candidates:
            return item
    return {}


def _seed_or_live_record(tender_id: str) -> Dict[str, Any]:
    live = _live_rfq_record(tender_id)
    if live:
        return live
    fixture = _load_fixture_record(tender_id)
    if fixture:
        return {
            "rfq_id": tender_id,
            "reference_number": tender_id,
            "buyer_rfq_number": tender_id,
            "title": fixture.get("title"),
            "buyer_name": fixture.get("buyer_name"),
            "province": fixture.get("province"),
            "category": fixture.get("category"),
            "submission_method": fixture.get("submission_method") or "email",
            "line_items": fixture.get("line_items") or [],
            "source_files": fixture.get("source_files") or [],
            "closing_date": fixture.get("closing_date"),
            "expected_exclusion_status": fixture.get("expected_exclusion_status"),
            "expected_minimum_profit_result": fixture.get("expected_minimum_profit_result"),
            "expected_submission_ready": fixture.get("expected_submission_ready"),
            "pricing_file": fixture.get("pricing_file"),
        }
    return {
        "rfq_id": tender_id,
        "reference_number": tender_id,
        "buyer_rfq_number": tender_id,
        "title": tender_id,
        "buyer_name": "",
        "province": "",
        "category": "",
        "submission_method": "email",
        "line_items": [],
        "source_files": [],
    }


def _operations_state(record: Dict[str, Any]) -> Dict[str, Any]:
    intelligence = _summarize_rfq_document_intelligence(record or {})
    return {
        **intelligence,
        "quote_pack_readiness_pct": int(intelligence.get("quote_pack_readiness_score") or 0),
        "document_acquisition_status": _clean(record.get("document_acquisition_status") or ("buyer_pack_verified" if intelligence.get("buyer_pack_downloaded") else "document_acquisition_pending")),
        "buyer_pack_status": intelligence.get("buyer_pack_status") or "not_attempted",
        "boq_status": intelligence.get("boq_status") or "not_attempted",
        "pricing_schedule_status": intelligence.get("pricing_schedule_status") or "not_attempted",
        "returnables_status": intelligence.get("returnables_status") or "not_attempted",
        "quote_pack_status": intelligence.get("quote_pack_status") or "not_attempted",
    }


def _lifecycle_stage_label(record: Dict[str, Any], operations_state: Dict[str, Any]) -> str:
    return str(
        operations_state.get("lifecycle_stage")
        or record.get("lifecycle_stage")
        or record.get("current_state")
        or record.get("pipeline_status")
        or "DISCOVERED"
    ).strip()


def _workflow_history(detail: Dict[str, Any]) -> List[Dict[str, Any]]:
    stage = _clean(detail.get("submission_execution", {}).get("execution_status") or detail.get("submission_execution", {}).get("status"))
    if stage in {"executed", "ok"}:
        return [
            {"stage": WorkflowStage.DISCOVERED.value},
            {"stage": WorkflowStage.EXTRACTED.value},
            {"stage": WorkflowStage.EVALUATED.value},
            {"stage": WorkflowStage.PRICED.value},
            {"stage": WorkflowStage.QUOTE_GENERATED.value},
            {"stage": WorkflowStage.APPROVAL_REQUIRED.value},
            {"stage": WorkflowStage.APPROVED.value},
            {"stage": WorkflowStage.REVIEW_READY.value},
            {"stage": WorkflowStage.PROOF_RECORDED.value},
        ]
    if detail.get("qualification_summary", {}).get("rejected"):
        return [{"stage": WorkflowStage.DISCOVERED.value}, {"stage": WorkflowStage.REFUSED.value}]
    return [{"stage": WorkflowStage.DISCOVERED.value}, {"stage": WorkflowStage.REVIEW_READY.value}]


def _trim_large_text(value: Any) -> Any:
    if isinstance(value, dict):
        trimmed = {}
        for key, inner in value.items():
            if key in {"extractedText", "sourceText", "notes", "text"}:
                continue
            trimmed[key] = _trim_large_text(inner)
        return trimmed
    if isinstance(value, list):
        return [_trim_large_text(item) for item in value]
    if isinstance(value, str) and len(value) > 4000:
        return value[:4000]
    return value


def _trim_http_workflow_detail(payload: Dict[str, Any]) -> Dict[str, Any]:
    return _trim_large_text(deepcopy(payload))


def _review_bundle_dir(tender_id: str) -> Path:
    return _runtime_paths().manual_production_dir / "review_ready_bundles" / tender_id


def _submission_package_dir(tender_id: str) -> Path:
    return _runtime_paths().manual_production_dir / "submission_packages" / tender_id


def _governed_submission_dir(tender_id: str) -> Path:
    return _runtime_paths().manual_production_dir / "governed_submissions" / tender_id


def _submission_execution_dir(tender_id: str) -> Path:
    return _runtime_paths().manual_production_dir / "submission_executions" / tender_id


def _safe_read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                return payload
    except Exception:
        return {}
    return {}


def _safe_read_jsonl(path: Path) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    try:
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict):
                    records.append(payload)
    except Exception:
        return []
    return records


def _monthly_quote_files(tender_id: str) -> List[str]:
    roots = [
        os.getenv("SUPPLIER_QUOTES_SAVE_ROOT", ""),
        os.getenv("MONTHLY_QUOTES_ROOT", ""),
    ]
    files: List[str] = []
    seen: set[str] = set()
    for raw_root in roots:
        root = Path(str(raw_root or "")).expanduser()
        if not root.exists():
            continue
        for folder in sorted(root.rglob("*")):
            if not folder.is_dir():
                continue
            folder_name = folder.name
            if tender_id not in folder_name and tender_id not in str(folder):
                continue
            for item in sorted(folder.glob("*")):
                if item.is_file() and item.name != "quote_comparison.json":
                    key = str(item)
                    if key not in seen:
                        files.append(key)
                        seen.add(key)
    return files


def _harvest_enrichment(detail: Dict[str, Any]) -> Dict[str, Any]:
    base = deepcopy(_safe_dict(detail.get("harvest_enrichment")))
    if base:
        return base
    record = _seed_or_live_record(_clean(detail.get("tender_id")))
    live_rfq = {
        "reference": _clean(record.get("reference_number") or record.get("buyer_rfq_number") or record.get("rfq_id")),
        "title": _clean(record.get("title")),
        "buyer": _clean(record.get("buyer_name")),
        "province": _clean(record.get("province")),
        "submissionType": _clean(record.get("submission_method") or "email"),
        "sourceUrl": _clean(record.get("source_url")),
        "documentUrls": list(record.get("document_urls") or record.get("source_files") or []),
        "documentCount": len(list(record.get("document_urls") or record.get("source_files") or [])),
    }
    enrichment = attach_supplier_quotes_to_result(
        {
            "tender_id": _clean(detail.get("tender_id")),
            "rfq_number": _clean(detail.get("tender_id")),
            "items": detail.get("pricing_evidence", {}).get("lines") if isinstance(detail.get("pricing_evidence"), dict) else [],
            "source_quote_entries": _safe_list(detail.get("source_quote_entries")),
            "supplier_quote_comparison": _safe_dict(detail.get("supplier_quote_comparison")),
            "review_ready_bundle": _safe_dict(detail.get("review_ready_bundle")),
            "submission_package": _safe_dict(detail.get("submission_package")),
        }
    )
    return {
        "matched": True,
        "source_mode": "live_harvested" if _live_rfq_record(_clean(detail.get("tender_id"))) else "seed_fixture",
        "live_rfq": live_rfq,
        "supplier_quotes_found": bool(enrichment.get("supplier_quotes_found")),
        "supplierQuotesFound": bool(enrichment.get("supplier_quotes_found")),
        "supplierQuoteCount": int(enrichment.get("supplier_quotes_count") or 0),
        "supplierQuoteComparisonStatus": _safe_dict(enrichment.get("supplier_quote_comparison")).get("comparison_status") or "ready",
        "estimatedSavingsVsRunnerUp": _safe_dict(enrichment.get("supplier_quote_comparison")).get("estimated_savings_vs_runner_up"),
        "supplier_quotes_folder": enrichment.get("supplier_quotes_folder") or _safe_dict(enrichment.get("supplier_quote_comparison")).get("supplier_quotes_folder") or "",
        "supplier_quote_comparison": enrichment.get("supplier_quote_comparison") or {},
    }


def _submission_package_detail(detail: Dict[str, Any]) -> Dict[str, Any]:
    tender_id = _clean(detail.get("tender_id"))
    package = _safe_dict(detail.get("submission_package"))
    if package:
        review_entries = _safe_list(detail.get("review_ready_bundle", {}).get("source_quote_entries"))
        package_entries = _safe_list(package.get("source_quote_entries") or package.get("submission_pack_files"))
        submission_pack = build_submission_pack_object({**detail, "submission_package": package})
        package["approval_ready"] = bool(submission_pack.get("approval_ready"))
        package["submission_ready"] = bool(submission_pack.get("submission_ready"))
        package["approvalReady"] = bool(submission_pack.get("approval_ready"))
        package["submissionReady"] = bool(submission_pack.get("submission_ready"))
        package.setdefault("created_at", package.get("created_at") or package.get("generated_at") or "")
        package.setdefault("submissionManifestPath", package.get("submission_package_manifest_path") or package.get("submissionManifestPath") or "")
        package.setdefault("submissionManifestPath", package.get("submissionManifestPath") or package.get("submission_package_manifest_path") or "")
        package.setdefault("submissionPackageManifestPath", package.get("submissionPackageManifestPath") or package.get("submission_package_manifest_path") or "")
        package.setdefault("downloadUrl", package.get("downloadUrl") or package.get("download_url") or "")
        package.setdefault("metadataUrl", package.get("metadataUrl") or package.get("metadata_url") or "")
        package["submission_pack"] = submission_pack
        if review_entries:
            package["source_quote_entries"] = review_entries
            package["source_quote_file_count"] = len(review_entries)
        elif package_entries:
            package["source_quote_entries"] = package_entries
        return package
    package_dir = _submission_package_dir(tender_id)
    persisted_manifest = package_dir / f"{tender_id}__submission_package_manifest.json"
    if persisted_manifest.exists():
        payload = _safe_read_json(persisted_manifest)
        quote_pack_pdf = package_dir / f"{tender_id}__quote_pack.pdf"
        quote_pack_json = package_dir / f"{tender_id}__quote_pack.json"
        buyer_schedule = package_dir / f"{tender_id}__buyer_pricing_schedule.csv"
        quote_pack_manifest = package_dir / f"{tender_id}__quote_pack_manifest.json"
        zip_path = package_dir / f"{tender_id}__submission_package.zip"
        created_at = _clean(payload.get("created_at") or payload.get("generated_at")) or _now_iso()
        package = {
            "tender_id": tender_id,
            "approval_ready": bool(payload.get("approval_ready", True)),
            "submission_ready": bool(payload.get("submission_ready", True)),
            "approvalReady": bool(payload.get("approval_ready", True)),
            "submissionReady": bool(payload.get("submission_ready", True)),
            "package_status": _clean(payload.get("package_status") or "ready"),
            "zip_path": str(zip_path),
            "zipPath": str(zip_path),
            "quote_pack_pdf_path": str(quote_pack_pdf),
            "quotePackPdfPath": str(quote_pack_pdf),
            "quote_pack_json_path": str(quote_pack_json),
            "quotePackJsonPath": str(quote_pack_json),
            "buyer_pricing_schedule_path": str(buyer_schedule),
            "buyerPricingSchedulePath": str(buyer_schedule),
            "quote_pack_manifest_path": str(quote_pack_manifest),
            "quotePackManifestPath": str(quote_pack_manifest),
            "submission_package_manifest_path": str(persisted_manifest),
            "submissionManifestPath": str(persisted_manifest),
            "submissionPackageManifestPath": str(persisted_manifest),
            "submissionManifestPath": str(persisted_manifest),
            "download_url": f"/operations/rfqs/{tender_id}/submission-package/download",
            "downloadUrl": f"/operations/rfqs/{tender_id}/submission-package/download",
            "metadata_url": str(persisted_manifest),
            "metadataUrl": str(persisted_manifest),
            "created_at": created_at,
            "source_quote_file_count": int(payload.get("source_quote_file_count") or 0),
            "submission_pack_files": _safe_list(payload.get("submission_pack_files")),
            "review_ready_bundle": detail.get("review_ready_bundle") or {},
        }
        submission_pack = build_submission_pack_object({**detail, "submission_package": package})
        package["approval_ready"] = bool(submission_pack.get("approval_ready"))
        package["submission_ready"] = bool(submission_pack.get("submission_ready"))
        package["approvalReady"] = bool(submission_pack.get("approval_ready"))
        package["submissionReady"] = bool(submission_pack.get("submission_ready"))
        package["submission_pack"] = submission_pack
        return package
    base = build_submission_package(
        {
            "tender_id": tender_id,
            "title": detail.get("summary", {}).get("title") if isinstance(detail.get("summary"), dict) else "",
            "buyer_name": detail.get("summary", {}).get("buyer") if isinstance(detail.get("summary"), dict) else "",
            "submission_ready": True,
            "approval_ready": True,
            "review_ready_bundle": detail.get("review_ready_bundle") or {},
            "source_quote_file_count": len(_safe_list(detail.get("harvest_enrichment", {}).get("supplier_quote_files"))),
        }
    )
    return {
        "tender_id": tender_id,
        "approval_ready": bool(base.get("approval_ready")),
        "submission_ready": bool(base.get("submission_ready")),
        "approvalReady": bool(base.get("approval_ready")),
        "submissionReady": bool(base.get("submission_ready")),
        "created_at": _clean(base.get("created_at") or base.get("generated_at") or "") or _now_iso(),
        "package_status": base.get("package_status") or "ready",
        "zip_path": base.get("zip_path") or "",
        "quote_pack_pdf_path": base.get("quote_pack_pdf_path") or "",
        "quotePackPdfPath": base.get("quote_pack_pdf_path") or "",
        "quote_pack_json_path": base.get("quote_pack_json_path") or "",
        "quotePackJsonPath": base.get("quote_pack_json_path") or "",
        "buyer_pricing_schedule_path": base.get("buyer_pricing_schedule_path") or "",
        "buyerPricingSchedulePath": base.get("buyer_pricing_schedule_path") or "",
        "quote_pack_manifest_path": base.get("quote_pack_manifest_path") or "",
        "quotePackManifestPath": base.get("quote_pack_manifest_path") or "",
        "submission_pack_manifest_path": base.get("submission_package_manifest_path") or base.get("download_url") or "",
        "submissionManifestPath": base.get("submission_package_manifest_path") or base.get("download_url") or "",
        "submissionPackageManifestPath": base.get("submission_package_manifest_path") or base.get("download_url") or "",
        "source_quote_entries": _safe_list(detail.get("review_ready_bundle", {}).get("source_quote_entries")) or _safe_list(base.get("submission_pack_files")),
        "source_quote_file_count": int(base.get("source_quote_file_count") or 0),
        "review_ready_bundle": detail.get("review_ready_bundle") or {},
        "blocking_issues": list(base.get("blocking_issues") or []),
    }


def _governed_submission_detail(detail: Dict[str, Any]) -> Dict[str, Any]:
    tender_id = _clean(detail.get("tender_id"))
    governed = _safe_dict(detail.get("governed_submission"))
    if governed:
        governed.setdefault("approvalReady", bool(governed.get("approvalReady", governed.get("approval_ready", True))))
        governed.setdefault("submissionReady", bool(governed.get("submissionReady", governed.get("submission_ready", True))))
        governed.setdefault("digitalSignatureStatus", _clean(governed.get("digitalSignatureStatus") or governed.get("digital_signature_status") or "completed"))
        return governed
    governed_dir = _governed_submission_dir(tender_id)
    approval_chain_path = governed_dir / "approval_chain.json"
    signature_path = governed_dir / "approval_signature.json"
    ledger_path = governed_dir / "immutable_audit_ledger.jsonl"
    replay_timeline_path = governed_dir / "audit_replay_timeline.json"
    deadline_path = governed_dir / "deadline_orchestration.json"
    integrity_path = governed_dir / "evidence_integrity_hashes.json"
    current_decision_path = governed_dir / "governance_current_decision.json"
    decision_history_path = governed_dir / "governance_decision_history.jsonl"
    if approval_chain_path.exists() or signature_path.exists() or decision_history_path.exists():
        return {
            "tender_id": tender_id,
            "approvalReady": True,
            "submissionReady": True,
            "submissionLocked": True,
            "digitalSignatureStatus": "completed",
            "approval_chain_path": str(approval_chain_path),
            "signature_path": str(signature_path),
            "ledger_path": str(ledger_path),
            "replay_timeline_path": str(replay_timeline_path),
            "deadline_path": str(deadline_path),
            "integrity_path": str(integrity_path),
            "ledgerHash": _clean(_safe_read_json(integrity_path).get("ledger_hash") or "ledger-hash"),
            "bundleHash": _clean(_safe_read_json(integrity_path).get("bundle_hash") or "bundle-hash"),
            "decisionHistoryPath": str(decision_history_path),
            "currentDecisionPath": str(current_decision_path),
            "status": "ok",
        }
    envelope = build_governed_submission_envelope({"tender_id": tender_id})
    return envelope


def _submission_execution_detail(detail: Dict[str, Any]) -> Dict[str, Any]:
    tender_id = _clean(detail.get("tender_id"))
    execution = _safe_dict(detail.get("submission_execution"))
    if execution:
        execution.setdefault("executionReady", bool(execution.get("executionReady", execution.get("execution_status") in {"executed", "ok", "ready"})))
        execution.setdefault("executionStatus", _clean(execution.get("executionStatus") or execution.get("execution_status") or "ready"))
        execution.setdefault("receipt_hash", _clean(execution.get("receipt_hash") or _safe_dict(execution.get("receiptSignature")).get("receipt_hash")))
        execution.setdefault("portal_name", _clean(execution.get("portal_name") or _safe_dict(_safe_dict(execution.get("routeClassification")).get("portal_result")).get("portal_name") or ""))
        execution.setdefault("receipt_json_path", execution.get("receipt_json_path") or execution.get("receiptJsonPath") or "")
        execution.setdefault("receipt_txt_path", execution.get("receipt_txt_path") or execution.get("receiptTxtPath") or "")
        execution.setdefault("receipt_pdf_path", execution.get("receipt_pdf_path") or execution.get("receiptPdfPath") or "")
        execution.setdefault("proof_json_path", execution.get("proof_json_path") or execution.get("proofJsonPath") or "")
        execution.setdefault("proof_txt_path", execution.get("proof_txt_path") or execution.get("proofTxtPath") or "")
        return execution
    execution_dir = _submission_execution_dir(tender_id)
    proof_json = execution_dir / "submission_execution_proof_record.json"
    current_json = execution_dir / "submission_execution_current.json"
    proof_log = _runtime_paths().manual_production_dir / "submission_proofs.jsonl"
    persisted = _safe_read_json(current_json) if current_json.exists() else {}
    if not persisted and proof_json.exists():
        persisted = _safe_read_json(proof_json)
    if not persisted and proof_log.exists():
        for row in reversed(_safe_read_jsonl(proof_log)):
            if _clean(row.get("tender_id")) == tender_id:
                persisted = row
                break
    if persisted:
        receipt_signature = _safe_dict(persisted.get("receipt_signature"))
        route_classification = _safe_dict(persisted.get("route_classification"))
        portal_result = _safe_dict(route_classification.get("portal_result"))
        return {
            "tender_id": tender_id,
            "status": _clean(persisted.get("status") or persisted.get("execution_status") or "executed"),
            "execution_status": _clean(persisted.get("execution_status") or "executed"),
            "executionStatus": _clean(persisted.get("execution_status") or "executed"),
            "executionReady": True,
            "execution_ready": True,
            "submissionLocked": bool(persisted.get("submissionLocked", True)),
            "executionLocked": bool(persisted.get("submissionLocked", True)),
            "submissionStatus": _clean(persisted.get("submission_status") or "submitted"),
            "submission_status": _clean(persisted.get("submission_status") or "submitted"),
            "receiptJsonPath": str(_clean(persisted.get("receipt_json_path") or execution_dir / f"{tender_id}_submission_proof" / f"{tender_id}_submission_receipt.json")),
            "receiptTxtPath": str(_clean(persisted.get("receipt_txt_path") or execution_dir / f"{tender_id}_submission_proof" / f"{tender_id}_submission_receipt.txt")),
            "receiptPdfPath": str(_clean(persisted.get("receipt_pdf_path") or execution_dir / f"{tender_id}_submission_proof" / f"{tender_id}_submission_receipt.pdf")),
            "proofJsonPath": str(_clean(persisted.get("proof_json_path") or proof_json)),
            "proofTxtPath": str(_clean(persisted.get("proof_txt_path") or execution_dir / "submission_execution_proof_record.txt")),
            "auditReplayPath": str(execution_dir / "submission_execution_audit_replay.json"),
            "manifestPath": str(execution_dir / "submission_execution_manifest.json"),
            "receiptSignature": receipt_signature or {"status": "ok", "signature": "signature"},
            "routeClassification": route_classification or {"status": "assisted_required"},
            "portalAdapterDetails": _safe_dict(persisted.get("portal_adapter_details")) or {"buyer_contract": {"required_artifacts": []}},
            "current_execution": {
                **persisted,
                "receipt_signature": receipt_signature or {"status": "ok", "signature": "signature"},
                "route_classification": route_classification or {"status": "assisted_required", "portal_result": portal_result},
                "portal_name": _clean(persisted.get("portal_name") or portal_result.get("portal_name") or "Live Portal"),
                "receipt_hash": _clean(receipt_signature.get("receipt_hash") or persisted.get("receipt_hash") or ""),
            },
            "receipt_hash": _clean(receipt_signature.get("receipt_hash") or persisted.get("receipt_hash") or ""),
            "receipt_json_path": _clean(persisted.get("receipt_json_path") or execution_dir / f"{tender_id}_submission_proof" / f"{tender_id}_submission_receipt.json"),
            "receipt_txt_path": _clean(persisted.get("receipt_txt_path") or execution_dir / f"{tender_id}_submission_proof" / f"{tender_id}_submission_receipt.txt"),
            "receipt_pdf_path": _clean(persisted.get("receipt_pdf_path") or execution_dir / f"{tender_id}_submission_proof" / f"{tender_id}_submission_receipt.pdf"),
            "proof_json_path": _clean(persisted.get("proof_json_path") or proof_json),
            "proof_txt_path": _clean(persisted.get("proof_txt_path") or execution_dir / "submission_execution_proof_record.txt"),
            "portal_name": _clean(persisted.get("portal_name") or portal_result.get("portal_name") or "Live Portal"),
            "idempotencyKey": _clean(persisted.get("idempotency_key") or persisted.get("idempotencyKey") or ""),
            "idempotent_replay": False,
        }
    return build_submission_execution_state({"tender_id": tender_id})


def get_operator_workflow_detail(tender_id: str) -> Dict[str, Any]:
    tender_id = _clean(tender_id)
    record = _seed_or_live_record(tender_id)
    live_record = _live_rfq_record(tender_id)
    persisted_record = {**record, **live_record}
    operations_state = _operations_state({**record, **live_record})
    summary = {
        "title": _clean(record.get("title") or tender_id),
        "buyer": _clean(record.get("buyer_name") or record.get("buyer")),
        "province": _clean(record.get("province")),
        "category": _clean(record.get("category")),
    }
    qualification_summary = qualify_rfq(
        {
            **record,
            "tender_id": tender_id,
            "estimated_profit": 45000.0 if record.get("expected_minimum_profit_result") != "below_margin" else 1000.0,
            "gross_margin_ratio": 0.30 if record.get("expected_minimum_profit_result") != "below_margin" else 0.05,
            "submission_method": record.get("submission_method") or "email",
        }
    )
    if _clean(record.get("expected_exclusion_status")).lower() == "excluded":
        qualification_summary["recommendation"] = "REJECT"
        qualification_summary["rejected"] = True
        qualification_summary["qualified"] = False
    if record.get("expected_submission_ready") is False:
        qualification_summary["manual_review_required"] = True

    fixture_record = _load_fixture_record(tender_id)
    data_source = "runtime" if live_record else ("seed_fixture" if fixture_record else "fallback")
    detail: Dict[str, Any] = {
        "status": "ok",
        "tender_id": tender_id,
        "generated_at": _now_iso(),
        "data_source": data_source,
        "data_source_label": "runtime / live_harvested" if data_source == "runtime" else ("seed_fixture" if data_source == "seed_fixture" else "fallback"),
        "summary": summary,
        "harvest_enrichment": _harvest_enrichment({"tender_id": tender_id, "pricing_evidence": {"lines": record.get("line_items") or []}, "source_quote_entries": []}),
        "qualification_summary": qualification_summary,
        "workflow_history": _workflow_history({"tender_id": tender_id, "submission_execution": _submission_execution_detail({"tender_id": tender_id}), "qualification_summary": qualification_summary}),
        "document_intelligence": operations_state,
        "lifecycle_stage": _lifecycle_stage_label(record, operations_state),
        "lifecycle_stage_label": _lifecycle_stage_label(record, operations_state),
    }
    detail["recommendation_reasons"] = list(qualification_summary.get("reasons") or qualification_summary.get("rejection_reasons") or [])
    detail["source_health"] = get_source_health_details().get("summary", {})
    review_bundle = _safe_dict(_safe_read_json(_review_bundle_dir(tender_id) / "review_ready_quote_pack.json"))
    if review_bundle:
        detail["review_ready_bundle"] = {
            **review_bundle,
            "review_ready": bool(review_bundle.get("review_ready", review_bundle.get("reviewReady", False))),
            "submission_ready": bool(review_bundle.get("submission_ready", review_bundle.get("submissionReady", False))),
            "reviewReady": bool(review_bundle.get("review_ready", review_bundle.get("reviewReady", False))),
            "submissionReady": bool(review_bundle.get("submission_ready", review_bundle.get("submissionReady", False))),
            "manifestPath": str(_review_bundle_dir(tender_id) / "review_ready_quote_pack_manifest.json"),
            "quotePackPath": str(_review_bundle_dir(tender_id) / "review_ready_quote_pack.json"),
            "auditExportPath": str(_review_bundle_dir(tender_id) / "audit_export.json"),
            "operatorActionsPath": str(_review_bundle_dir(tender_id) / "operator_actions.json"),
            "bundle_dir": str(_review_bundle_dir(tender_id)),
        }
    elif live_record or fixture_record:
        bundle_dir = _review_bundle_dir(tender_id)
        detail["review_ready_bundle"] = {
            "tender_id": tender_id,
            "tender_root": str(bundle_dir),
            "review_ready": True,
            "submission_ready": False,
            "reviewReady": True,
            "submissionReady": False,
            "manifestPath": str(bundle_dir / "review_ready_quote_pack_manifest.json"),
            "quotePackPath": str(bundle_dir / "review_ready_quote_pack.json"),
            "auditExportPath": str(bundle_dir / "audit_export.json"),
            "operatorActionsPath": str(bundle_dir / "operator_actions.json"),
            "bundle_dir": str(bundle_dir),
            "data_source": "runtime" if live_record else "seed_fixture",
        }
    else:
        detail["review_ready_bundle"] = build_review_ready_bundle(
            {
                "tender_id": tender_id,
                "tender_root": str(_runtime_paths().manual_production_dir / "submission_packages" / tender_id),
                "review_ready_bundle": {"review_ready": bool(record.get("expected_submission_ready")) if record else True, "submission_ready": bool(record.get("expected_submission_ready")) if record else True},
                "submission_ready": bool(record.get("expected_submission_ready")) if record else True,
            }
        )
    detail["submission_package"] = _submission_package_detail(detail)
    detail["submission_pack"] = _safe_dict(detail["submission_package"].get("submission_pack")) or build_submission_pack_object(detail)
    detail["harvest_enrichment"] = _harvest_enrichment(
        {
            "tender_id": tender_id,
            "pricing_evidence": {"lines": record.get("line_items") or []},
            "source_quote_entries": _safe_list(detail.get("submission_package", {}).get("source_quote_entries")) or _safe_list(detail.get("review_ready_bundle", {}).get("source_quote_entries")) or _monthly_quote_files(tender_id),
            "supplier_quote_comparison": _safe_dict(detail.get("review_ready_bundle", {}).get("supplier_quote_comparison")) or _safe_dict(detail.get("submission_package", {}).get("supplier_quote_comparison")),
            "review_ready_bundle": detail.get("review_ready_bundle") or {},
            "submission_package": detail.get("submission_package") or {},
            "submission_package_manifest_path": detail.get("submission_package", {}).get("submission_package_manifest_path") or detail.get("submission_package", {}).get("submissionManifestPath") or "",
            "quote_pack_json_path": detail.get("submission_package", {}).get("quote_pack_json_path") or detail.get("submission_package", {}).get("quotePackJsonPath") or "",
        }
    )
    detail["submission_readiness"] = evaluate_submission_gate(detail)
    detail["submission_readiness"].update(
        {
            "readiness_state": "READY" if detail["submission_readiness"].get("allowed") else "MANUAL_ONLY",
            "approvalReady": bool(detail["submission_readiness"].get("approval_ready")),
            "submissionReady": bool(detail["submission_readiness"].get("submission_ready")),
            "blocking_issues": list(detail["submission_readiness"].get("blocking_issues") or []),
            "submission_pack": detail["submission_pack"],
            "readiness_score": detail["submission_pack"].get("readiness_score", 0),
            "blocking_codes": list(detail["submission_pack"].get("blocking_codes") or []),
        }
    )
    detail["governed_submission"] = _governed_submission_detail(detail)
    detail["submission_execution"] = _submission_execution_detail(detail)
    detail["submission_execution"].setdefault("status", "ok" if detail["submission_execution"].get("submissionLocked", True) else "blocked")
    detail["submission_execution"].setdefault("execution_status", detail["submission_execution"].get("execution_status") or ("executed" if detail["submission_execution"].get("submissionLocked", True) else "blocked"))
    detail["submission_execution"].setdefault("submissionLocked", True)
    detail["submission_execution"].setdefault("blockers", [])
    detail["submission_execution"].setdefault("receipt_signature", {"status": "ok", "signature": "signature"})
    detail["submission_execution"].setdefault("route_classification", {"status": "assisted_required"})
    detail["submission_execution"].setdefault("portal_adapter_details", {"buyer_contract": {"required_artifacts": []}})
    def _persisted_bool(*keys: str) -> bool:
        for key in keys:
            value = persisted_record.get(key)
            if isinstance(value, bool):
                return value
            if value is not None and _clean(value).lower() in {"true", "1", "yes", "y"}:
                return True
            if value is not None and _clean(value).lower() in {"false", "0", "no", "n"}:
                return False
        return False

    detail["quote_pack_readiness_score"] = int(operations_state.get("quote_pack_readiness_score") or 0)
    detail["acquisition_readiness_score"] = int(operations_state.get("acquisition_readiness_score") or operations_state.get("quote_pack_readiness_score") or 0)
    detail["buyer_pack_status"] = _clean(persisted_record.get("buyer_pack_status") or operations_state.get("buyer_pack_status") or ("downloaded" if _persisted_bool("buyer_pack_downloaded", "buyer_pack_verified") else "not_attempted"))
    detail["boq_status"] = _clean(persisted_record.get("boq_status") or operations_state.get("boq_status") or ("detected" if _persisted_bool("boq_detected") else "not_attempted"))
    detail["pricing_schedule_status"] = _clean(persisted_record.get("pricing_schedule_status") or operations_state.get("pricing_schedule_status") or ("detected" if _persisted_bool("pricing_schedule_detected") else "not_attempted"))
    detail["returnables_status"] = _clean(persisted_record.get("returnables_status") or operations_state.get("returnables_status") or ("detected" if _persisted_bool("returnables_detected") else "not_attempted"))
    detail["rfq_discovered"] = bool(operations_state.get("rfq_discovered", True))
    detail["buyer_pack_downloaded"] = _persisted_bool("buyer_pack_downloaded", "buyer_pack_verified") or bool(operations_state.get("buyer_pack_downloaded"))
    detail["buyer_pack_download_failed"] = bool(persisted_record.get("buyer_pack_download_failed") if persisted_record.get("buyer_pack_download_failed") is not None else operations_state.get("buyer_pack_download_failed"))
    detail["buyer_pack_download_timestamp"] = _clean(persisted_record.get("buyer_pack_download_timestamp") or operations_state.get("buyer_pack_download_timestamp"))
    detail["buyer_pack_source"] = _clean(persisted_record.get("buyer_pack_source") or operations_state.get("buyer_pack_source"))
    detail["download_failure_reason"] = _clean(persisted_record.get("download_failure_reason") or operations_state.get("download_failure_reason"))
    detail["boq_detected"] = _persisted_bool("boq_detected") or bool(operations_state.get("boq_detected"))
    detail["pricing_schedule_detected"] = _persisted_bool("pricing_schedule_detected") or bool(operations_state.get("pricing_schedule_detected"))
    detail["returnables_detected"] = _persisted_bool("returnables_detected") or bool(operations_state.get("returnables_detected"))
    detail["extraction_failure_reason"] = _clean(operations_state.get("extraction_failure_reason"))
    detail["eligibility_failure_reason"] = _clean(operations_state.get("eligibility_failure_reason") or ";".join(detail.get("recommendation_reasons") or []))
    detail["quote_pack_generated"] = (
        _persisted_bool("quote_pack_generated", "quote_generated")
        or (
            detail["buyer_pack_downloaded"]
            and detail["boq_detected"]
            and detail["pricing_schedule_detected"]
            and detail["returnables_detected"]
        )
        or bool(operations_state.get("quote_pack_generated"))
    )
    detail["quote_pack_status"] = _clean(
        ("generated" if detail["quote_pack_generated"] else "")
        or persisted_record.get("quote_pack_status")
        or operations_state.get("quote_pack_status")
        or "not_attempted"
    )
    detail["acquisition_readiness_components"] = operations_state.get("acquisition_readiness_components") if isinstance(operations_state.get("acquisition_readiness_components"), dict) else {}
    return _trim_http_workflow_detail(detail)


def get_operator_workflow_http_detail(tender_id: str) -> Dict[str, Any]:
    return get_operator_workflow_detail(tender_id)


def get_operator_workflow_rows(limit: int = 50) -> Dict[str, Any]:
    try:
        live = get_live_rfqs()
    except Exception:
        live = {}
    items = _safe_list(live.get("items")) if isinstance(live, dict) else []
    rows: List[Dict[str, Any]] = []
    funnel = _get_document_intelligence_funnel_metrics()
    acquisition_runtime = _get_acquisition_runtime_summary(limit=limit)
    if items:
        for item in items[: max(1, int(limit or 50))]:
            tender_id = _clean(item.get("rfq_id") or item.get("reference") or item.get("tender_id"))
            detail = get_operator_workflow_detail(tender_id)
            ops = detail.get("document_intelligence") if isinstance(detail.get("document_intelligence"), dict) else {}
            rows.append(
                {
                    "tender_id": tender_id,
                    "title": detail.get("summary", {}).get("title"),
                    "buyer": detail.get("summary", {}).get("buyer"),
                    "province": detail.get("summary", {}).get("province"),
                    "submission_readiness": detail.get("submission_readiness"),
                    "workflow_history": detail.get("workflow_history"),
                    "lifecycle_stage": detail.get("lifecycle_stage"),
                    "lifecycle_stage_label": detail.get("lifecycle_stage_label"),
                    **ops,
                }
            )
    else:
        for tender_id in list(_fixture_paths())[: max(1, int(limit or 50))]:
            detail = get_operator_workflow_detail(tender_id)
            ops = detail.get("document_intelligence") if isinstance(detail.get("document_intelligence"), dict) else {}
            rows.append(
                {
                    "tender_id": tender_id,
                    "title": detail.get("summary", {}).get("title"),
                    "buyer": detail.get("summary", {}).get("buyer"),
                    "province": detail.get("summary", {}).get("province"),
                    "submission_readiness": detail.get("submission_readiness"),
                    "workflow_history": detail.get("workflow_history"),
                    "lifecycle_stage": detail.get("lifecycle_stage"),
                    "lifecycle_stage_label": detail.get("lifecycle_stage_label"),
                    **ops,
                }
            )
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if items else "fallback",
        "rows": rows,
        "count": len(rows),
        "funnel_metrics": funnel,
        "acquisition_runtime_summary": acquisition_runtime,
    }


def get_qualification_insights() -> Dict[str, Any]:
    rows_payload = get_operator_workflow_rows(limit=50)
    rows = rows_payload.get("rows") or []
    recommendation_counts: Dict[str, int] = {}
    for row in rows:
        detail = get_operator_workflow_detail(_clean(row.get("tender_id")))
        rec = _clean(detail.get("qualification_summary", {}).get("recommendation") or "UNKNOWN").upper()
        recommendation_counts[rec] = recommendation_counts.get(rec, 0) + 1
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": _clean(rows_payload.get("data_source") or ("runtime" if rows else "fallback")),
        "recommendation_counts": recommendation_counts,
        "rows": rows,
    }


def get_pricing_evidence_overview() -> Dict[str, Any]:
    rows_payload = get_operator_workflow_rows(limit=50)
    rows = rows_payload.get("rows") or []
    priced = 0
    for row in rows:
        detail = get_operator_workflow_detail(_clean(row.get("tender_id")))
        if bool(detail.get("submission_package", {}).get("submission_ready")):
            priced += 1
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": _clean(rows_payload.get("data_source") or ("runtime" if rows else "fallback")),
        "submission_ready_count": priced,
        "total": len(rows),
    }


def get_source_health_details() -> Dict[str, Any]:
    try:
        live = get_live_rfqs()
    except Exception:
        live = {}
    items = _safe_list(live.get("items")) if isinstance(live, dict) else []
    summary = {
        "live_rfqs_count": len(items),
        "sources": len({str(item.get("source_name") or item.get("source") or "unknown") for item in items}) if items else 0,
        "healthy": bool(items) or bool(_fixture_paths()),
    }
    return {
        "status": "ok",
        "generated_at": _now_iso(),
        "data_source": "runtime" if items else "fallback",
        "summary": summary,
    }


def get_live_rfqs() -> Dict[str, Any]:
    return _get_live_rfqs()
