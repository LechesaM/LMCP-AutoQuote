from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.rfq_lifecycle_service import RfqLifecycleService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "pricing-governance"
POLICY_FILE = DEFAULT_RUNTIME_DIR / "margin_scenario_policy.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "margin_scenario_history.json"


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


def _load_policy() -> Dict[str, Any]:
    try:
        if POLICY_FILE.exists():
            payload = json.loads(POLICY_FILE.read_text())
            return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}
    return {}


class MarginScenarioService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.lifecycle = RfqLifecycleService()
        self.policy = _load_policy()

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
            "rfq_id": "margin-scenario:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "unit_price": 120.0,
            "quantity": 20,
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

    def _scenarios(self, item: Dict[str, Any], benchmark: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        benchmark = benchmark or {}
        benchmark_rate = _safe_float(benchmark.get("market_rate"), 100.0)
        base_unit_price = _safe_float(item.get("unit_price") or item.get("quoted_unit_price") or item.get("price"), benchmark_rate)
        quantity = max(1.0, _safe_float(item.get("quantity"), 1.0))
        vat_rate = _safe_float(item.get("vat_rate"), 0.15)
        markup_rate = _safe_float(item.get("markup_rate"), 0.25)
        scenarios = []
        policy_scenarios = self.policy.get("scenarios", []) if isinstance(self.policy.get("scenarios"), list) else []
        if not policy_scenarios:
            policy_scenarios = [
                {"name": "conservative", "markup_adjustment": -0.05},
                {"name": "base", "markup_adjustment": 0.0},
                {"name": "aggressive", "markup_adjustment": 0.08},
            ]
        for scenario in policy_scenarios:
            adj = _safe_float(scenario.get("markup_adjustment"), 0.0)
            scenario_markup = max(0.0, markup_rate + adj)
            unit_price = round(base_unit_price * (1.0 + scenario_markup), 2)
            total_price = round(unit_price * quantity, 2)
            gross_margin_pct = round(((unit_price - benchmark_rate) / unit_price) * 100.0, 2) if unit_price else 0.0
            estimated_profit = round((unit_price - benchmark_rate) * quantity, 2)
            scenarios.append(
                {
                    "scenario": _safe_str(scenario.get("name"), "base"),
                    "unit_price": unit_price,
                    "total_price": total_price,
                    "gross_margin_pct": gross_margin_pct,
                    "estimated_profit": estimated_profit,
                    "vat_amount": round(total_price * vat_rate, 2),
                    "markup_rate": round(scenario_markup, 4),
                    "human_approval_required": True,
                }
            )
        return {
            "scenarios": scenarios,
            "benchmark_rate": round(benchmark_rate, 2),
            "base_unit_price": round(base_unit_price, 2),
            "quantity": quantity,
            "vat_rate": vat_rate,
            "markup_rate": markup_rate,
        }

    def build_margin_scenarios(self, item: Dict[str, Any], benchmark: Optional[Dict[str, Any]] = None, record_history: bool = False) -> Dict[str, Any]:
        scenario_set = self._scenarios(item, benchmark=benchmark)
        scenarios = scenario_set["scenarios"]
        ready = bool(scenarios) and scenario_set["benchmark_rate"] > 0 and scenario_set["base_unit_price"] > 0
        risk_flags = []
        if scenario_set["base_unit_price"] < scenario_set["benchmark_rate"] * 0.9:
            risk_flags.append("underpricing_risk")
        if scenario_set["base_unit_price"] > scenario_set["benchmark_rate"] * 1.2:
            risk_flags.append("overpricing_competitiveness_risk")
        if not item.get("unit_price") and not item.get("quoted_unit_price") and not item.get("price"):
            risk_flags.append("missing_price_reference")

        blockers: List[str] = []
        if not ready:
            blockers.append("margin_scenario_not_ready")
        if risk_flags:
            blockers.append("pricing_review_required")

        readiness_score = _clamp(mean([
            100.0 if ready else 50.0,
            100.0 if scenario_set["benchmark_rate"] > 0 else 40.0,
            100.0 if scenario_set["base_unit_price"] > 0 else 40.0,
            100.0 if scenarios else 0.0,
        ]))
        analysis = {
            "analysis_id": f"margin-scenario:{_safe_str(item.get('rfq_id') or item.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "margin_scenarios": scenarios,
            "margin_scenario_readiness": {
                "ready": ready and readiness_score >= 70.0,
                "score": round(readiness_score, 2),
            },
            "margin_scenario_status": "ready" if ready and readiness_score >= 80.0 else "watch" if ready else "blocked",
            "pricing_benchmark_rate": scenario_set["benchmark_rate"],
            "base_unit_price": scenario_set["base_unit_price"],
            "pricing_confidence_indicators": {
                "vat_visible": scenario_set["vat_rate"] >= 0.0,
                "markup_visible": scenario_set["markup_rate"] >= 0.0,
                "human_approval_required": True,
            },
            "abnormal_price_variance_indicators": {
                "underpricing_risk": "underpricing_risk" in risk_flags,
                "overpricing_competitiveness_risk": "overpricing_competitiveness_risk" in risk_flags,
            },
            "underpricing_risk_indicators": {
                "underpricing_risk": "underpricing_risk" in risk_flags,
                "variance_from_benchmark": round(scenario_set["base_unit_price"] - scenario_set["benchmark_rate"], 2),
            },
            "overpricing_competitiveness_indicators": {
                "overpricing_competitiveness_risk": "overpricing_competitiveness_risk" in risk_flags,
                "competitively_priced": scenario_set["base_unit_price"] <= scenario_set["benchmark_rate"] * 1.05,
            },
            "escalation_required_pricing_items": risk_flags,
            "mandatory_human_price_approval": True,
            "unresolved_pricing_blockers": blockers,
            "governance_rules": {
                "advisory_only": True,
                "human_price_approval_required": True,
                "automatic_submission_disabled": True,
                "dry_run_enforced": True,
                "supervision_mandatory": True,
            },
            "warnings": [
                "Margin scenario review is required" if blockers else "",
            ],
        }
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "margin_scenario_status": analysis["margin_scenario_status"],
                    "margin_scenario_readiness": analysis["margin_scenario_readiness"]["score"],
                    "pricing_benchmark_rate": analysis["pricing_benchmark_rate"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_margin_scenarios(self, benchmark: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        item = self._latest_item()
        analysis = self.build_margin_scenarios(item, benchmark=benchmark, record_history=True)
        history = self._load_history()
        return {
            "status": "ok" if analysis["margin_scenario_readiness"]["ready"] else "watch",
            "margin_scenario_status": analysis["margin_scenario_status"],
            "margin_scenario_readiness_score": analysis["margin_scenario_readiness"]["score"],
            "latest_margin_scenarios": analysis,
            "margin_scenario_history": history,
            "margin_scenario_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": _safe_str(item.get("rfq_id") or item.get("title"), "n/a"),
            },
            "warnings": analysis["warnings"],
        }

    def margin_scenario_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        score = _safe_float(latest.get("margin_scenario_readiness"), 0.0) if history else 0.0
        return {
            "status": "ok",
            "count": len(history),
            "margin_scenario_status": "ready" if score >= 80 else "watch" if history else "not_found",
            "margin_scenario_readiness_score": score,
            "latest_margin_scenarios": latest,
            "margin_scenario_history": history,
            "margin_scenario_history_summary": {
                "analysis_count": len(history),
                "latest_rfq_id": latest.get("analysis_id", "n/a") if history else "n/a",
            },
            "warnings": [],
        }


margin_scenario_service = MarginScenarioService()
