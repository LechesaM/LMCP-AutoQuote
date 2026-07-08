from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.commodity_relationship_service import CommodityRelationshipService
from app.services.entity_relationship_mapping_service import EntityRelationshipMappingService
from app.services.historical_learning_service import HistoricalLearningService
from app.services.procurement_entity_resolution_service import ProcurementEntityResolutionService
from app.services.recommendation_feedback_service import RecommendationFeedbackService
from app.services.risk_relationship_intelligence_service import RiskRelationshipIntelligenceService
from app.services.vector_intelligence_service import VectorIntelligenceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "knowledge-graph-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "tender_knowledge_graph_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class TenderKnowledgeGraphService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.vector_service = VectorIntelligenceService(runtime_dir=self.runtime_dir)
        self.historical_learning_service = HistoricalLearningService(runtime_dir=self.runtime_dir)
        self.recommendation_feedback_service = RecommendationFeedbackService(runtime_dir=self.runtime_dir)
        self.procurement_entity_resolution_service = ProcurementEntityResolutionService(runtime_dir=self.runtime_dir)
        self.entity_relationship_mapping_service = EntityRelationshipMappingService(runtime_dir=self.runtime_dir)
        self.commodity_relationship_service = CommodityRelationshipService(runtime_dir=self.runtime_dir)
        self.risk_relationship_intelligence_service = RiskRelationshipIntelligenceService(runtime_dir=self.runtime_dir)

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
        vector = self.vector_service.latest_vector_intelligence()
        historical = self.historical_learning_service.latest_historical_learning()
        feedback = self.recommendation_feedback_service.latest_recommendation_feedback()
        procurement = self.procurement_entity_resolution_service.latest_procurement_entity_resolution()
        relationships = self.entity_relationship_mapping_service.latest_entity_relationship_mapping()
        commodity = self.commodity_relationship_service.latest_commodity_relationship()
        risk = self.risk_relationship_intelligence_service.latest_risk_relationship_intelligence()

        readiness_score = _clamp(mean([
            100.0 if vector.get("vector_intelligence_readiness", {}).get("ready") else 55.0,
            100.0 if historical.get("historical_learning_readiness", {}).get("ready") else 55.0,
            100.0 if feedback.get("recommendation_feedback_readiness", {}).get("ready") else 55.0,
            100.0 if procurement.get("procurement_entity_resolution_readiness", {}).get("ready") else 55.0,
            100.0 if relationships.get("entity_relationship_mapping_readiness", {}).get("ready") else 55.0,
            100.0 if commodity.get("commodity_relationship_readiness", {}).get("ready") else 55.0,
            100.0 if risk.get("risk_relationship_intelligence_readiness", {}).get("ready") else 55.0,
        ]))
        ready = readiness_score >= 70.0
        status = "ok" if ready else "watch" if readiness_score >= 55.0 else "blocked"
        blockers = [] if ready else ["knowledge graph coverage incomplete"]
        snapshot = {
            "analysis_id": f"tender-knowledge-graph:{_safe_str(vector.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(readiness_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "knowledge_graph_status": status,
            "knowledge_graph_score": round(readiness_score, 2),
            "knowledge_graph_readiness": {"ready": ready, "status": status, "score": round(readiness_score, 2), "blockers": blockers},
            "entity_relationship_mapping_readiness": relationships.get("entity_relationship_mapping_readiness"),
            "procurement_entity_resolution_readiness": procurement.get("procurement_entity_resolution_readiness"),
            "commodity_relationship_readiness": commodity.get("commodity_relationship_readiness"),
            "risk_relationship_intelligence_readiness": risk.get("risk_relationship_intelligence_readiness"),
            "supplier_relationship_coverage": relationships.get("supplier_relationship_coverage"),
            "department_relationship_coverage": relationships.get("department_relationship_coverage"),
            "boq_to_pricing_relationship_coverage": relationships.get("boq_to_pricing_relationship_coverage"),
            "outcome_relationship_coverage": relationships.get("outcome_relationship_coverage"),
            "knowledge_graph_entities": {
                "vector": vector.get("vector_intelligence_readiness", {}),
                "historical": historical.get("historical_learning_readiness", {}),
                "feedback": feedback.get("recommendation_feedback_readiness", {}),
                "procurement": procurement.get("procurement_entities", {}),
                "relationships": relationships.get("knowledge_graph_entities", {}),
                "commodity": commodity.get("commodity_entities", {}),
                "risk": risk.get("risk_relationship_coverage", {}),
            },
            "unresolved_knowledge_graph_blockers": blockers,
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
                {"event": "knowledge_graph_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "graph_relationships_reconciled", "status": "passed" if relationships.get("ready") else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Relationship intelligence remains advisory only" if not ready else "",
                "Production graph learning remains disabled",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_tender_knowledge_graph(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "knowledge_graph_status": snapshot["knowledge_graph_status"], "knowledge_graph_score": snapshot["knowledge_graph_score"]})
            self._write_history(history)
        return snapshot

    def latest_tender_knowledge_graph(self) -> Dict[str, Any]:
        snapshot = self.analyze_tender_knowledge_graph(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_tender_knowledge_graph"] = dict(snapshot)
        payload["tender_knowledge_graph_history"] = history
        return payload

    def tender_knowledge_graph_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("knowledge_graph_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "tender_knowledge_graph_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_relationship_review_required": True, "graph_governance_review_required": True, "autonomous_graph_decisioning_enabled": False, "autonomous_supplier_ranking_updates_enabled": False, "autonomous_pricing_override_enabled": False, "autonomous_strategy_modification_enabled": False, "autonomous_procurement_decisioning_enabled": False, "production_graph_learning_enabled": False, "warnings": latest.get("warnings", []) if history else []}


tender_knowledge_graph_service = TenderKnowledgeGraphService()
