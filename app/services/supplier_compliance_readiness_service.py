from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "supplier-intelligence"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "supplier_compliance_readiness_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class SupplierComplianceReadinessService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    def _load_history(self) -> List[Dict[str, Any]]:
        path = _history_file(self.runtime_dir)
        if not path.exists():
            return []
        try:
            payload = json.loads(path.read_text())
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

    def _write_history(self, history: List[Dict[str, Any]]) -> None:
        path = _history_file(self.runtime_dir)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(history[-250:], indent=2, default=str))

    def assess_supplier_compliance(self, supplier: Dict[str, Any], record_history: bool = False) -> Dict[str, Any]:
        contact_person = _safe_str(supplier.get("contact_person"))
        email = _safe_str(supplier.get("email"))
        phone = _safe_str(supplier.get("phone"))
        regions = supplier.get("delivery_regions") if isinstance(supplier.get("delivery_regions"), list) else []
        products = supplier.get("products") if isinstance(supplier.get("products"), list) else []

        contact_score = 0.0
        if contact_person:
            contact_score += 25.0
        if "@" in email:
            contact_score += 25.0
        if phone:
            contact_score += 20.0
        if regions:
            contact_score += 15.0
        if products:
            contact_score += 15.0

        document_score = 0.0
        supplier_document_blocks: List[str] = []
        if contact_person and email and phone:
            document_score += 35.0
        else:
            supplier_document_blocks.append("missing_contact_documentation")
        if regions:
            document_score += 25.0
        else:
            supplier_document_blocks.append("missing_delivery_regions")
        if products:
            document_score += 25.0
        else:
            supplier_document_blocks.append("missing_product_catalogue")

        product_details = 0
        for product in products:
            if not isinstance(product, dict):
                continue
            if _safe_str(product.get("product_name")) and _safe_str(product.get("category")):
                product_details += 1
        if product_details:
            document_score += min(15.0, product_details * 3.0)
        else:
            supplier_document_blocks.append("incomplete_product_metadata")

        readiness = _clamp((contact_score * 0.6) + (document_score * 0.4))
        status = "ok" if readiness >= 80 else "watch" if readiness >= 55 else "blocked"
        blockers = supplier_document_blocks if readiness < 80 else []
        analysis = {
            "analysis_id": f"supplier-compliance:{_safe_str(supplier.get('supplier_id') or supplier.get('supplier_name'), 'sample')}",
            "generated_at": _now_iso(),
            "supplier_id": _safe_str(supplier.get("supplier_id"), "unknown"),
            "supplier_name": _safe_str(supplier.get("supplier_name"), "Unknown supplier"),
            "compliance_readiness": round(readiness, 2),
            "supplier_document_readiness": round(document_score, 2),
            "supplier_document_blocks": supplier_document_blocks,
            "supplier_compliance_status": status,
            "supplier_compliance_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
            "compliance_signals": {
                "contact_person_present": bool(contact_person),
                "email_present": bool(email),
                "phone_present": bool(phone),
                "delivery_regions_present": bool(regions),
                "product_catalogue_present": bool(products),
            },
            "unresolved_supplier_blockers": blockers,
            "warnings": [
                "Supplier compliance records are incomplete" if blockers else "",
            ],
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]

        if record_history:
            history = self._load_history()
            history.append({
                "analysis_id": analysis["analysis_id"],
                "generated_at": analysis["generated_at"],
                "supplier_id": analysis["supplier_id"],
                "supplier_name": analysis["supplier_name"],
                "compliance_readiness": analysis["compliance_readiness"],
                "supplier_document_readiness": analysis["supplier_document_readiness"],
                "supplier_compliance_status": analysis["supplier_compliance_status"],
            })
            self._write_history(history)

        return analysis

    def latest_supplier_compliance_readiness(self, supplier: Dict[str, Any]) -> Dict[str, Any]:
        analysis = self.assess_supplier_compliance(supplier, record_history=True)
        history = self._load_history()
        return {
            "status": "ok" if analysis["supplier_compliance_status"] in {"ok", "watch"} else "blocked",
            "supplier_compliance_status": analysis["supplier_compliance_status"],
            "supplier_compliance_score": analysis["compliance_readiness"],
            "latest_supplier_compliance_readiness": analysis,
            "supplier_compliance_readiness_history": history,
            "supplier_compliance_readiness_history_summary": {
                "analysis_count": len(history),
                "latest_supplier_name": analysis["supplier_name"],
            },
            "warnings": analysis["warnings"],
        }

    def supplier_compliance_readiness_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("supplier_document_readiness"), 0.0) if history else 0.0
        status = "ok" if score >= 80 else "watch" if score >= 55 else ("blocked" if history else "not_found")
        return {
            "status": "ok",
            "count": len(history),
            "supplier_compliance_status": status,
            "supplier_compliance_score": score,
            "latest_supplier_compliance_readiness": latest,
            "supplier_compliance_readiness_history": history,
            "supplier_compliance_readiness_history_summary": {
                "analysis_count": len(history),
                "latest_supplier_name": latest.get("supplier_name", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


supplier_compliance_readiness_service = SupplierComplianceReadinessService()

