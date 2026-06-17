from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.auth.auth_models import AuthContext
from app.api.operator_workflow_contracts import get_operator_workflow_detail
from app.auth.jwt_service import encode_token
from app.services.submission_execution_service import build_submission_execution_state
from app.services.submission_package_service import build_submission_package
from app.services.supplier_quote_ingestion_service import SupplierQuoteIngestionService
from app.auth.session_service import permissions_for_role

SUPERVISOR_EMAIL = os.environ.get("LMCP_SUPERVISOR_EMAIL", "supervisor@lmcp.local")
SUPERVISOR_PASSWORD = os.environ.get("LMCP_SUPERVISOR_PASSWORD", "supervisor")
SEARCH_QUERY = os.environ.get("LMCP_LIVE_RFQ_QUERY", "Stationary Extra")
MAX_MESSAGES = int(os.environ.get("LMCP_LIVE_RFQ_MAX_MESSAGES", "25") or 25)
RFQ_REFERENCE = os.environ.get("LMCP_BACKEND_SMOKE_RFQ_NUMBER", "PAPER")
TRY_LIVE_INGEST = os.environ.get("LMCP_BACKEND_SMOKE_TRY_INGEST", "0").strip() in {"1", "true", "TRUE", "yes", "YES"}


def _exists(path_value: Any) -> bool:
    path = str(path_value or "").strip()
    return bool(path) and Path(path).exists()


def _require(name: str, condition: bool, blockers: List[str], details: str = "") -> None:
    if not condition:
        blockers.append(f"{name}{': ' + details if details else ''}")


def main() -> int:
    session = AuthContext(
        user_id="supervisor",
        email=SUPERVISOR_EMAIL,
        display_name="Supervisor",
        role="supervisor",
        permissions=tuple(permissions_for_role("supervisor")),
        token=encode_token(
            {
                "user_id": "supervisor",
                "email": SUPERVISOR_EMAIL,
                "role": "supervisor",
                "permissions": list(permissions_for_role("supervisor")),
            }
        ),
    )
    auth_source = "local_token"
    access_token = str(session.token or "").strip()
    if not access_token:
        raise RuntimeError("Login/auth failed: no access token generated")

    ingest_result: Dict[str, Any] = {}
    if TRY_LIVE_INGEST:
        service = SupplierQuoteIngestionService()
        ingest_result = service.ingest_once(search_query=SEARCH_QUERY, max_messages=MAX_MESSAGES)

    detail = get_operator_workflow_detail(RFQ_REFERENCE)
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

    summary = {
        "stage": "fresh_live_rfq_backend_smoke_test",
        "auth_source": auth_source,
        "login_email": SUPERVISOR_EMAIL,
        "rfq_reference": RFQ_REFERENCE,
        "targeted_ingest_attempted": TRY_LIVE_INGEST,
        "search_query": SEARCH_QUERY if TRY_LIVE_INGEST else None,
        "ingest_status": ingest_result.get("status") if ingest_result else None,
        "ingest_success": bool(ingest_result.get("success")) if ingest_result else None,
        "ingest_reason": ingest_result.get("reason") if ingest_result else None,
        "workflow_status": detail.get("status"),
        "review_ready": review_ready,
        "approval_ready": approval_ready,
        "submission_ready": submission_ready,
        "submissionLocked": submission_locked,
        "package_zip_path": str(zip_path or ""),
        "package_zip_exists": _exists(zip_path),
        "package_status": package.get("package_status") or package.get("packageStatus"),
        "package_approval_ready": bool(package.get("approval_ready") or package.get("approvalReady")),
        "package_submission_ready": bool(package.get("submission_ready") or package.get("submissionReady")),
        "execution_status": execution_api_status,
        "execution_state": execution_status,
        "execution_blockers": execution.get("blockers") or [],
        "detail": {
            "status": detail.get("status"),
            "tender_id": detail.get("tender_id") or detail.get("tenderId"),
        },
        "package": {
            "status": package.get("status"),
            "package_status": package.get("package_status") or package.get("packageStatus"),
            "approval_ready": package.get("approval_ready") or package.get("approvalReady"),
            "submission_ready": package.get("submission_ready") or package.get("submissionReady"),
        },
        "execution": {
            "status": execution.get("status"),
            "execution_status": execution.get("execution_status") or execution.get("executionStatus"),
            "blockers": execution.get("blockers") or [],
        },
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if blockers:
        raise AssertionError("; ".join(blockers))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
