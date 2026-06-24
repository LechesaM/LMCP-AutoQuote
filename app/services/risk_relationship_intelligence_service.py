from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.entity_relationship_mapping_service import EntityRelationshipMappingService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "knowledge-graph-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "risk_relationship_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class RiskRelationshipIntelligenceService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.entity_relationship_mapping_service = EntityRelationshipMappingService(runtime_dir=self.runtime_dir)

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
        relationships = self.entity_relationship_mapping_service.latest_entity_relationship_mapping()
        readiness_score = _clamp(mean([
            100.0 if relationships.get("entity_relationship_mapping_readiness", {}).get("ready") else 55.0,
            100.0 if relationships.get("supplier_relationship_coverage", {}).get("ready") else 55.0,
            100.0 if relationships.get("department_relationship_coverage", {}).get("ready") else 55.0,
            100.0 if relationships.get("outcome_relationship_coverage", {}).get("ready") else 55.0,
        ]))
        ready = readiness_score >= 70.0
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        risk_flags = [] if ready else ["relationship risk coverage incomplete"]
        snapshot = {
            "analysis_id": f"risk-relationship-intelligence:{_safe_str(relationships.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "blockers": risk_flags,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "risk_relationship_intelligence_status": status,
            "risk_relationship_intelligence_score": round(readiness_score, 2),
            "risk_relationship_intelligence_readiness": {"ready": ready, "status": status, "score": round(readiness_score, 2), "blockers": risk_flags},
            "supplier_relationship_coverage": relationships.get("supplier_relationship_coverage"),
            "department_relationship_coverage": relationships.get("department_relationship_coverage"),
            "boq_to_pricing_relationship_coverage": relationships.get("boq_to_pricing_relationship_coverage"),
            "outcome_relationship_coverage": relationships.get("outcome_relationship_coverage"),
            "risk_relationship_coverage": {
                "supplier_relationship_coverage": relationships.get("supplier_relationship_coverage"),
                "department_relationship_coverage": relationships.get("department_relationship_coverage"),
                "boq_to_pricing_relationship_coverage": relationships.get("boq_to_pricing_relationship_coverage"),
                "outcome_relationship_coverage": relationships.get("outcome_relationship_coverage"),
            },
            "risk_relationship_flags": risk_flags,
            "unresolved_knowledge_graph_blockers": risk_flags,
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
                {"event": "risk_relationship_intelligence_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
            ],
            "warnings": ["Risk relationship intelligence remains advisory only" if not ready else ""],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_risk_relationship_intelligence(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "risk_relationship_intelligence_status": snapshot["risk_relationship_intelligence_status"], "risk_relationship_intelligence_score": snapshot["risk_relationship_intelligence_score"]})
            self._write_history(history)
        return snapshot

    def latest_risk_relationship_intelligence(self) -> Dict[str, Any]:
        snapshot = self.analyze_risk_relationship_intelligence(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_risk_relationship_intelligence"] = dict(snapshot)
        payload["risk_relationship_history"] = history
        return payload

    def risk_relationship_intelligence_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("risk_relationship_intelligence_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "risk_relationship_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_relationship_review_required": True, "graph_governance_review_required": True, "autonomous_graph_decisioning_enabled": False, "autonomous_supplier_ranking_updates_enabled": False, "autonomous_pricing_override_enabled": False, "autonomous_strategy_modification_enabled": False, "autonomous_procurement_decisioning_enabled": False, "production_graph_learning_enabled": False, "warnings": latest.get("warnings", []) if history else []}


risk_relationship_intelligence_service = RiskRelationshipIntelligenceService()
