from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services import supplier_catalog_service
from app.services.supplier_compliance_readiness_service import SupplierComplianceReadinessService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "supplier-intelligence"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "supplier_risk_scoring_history.json"


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


def _tender_blob(tender: Dict[str, Any]) -> str:
    parts = [
        tender.get("title"),
        tender.get("description"),
        tender.get("raw_text"),
        tender.get("category"),
        tender.get("province"),
        tender.get("delivery_location"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


class SupplierRiskScoringService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.compliance_service = SupplierComplianceReadinessService(runtime_dir=self.runtime_dir)

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

    def _latest_tender(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=1).get("items", [])
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                return first
        return {
            "rfq_id": "supplier-intelligence:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "province": "Gauteng",
            "delivery_location": "Gauteng",
        }

    def _supplier_records(self) -> List[Dict[str, Any]]:
        suppliers = supplier_catalog_service._load_suppliers()  # type: ignore[attr-defined]
        return suppliers if isinstance(suppliers, list) else []

    def _delivery_risk(self, supplier: Dict[str, Any], tender: Dict[str, Any]) -> float:
        products = supplier.get("products") if isinstance(supplier.get("products"), list) else []
        lead_times = [float(product.get("lead_time_days") or 0.0) for product in products if isinstance(product, dict)]
        avg_lead = mean(lead_times) if lead_times else 10.0
        regions = supplier.get("delivery_regions") if isinstance(supplier.get("delivery_regions"), list) else []
        location = _safe_str(tender.get("delivery_location") or tender.get("province") or tender.get("buyer_province"))
        supplier_blob = _safe_str(supplier.get("supplier_name")) + " " + " ".join(str(region) for region in regions)
        tender_blob = _tender_blob(tender)

        risk = 25.0
        if avg_lead <= 2:
            risk += 5.0
        elif avg_lead <= 5:
            risk += 15.0
        elif avg_lead <= 10:
            risk += 25.0
        else:
            risk += 35.0

        if location:
            location_lower = location.lower()
            if "all" in [str(region).lower() for region in regions]:
                risk -= 10.0
            elif any(str(region).lower() in location_lower for region in regions):
                risk -= 6.0
            elif any(token in supplier_blob.lower() for token in location_lower.split()):
                risk -= 3.0
            else:
                risk += 15.0
        else:
            risk += 5.0

        if any(token in tender_blob for token in ["urgent", "critical", "immediate"]):
            risk += 10.0

        return _clamp(risk)

    def _risk_flags(self, supplier: Dict[str, Any], tender: Dict[str, Any], compliance: Dict[str, Any]) -> List[str]:
        flags: List[str] = []
        products = supplier.get("products") if isinstance(supplier.get("products"), list) else []
        regions = supplier.get("delivery_regions") if isinstance(supplier.get("delivery_regions"), list) else []
        tender_blob = _tender_blob(tender)
        if not products:
            flags.append("no_product_catalogue")
        if not regions:
            flags.append("no_delivery_regions")
        if _safe_float(compliance.get("compliance_readiness"), 0.0) < 55:
            flags.append("low_compliance_readiness")
        if _safe_float(self._delivery_risk(supplier, tender), 0.0) >= 60:
            flags.append("high_delivery_risk")
        if any(token in tender_blob for token in ["urgent", "critical", "immediate"]):
            flags.append("urgent_tender")
        if any("all" not in str(region).lower() for region in regions) and not _safe_str(tender.get("delivery_location") or tender.get("province") or tender.get("buyer_province")):
            flags.append("unknown_delivery_location")
        return flags

    def _score_supplier(self, supplier: Dict[str, Any], tender: Dict[str, Any]) -> Dict[str, Any]:
        compliance = self.compliance_service.assess_supplier_compliance(supplier, record_history=False)
        delivery_risk_score = self._delivery_risk(supplier, tender)
        products = supplier.get("products") if isinstance(supplier.get("products"), list) else []
        total_stock = sum(int(product.get("available_stock") or 0) for product in products if isinstance(product, dict))
        pricing_reliability = 100.0 if products and all(product.get("unit_price") is not None for product in products if isinstance(product, dict)) else 55.0
        if len(products) >= 8:
            pricing_reliability += 5.0
        elif len(products) <= 2:
            pricing_reliability -= 10.0
        geographic_suitability = 100.0 if "All" in [str(region) for region in (supplier.get("delivery_regions") or [])] else 80.0 if supplier.get("province") else 60.0
        capacity_suitability = _clamp(20.0 + min(total_stock / 1500.0, 60.0))
        supplier_risk_score = _clamp(
            mean([
                delivery_risk_score,
                100.0 - _safe_float(compliance.get("compliance_readiness"), 0.0),
                100.0 - pricing_reliability,
                100.0 - geographic_suitability,
                100.0 - capacity_suitability,
            ])
        )
        risk_flags = self._risk_flags(supplier, tender, compliance)
        unresolved_blockers = list(compliance.get("unresolved_supplier_blockers") or [])
        if supplier_risk_score >= 70:
            unresolved_blockers.append("supplier_risk_above_threshold")
        if delivery_risk_score >= 70:
            unresolved_blockers.append("delivery_risk_above_threshold")
        analysis = {
            "analysis_id": f"supplier-risk:{_safe_str(supplier.get('supplier_id') or supplier.get('supplier_name'), 'sample')}:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "supplier_id": _safe_str(supplier.get("supplier_id"), "unknown"),
            "supplier_name": _safe_str(supplier.get("supplier_name"), "Unknown supplier"),
            "tender_reference": _safe_str(tender.get("rfq_id") or tender.get("title"), "n/a"),
            "delivery_risk_score": round(delivery_risk_score, 2),
            "supplier_risk_score": round(supplier_risk_score, 2),
            "supplier_risk_flags": risk_flags,
            "recommended_supplier_tier": "A" if supplier_risk_score < 35 else "B" if supplier_risk_score < 55 else "C" if supplier_risk_score < 70 else "D",
            "unresolved_supplier_blockers": unresolved_blockers,
            "risk_factors": {
                "compliance_readiness": round(_safe_float(compliance.get("compliance_readiness"), 0.0), 2),
                "pricing_reliability": round(pricing_reliability, 2),
                "geographic_suitability": round(geographic_suitability, 2),
                "capacity_suitability": round(capacity_suitability, 2),
            },
            "warnings": [
                "Supplier delivery risk is elevated" if delivery_risk_score >= 60 else "",
            ],
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]
        return analysis

    def score_supplier_risk(self, supplier: Dict[str, Any], tender: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tender = tender or self._latest_tender()
        analysis = self._score_supplier(supplier, tender)
        history = self._load_history()
        history.append({
            "analysis_id": analysis["analysis_id"],
            "generated_at": analysis["generated_at"],
            "supplier_id": analysis["supplier_id"],
            "supplier_name": analysis["supplier_name"],
            "tender_reference": analysis["tender_reference"],
            "delivery_risk_score": analysis["delivery_risk_score"],
            "supplier_risk_score": analysis["supplier_risk_score"],
            "recommended_supplier_tier": analysis["recommended_supplier_tier"],
        })
        self._write_history(history)
        return {
            "status": "ok" if analysis["supplier_risk_score"] < 55 else "watch" if analysis["supplier_risk_score"] < 70 else "blocked",
            "supplier_risk_status": "ok" if analysis["supplier_risk_score"] < 55 else "watch" if analysis["supplier_risk_score"] < 70 else "blocked",
            "supplier_risk_score": analysis["supplier_risk_score"],
            "latest_supplier_risk_scoring": analysis,
            "supplier_risk_scoring_history": history,
            "supplier_risk_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_supplier_name": analysis["supplier_name"],
            },
            "warnings": analysis["warnings"],
        }

    def latest_supplier_risk_scoring(self) -> Dict[str, Any]:
        suppliers = self._supplier_records()
        supplier = suppliers[0] if suppliers else {}
        return self.score_supplier_risk(supplier, tender=self._latest_tender())

    def supplier_risk_scoring_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("supplier_risk_score"), 0.0) if history else 0.0
        status = "ok" if score < 55 else "watch" if score < 70 else ("blocked" if history else "not_found")
        return {
            "status": "ok",
            "count": len(history),
            "supplier_risk_status": status,
            "supplier_risk_score": score,
            "latest_supplier_risk_scoring": latest,
            "supplier_risk_scoring_history": history,
            "supplier_risk_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_supplier_name": latest.get("supplier_name", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


supplier_risk_scoring_service = SupplierRiskScoringService()
