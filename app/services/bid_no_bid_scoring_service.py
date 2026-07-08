from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.pricing_intelligence_governance_service import PricingIntelligenceGovernanceService
from app.services.procurement_intelligence_service import ProcurementIntelligenceService
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.supplier_intelligence_service import SupplierIntelligenceService
from app.services.tender_classification_service import TenderClassificationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "tender-strategy-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "bid_no_bid_scoring_history.json"


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
    result: List[str] = []
    for value in values:
        cleaned = _safe_str(value)
        if cleaned and cleaned not in result:
            result.append(cleaned)
    return result


class BidNoBidScoringService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.classification_service = TenderClassificationService(runtime_dir=self.runtime_dir)
        self.procurement_intelligence_service = ProcurementIntelligenceService(runtime_dir=self.runtime_dir)
        self.supplier_intelligence_service = SupplierIntelligenceService(runtime_dir=self.runtime_dir)
        self.pricing_intelligence_service = PricingIntelligenceGovernanceService(runtime_dir=self.runtime_dir)

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
            "rfq_id": "tender-strategy:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "submission_method": "portal",
            "closing_date": _now_iso(),
            "unit_price": 118.0,
            "quantity": 20,
            "unit": "Each",
            "vat_rate": 0.15,
            "markup_rate": 0.25,
        }

    def _latest_tender(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return self._sample_tender()

    def _score(self, tender: Dict[str, Any]) -> Dict[str, Any]:
        classification = self.classification_service.analyze_tender(tender, record_history=False)
        procurement = self.procurement_intelligence_service.analyze_tender(tender, record_history=False)
        supplier = self.supplier_intelligence_service.latest_supplier_intelligence()
        pricing = self.pricing_intelligence_service.latest_pricing_intelligence()

        tender_complexity = _safe_float((classification.get("tender_complexity") or {}).get("score"), 0.0)
        opportunity_score = _safe_float(procurement.get("opportunity_score"), 0.0)
        supplier_fit_score = _safe_float(procurement.get("supplier_fit_scoring", {}).get("supplier_fit_score"), 0.0)
        supplier_readiness_score = _safe_float(supplier.get("supplier_intelligence_score"), 0.0)
        compliance_readiness_score = _safe_float(supplier.get("compliance_readiness"), 0.0)
        pricing_confidence = _safe_float(pricing.get("pricing_confidence_score"), 0.0)
        pricing_benchmark_ready = bool((pricing.get("pricing_benchmark_readiness") or {}).get("ready"))

        strategic_fit_score = _clamp(mean([
            100.0 if classification.get("supply_tender") else 65.0,
            100.0 if classification.get("procurement_category") in {"supplies", "construction", "information_technology", "professional_services"} else 70.0,
            100.0 - min(tender_complexity, 80.0),
            opportunity_score,
            supplier_fit_score,
        ]))
        pricing_competitiveness_alignment = _clamp(mean([
            pricing_confidence,
            100.0 if pricing_benchmark_ready else 50.0,
            100.0 - min(abs(_safe_float((pricing.get("market_benchmarking") or {}).get("price_variance_pct"), 0.0)), 50.0),
        ]))
        supplier_readiness_alignment = _clamp(mean([supplier_fit_score, supplier_readiness_score]))
        compliance_readiness_alignment = _clamp(mean([compliance_readiness_score, 100.0 if not supplier.get("unresolved_supplier_blockers") else 55.0]))
        risk_adjusted_opportunity_score = _clamp(mean([
            opportunity_score,
            strategic_fit_score,
            pricing_competitiveness_alignment,
            supplier_readiness_alignment,
            compliance_readiness_alignment,
        ]) - min(tender_complexity * 0.25, 20.0))
        tender_attractiveness_score = _clamp(mean([
            opportunity_score,
            strategic_fit_score,
            pricing_competitiveness_alignment,
        ]))
        if risk_adjusted_opportunity_score >= 70.0 and tender_complexity < 65.0:
            recommendation = "bid"
        elif risk_adjusted_opportunity_score >= 50.0:
            recommendation = "review"
        else:
            recommendation = "no_bid"

        win_probability_estimate = _clamp(mean([
            strategic_fit_score,
            pricing_competitiveness_alignment,
            supplier_readiness_alignment,
            compliance_readiness_alignment,
            risk_adjusted_opportunity_score,
        ]))
        bid_no_bid_readiness = bid_ready = bool(
            tender_attractiveness_score >= 60.0
            and win_probability_estimate >= 55.0
            and strategic_fit_score >= 55.0
            and risk_adjusted_opportunity_score >= 40.0
        )
        unresolved_blockers = _unique(
            list(classification.get("warnings") or [])
            + list(procurement.get("warnings") or [])
            + list(supplier.get("warnings") or [])
            + list(pricing.get("warnings") or [])
        )
        if not pricing_benchmark_ready:
            unresolved_blockers.append("pricing_benchmark_not_ready")
        if not supplier_readiness_alignment:
            unresolved_blockers.append("supplier_readiness_alignment_incomplete")
        if risk_adjusted_opportunity_score < 50.0:
            unresolved_blockers.append("risk_adjusted_opportunity_below_threshold")

        executive_review_required = bool(
            tender_complexity >= 60.0
            or _safe_float(procurement.get("risk_scoring", {}).get("risk_score"), 0.0) >= 55.0
            or _safe_float(pricing.get("pricing_confidence_score"), 0.0) < 70.0
            or unresolved_blockers
        )
        if bid_ready and executive_review_required:
            decision = "bid_with_review"
        elif bid_ready:
            decision = "bid"
        elif recommendation == "review":
            decision = "review"
        else:
            decision = "no_bid"

        analysis = {
            "analysis_id": f"bid-no-bid:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "rfq_id": _safe_str(tender.get("rfq_id"), "n/a"),
            "title": _safe_str(tender.get("title"), "n/a"),
            "bid_no_bid_readiness": {
                "ready": bid_no_bid_readiness,
                "score": round(tender_attractiveness_score, 2),
            },
            "tender_attractiveness_score": round(tender_attractiveness_score, 2),
            "win_probability_estimate": round(win_probability_estimate, 2),
            "strategic_fit_score": round(strategic_fit_score, 2),
            "pricing_competitiveness_alignment": round(pricing_competitiveness_alignment, 2),
            "supplier_readiness_alignment": round(supplier_readiness_alignment, 2),
            "compliance_readiness_alignment": round(compliance_readiness_alignment, 2),
            "risk_adjusted_opportunity_score": round(risk_adjusted_opportunity_score, 2),
            "mandatory_document_readiness": {
                "ready": bool(classification.get("mandatory_documents")),
                "document_count": len(classification.get("mandatory_documents") or []),
            },
            "submission_urgency_indicators": classification.get("submission_urgency") or {},
            "executive_review_required": executive_review_required,
            "recommendation_degradation_indicators": {
                "low_win_probability": win_probability_estimate < 45.0,
                "high_complexity": tender_complexity >= 60.0,
                "pricing_confidence_gap": _safe_float(pricing.get("pricing_confidence_score"), 0.0) < 70.0,
            },
            "unresolved_strategy_blockers": unresolved_blockers,
            "bid_decision_recommendation": decision,
            "strategy_rules": {
                "advisory_only": True,
                "human_approval_required": True,
                "executive_review_required": True,
                "dry_run_enforced": True,
                "supervision_mandatory": True,
                "autonomous_bid_submission_enabled": False,
                "auto_bid_no_bid_approval_enabled": False,
                "production_submission_authority_enabled": False,
                "procurement_commitment_generation_enabled": False,
                "live_tender_portal_credentials_present": False,
            },
            "warnings": [
                "Tender strategy is advisory only" if not bid_ready else "",
                "Executive review remains mandatory for this tender" if executive_review_required else "",
            ],
            "classification": classification,
            "procurement_intelligence": procurement,
            "supplier_intelligence": supplier,
            "pricing_intelligence": pricing,
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]
        return analysis

    def score_bid_no_bid(self, tender: Dict[str, Any], record_history: bool = False) -> Dict[str, Any]:
        analysis = self._score(tender)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "rfq_id": analysis["rfq_id"],
                    "title": analysis["title"],
                    "bid_no_bid_readiness": analysis["bid_no_bid_readiness"]["score"],
                    "win_probability_estimate": analysis["win_probability_estimate"],
                    "strategic_fit_score": analysis["strategic_fit_score"],
                    "recommendation": analysis["bid_decision_recommendation"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_bid_no_bid_scoring(self) -> Dict[str, Any]:
        analysis = self.score_bid_no_bid(self._latest_tender(), record_history=True)
        history = self._load_history()
        return {
            "status": "ok" if analysis["bid_no_bid_readiness"]["ready"] else "watch",
            "bid_no_bid_status": "ready" if analysis["bid_no_bid_readiness"]["ready"] else "watch",
            "bid_no_bid_score": analysis["bid_no_bid_readiness"]["score"],
            "latest_bid_no_bid_scoring": analysis,
            "bid_no_bid_scoring_history": history,
            "bid_no_bid_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": analysis["rfq_id"],
            },
            "warnings": analysis["warnings"],
        }

    def bid_no_bid_scoring_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("bid_no_bid_readiness"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "bid_no_bid_status": "ready" if score >= 70 else "watch" if history else "not_found",
            "bid_no_bid_score": score,
            "latest_bid_no_bid_scoring": latest,
            "bid_no_bid_scoring_history": history,
            "bid_no_bid_scoring_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": latest.get("rfq_id", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


bid_no_bid_scoring_service = BidNoBidScoringService()
