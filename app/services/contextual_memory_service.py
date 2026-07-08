from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.historical_learning_service import HistoricalLearningService
from app.services.supplier_intelligence_service import SupplierIntelligenceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "vector-intelligence-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "contextual_memory_history.json"


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


class ContextualMemoryService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.historical_learning_service = HistoricalLearningService(runtime_dir=self.runtime_dir)
        self.supplier_service = SupplierIntelligenceService(runtime_dir=self.runtime_dir)

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
        historical = self.historical_learning_service.latest_historical_learning()
        supplier = self.supplier_service.latest_supplier_intelligence()
        history_coverage = len(historical.get("historical_learning_history", [])) + len(supplier.get("supplier_intelligence_history", []))
        memory_score = _clamp(mean([
            100.0 if historical.get("historical_learning_readiness", {}).get("ready") else 55.0,
            100.0 if supplier.get("supplier_memory_readiness", {}).get("ready") else 55.0,
            100.0 if history_coverage > 0 else 55.0,
        ]))
        ready = memory_score >= 70.0
        status = "ok" if ready else "watch" if memory_score >= 55.0 else "blocked"
        blockers = [] if ready else ["contextual memory coverage incomplete"]
        snapshot = {
            "analysis_id": f"contextual-memory:{_safe_str(historical.get('analysis_id'), 'sample')}",
            "generated_at": _now_iso(),
            "environment": "staging",
            "governance_mode": "read_only",
            "ready": ready,
            "status": status,
            "score": round(memory_score, 2),
            "blockers": blockers,
            "authority": "GO" if ready else "WATCH" if status == "watch" else "NO_GO",
            "contextual_memory_status": status,
            "contextual_memory_score": round(memory_score, 2),
            "contextual_memory_readiness": {"ready": ready, "status": status, "score": round(memory_score, 2), "blockers": blockers},
            "historical_learning_readiness": historical.get("historical_learning_readiness"),
            "procurement_intelligence_memory": historical.get("procurement_intelligence_history", []),
            "supplier_memory": supplier.get("supplier_intelligence_history", []),
            "historical_retrieval_coverage": {"ready": history_coverage > 0, "count": history_coverage},
            "unresolved_vector_blockers": blockers,
            "autonomous_vector_decisioning_enabled": False,
            "autonomous_procurement_execution_enabled": False,
            "autonomous_supplier_selection_enabled": False,
            "autonomous_pricing_override_enabled": False,
            "production_vector_learning_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "supervised_retrieval_review_required": True,
            "embedding_governance_review_required": True,
            "vector_governance_history": [
                {"event": "contextual_memory_ready", "status": "ready" if ready else "blocked", "timestamp": _now_iso()},
                {"event": "historical_memory_reconciled", "status": "passed" if history_coverage > 0 else "watch", "timestamp": _now_iso()},
            ],
            "warnings": [
                "Contextual memory is advisory only" if not ready else "",
                "Production vector learning remains disabled",
            ],
        }
        snapshot["warnings"] = [warning for warning in snapshot["warnings"] if warning]
        return snapshot

    def analyze_contextual_memory(self, record_history: bool = False) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        if record_history:
            history = self._load_history()
            history.append({"analysis_id": snapshot["analysis_id"], "generated_at": snapshot["generated_at"], "contextual_memory_status": snapshot["contextual_memory_status"], "contextual_memory_score": snapshot["contextual_memory_score"]})
            self._write_history(history)
        return snapshot

    def latest_contextual_memory(self) -> Dict[str, Any]:
        snapshot = self.analyze_contextual_memory(record_history=True)
        history = self._load_history()
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_contextual_memory"] = dict(snapshot)
        payload["contextual_memory_history"] = history
        payload["contextual_memory_history_summary"] = {"analysis_count": len(history), "latest_score": snapshot["contextual_memory_score"], "latest_status": snapshot["contextual_memory_status"]}
        return payload

    def contextual_memory_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {"status": latest.get("contextual_memory_status", "not_found") if history else "not_found", "environment": "staging", "governance_mode": "read_only", "count": len(history), "contextual_memory_history": history, "dry_run_enforced": True, "human_supervision_required": True, "supervised_retrieval_review_required": True, "embedding_governance_review_required": True, "autonomous_vector_decisioning_enabled": False, "autonomous_procurement_execution_enabled": False, "autonomous_supplier_selection_enabled": False, "autonomous_pricing_override_enabled": False, "production_vector_learning_enabled": False, "warnings": latest.get("warnings", []) if history else []}


contextual_memory_service = ContextualMemoryService()
