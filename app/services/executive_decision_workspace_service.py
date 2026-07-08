from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.boq_semantic_understanding_service import BoqSemanticUnderstandingService
from app.services.pricing_intelligence_governance_service import PricingIntelligenceGovernanceService
from app.services.procurement_intelligence_service import ProcurementIntelligenceService
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.supplier_intelligence_service import SupplierIntelligenceService
from app.services.tender_strategy_governance_service import TenderStrategyGovernanceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "executive-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "executive_decision_workspace_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _unique(values: List[str]) -> List[str]:
    seen: List[str] = []
    for value in values:
        cleaned = _safe_str(value)
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


class ExecutiveDecisionWorkspaceService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.procurement_intelligence_service = ProcurementIntelligenceService(runtime_dir=self.runtime_dir)
        self.supplier_intelligence_service = SupplierIntelligenceService(runtime_dir=self.runtime_dir)
        self.pricing_intelligence_service = PricingIntelligenceGovernanceService(runtime_dir=self.runtime_dir)
        self.boq_semantic_understanding_service = BoqSemanticUnderstandingService(runtime_dir=self.runtime_dir)
        self.tender_strategy_governance_service = TenderStrategyGovernanceService(runtime_dir=self.runtime_dir)

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

    def _sample_tender(self) -> Dict[str, Any]:
        return {
            "rfq_id": "executive-workspace:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "submission_method": "portal",
            "closing_date": "2026-06-30T00:00:00+00:00",
            "province": "Gauteng",
            "delivery_location": "Gauteng",
            "unit_price": 118.0,
            "quantity": 20,
            "unit": "Each",
            "vat_rate": 0.15,
            "markup_rate": 0.25,
            "boq_rows": [
                {"item_number": 1, "description": "A4 paper", "specification": "Ream of 500 sheets", "unit": "Ream", "quantity": 100},
                {"item_number": 2, "description": "Ballpoint pen", "specification": "Blue ink", "unit": "Each", "quantity": 500},
            ],
        }

    def _sample_supplier(self) -> Dict[str, Any]:
        return {
            "supplier_id": "SUP-EXEC-001",
            "supplier_name": "Executive Office Solutions",
            "province": "Gauteng",
            "city": "Johannesburg",
            "contact_person": "Bid Desk",
            "email": "bids@executiveoffice.co.za",
            "phone": "+27-11-555-0101",
            "delivery_regions": ["Gauteng", "National"],
            "products": [
                {
                    "product_name": "A4 paper",
                    "category": "stationery_office",
                    "description": "Premium office paper",
                    "unit_price": 72.0,
                    "available_stock": 50000,
                    "lead_time_days": 2,
                },
                {
                    "product_name": "Ballpoint pen",
                    "category": "stationery_office",
                    "description": "Blue ink pen pack",
                    "unit_price": 18.0,
                    "available_stock": 20000,
                    "lead_time_days": 2,
                },
            ],
        }

    def _sample_pricing_item(self) -> Dict[str, Any]:
        tender = self._sample_tender()
        return {
            "rfq_id": tender["rfq_id"],
            "title": tender["title"],
            "description": tender["description"],
            "unit_price": tender["unit_price"],
            "quantity": tender["quantity"],
            "unit": tender["unit"],
            "vat_rate": tender["vat_rate"],
            "markup_rate": tender["markup_rate"],
        }

    def _latest_context(self) -> Dict[str, Any]:
        tender = self._sample_tender()
        procurement = self.procurement_intelligence_service.analyze_tender(tender, record_history=False)
        supplier = self.supplier_intelligence_service.analyze_supplier_intelligence(self._sample_supplier(), tender=tender, record_history=False)
        pricing = self.pricing_intelligence_service.analyze_pricing_intelligence(self._sample_pricing_item(), record_history=False)
        boq = self.boq_semantic_understanding_service.analyze_boq_semantics(self._sample_tender(), record_history=False)
        strategy = self.tender_strategy_governance_service.analyze_tender_strategy(tender, record_history=False)

        return {
            "tender": tender,
            "procurement": procurement,
            "supplier": supplier,
            "pricing": pricing,
            "boq": boq,
            "strategy": strategy,
        }

    def _build_analysis(self) -> Dict[str, Any]:
        context = self._latest_context()
        tender = context["tender"]
        procurement = context["procurement"]
        supplier = context["supplier"]
        pricing = context["pricing"]
        boq = context["boq"]
        strategy = context["strategy"]

        procurement_score = _safe_float(procurement.get("procurement_intelligence_score"), 0.0)
        supplier_score = _safe_float(supplier.get("supplier_intelligence_score"), 0.0)
        pricing_score = _safe_float(pricing.get("pricing_intelligence_score"), 0.0)
        boq_score = _safe_float(boq.get("boq_semantic_understanding_score"), 0.0)
        strategy_score = _safe_float(strategy.get("tender_strategy_governance_score"), 0.0)

        executive_workspace_score = _clamp(mean([procurement_score, supplier_score, pricing_score, boq_score, strategy_score]))
        executive_decision_queue_score = _clamp(mean([executive_workspace_score, 100.0 - min(len(procurement.get("warnings") or []), 10) * 5.0, 100.0 - min(len(strategy.get("unresolved_strategy_blockers") or []), 10) * 4.0]))
        strategic_alignment_score = _clamp(mean([procurement_score, strategy_score, supplier_score, pricing_score]))

        financial_exposure_indicators = {
            "underpricing_risk": bool(pricing.get("underpricing_risk_indicators", {}).get("underpricing_risk_flag")),
            "overpricing_risk": bool(pricing.get("overpricing_competitiveness_indicators", {}).get("overpriced")),
            "margin_pressure": _safe_float(pricing.get("pricing_confidence_score"), 0.0) < 70.0,
            "abnormal_variance": bool(pricing.get("abnormal_price_variance_indicators", {}).get("variance_pct_abnormal")),
        }
        pricing_escalation_indicators = {
            "pricing_benchmark_incomplete": not bool((pricing.get("pricing_benchmark_readiness") or {}).get("ready")),
            "margin_scenario_incomplete": not bool((pricing.get("margin_scenario_readiness") or {}).get("ready")),
            "abnormal_variance": financial_exposure_indicators["abnormal_variance"],
            "escalation_required_items": list(pricing.get("escalation_required_pricing_items") or []),
        }
        supplier_escalation_indicators = {
            "delivery_risk": _safe_float(supplier.get("delivery_risk_score"), 0.0) >= 60.0,
            "compliance_gap": _safe_float(supplier.get("compliance_readiness"), 0.0) < 70.0,
            "capacity_constraints": _safe_float(supplier.get("capacity_suitability"), 0.0) < 70.0,
        }
        compliance_escalation_indicators = {
            "boq_semantic_gap": not bool((boq.get("pricing_preparation_readiness") or {}).get("ready")),
            "supplier_compliance_gap": _safe_float(supplier.get("compliance_readiness"), 0.0) < 70.0,
            "mandatory_docs_complete": bool((strategy.get("mandatory_document_readiness") or {}).get("ready")),
        }
        risk_escalation_indicators = {
            "procurement_risk": _safe_float(procurement.get("risk_scoring", {}).get("risk_score"), 0.0) >= 55.0,
            "supplier_risk": _safe_float(supplier.get("delivery_risk_score"), 0.0) >= 60.0,
            "pricing_risk": financial_exposure_indicators["margin_pressure"],
            "strategy_risk": _safe_float(strategy.get("tender_strategy_governance_score"), 0.0) < 70.0,
            "boq_risk": _safe_float(boq.get("measurement_risk_score"), 0.0) >= 40.0,
        }

        blockers = _unique(
            (
                list(procurement.get("warnings") or [])
                if _safe_str(procurement.get("procurement_intelligence_status"), "blocked") == "blocked"
                else []
            )
            + (
                list(supplier.get("unresolved_supplier_blockers") or [])
                if _safe_str(supplier.get("supplier_intelligence_status"), "blocked") == "blocked"
                else []
            )
            + (
                list(pricing.get("unresolved_pricing_blockers") or [])
                if _safe_str(pricing.get("pricing_intelligence_status"), "blocked") == "blocked"
                else []
            )
            + (
                list(boq.get("unresolved_boq_semantic_blockers") or [])
                if _safe_str(boq.get("boq_semantic_understanding_status"), "blocked") == "blocked"
                else []
            )
            + (
                list(strategy.get("unresolved_strategy_blockers") or [])
                if _safe_str(strategy.get("tender_strategy_governance_status"), "blocked") == "blocked"
                else []
            )
        )
        executive_review_ready = executive_workspace_score >= 70.0 and not blockers
        executive_queue_ready = executive_decision_queue_score >= 65.0
        strategic_alignment_ready = strategic_alignment_score >= 70.0 and not blockers

        status = "ok" if executive_review_ready else "watch" if executive_workspace_score >= 55.0 else "blocked"
        warnings = list(procurement.get("warnings") or []) + list(supplier.get("warnings") or []) + list(pricing.get("warnings") or []) + list(boq.get("warnings") or []) + list(strategy.get("warnings") or [])
        if not executive_review_ready:
            warnings.append("Executive review remains mandatory for this workspace")

        analysis = {
            "analysis_id": f"executive-decision-workspace:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "title": _safe_str(tender.get("title"), "n/a"),
            "rfq_id": _safe_str(tender.get("rfq_id"), "n/a"),
            "executive_decision_workspace_status": status,
            "executive_decision_workspace_score": round(executive_workspace_score, 2),
            "executive_decision_workspace_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
            "executive_review_readiness": {
                "ready": executive_review_ready,
                "score": round(executive_workspace_score, 2),
                "status": status,
            },
            "executive_decision_queue_readiness": {
                "ready": executive_queue_ready,
                "score": round(executive_decision_queue_score, 2),
                "status": "ok" if executive_queue_ready else "watch" if executive_decision_queue_score >= 55.0 else "blocked",
            },
            "strategic_alignment_readiness": {
                "ready": strategic_alignment_ready,
                "score": round(strategic_alignment_score, 2),
                "status": "ok" if strategic_alignment_ready else "watch" if strategic_alignment_score >= 55.0 else "blocked",
            },
            "financial_exposure_indicators": financial_exposure_indicators,
            "pricing_escalation_indicators": pricing_escalation_indicators,
            "supplier_escalation_indicators": supplier_escalation_indicators,
            "compliance_escalation_indicators": compliance_escalation_indicators,
            "risk_escalation_indicators": risk_escalation_indicators,
            "submission_urgency_indicators": procurement.get("submission_urgency") or {},
            "unresolved_executive_blockers": blockers,
            "procurement_intelligence": procurement,
            "supplier_intelligence": supplier,
            "pricing_intelligence": pricing,
            "boq_semantic_understanding": boq,
            "tender_strategy_governance": strategy,
            "governance_readiness": {
                "ready": strategic_alignment_ready and not risk_escalation_indicators["pricing_risk"] and not risk_escalation_indicators["supplier_risk"],
                "score": round(mean([executive_workspace_score, strategic_alignment_score]), 2),
            },
            "autonomous_executive_approval_enabled": False,
            "production_submission_authority_enabled": False,
            "procurement_commitment_generation_enabled": False,
            "live_executive_notification_enabled": False,
            "autonomous_tender_authorization_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "executive_human_approval_required": True,
            "escalation_review_required": True,
            "governance_rules": {
                "advisory_only": True,
                "human_supervision_required": True,
                "executive_human_approval_required": True,
                "escalation_review_required": True,
                "dry_run_enforced": True,
                "production_submission_authority_enabled": False,
                "procurement_commitment_generation_enabled": False,
                "live_executive_notification_enabled": False,
                "autonomous_executive_approval_enabled": False,
                "autonomous_tender_authorization_enabled": False,
            },
            "what_this_unlocks": [
                "executive review readiness",
                "executive decision queue readiness",
                "strategic alignment readiness",
                "financial exposure visibility",
                "pricing escalation visibility",
                "supplier escalation visibility",
                "compliance escalation visibility",
                "supervised executive decision support",
            ],
            "warnings": warnings,
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]
        return analysis

    def analyze_executive_decision_workspace(self, record_history: bool = False) -> Dict[str, Any]:
        analysis = self._build_analysis()
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "rfq_id": analysis["rfq_id"],
                    "title": analysis["title"],
                    "executive_decision_workspace_status": analysis["executive_decision_workspace_status"],
                    "executive_decision_workspace_score": analysis["executive_decision_workspace_score"],
                    "executive_review_readiness": analysis["executive_review_readiness"]["score"],
                    "executive_decision_queue_readiness": analysis["executive_decision_queue_readiness"]["score"],
                    "strategic_alignment_readiness": analysis["strategic_alignment_readiness"]["score"],
                }
            )
            self._write_history(history)
        return analysis

    def _response(self, analysis: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "status": analysis["executive_decision_workspace_status"],
            "executive_decision_workspace_status": analysis["executive_decision_workspace_status"],
            "executive_decision_workspace_score": analysis["executive_decision_workspace_score"],
            "executive_decision_workspace_grade": analysis["executive_decision_workspace_grade"],
            "latest_executive_decision_workspace": analysis,
            "executive_decision_governance_history": history,
            "executive_decision_governance_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": analysis["rfq_id"],
                "latest_workspace_score": analysis["executive_decision_workspace_score"],
            },
            "executive_review_readiness": analysis["executive_review_readiness"],
            "executive_decision_queue_readiness": analysis["executive_decision_queue_readiness"],
            "strategic_alignment_readiness": analysis["strategic_alignment_readiness"],
            "financial_exposure_indicators": analysis["financial_exposure_indicators"],
            "pricing_escalation_indicators": analysis["pricing_escalation_indicators"],
            "supplier_escalation_indicators": analysis["supplier_escalation_indicators"],
            "compliance_escalation_indicators": analysis["compliance_escalation_indicators"],
            "risk_escalation_indicators": analysis["risk_escalation_indicators"],
            "submission_urgency_indicators": analysis["submission_urgency_indicators"],
            "unresolved_executive_blockers": analysis["unresolved_executive_blockers"],
            "autonomous_executive_approval_enabled": analysis["autonomous_executive_approval_enabled"],
            "production_submission_authority_enabled": analysis["production_submission_authority_enabled"],
            "procurement_commitment_generation_enabled": analysis["procurement_commitment_generation_enabled"],
            "live_executive_notification_enabled": analysis["live_executive_notification_enabled"],
            "autonomous_tender_authorization_enabled": analysis["autonomous_tender_authorization_enabled"],
            "dry_run_enforced": analysis["dry_run_enforced"],
            "human_supervision_required": analysis["human_supervision_required"],
            "executive_human_approval_required": analysis["executive_human_approval_required"],
            "escalation_review_required": analysis["escalation_review_required"],
            "governance_rules": analysis["governance_rules"],
            "what_this_unlocks": analysis["what_this_unlocks"],
            "warnings": analysis["warnings"],
        }

    def list_executive_decision_workspace(self, limit: int = 20) -> Dict[str, Any]:
        return self.latest_executive_decision_workspace()

    def latest_executive_decision_workspace(self) -> Dict[str, Any]:
        analysis = self.analyze_executive_decision_workspace(record_history=True)
        history = self._load_history()
        return self._response(analysis, history)

    def executive_decision_workspace_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("executive_decision_workspace_score"), 0.0) if history else 0.0
        return {
            "status": "ok" if history else "not_found",
            "count": len(history),
            "executive_decision_workspace_status": "ok" if score >= 70.0 else "watch" if history else "not_found",
            "executive_decision_workspace_score": score,
            "latest_executive_decision_workspace": latest,
            "executive_decision_governance_history": history,
            "executive_decision_governance_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": latest.get("rfq_id", "n/a") if history else "n/a",
            },
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "executive_human_approval_required": True,
            "escalation_review_required": True,
            "warnings": [],
        }


executive_decision_workspace_service = ExecutiveDecisionWorkspaceService()
