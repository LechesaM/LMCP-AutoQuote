from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services import supplier_catalog_service
from app.services.supplier_compliance_readiness_service import SupplierComplianceReadinessService
from app.services.supplier_fit_scoring_service import SupplierFitScoringService
from app.services.supplier_risk_scoring_service import SupplierRiskScoringService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "supplier-intelligence"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "supplier_intelligence_history.json"


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


class SupplierIntelligenceService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.compliance_service = SupplierComplianceReadinessService(runtime_dir=self.runtime_dir)
        self.fit_service = SupplierFitScoringService(runtime_dir=self.runtime_dir)
        self.risk_service = SupplierRiskScoringService(runtime_dir=self.runtime_dir)

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
            "closing_date": _now_iso(),
        }

    def _supplier_records(self) -> List[Dict[str, Any]]:
        suppliers = supplier_catalog_service._load_suppliers()  # type: ignore[attr-defined]
        return suppliers if isinstance(suppliers, list) else []

    def _recommended_tier(self, fit_score: float, compliance_score: float, risk_score: float) -> str:
        if fit_score >= 85 and compliance_score >= 85 and risk_score < 35:
            return "A"
        if fit_score >= 70 and compliance_score >= 70 and risk_score < 55:
            return "B"
        if fit_score >= 55:
            return "C"
        return "D"

    def _supplier_blob(self, supplier: Dict[str, Any]) -> str:
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

    def _score_supplier(self, supplier: Dict[str, Any], tender: Dict[str, Any]) -> Dict[str, Any]:
        fit = self.fit_service._score_supplier(supplier, tender)
        risk = self.risk_service._score_supplier(supplier, tender)
        compliance = self.compliance_service.assess_supplier_compliance(supplier, record_history=False)
        supplier_blob = self._supplier_blob(supplier)
        tender_blob = " ".join(str(tender.get(field) or "") for field in ("title", "description", "category", "province", "delivery_location")).lower()
        geo = _safe_float(fit.get("geographic_suitability"), 0.0)
        capacity = _safe_float(fit.get("capacity_suitability"), 0.0)
        pricing = _safe_float(fit.get("pricing_reliability"), 0.0)
        historical = _safe_float(fit.get("historical_suitability"), 0.0)
        compliance_score = _safe_float(compliance.get("compliance_readiness"), 0.0)
        risk_score = _safe_float(risk.get("supplier_risk_score"), 0.0)
        delivery_risk_score = _safe_float(risk.get("latest_supplier_risk_scoring", {}).get("delivery_risk_score"), 0.0)
        fit_score = _clamp(mean([_safe_float(fit.get("supplier_fit_score"), 0.0), compliance_score, 100.0 - risk_score]))
        if fit_score >= 85:
            status = "ok"
            grade = "ready"
        elif fit_score >= 60:
            status = "watch"
            grade = "watch"
        else:
            status = "blocked"
            grade = "blocked"

        unresolved_blockers: List[str] = []
        unresolved_blockers.extend(list(compliance.get("unresolved_supplier_blockers") or []))
        unresolved_blockers.extend(list(risk.get("latest_supplier_risk_scoring", {}).get("unresolved_supplier_blockers") or []))
        if geo < 60:
            unresolved_blockers.append("geographic_mismatch")
        if capacity < 50:
            unresolved_blockers.append("capacity_constraints")
        if pricing < 50:
            unresolved_blockers.append("pricing_unreliable")

        risk_flags = list(risk.get("latest_supplier_risk_scoring", {}).get("supplier_risk_flags") or [])
        if not risk_flags and fit_score < 70:
            risk_flags.append("supplier_fit_below_preferred_threshold")

        analysis_id = f"supplier-intelligence:{_safe_str(supplier.get('supplier_id') or supplier.get('supplier_name'), 'sample')}:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}"
        analysis = {
            "analysis_id": analysis_id,
            "generated_at": _now_iso(),
            "supplier_id": _safe_str(supplier.get("supplier_id"), "unknown"),
            "supplier_name": _safe_str(supplier.get("supplier_name"), "Unknown supplier"),
            "tender_reference": _safe_str(tender.get("rfq_id") or tender.get("title"), "n/a"),
            "supplier_intelligence_status": status,
            "supplier_intelligence_score": round(fit_score, 2),
            "supplier_intelligence_grade": grade,
            "supplier_fit_score": round(_safe_float(fit.get("supplier_fit_score"), 0.0), 2),
            "delivery_risk_score": round(delivery_risk_score, 2),
            "compliance_readiness": round(compliance_score, 2),
            "pricing_reliability": round(pricing, 2),
            "geographic_suitability": round(geo, 2),
            "capacity_suitability": round(capacity, 2),
            "supplier_document_readiness": round(_safe_float(fit.get("supplier_document_readiness"), 0.0), 2),
            "supplier_risk_flags": risk_flags,
            "recommended_supplier_tier": self._recommended_tier(fit_score, compliance_score, risk_score),
            "unresolved_supplier_blockers": unresolved_blockers,
            "supplier_fit_scoring": fit,
            "supplier_risk_scoring": risk,
            "supplier_compliance_readiness": compliance,
            "historical_suitability": round(_safe_float(fit.get("historical_suitability"), 0.0), 2),
            "supplier_match_reason": {
                "tender_blob": tender_blob[:240],
                "supplier_blob": supplier_blob[:240],
                "top_tier": self._recommended_tier(fit_score, compliance_score, risk_score),
            },
            "what_this_unlocks": [
                "supplier fit scoring",
                "delivery risk visibility",
                "compliance readiness monitoring",
                "pricing reliability analysis",
                "geographic suitability assessment",
                "capacity suitability assessment",
                "supplier document readiness",
                "supplier selection support",
            ],
            "warnings": [
                "Supplier intelligence is blocked by unresolved supplier blockers" if unresolved_blockers else "",
                "Supplier risk profile is elevated" if risk_score >= 70 else "",
            ],
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]
        return analysis

    def _best_supplier(self, tender: Dict[str, Any]) -> Dict[str, Any]:
        suppliers = self._supplier_records()
        if not suppliers:
            return self._score_supplier(
                {
                    "supplier_id": "sample",
                    "supplier_name": "Sample Supplier",
                    "province": "Gauteng",
                    "city": "Johannesburg",
                    "contact_person": "Sales Desk",
                    "email": "sales@example.com",
                    "phone": "+27-11-000-0000",
                    "delivery_regions": ["All"],
                    "products": [],
                },
                tender,
            )
        scored = [self._score_supplier(supplier, tender) for supplier in suppliers]
        scored.sort(key=lambda row: (row["supplier_intelligence_score"], -row["delivery_risk_score"]), reverse=True)
        return scored[0]

    def _category_heatmap(self, analyses: List[Dict[str, Any]]) -> Dict[str, Any]:
        rows: Dict[str, Dict[str, Any]] = {}
        for analysis in analyses:
            tier = _safe_str(analysis.get("recommended_supplier_tier"), "D")
            row = rows.setdefault(tier, {"count": 0, "total_score": 0.0, "total_risk": 0.0})
            row["count"] += 1
            row["total_score"] += _safe_float(analysis.get("supplier_intelligence_score"), 0.0)
            row["total_risk"] += _safe_float(analysis.get("delivery_risk_score"), 0.0)
        categories = []
        for tier, row in rows.items():
            count = row["count"]
            categories.append({
                "supplier_tier": tier,
                "supplier_count": count,
                "average_supplier_score": round(row["total_score"] / count, 2) if count else 0.0,
                "average_delivery_risk": round(row["total_risk"] / count, 2) if count else 0.0,
                "temperature": "hot" if tier == "A" else "warm" if tier == "B" else "cool" if tier == "C" else "cold",
            })
        categories.sort(key=lambda item: item["supplier_tier"])
        return {
            "summary": {
                "generated_at": _now_iso(),
                "total_tiers": len(categories),
                "total_suppliers": len(analyses),
                "dominant_tier": categories[0]["supplier_tier"] if categories else "n/a",
            },
            "categories": categories,
        }

    def _record_history(self, analysis: Dict[str, Any]) -> None:
        history = self._load_history()
        history.append({
            "analysis_id": analysis["analysis_id"],
            "generated_at": analysis["generated_at"],
            "supplier_id": analysis["supplier_id"],
            "supplier_name": analysis["supplier_name"],
            "tender_reference": analysis["tender_reference"],
            "supplier_intelligence_score": analysis["supplier_intelligence_score"],
            "supplier_intelligence_grade": analysis["supplier_intelligence_grade"],
            "recommended_supplier_tier": analysis["recommended_supplier_tier"],
            "supplier_fit_score": analysis["supplier_fit_score"],
            "delivery_risk_score": analysis["delivery_risk_score"],
        })
        self._write_history(history)

    def _response(self, analysis: Dict[str, Any], history: List[Dict[str, Any]], supplier_rankings: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "status": analysis["supplier_intelligence_status"],
            "supplier_intelligence_status": analysis["supplier_intelligence_status"],
            "supplier_intelligence_score": analysis["supplier_intelligence_score"],
            "supplier_intelligence_grade": analysis["supplier_intelligence_grade"],
            "latest_supplier_intelligence": analysis,
            "supplier_intelligence_history": history,
            "supplier_intelligence_history_summary": {
                "analysis_count": len(history),
                "latest_supplier_name": analysis["supplier_name"],
                "latest_tier": analysis["recommended_supplier_tier"],
            },
            "supplier_fit_score": analysis["supplier_fit_score"],
            "delivery_risk_score": analysis["delivery_risk_score"],
            "compliance_readiness": analysis["compliance_readiness"],
            "pricing_reliability": analysis["pricing_reliability"],
            "geographic_suitability": analysis["geographic_suitability"],
            "capacity_suitability": analysis["capacity_suitability"],
            "supplier_document_readiness": analysis["supplier_document_readiness"],
            "supplier_risk_flags": analysis["supplier_risk_flags"],
            "recommended_supplier_tier": analysis["recommended_supplier_tier"],
            "unresolved_supplier_blockers": analysis["unresolved_supplier_blockers"],
            "supplier_rankings": supplier_rankings,
            "supplier_category_heatmap": self._category_heatmap(supplier_rankings),
            "what_this_unlocks": analysis["what_this_unlocks"],
            "warnings": analysis["warnings"],
        }

    def analyze_supplier_intelligence(self, supplier: Dict[str, Any], tender: Optional[Dict[str, Any]] = None, record_history: bool = False) -> Dict[str, Any]:
        tender = tender or self._latest_tender()
        analysis = self._score_supplier(supplier, tender)
        if record_history:
            self._record_history(analysis)
        return analysis

    def list_supplier_intelligence(self, limit: int = 20) -> Dict[str, Any]:
        tender = self._latest_tender()
        suppliers = self._supplier_records()
        rankings = [self._score_supplier(supplier, tender) for supplier in suppliers]
        rankings.sort(key=lambda row: (row["supplier_intelligence_score"], -row["delivery_risk_score"]), reverse=True)
        best = rankings[0] if rankings else self._score_supplier({
            "supplier_id": "sample",
            "supplier_name": "Sample Supplier",
            "province": "Gauteng",
            "city": "Johannesburg",
            "contact_person": "Sales Desk",
            "email": "sales@example.com",
            "phone": "+27-11-000-0000",
            "delivery_regions": ["All"],
            "products": [],
        }, tender)
        best["generated_at"] = _now_iso()
        best["tender_reference"] = _safe_str(tender.get("rfq_id") or tender.get("title"), "n/a")
        best["supplier_intelligence_status"] = "ok" if best["supplier_intelligence_score"] >= 70 else "watch" if best["supplier_intelligence_score"] >= 55 else "blocked"
        self._record_history(best)
        history = self._load_history()
        history_slice = history[-max(1, int(limit)) :]
        return self._response(best, history_slice, rankings[: max(1, int(limit))])

    def latest_supplier_intelligence(self) -> Dict[str, Any]:
        return self.list_supplier_intelligence(limit=20)

    def supplier_intelligence_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("supplier_intelligence_score"), 0.0) if history else 0.0
        status = "ok" if score >= 70 else "watch" if score >= 55 else ("blocked" if history else "not_found")
        return {
            "status": "ok",
            "count": len(history),
            "supplier_intelligence_status": status,
            "supplier_intelligence_score": score,
            "latest_supplier_intelligence": latest,
            "supplier_intelligence_history": history,
            "supplier_intelligence_history_summary": {
                "analysis_count": len(history),
                "latest_supplier_name": latest.get("supplier_name", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


supplier_intelligence_service = SupplierIntelligenceService()
