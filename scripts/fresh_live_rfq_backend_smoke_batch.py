from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.api.operator_workflow_contracts import get_operator_workflow_detail, get_operator_workflow_http_detail
from app.services.submission_execution_service import build_submission_execution_state
from app.services.submission_package_service import build_submission_package


DEFAULT_RFQ_REFERENCES = [
    "REAL-PILOT-001",
    "HTTPPROBE-20260523190924",
    "PAPER",
]


def _parse_refs(value: str | None) -> List[str]:
    raw = (value or "").strip()
    if not raw:
        return list(DEFAULT_RFQ_REFERENCES)
    refs = [item.strip() for item in raw.split(",")]
    return [ref for ref in refs if ref]


def _exists(path_value: Any) -> bool:
    path = str(path_value or "").strip()
    return bool(path) and Path(path).exists()


def _require(name: str, condition: bool, blockers: List[str], details: str = "") -> None:
    if not condition:
        blockers.append(f"{name}{': ' + details if details else ''}")


def _smoke_one(rfq_reference: str) -> Dict[str, Any]:
    http_detail = get_operator_workflow_http_detail(rfq_reference)
    detail = get_operator_workflow_detail(rfq_reference)
    package = detail.get("submission_package") if isinstance(detail.get("submission_package"), dict) else None
    if not isinstance(package, dict) or not package:
        package = build_submission_package(detail)
    execution = detail.get("submission_execution") if isinstance(detail.get("submission_execution"), dict) else None
    if not isinstance(execution, dict) or not execution:
        execution = build_submission_execution_state(detail)
    review_bundle = package.get("review_ready_bundle") if isinstance(package.get("review_ready_bundle"), dict) else {}

    review_ready = bool(review_bundle.get("review_ready") or review_bundle.get("reviewReady") or package.get("review_ready") or package.get("reviewReady"))
    approval_ready = bool(package.get("approval_ready") or package.get("approvalReady"))
    submission_ready = bool(package.get("submission_ready") or package.get("submissionReady"))
    submission_locked = bool(execution.get("submissionLocked") or execution.get("submission_locked"))
    zip_path = package.get("zip_path") or package.get("zipPath")
    execution_status = str(execution.get("execution_status") or execution.get("executionStatus") or "").lower()
    execution_api_status = str(execution.get("status") or "").lower()

    blockers: List[str] = []
    _require("review_ready", review_ready, blockers)
    _require("approval_ready", approval_ready, blockers)
    _require("submission_ready", submission_ready, blockers)
    _require("submissionLocked", submission_locked, blockers)
    _require("package ZIP available", _exists(zip_path), blockers)
    _require("execution status", execution_api_status == "ok", blockers, f"got {execution_api_status or 'missing'}")

    return {
        "rfq_reference": rfq_reference,
        "http_payload_bytes": len(json.dumps(http_detail, ensure_ascii=False).encode("utf-8")),
        "workflow_status": detail.get("status"),
        "review_ready": review_ready,
        "approval_ready": approval_ready,
        "submission_ready": submission_ready,
        "submissionLocked": submission_locked,
        "package_zip_path": str(zip_path or ""),
        "package_zip_exists": _exists(zip_path),
        "package_status": package.get("package_status") or package.get("packageStatus"),
        "execution_status": execution_api_status,
        "execution_state": execution_status,
        "execution_blockers": execution.get("blockers") or [],
        "blockers": blockers,
    }


def main(argv: Sequence[str] | None = None) -> int:
    _ = argv or []
    rfq_references = _parse_refs(os.environ.get("LMCP_BACKEND_SMOKE_RFQ_NUMBERS"))
    summaries = [_smoke_one(rfq_reference) for rfq_reference in rfq_references]
    print(json.dumps({"stage": "fresh_live_rfq_backend_smoke_batch", "results": summaries}, indent=2, ensure_ascii=False))

    blockers = [f"{summary['rfq_reference']}: {issue}" for summary in summaries for issue in summary.get("blockers", [])]
    if blockers:
        raise AssertionError("; ".join(blockers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
