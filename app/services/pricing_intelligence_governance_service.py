from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.market_benchmarking_service import MarketBenchmarkingService
from app.services.margin_scenario_service import MarginScenarioService
from app.services.pricing_confidence_service import PricingConfidenceService
from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "pricing-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "pricing_intelligence_history.json"


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


class PricingIntelligenceGovernanceService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.market_benchmarking_service = MarketBenchmarkingService(runtime_dir=self.runtime_dir)
        self.pricing_confidence_service = PricingConfidenceService(runtime_dir=self.runtime_dir)
        self.margin_scenario_service = MarginScenarioService(runtime_dir=self.runtime_dir)

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

    def _sample_item(self) -> Dict[str, Any]:
        return {
            "rfq_id": "pricing-intelligence:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "unit_price": 120.0,
            "quantity": 20,
            "unit": "Each",
            "vat_rate": 0.15,
            "markup_rate": 0.25,
        }

    def _latest_item(self) -> Dict[str, Any]:
        items = self.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return self._sample_item()

    def _analyze(self, item: Dict[str, Any]) -> Dict[str, Any]:
        benchmark = self.market_benchmarking_service.benchmark_market_rates(item, record_history=False)
        margin = self.margin_scenario_service.build_margin_scenarios(item, benchmark=benchmark, record_history=False)
        confidence = self.pricing_confidence_service.assess_pricing_confidence(item, benchmark=benchmark, margin=margin, record_history=False)

        benchmark_ready = bool(benchmark.get("pricing_benchmark_readiness", {}).get("ready"))
        market_ready = bool(benchmark.get("market_rate_comparison_readiness", {}).get("ready"))
        historical_ready = bool(benchmark.get("historical_pricing_reference_readiness", {}).get("ready"))
        supplier_ready = bool(benchmark.get("supplier_quote_comparison_readiness", {}).get("ready"))
        margin_ready = bool(margin.get("margin_scenario_readiness", {}).get("ready"))
        confidence_score = _safe_float(confidence.get("pricing_confidence_score"), 0.0)

        underpricing = bool(benchmark.get("underpricing_risk_indicators", {}).get("underpricing_risk_flag")) or bool(margin.get("underpricing_risk_indicators", {}).get("underpricing_risk"))
        overpricing = bool(benchmark.get("overpricing_competitiveness_indicators", {}).get("overpriced")) or bool(margin.get("overpricing_competitiveness_indicators", {}).get("overpricing_competitiveness_risk"))
        abnormal_variance = bool(benchmark.get("abnormal_price_variance_indicators", {}).get("variance_pct_abnormal"))

        blockers = _unique(
            list(benchmark.get("unresolved_pricing_blockers") or [])
            + list(confidence.get("unresolved_pricing_blockers") or [])
            + list(margin.get("unresolved_pricing_blockers") or [])
        )
        escalation_items = _unique(
            [str(item.get("title") or item.get("description") or item.get("rfq_id") or "n/a")]
            if abnormal_variance or underpricing or overpricing or blockers
            else []
        )

        readiness_score = _clamp(mean([
            100.0 if benchmark_ready else 55.0,
            100.0 if market_ready else 55.0,
            100.0 if historical_ready else 55.0,
            100.0 if supplier_ready else 55.0,
            100.0 if margin_ready else 55.0,
            confidence_score,
        ]))
        if readiness_score >= 80.0 and not blockers:
            status = "ok"
        elif readiness_score >= 55.0:
            status = "watch"
        else:
            status = "blocked"

        analysis = {
            "analysis_id": f"pricing-intelligence:{_safe_str(item.get('rfq_id') or item.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "rfq_id": _safe_str(item.get("rfq_id"), "n/a"),
            "title": _safe_str(item.get("title"), "n/a"),
            "pricing_intelligence_status": status,
            "pricing_intelligence_score": round(readiness_score, 2),
            "pricing_intelligence_grade": "ready" if status == "ok" else "watch" if status == "watch" else "blocked",
            "pricing_benchmark_readiness": benchmark.get("pricing_benchmark_readiness"),
            "market_rate_comparison_readiness": benchmark.get("market_rate_comparison_readiness"),
            "historical_pricing_reference_readiness": benchmark.get("historical_pricing_reference_readiness"),
            "supplier_quote_comparison_readiness": benchmark.get("supplier_quote_comparison_readiness"),
            "margin_scenario_readiness": margin.get("margin_scenario_readiness"),
            "pricing_confidence_score": confidence_score,
            "pricing_confidence": confidence,
            "market_benchmarking": benchmark,
            "margin_scenarios": margin,
            "abnormal_price_variance_indicators": benchmark.get("abnormal_price_variance_indicators"),
            "underpricing_risk_indicators": benchmark.get("underpricing_risk_indicators"),
            "overpricing_competitiveness_indicators": benchmark.get("overpricing_competitiveness_indicators"),
            "vat_visibility": benchmark.get("vat_visibility"),
            "markup_visibility": benchmark.get("markup_visibility"),
            "escalation_required_pricing_items": escalation_items or list(margin.get("escalation_required_pricing_items") or []),
            "mandatory_human_price_approval": True,
            "autonomous_pricing_submission_enabled": False,
            "live_procurement_commitment_enabled": False,
            "live_supplier_ordering_enabled": False,
            "production_tender_submission_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "governance_mode": "read_only",
            "environment": "staging",
            "governance_rules": {
                "advisory_only": True,
                "human_price_approval_required": True,
                "automatic_submission_disabled": True,
                "dry_run_enforced": True,
                "supervision_mandatory": True,
                "live_procurement_commitment_enabled": False,
                "live_supplier_ordering_enabled": False,
                "production_tender_submission_enabled": False,
            },
            "unresolved_pricing_blockers": blockers,
            "pricing_intelligence_history": [],
            "pricing_intelligence_history_summary": {},
            "what_this_unlocks": [
                "pricing benchmark readiness",
                "market rate comparison readiness",
                "historical pricing reference readiness",
                "supplier quote comparison readiness",
                "margin scenario readiness",
                "human price approval workflows",
                "pricing governance decision support",
            ],
            "warnings": [
                "Pricing intelligence is advisory only" if status != "ok" else "",
                "Mandatory human price approval remains in force" if blockers or confidence_score < 70.0 else "",
            ],
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]
        return analysis

    def analyze_pricing_intelligence(self, item: Dict[str, Any], record_history: bool = False) -> Dict[str, Any]:
        analysis = self._analyze(item)
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "rfq_id": analysis["rfq_id"],
                    "title": analysis["title"],
                    "pricing_intelligence_status": analysis["pricing_intelligence_status"],
                    "pricing_intelligence_score": analysis["pricing_intelligence_score"],
                    "pricing_confidence_score": analysis["pricing_confidence_score"],
                    "mandatory_human_price_approval": analysis["mandatory_human_price_approval"],
                }
            )
            self._write_history(history)
        return analysis

    def _response(self, analysis: Dict[str, Any], history: List[Dict[str, Any]]) -> Dict[str, Any]:
        readiness_count = sum(
            1 for key in (
                "pricing_benchmark_readiness",
                "market_rate_comparison_readiness",
                "historical_pricing_reference_readiness",
                "supplier_quote_comparison_readiness",
                "margin_scenario_readiness",
            )
            if bool((analysis.get(key) or {}).get("ready"))
        )
        return {
            "status": "ok" if analysis["pricing_intelligence_status"] in {"ok", "watch"} else "blocked",
            "pricing_intelligence_status": analysis["pricing_intelligence_status"],
            "pricing_intelligence_score": analysis["pricing_intelligence_score"],
            "pricing_intelligence_grade": analysis["pricing_intelligence_grade"],
            "latest_pricing_intelligence": analysis,
            "pricing_intelligence_history": history,
            "pricing_intelligence_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": analysis["rfq_id"],
                "readiness_count": readiness_count,
            },
            "pricing_benchmark_readiness": analysis["pricing_benchmark_readiness"],
            "market_rate_comparison_readiness": analysis["market_rate_comparison_readiness"],
            "historical_pricing_reference_readiness": analysis["historical_pricing_reference_readiness"],
            "supplier_quote_comparison_readiness": analysis["supplier_quote_comparison_readiness"],
            "margin_scenario_readiness": analysis["margin_scenario_readiness"],
            "pricing_confidence_score": analysis["pricing_confidence_score"],
            "abnormal_price_variance_indicators": analysis["abnormal_price_variance_indicators"],
            "underpricing_risk_indicators": analysis["underpricing_risk_indicators"],
            "overpricing_competitiveness_indicators": analysis["overpricing_competitiveness_indicators"],
            "vat_visibility": analysis["vat_visibility"],
            "markup_visibility": analysis["markup_visibility"],
            "escalation_required_pricing_items": analysis["escalation_required_pricing_items"],
            "mandatory_human_price_approval": analysis["mandatory_human_price_approval"],
            "autonomous_pricing_submission_enabled": analysis["autonomous_pricing_submission_enabled"],
            "live_procurement_commitment_enabled": analysis["live_procurement_commitment_enabled"],
            "live_supplier_ordering_enabled": analysis["live_supplier_ordering_enabled"],
            "production_tender_submission_enabled": analysis["production_tender_submission_enabled"],
            "dry_run_enforced": analysis["dry_run_enforced"],
            "human_supervision_required": analysis["human_supervision_required"],
            "governance_mode": analysis["governance_mode"],
            "environment": analysis["environment"],
            "unresolved_pricing_blockers": analysis["unresolved_pricing_blockers"],
            "governance_rules": analysis["governance_rules"],
            "what_this_unlocks": analysis["what_this_unlocks"],
            "warnings": analysis["warnings"],
        }

    def latest_pricing_intelligence(self) -> Dict[str, Any]:
        analysis = self.analyze_pricing_intelligence(self._latest_item(), record_history=True)
        history = self._load_history()
        return self._response(analysis, history)

    def list_pricing_intelligence(self, limit: int = 20) -> Dict[str, Any]:
        return self.latest_pricing_intelligence()

    def pricing_intelligence_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("pricing_intelligence_score"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "pricing_intelligence_status": "ok" if score >= 80 else "watch" if score >= 55 else ("blocked" if history else "not_found"),
            "pricing_intelligence_score": score,
            "latest_pricing_intelligence": latest,
            "pricing_intelligence_history": history,
            "pricing_intelligence_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": latest.get("rfq_id", "n/a") if history else "n/a",
            },
            "environment": "staging",
            "governance_mode": "read_only",
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "warnings": [],
        }


pricing_intelligence_governance_service = PricingIntelligenceGovernanceService()
