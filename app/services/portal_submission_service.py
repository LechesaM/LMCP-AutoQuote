from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


SERVICE_VERSION = "PORTAL_SUBMISSION_SERVICE_DOCUMENT_CAPABILITY_AWARE_V1"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _normalise_status(result: Dict[str, Any]) -> str:
    status = str(result.get("status") or "").strip().lower()

    if status == "documents_only":
        return "documents_only"

    if result.get("submitted") is True:
        return "ok"

    if result.get("uploaded") is True or result.get("documents_uploaded") is True:
        return "portal_uploaded"

    if status in {"ok", "uploaded", "portal_uploaded", "submitted"}:
        return status

    return "assisted_required"


def _is_safe_non_failure(status: str) -> bool:
    return status in {
        "ok",
        "submitted",
        "portal_uploaded",
        "uploaded",
        "documents_only",
    }


def build_portal_submission_result(
    payload: Dict[str, Any],
    final_result: Dict[str, Any],
) -> Dict[str, Any]:
    payload = _safe_dict(payload)
    final_result = _safe_dict(final_result)

    status = _normalise_status(final_result)

    result = {
        "status": status,
        "service_version": SERVICE_VERSION,
        "buyer_rfq_number": (
            payload.get("buyer_rfq_number")
            or payload.get("rfq_reference")
            or final_result.get("buyer_rfq_number")
            or "UNKNOWN-RFQ"
        ),
        "quote_number": payload.get("quote_number") or final_result.get("quote_number"),
        "submitted": bool(final_result.get("submitted")),
        "uploaded": bool(final_result.get("uploaded") or final_result.get("documents_uploaded")),
        "documents_uploaded": bool(final_result.get("documents_uploaded")),
        "attachments_uploaded": bool(final_result.get("attachments_uploaded")),
        "submission_capability": final_result.get("submission_capability")
        or final_result.get("navigation", {}).get("submission_capability_after_respond"),
        "portal_result": final_result,
        "safe_non_failure": _is_safe_non_failure(status),
        "updated_at": _now(),
    }

    if status == "documents_only":
        result.update(
            {
                "submitted": False,
                "uploaded": False,
                "documents_uploaded": False,
                "portal_submission_state": "safe_blocked_documents_only",
                "message": (
                    "Portal reached and tender details verified, but only public tender "
                    "documents were exposed. No upload/submission controls were detected."
                ),
                "operator_action_required": True,
            }
        )

    elif status in {"ok", "submitted"}:
        result.update(
            {
                "portal_submission_state": "submitted_or_completed",
                "message": final_result.get("message") or "Portal submission completed.",
                "operator_action_required": False,
            }
        )

    elif status in {"portal_uploaded", "uploaded"}:
        result.update(
            {
                "portal_submission_state": "uploaded_pending_final_review",
                "message": final_result.get("message") or "Documents uploaded; final submission still requires review.",
                "operator_action_required": True,
            }
        )

    else:
        result.update(
            {
                "portal_submission_state": "assisted_required",
                "message": final_result.get("reason") or final_result.get("message") or "Manual assistance required.",
                "operator_action_required": True,
            }
        )

    return result


def classify_portal_submission_result(final_result: Dict[str, Any]) -> Dict[str, Any]:
    final_result = _safe_dict(final_result)
    status = _normalise_status(final_result)

    return {
        "status": status,
        "safe_non_failure": _is_safe_non_failure(status),
        "documents_only": status == "documents_only",
        "uploaded": status in {"uploaded", "portal_uploaded", "ok", "submitted"},
        "submitted": bool(final_result.get("submitted")),
        "submission_capability": final_result.get("submission_capability")
        or final_result.get("navigation", {}).get("submission_capability_after_respond"),
        "updated_at": _now(),
    }


def portal_submission_status() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "supports": [
            "documents_only",
            "portal_uploaded",
            "assisted_required",
            "submitted",
            "safe_blocked_documents_only",
        ],
        "updated_at": _now(),
    }


def get_portal_submission_status(limit: int = 50) -> Dict[str, Any]:
    return portal_submission_status()


def get_status() -> Dict[str, Any]:
    return portal_submission_status()


def route_portal_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _safe_dict(payload)
    final_result = _safe_dict(payload.get("portal_result") or payload.get("final_result") or payload)
    return build_portal_submission_result(payload, final_result)


async def prepare_portal_submission(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _safe_dict(payload)
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "message": "Portal submission preparation accepted.",
        "payload": payload,
        "updated_at": _now(),
    }


async def mark_portal_submission_proof(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _safe_dict(payload)
    return {
        "status": "ok",
        "service_version": SERVICE_VERSION,
        "message": "Portal submission proof marked.",
        "payload": payload,
        "updated_at": _now(),
    }


async def auto_submit_portal(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _safe_dict(payload)

    # Safety: this service never final-submits directly.
    # It classifies/routes and leaves final submission to V47/V48 policy controls.
    routed = route_portal_submission(payload)

    routed.update({
        "auto_submit_attempted": False,
        "final_submit_blocked": True,
        "message": routed.get("message") or "Auto-submit is blocked by safety policy; routed for controlled review.",
    })

    return routed


def classify_submission_route(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = _safe_dict(payload)
    final_result = _safe_dict(payload.get("portal_result") or payload.get("final_result") or payload)
    return classify_portal_submission_result(final_result)
