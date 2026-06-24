from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.procurement_intelligence_service import ProcurementIntelligenceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "knowledge-graph-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "procurement_entity_resolution_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class ProcurementEntityResolutionService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.procurement_service = ProcurementIntelligenceService(runtime_dir=self.runtime_dir)

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

    def _build_snapshot(self) -> Dict[str, Any]:
        procurement = self.procurement_service.latest_procurement_intelligence()
        entity_count = len(procurement.get("procurement_intelligence_history", [])) + len(procurement.get("procurement_category_heatmap", {}).get("categories", []))
        readiness_score = _clamp(mean([
            100.0 if procurement.get("procurement_intelligence_score", 0.0) >= 55.0 else 55.0,
            100.0 if procurement.get("procurement_category") else 55.0,
            100.0 if entity_count > 0 else 55.0,
        ]))
        ready = readiness_score >= 70.0
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        snapshot = {
            "analysis_id": f"procurement-entity-resolution:{_safe_str(procurement.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "blockers": [] if ready else ["procurement entity resolution coverage incomplete"],
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "procurement_entity_resolution_status": status,
            "procurement_entity_resolution_score": round(readiness_score, 2),
            "procurement_entity_resolution_readiness": {"ready": ready, "status": status, "score": round(readiness_score, 2), "blockers": [] if ready else ["procurement entity resolution coverage incomplete"]},
            "procurement_entities": {
                "buyers": [procurement.get("buyer_name")],
                "categories": [procurement.get("procurement_category")],
                "sectors": [procurement.get("procurement_sector")],
            },
            "entity_counts": {"total": entity_count},
            "unresolved_knowledge_graph_blockers": [] if ready else ["procurement entity resolution coverage incomplete"],
            "autonomous_graph_decisioning_enabled": False,
            "autonomous_supplier_ranking_updates_enabled": False,
            "autonomous_pricing_override_enabled": False,
            "autonomous_strategy_modification_enabled": False,
            "autonomous_procurement_decisioning_enabled": False,
            "production_graph_learning_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_relationship_review_required": True,
            "graph_governance_review_required": True,
            "knowledge_graph_governance_history": [
                {"event": "procurement_entity_resolution_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
            ],
            "warnings": ["Procurement entity resolution remains advisory only" if not ready else ""],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_procurement_entity_resolution(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "procurement_entity_resolution_status": snapshot["procurement_entity_resolution_status"], "procurement_entity_resolution_score": snapshot["procurement_entity_resolution_score"]})
            self._write_history(history)
        return snapshot

    def latest_procurement_entity_resolution(self) -> Dict[str, Any]:
        snapshot = self.analyze_procurement_entity_resolution(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_procurement_entity_resolution"] = dict(snapshot)
        payload["procurement_entity_resolution_history"] = history
        return payload

    def procurement_entity_resolution_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("procurement_entity_resolution_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "procurement_entity_resolution_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_relationship_review_required": True, "graph_governance_review_required": True, "autonomous_graph_decisioning_enabled": False, "autonomous_supplier_ranking_updates_enabled": False, "autonomous_pricing_override_enabled": False, "autonomous_strategy_modification_enabled": False, "autonomous_procurement_decisioning_enabled": False, "production_graph_learning_enabled": False, "warnings": latest.get("warnings", []) if history else []}


procurement_entity_resolution_service = ProcurementEntityResolutionService()
