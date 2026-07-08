from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.procurement_entity_resolution_service import ProcurementEntityResolutionService
from app.services.supplier_intelligence_service import SupplierIntelligenceService
from app.services.pricing_intelligence_governance_service import PricingIntelligenceGovernanceService
from app.services.boq_semantic_understanding_service import BoqSemanticUnderstandingService
from app.services.tender_strategy_governance_service import TenderStrategyGovernanceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "knowledge-graph-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "entity_relationship_mapping_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class EntityRelationshipMappingService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.procurement_entity_resolution_service = ProcurementEntityResolutionService(runtime_dir=self.runtime_dir)
        self.supplier_service = SupplierIntelligenceService(runtime_dir=self.runtime_dir)
        self.pricing_service = PricingIntelligenceGovernanceService(runtime_dir=self.runtime_dir)
        self.boq_service = BoqSemanticUnderstandingService(runtime_dir=self.runtime_dir)
        self.strategy_service = TenderStrategyGovernanceService(runtime_dir=self.runtime_dir)

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
        procurement = self.procurement_entity_resolution_service.latest_procurement_entity_resolution()
        supplier = self.supplier_service.latest_supplier_intelligence()
        pricing = self.pricing_service.latest_pricing_intelligence()
        boq = self.boq_service.analyze_boq_semantics(self.boq_service._latest_record(), record_history=False)
        strategy = self.strategy_service.latest_tender_strategy_governance()

        entity_score = _clamp(mean([
            100.0 if procurement.get("procurement_entity_resolution_readiness", {}).get("ready") else 55.0,
            100.0 if supplier.get("supplier_intelligence_readiness", {}).get("ready") else 55.0,
            100.0 if pricing.get("pricing_benchmark_readiness", {}).get("ready") else 55.0,
            100.0 if boq.get("boq_semantic_understanding_grade") == "ready" else 55.0,
            100.0 if strategy.get("tender_strategy_governance_status") in {"ok", "watch"} else 55.0,
        ]))
        ready = entity_score >= 70.0
        status = "ok" if ready else "watch" if entity_score >= 55.0 else "blocked"
        snapshot = {
            "analysis_id": f"entity-relationship-mapping:{_safe_str(procurement.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(entity_score, 2),
            "blockers": [] if ready else ["entity relationship mapping coverage incomplete"],
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "entity_relationship_mapping_status": status,
            "entity_relationship_mapping_score": round(entity_score, 2),
            "entity_relationship_mapping_readiness": {"ready": ready, "status": status, "score": round(entity_score, 2), "blockers": [] if ready else ["entity relationship mapping coverage incomplete"]},
            "supplier_relationship_coverage": {"ready": bool(supplier.get("supplier_intelligence_readiness", {}).get("ready")), "count": len(supplier.get("supplier_intelligence_history", []))},
            "department_relationship_coverage": {"ready": bool(procurement.get("procurement_entity_resolution_readiness", {}).get("ready")), "count": len(procurement.get("procurement_intelligence_history", []))},
            "boq_to_pricing_relationship_coverage": {"ready": bool(boq.get("pricing_preparation_readiness", {}).get("ready")), "count": len(boq.get("boq_row_analyses", []))},
            "outcome_relationship_coverage": {"ready": bool(strategy.get("tender_strategy_governance_status") in {"ok", "watch"}), "count": len(strategy.get("tender_strategy_governance_history", []))},
            "knowledge_graph_entities": {
                "procurement": procurement.get("procurement_entities", {}),
                "supplier": supplier.get("supplier_match_reason", {}),
                "pricing": pricing.get("pricing_intelligence_history_summary", {}),
                "boq": boq.get("boq_row_analyses", [])[:5],
                "strategy": strategy.get("what_this_unlocks", []),
            },
            "unresolved_knowledge_graph_blockers": [] if ready else ["entity relationship mapping coverage incomplete"],
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
                {"event": "entity_relationship_mapping_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
            ],
            "warnings": ["Relationship mapping remains advisory only" if not ready else ""],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_entity_relationship_mapping(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "entity_relationship_mapping_status": snapshot["entity_relationship_mapping_status"], "entity_relationship_mapping_score": snapshot["entity_relationship_mapping_score"]})
            self._write_history(history)
        return snapshot

    def latest_entity_relationship_mapping(self) -> Dict[str, Any]:
        snapshot = self.analyze_entity_relationship_mapping(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_entity_relationship_mapping"] = dict(snapshot)
        payload["entity_relationship_mapping_history"] = history
        return payload

    def entity_relationship_mapping_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("entity_relationship_mapping_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "entity_relationship_mapping_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_relationship_review_required": True, "graph_governance_review_required": True, "autonomous_graph_decisioning_enabled": False, "autonomous_supplier_ranking_updates_enabled": False, "autonomous_pricing_override_enabled": False, "autonomous_strategy_modification_enabled": False, "autonomous_procurement_decisioning_enabled": False, "production_graph_learning_enabled": False, "warnings": latest.get("warnings", []) if history else []}


entity_relationship_mapping_service = EntityRelationshipMappingService()
