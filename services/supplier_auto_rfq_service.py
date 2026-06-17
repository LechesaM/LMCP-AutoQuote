from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_suppliers(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    suppliers = payload.get("supplier_targets") or payload.get("suppliers") or payload.get("preferred_suppliers") or []
    if not isinstance(suppliers, list):
        return []

    output = []
    seen = set()

    for supplier in suppliers:
        if not isinstance(supplier, dict):
            continue

        email = _safe_str(supplier.get("email") or supplier.get("supplier_email"))
        name = _safe_str(supplier.get("name") or supplier.get("supplier_name") or email)

        if not email or "@" not in email:
            continue

        key = email.lower()
        if key in seen:
            continue

        seen.add(key)
        output.append({"supplier_name": name, "supplier_email": email})

    return output


async def run_supplier_auto_rfq(payload: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(payload if isinstance(payload, dict) else {})
    suppliers = _extract_suppliers(result)

    if not suppliers:
        result["supplier_auto_rfq"] = {
            "status": "skipped",
            "reason": "No supplier targets configured",
            "sent": 0,
            "failed": 0,
            "checked_at": _now(),
        }
        return result

    try:
        from app.services.supplier_rfq_request_service import SupplierRFQRequestService

        request_payload = deepcopy(result)
        request_payload["supplier_targets"] = suppliers

        service_result = SupplierRFQRequestService.send_supplier_rfq_requests(request_payload)
        if not isinstance(service_result, dict):
            service_result = {"raw_result": str(service_result)}

        result["supplier_auto_rfq"] = {
            "status": "ok",
            "reason": "Supplier RFQ request workflow completed",
            "supplier_count": len(suppliers),
            "result": service_result,
            "checked_at": _now(),
        }
        return result

    except Exception as exc:
        logger.exception("Supplier auto RFQ failed")
        result["supplier_auto_rfq"] = {
            "status": "failed",
            "reason": str(exc),
            "supplier_count": len(suppliers),
            "checked_at": _now(),
        }
        return result
