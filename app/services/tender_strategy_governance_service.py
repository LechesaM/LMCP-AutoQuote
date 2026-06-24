from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.bid_no_bid_scoring_service import BidNoBidScoringService
from app.services.pricing_intelligence_governance_service import PricingIntelligenceGovernanceService
from app.services.procurement_intelligence_service import ProcurementIntelligenceService
from app.services.rfq_lifecycle_service import RfqLifecycleService
from app.services.supplier_intelligence_service import SupplierIntelligenceService
from app.services.tender_win_probability_service import TenderWinProbabilityService
from app.services.tender_strategy_risk_service import TenderStrategyRiskService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "tender-strategy-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "tender_strategy_governance_history.json"


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


class TenderStrategyGovernanceService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.bid_no_bid_scoring_service = BidNoBidScoringService(runtime_dir=self.runtime_dir)
        self.tender_win_probability_service = TenderWinProbabilityService(runtime_dir=self.runtime_dir)
        self.tender_strategy_risk_service = TenderStrategyRiskService(runtime_dir=self.runtime_dir)
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
        return self._sample_tender()

    def _analyze(self, tender: Dict[str, Any]) -> Dict[str, Any]:
        bid_no_bid = self.bid_no_bid_scoring_service.score_bid_no_bid(tender, record_history=False)
        win_probability = self.tender_win_probability_service.estimate_win_probability(tender, bid_no_bid=bid_no_bid, record_history=False)
        risk = self.tender_strategy_risk_service.assess_strategy_risk(tender, bid_no_bid=bid_no_bid, win_probability=win_probability, record_history=False)
        procurement = self.procurement_intelligence_service.analyze_tender(tender, record_history=False)
        supplier = self.supplier_intelligence_service.latest_supplier_intelligence()
        pricing = self.pricing_intelligence_service.latest_pricing_intelligence()

        bid_ready = bool((bid_no_bid.get("bid_no_bid_readiness") or {}).get("ready"))
        attractiveness = _safe_float(bid_no_bid.get("tender_attractiveness_score"), 0.0)
        strategic_fit = _safe_float(bid_no_bid.get("strategic_fit_score"), 0.0)
        win_probability_estimate = _safe_float(win_probability.get("win_probability_estimate"), 0.0)
        pricing_alignment = _safe_float(bid_no_bid.get("pricing_competitiveness_alignment"), 0.0)
        supplier_alignment = _safe_float(bid_no_bid.get("supplier_readiness_alignment"), 0.0)
        compliance_alignment = _safe_float(bid_no_bid.get("compliance_readiness_alignment"), 0.0)
        risk_adjusted_opportunity = _safe_float(bid_no_bid.get("risk_adjusted_opportunity_score"), 0.0)
        mandatory_document_ready = bool((bid_no_bid.get("mandatory_document_readiness") or {}).get("ready"))
        urgency = bid_no_bid.get("submission_urgency_indicators") or {}

        unresolved_blockers = _unique(
            list(bid_no_bid.get("unresolved_strategy_blockers") or [])
            + list(win_probability.get("unresolved_strategy_blockers") or [])
            + list(risk.get("unresolved_strategy_blockers") or [])
        )
        if not pricing.get("pricing_benchmark_readiness", {}).get("ready"):
            unresolved_blockers.append("pricing_benchmark_incomplete")
        if not supplier.get("supplier_intelligence_score"):
            unresolved_blockers.append("supplier_readiness_unknown")

        executive_review_required = bool(
            risk.get("executive_review_required")
            or risk_adjusted_opportunity < 55.0
            or win_probability_estimate < 50.0
            or _safe_float((pricing.get("pricing_confidence") or {}).get("pricing_confidence_score"), 0.0) < 70.0
        )
        recommendation_degradation_indicators = {
            "low_win_probability": win_probability_estimate < 50.0,
            "risk_pressure": _safe_float(risk.get("risk_score"), 0.0) >= 60.0,
            "pricing_gap": pricing_alignment < 70.0,
            "supplier_gap": supplier_alignment < 60.0,
        }
        if bid_ready and not executive_review_required:
            recommendation = "bid"
        elif bid_ready:
            recommendation = "bid_with_review"
        elif risk_adjusted_opportunity >= 50.0:
            recommendation = "review"
        else:
            recommendation = "no_bid"

        governance_score = _clamp(mean([
            attractiveness,
            strategic_fit,
            win_probability_estimate,
            pricing_alignment,
            supplier_alignment,
            compliance_alignment,
            risk_adjusted_opportunity,
            100.0 if mandatory_document_ready else 55.0,
        ]))
        if governance_score >= 80.0 and not unresolved_blockers:
            status = "ok"
        elif governance_score >= 55.0:
            status = "watch"
        else:
            status = "blocked"

        analysis = {
            "analysis_id": f"tender-strategy-governance:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "rfq_id": _safe_str(tender.get("rfq_id"), "n/a"),
            "title": _safe_str(tender.get("title"), "n/a"),
            "environment": "staging",
            "governance_mode": "read_only",
            "tender_strategy_governance_status": status,
            "tender_strategy_governance_score": round(governance_score, 2),
            "tender_strategy_governance_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
            "bid_no_bid_readiness": bid_no_bid.get("bid_no_bid_readiness"),
            "tender_attractiveness_score": attractiveness,
            "win_probability_estimate": win_probability_estimate,
            "strategic_fit_score": strategic_fit,
            "pricing_competitiveness_alignment": pricing_alignment,
            "supplier_readiness_alignment": supplier_alignment,
            "compliance_readiness_alignment": compliance_alignment,
            "risk_adjusted_opportunity_score": risk_adjusted_opportunity,
            "mandatory_document_readiness": bid_no_bid.get("mandatory_document_readiness"),
            "submission_urgency_indicators": urgency,
            "executive_review_required": executive_review_required,
            "recommendation_degradation_indicators": recommendation_degradation_indicators,
            "unresolved_strategy_blockers": unresolved_blockers,
            "bid_decision_recommendation": recommendation,
            "bid_no_bid_human_approval_required": True,
            "autonomous_bid_submission_enabled": False,
            "auto_bid_no_bid_approval_enabled": False,
            "production_submission_authority_enabled": False,
            "procurement_commitment_generation_enabled": False,
            "live_tender_portal_credentials_present": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "governance_rules": {
                "advisory_only": True,
                "bid_no_bid_human_approval_required": True,
                "executive_review_required": True,
                "dry_run_enforced": True,
                "supervision_mandatory": True,
                "autonomous_bid_submission_enabled": False,
                "auto_bid_no_bid_approval_enabled": False,
                "production_submission_authority_enabled": False,
                "procurement_commitment_generation_enabled": False,
                "live_tender_portal_credentials_present": False,
            },
            "what_this_unlocks": [
                "bid/no-bid readiness",
                "tender attractiveness scoring",
                "win probability estimation",
                "strategic fit assessment",
                "pricing competitiveness alignment",
                "supplier readiness alignment",
                "compliance readiness alignment",
                "risk-adjusted opportunity scoring",
            ],
            "classification": bid_no_bid.get("classification") or {},
            "procurement_intelligence": procurement,
            "supplier_intelligence": supplier,
            "pricing_intelligence": pricing,
            "bid_no_bid_scoring": bid_no_bid,
            "tender_win_probability": win_probability,
            "tender_strategy_risk": risk,
            "warnings": [
                "Tender strategy is advisory only" if status != "ok" else "",
                "Executive review is mandatory for this tender" if executive_review_required else "",
            ],
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]
        return analysis

    def analyze_tender_strategy(self, tender: Dict[str, Any], record_history: bool = False) -> Dict[str, Any]:
        analysis = self._analyze(tender)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "rfq_id": analysis["rfq_id"],
                    "title": analysis["title"],
                    "tender_strategy_governance_status": analysis["tender_strategy_governance_status"],
                    "tender_strategy_governance_score": analysis["tender_strategy_governance_score"],
                    "win_probability_estimate": analysis["win_probability_estimate"],
                    "bid_decision_recommendation": analysis["bid_decision_recommendation"],
                }
            )
            self._write_history(history)
        return analysis

    def _response(self, analysis: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "status": "ok" if analysis["tender_strategy_governance_status"] in {"ok", "watch"} else "blocked",
            "tender_strategy_governance_status": analysis["tender_strategy_governance_status"],
            "tender_strategy_governance_score": analysis["tender_strategy_governance_score"],
            "tender_strategy_governance_grade": analysis["tender_strategy_governance_grade"],
            "environment": analysis["environment"],
            "governance_mode": analysis["governance_mode"],
            "latest_tender_strategy_governance": analysis,
            "tender_strategy_governance_history": history,
            "tender_strategy_governance_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": analysis["rfq_id"],
                "latest_recommendation": analysis["bid_decision_recommendation"],
            },
            "bid_no_bid_readiness": analysis["bid_no_bid_readiness"],
            "tender_attractiveness_score": analysis["tender_attractiveness_score"],
            "win_probability_estimate": analysis["win_probability_estimate"],
            "strategic_fit_score": analysis["strategic_fit_score"],
            "pricing_competitiveness_alignment": analysis["pricing_competitiveness_alignment"],
            "supplier_readiness_alignment": analysis["supplier_readiness_alignment"],
            "compliance_readiness_alignment": analysis["compliance_readiness_alignment"],
            "risk_adjusted_opportunity_score": analysis["risk_adjusted_opportunity_score"],
            "mandatory_document_readiness": analysis["mandatory_document_readiness"],
            "submission_urgency_indicators": analysis["submission_urgency_indicators"],
            "executive_review_required": analysis["executive_review_required"],
            "recommendation_degradation_indicators": analysis["recommendation_degradation_indicators"],
            "unresolved_strategy_blockers": analysis["unresolved_strategy_blockers"],
            "autonomous_bid_submission_enabled": analysis["governance_rules"]["autonomous_bid_submission_enabled"],
            "auto_bid_no_bid_approval_enabled": analysis["governance_rules"]["auto_bid_no_bid_approval_enabled"],
            "production_submission_authority_enabled": analysis["governance_rules"]["production_submission_authority_enabled"],
            "procurement_commitment_generation_enabled": analysis["governance_rules"]["procurement_commitment_generation_enabled"],
            "live_tender_portal_credentials_present": analysis["governance_rules"]["live_tender_portal_credentials_present"],
            "dry_run_enforced": analysis["governance_rules"]["dry_run_enforced"],
            "human_supervision_required": analysis["governance_rules"]["supervision_mandatory"],
            "bid_no_bid_human_approval_required": analysis["governance_rules"]["bid_no_bid_human_approval_required"],
            "executive_review_required_flag": analysis["executive_review_required"],
            "governance_rules": analysis["governance_rules"],
            "what_this_unlocks": analysis["what_this_unlocks"],
            "warnings": analysis["warnings"],
        }

    def list_tender_strategy_governance(self, limit: int = 20) -> Dict[str, Any]:
        return self.latest_tender_strategy_governance()

    def latest_tender_strategy_governance(self) -> Dict[str, Any]:
        analysis = self.analyze_tender_strategy(self._latest_tender(), record_history=True)
        history = self._load_history()
        return self._response(analysis, history)

    def tender_strategy_governance_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("tender_strategy_governance_score"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "tender_strategy_governance_status": "ok" if score >= 80 else "watch" if score >= 55 else ("blocked" if history else "not_found"),
            "tender_strategy_governance_score": score,
            "latest_tender_strategy_governance": latest,
            "tender_strategy_governance_history": history,
            "tender_strategy_governance_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": latest.get("rfq_id", "n/a") if history else "n/a",
            },
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "bid_no_bid_human_approval_required": True,
            "executive_review_required": True,
            "warnings": [],
        }


tender_strategy_governance_service = TenderStrategyGovernanceService()
