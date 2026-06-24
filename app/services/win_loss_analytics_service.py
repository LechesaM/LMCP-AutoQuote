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
    return _runtime_dir(runtime_dir) / "win_loss_analytics_history.json"


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


class WinLossAnalyticsService:
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
            "rfq_id": "historical-learning-winloss:sample",
            "title": "Supply and delivery of office stationery",
            "description": "Framework agreement for stationery and consumables.",
            "buyer_name": "Sample Municipality",
            "category": "supplies",
            "submission_method": "portal",
            "closing_date": _now_iso(),
        }

    def _build_snapshot(self) -> Dict[str, Any]:
        tender = self._sample_tender()
        procurement = self.procurement_service.analyze_tender(tender, record_history=False)
        strategy = self.tender_strategy_service.analyze_tender_strategy(tender, record_history=False)
        executive = self.executive_service.analyze_executive_decision_workspace(record_history=False)

        procurement_history = self.procurement_service.procurement_intelligence_history(limit=8).get("procurement_intelligence_history", [])
        strategy_history = self.tender_strategy_service.tender_strategy_governance_history(limit=8).get("tender_strategy_governance_history", [])
        executive_history = self.executive_service.executive_decision_workspace_history(limit=8).get("executive_decision_governance_history", [])

        bid_recommendations = [str(item.get("bid_decision_recommendation") or "") for item in strategy_history if isinstance(item, dict)]
        win_decisions = [rec for rec in bid_recommendations if rec in {"bid", "bid_with_review"}]
        no_bid_decisions = [rec for rec in bid_recommendations if rec == "no_bid"]
        review_decisions = [rec for rec in bid_recommendations if rec == "review"]
        total_decisions = len(bid_recommendations) or 1
        win_rate = round((len(win_decisions) / total_decisions) * 100.0, 2)
        loss_rate = round((len(no_bid_decisions) / total_decisions) * 100.0, 2)
        review_rate = round((len(review_decisions) / total_decisions) * 100.0, 2)
        opportunity_score = _safe_float(procurement.get("opportunity_score"), 0.0)
        strategy_score = _safe_float(strategy.get("tender_strategy_governance_score"), 0.0)
        executive_score = _safe_float(executive.get("executive_decision_workspace_score"), 0.0)
        recommendation_feedback_ready = bool(strategy.get("what_this_unlocks")) and bool(executive.get("what_this_unlocks"))
        historical_benchmark_ready = bool(procurement.get("what_this_unlocks")) and bool(strategy.get("what_this_unlocks"))
        analytics_score = _clamp(mean([
            100.0 if opportunity_score >= 0 else 55.0,
            100.0 if strategy_score >= 0 else 55.0,
            100.0 if executive_score >= 0 else 55.0,
            100.0 if recommendation_feedback_ready else 55.0,
            100.0 if historical_benchmark_ready else 55.0,
        ]))
        blockers = _unique(list((procurement.get("unresolved_learning_blockers") or [])) + list((executive.get("unresolved_executive_blockers") or [])))
        ready = analytics_score >= 75.0 and not blockers
        status = "ok" if ready else "watch" if analytics_score >= 55.0 else "blocked"
        snapshot = {
            "analysis_id": f"win-loss-analytics:{_safe_str(tender.get('rfq_id') or tender.get('title'), 'sample')}",
            "generated_at": _now_iso(),
            "rfq_id": _safe_str(tender.get("rfq_id"), "n/a"),
            "title": _safe_str(tender.get("title"), "n/a"),
            "ready": ready,
            "status": status,
            "score": round(analytics_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "win_loss_analytics_status": status,
            "win_loss_analytics_score": round(analytics_score, 2),
            "win_loss_analytics_grade": "ready" if ready else "watch" if status == "watch" else "blocked",
            "win_loss_analytics_readiness": {"ready": ready, "status": status, "score": round(analytics_score, 2), "blockers": blockers},
            "win_loss_summary": {
                "total_decisions": total_decisions,
                "win_decisions": len(win_decisions),
                "loss_decisions": len(no_bid_decisions),
                "review_decisions": len(review_decisions),
                "win_rate": win_rate,
                "loss_rate": loss_rate,
                "review_rate": review_rate,
                "dominant_recommendation": "bid" if len(win_decisions) >= max(len(no_bid_decisions), len(review_decisions)) else "no_bid" if len(no_bid_decisions) >= len(review_decisions) else "review",
            },
            "recommendation_feedback_readiness": {"ready": recommendation_feedback_ready, "status": "ok" if recommendation_feedback_ready else "watch", "score": 100.0 if recommendation_feedback_ready else 55.0, "blockers": [] if recommendation_feedback_ready else ["tender strategy feedback incomplete"]},
            "historical_benchmark_readiness": {"ready": historical_benchmark_ready, "status": "ok" if historical_benchmark_ready else "watch", "score": 100.0 if historical_benchmark_ready else 55.0, "blockers": [] if historical_benchmark_ready else ["insufficient history"]},
            "procurement_intelligence_history": procurement_history,
            "tender_strategy_outcomes": strategy_history,
            "executive_review_outcomes": executive_history,
            "win_loss_history": strategy_history,
            "unresolved_learning_blockers": blockers,
            "autonomous_learning_execution_enabled": False,
            "autonomous_procurement_decision_updates_enabled": False,
            "autonomous_supplier_blacklisting_enabled": False,
            "autonomous_strategy_modification_enabled": False,
            "production_learning_mode_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_learning_review_required": True,
            "executive_feedback_required": True,
            "learning_governance_history": [
                {"event": "win_loss_analytics_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "recommendation_feedback_reconciled", "status": "passed" if recommendation_feedback_ready else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Win/loss analytics remain advisory only" if not ready else "",
                "Historical benchmark evidence is limited" if not historical_benchmark_ready else "",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def latest_win_loss_analytics(self) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        history = self._load_history()
        history.append(
            {
                "analysis_id": snapshot["analysis_id"],
                "generated_at": snapshot["generated_at"],
                "rfq_id": snapshot["rfq_id"],
                "title": snapshot["title"],
                "win_loss_analytics_status": snapshot["win_loss_analytics_status"],
                "win_loss_analytics_score": snapshot["win_loss_analytics_score"],
            }
        )
        self._write_history(history)
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_win_loss_analytics"] = dict(snapshot)
        payload["win_loss_analytics_history"] = history
        payload["win_loss_analytics_history_summary"] = {
            "analysis_count": len(history),
            "latest_rfq_id": snapshot["rfq_id"],
            "latest_score": snapshot["win_loss_analytics_score"],
        }
        return payload

    def list_win_loss_analytics(self, limit: int = 20) -> Dict[str, Any]:
        latest = self.latest_win_loss_analytics()
        history = self._load_history()[-max(1, int(limit)) :]
        latest["count"] = len(history)
        latest["win_loss_analytics_history"] = history
        latest["win_loss_analytics_history_summary"] = {
            "analysis_count": len(history),
            "latest_rfq_id": latest["rfq_id"],
            "latest_score": latest["win_loss_analytics_score"],
        }
        return latest

    def win_loss_analytics_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("win_loss_analytics_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "win_loss_analytics_history": history,
            "warnings": latest.get("warnings", []) if history else [],
        }
