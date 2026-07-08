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
    return _runtime_dir(runtime_dir) / "supplier_fit_scoring_history.json"


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


def _text_blob(tender: Dict[str, Any]) -> str:
    parts = [
        tender.get("title"),
        tender.get("description"),
        tender.get("raw_text"),
        tender.get("category"),
        tender.get("buyer_name"),
        tender.get("province"),
        tender.get("delivery_location"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def _supplier_blob(supplier: Dict[str, Any]) -> str:
    parts = [
        supplier.get("supplier_name"),
        supplier.get("province"),
        supplier.get("city"),
        supplier.get("delivery_regions"),
    ]
    products = supplier.get("products") if isinstance(supplier.get("products"), list) else []
    for product in products:
        if isinstance(product, dict):
            parts.extend([product.get("product_name"), product.get("category"), product.get("description")])
    return " ".join(str(part or "") for part in parts).lower()


def _token_overlap_score(a: str, b: str) -> float:
    tokens_a = {token for token in a.replace(",", " ").replace("/", " ").split() if token}
    tokens_b = {token for token in b.replace(",", " ").replace("/", " ").split() if token}
    if not tokens_a or not tokens_b:
        return 0.0
    overlap = len(tokens_a.intersection(tokens_b))
    return round((overlap / max(len(tokens_a), 1)) * 100.0, 2)


class SupplierFitScoringService:
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

    def _geo_score(self, supplier: Dict[str, Any], tender: Dict[str, Any]) -> float:
        regions = supplier.get("delivery_regions") if isinstance(supplier.get("delivery_regions"), list) else []
        location = _safe_str(tender.get("delivery_location") or tender.get("province") or tender.get("buyer_province"))
        province = _safe_str(supplier.get("province"))
        city = _safe_str(supplier.get("city"))
        if not location:
            return 60.0
        blob = location.lower()
        if "all" in [str(region).lower() for region in regions]:
            return 100.0
        if any(str(region).lower() in blob for region in regions):
            return 92.0
        if province and province.lower() in blob:
            return 88.0
        if city and city.lower() in blob:
            return 82.0
        return 35.0

    def _capacity_score(self, supplier: Dict[str, Any]) -> float:
        products = supplier.get("products") if isinstance(supplier.get("products"), list) else []
        stocks = [int(product.get("available_stock") or 0) for product in products if isinstance(product, dict)]
        if not stocks:
            return 20.0
        total_stock = sum(stocks)
        average_stock = total_stock / len(stocks)
        score = 20.0
        if total_stock >= 50000:
            score += 40.0
        elif total_stock >= 20000:
            score += 30.0
        elif total_stock >= 5000:
            score += 20.0
        else:
            score += 10.0
        if average_stock >= 5000:
            score += 20.0
        elif average_stock >= 1000:
            score += 12.0
        else:
            score += 5.0
        return _clamp(score)

    def _pricing_reliability_score(self, supplier: Dict[str, Any]) -> float:
        products = supplier.get("products") if isinstance(supplier.get("products"), list) else []
        prices = [float(product.get("unit_price") or 0.0) for product in products if isinstance(product, dict) and product.get("unit_price") is not None]
        if not prices:
            return 20.0
        spread = max(prices) - min(prices)
        completeness = len(prices) / max(len(products), 1)
        reliability = 55.0 + (30.0 * completeness)
        if spread <= 100:
            reliability += 15.0
        elif spread <= 1000:
            reliability += 8.0
        else:
            reliability += 2.0
        if len(prices) >= 5:
            reliability += 5.0
        return _clamp(reliability)

    def _historical_suitability_score(self, supplier: Dict[str, Any]) -> float:
        products = supplier.get("products") if isinstance(supplier.get("products"), list) else []
        regions = supplier.get("delivery_regions") if isinstance(supplier.get("delivery_regions"), list) else []
        product_count = len(products)
        score = 35.0
        if product_count >= 8:
            score += 30.0
        elif product_count >= 5:
            score += 22.0
        elif product_count >= 3:
            score += 15.0
        else:
            score += 6.0
        if regions and "all" in [str(region).lower() for region in regions]:
            score += 15.0
        if supplier.get("contact_person") and supplier.get("email") and supplier.get("phone"):
            score += 10.0
        return _clamp(score)

    def _score_supplier(self, supplier: Dict[str, Any], tender: Dict[str, Any]) -> Dict[str, Any]:
        tender_blob = _text_blob(tender)
        supplier_blob = _supplier_blob(supplier)
        category_match = _token_overlap_score(tender_blob, supplier_blob)
        geo_score = self._geo_score(supplier, tender)
        capacity_score = self._capacity_score(supplier)
        pricing_score = self._pricing_reliability_score(supplier)
        historical_score = self._historical_suitability_score(supplier)
        compliance = self.compliance_service.assess_supplier_compliance(supplier, record_history=False)
        compliance_score = _safe_float(compliance.get("compliance_readiness"), 0.0)

        fit_score = _clamp(
            mean([category_match, geo_score, capacity_score, pricing_score, historical_score, compliance_score])
        )
        if fit_score >= 85:
            tier = "A"
        elif fit_score >= 70:
            tier = "B"
        elif fit_score >= 55:
            tier = "C"
        else:
            tier = "D"

        return {
            "analysis_id": f"supplier-fit:{_safe_str(supplier.get('supplier_id') or supplier.get('supplier_name'), 'sample')}:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "supplier_id": _safe_str(supplier.get("supplier_id"), "unknown"),
            "supplier_name": _safe_str(supplier.get("supplier_name"), "Unknown supplier"),
            "tender_reference": _safe_str(tender.get("rfq_id") or tender.get("title"), "n/a"),
            "supplier_fit_score": round(fit_score, 2),
            "supplier_fit_grade": tier,
            "geographic_suitability": round(geo_score, 2),
            "capacity_suitability": round(capacity_score, 2),
            "pricing_reliability": round(pricing_score, 2),
            "historical_suitability": round(historical_score, 2),
            "supplier_document_readiness": round(compliance.get("supplier_document_readiness"), 2),
            "supplier_compliance_readiness": round(compliance_score, 2),
            "supplier_compliance_status": compliance.get("supplier_compliance_status", "watch"),
            "supplier_risk_flags": [],
            "recommended_supplier_tier": tier,
            "unresolved_supplier_blockers": compliance.get("unresolved_supplier_blockers", []) if fit_score < 70 else [],
            "fit_factors": {
                "category_match": round(category_match, 2),
                "geographic_suitability": round(geo_score, 2),
                "capacity_suitability": round(capacity_score, 2),
                "pricing_reliability": round(pricing_score, 2),
                "historical_suitability": round(historical_score, 2),
                "compliance_readiness": round(compliance_score, 2),
            },
            "warnings": [
                "Supplier fit is below preferred threshold" if fit_score < 70 else "",
            ],
        }

    def score_supplier_fit(self, supplier: Dict[str, Any], tender: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        tender = tender or self._latest_tender()
        analysis = self._score_supplier(supplier, tender)
        history = self._load_history()
        history.append({
            "analysis_id": analysis["analysis_id"],
            "generated_at": analysis["generated_at"],
            "supplier_id": analysis["supplier_id"],
            "supplier_name": analysis["supplier_name"],
            "tender_reference": analysis["tender_reference"],
            "supplier_fit_score": analysis["supplier_fit_score"],
            "supplier_fit_grade": analysis["supplier_fit_grade"],
            "recommended_supplier_tier": analysis["recommended_supplier_tier"],
        })
        self._write_history(history)
        return {
            "status": "ok" if analysis["supplier_fit_score"] >= 70 else "watch" if analysis["supplier_fit_score"] >= 55 else "blocked",
            "supplier_fit_status": "ok" if analysis["supplier_fit_score"] >= 70 else "watch" if analysis["supplier_fit_score"] >= 55 else "blocked",
            "supplier_fit_score": analysis["supplier_fit_score"],
            "latest_supplier_fit_scoring": analysis,
            "supplier_fit_scoring_history": history,
            "supplier_fit_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_supplier_name": analysis["supplier_name"],
            },
            "warnings": analysis["warnings"],
        }

    def latest_supplier_fit_scoring(self) -> Dict[str, Any]:
        tender = self._latest_tender()
        supplier = self._supplier_records()[0] if self._supplier_records() else {}
        return self.score_supplier_fit(supplier, tender=tender)

    def supplier_fit_scoring_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("supplier_fit_score"), 0.0) if history else 0.0
        status = "ok" if score >= 70 else "watch" if score >= 55 else ("blocked" if history else "not_found")
        return {
            "status": "ok",
            "count": len(history),
            "supplier_fit_status": status,
            "supplier_fit_score": score,
            "latest_supplier_fit_scoring": latest,
            "supplier_fit_scoring_history": history,
            "supplier_fit_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_supplier_name": latest.get("supplier_name", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


supplier_fit_scoring_service = SupplierFitScoringService()
