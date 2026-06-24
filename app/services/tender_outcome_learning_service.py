from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.executive_decision_workspace_service import ExecutiveDecisionWorkspaceService
from app.services.procurement_intelligence_service import ProcurementIntelligenceService
from app.services.tender_strategy_governance_service import TenderStrategyGovernanceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "historical-learning-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "tender_outcome_learning_history.json"


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
        text = _safe_str(value)
        if text and text not in seen:
            seen.append(text)
    return seen


class TenderOutcomeLearningService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.procurement_service = ProcurementIntelligenceService(runtime_dir=self.runtime_dir)
        self.tender_strategy_service = TenderStrategyGovernanceService(runtime_dir=self.runtime_dir)
        self.executive_service = ExecutiveDecisionWorkspaceService(runtime_dir=self.runtime_dir)

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
            "rfq_id": "historical-learning:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "submission_method": "portal",
            "closing_date": _now_iso(),
        }

    def _latest_tender(self) -> Dict[str, Any]:
        items = self.procurement_service.lifecycle.list_items(limit=20).get("items", [])
        if isinstance(items, list) and items:
            for item in items:
                if isinstance(item, dict):
                    return item
        return self._sample_tender()

    def _build_snapshot(self) -> Dict[str, Any]:
        tender = self._latest_tender()
        procurement = self.procurement_service.analyze_tender(tender, record_history=False)
        strategy = self.tender_strategy_service.analyze_tender_strategy(tender, record_history=False)
        executive = self.executive_service.analyze_executive_decision_workspace(record_history=False)

        procurement_history = self.procurement_service.procurement_intelligence_history(limit=8).get("procurement_intelligence_history", [])
        strategy_history = self.tender_strategy_service.tender_strategy_governance_history(limit=8).get("tender_strategy_governance_history", [])
        executive_history = self.executive_service.executive_decision_workspace_history(limit=8).get("executive_decision_governance_history", [])

        procurement_ready = bool((procurement.get("what_this_unlocks") or []))
        strategy_ready = bool((strategy.get("what_this_unlocks") or []))
        executive_ready = bool((executive.get("what_this_unlocks") or []))
        feedback_ready = strategy_ready and executive_ready
        benchmark_ready = procurement_ready and bool(procurement.get("procurement_intelligence_score") is not None)

        readiness_score = _clamp(
            mean(
                [
                    100.0 if procurement_ready else 55.0,
                    100.0 if strategy_ready else 55.0,
                    100.0 if executive_ready else 55.0,
                    100.0 if feedback_ready else 55.0,
                    100.0 if benchmark_ready else 55.0,
                ]
            )
        )
        blockers = _unique(
            list((procurement.get("unresolved_learning_blockers") or []))
            + list((executive.get("unresolved_executive_blockers") or []))
        )
        ready = readiness_score >= 75.0 and not blockers
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        analysis = {
            "analysis_id": f"tender-outcome-learning:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "rfq_id": _safe_str(tender.get("rfq_id"), "n/a"),
            "title": _safe_str(tender.get("title"), "n/a"),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "tender_outcome_learning_status": status,
            "tender_outcome_learning_score": round(readiness_score, 2),
            "tender_outcome_learning_grade": "ready" if ready else "watch" if status == "watch" else "blocked",
            "tender_outcome_learning_readiness": {"ready": ready, "status": status, "score": round(readiness_score, 2), "blockers": blockers},
            "recommendation_feedback_readiness": {"ready": feedback_ready, "status": "ok" if feedback_ready else "watch", "score": 100.0 if feedback_ready else 55.0, "blockers": [] if feedback_ready else ["recommendation feedback history incomplete"]},
            "historical_benchmark_readiness": {"ready": benchmark_ready, "status": "ok" if benchmark_ready else "watch", "score": 100.0 if benchmark_ready else 55.0, "blockers": [] if benchmark_ready else ["procurement history incomplete"]},
            "procurement_intelligence_history": procurement_history,
            "tender_strategy_outcomes": strategy_history,
            "executive_review_outcomes": executive_history,
            "procurement_intelligence_outcomes": procurement,
            "tender_strategy_latest": strategy,
            "executive_review_latest": executive,
            "unresolved_learning_blockers": blockers,
            "tender_outcome_learning_history": [],
            "tender_outcome_learning_history_summary": {},
            "learning_governance_history": [
                {"event": "tender_outcome_learning_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "recommendation_feedback_verified", "status": "passed" if feedback_ready else "watch", "timestamp": _now_iso()},
            ],
            "autonomous_learning_execution_enabled": False,
            "autonomous_procurement_decision_updates_enabled": False,
            "autonomous_supplier_blacklisting_enabled": False,
            "autonomous_strategy_modification_enabled": False,
            "production_learning_mode_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_learning_review_required": True,
            "executive_feedback_required": True,
            "governance_rules": {
                "advisory_only": True,
                "dry_run_enforced": True,
                "human_supervision_required": True,
                "supervised_learning_review_required": True,
                "executive_feedback_required": True,
                "autonomous_learning_execution_enabled": False,
                "autonomous_procurement_decision_updates_enabled": False,
                "autonomous_supplier_blacklisting_enabled": False,
                "autonomous_strategy_modification_enabled": False,
                "production_learning_mode_enabled": False,
            },
            "what_this_unlocks": [
                "historical procurement outcome learning",
                "recommendation feedback readiness",
                "historical benchmark readiness",
                "executive review outcome tracking",
            ],
            "warnings": [
                "Historical learning is advisory only" if not ready else "",
                "Executive feedback remains supervised" if not feedback_ready else "",
            ],
        }
        analysis["warnings"] = [warning for warning in analysis["warnings"] if warning]
        return analysis

    def analyze_tender_outcome_learning(self, tender: Dict[str, Any], record_history: bool = False) -> Dict[str, Any]:
        analysis = self._build_snapshot()
        if tender:
            analysis["rfq_id"] = _safe_str(tender.get("rfq_id"), analysis["rfq_id"])
            analysis["title"] = _safe_str(tender.get("title"), analysis["title"])
        if record_history:
            history = self._load_history()
            history.append(
                {
                    "analysis_id": analysis["analysis_id"],
                    "generated_at": analysis["generated_at"],
                    "rfq_id": analysis["rfq_id"],
                    "title": analysis["title"],
                    "tender_outcome_learning_status": analysis["tender_outcome_learning_status"],
                    "tender_outcome_learning_score": analysis["tender_outcome_learning_score"],
                    "recommendation_feedback_readiness": analysis["recommendation_feedback_readiness"],
                    "historical_benchmark_readiness": analysis["historical_benchmark_readiness"],
                }
            )
            self._write_history(history)
        return analysis

    def latest_tender_outcome_learning(self) -> Dict[str, Any]:
        analysis = self.analyze_tender_outcome_learning(self._latest_tender(), record_history=True)
        history = self._load_history()
        payload = dict(analysis)
        payload["count"] = len(history)
        payload["latest_tender_outcome_learning"] = dict(analysis)
        payload["tender_outcome_learning_history"] = history
        payload["tender_outcome_learning_history_summary"] = {
            "analysis_count": len(history),
            "latest_rfq_id": analysis["rfq_id"],
            "latest_score": analysis["tender_outcome_learning_score"],
        }
        return payload

    def list_tender_outcome_learning(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.latest_tender_outcome_learning()
        history = self._load_history()[-max(1, int(limit)) :]
        latest["count"] = len(history)
        latest["tender_outcome_learning_history"] = history
        latest["tender_outcome_learning_history_summary"] = {
            "analysis_count": len(history),
            "latest_rfq_id": latest["rfq_id"],
            "latest_score": latest["tender_outcome_learning_score"],
        }
        return latest

    def tender_outcome_learning_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("tender_outcome_learning_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "tender_outcome_learning_history": history,
            "warnings": latest.get("warnings", []) if history else [],
        }
