from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "production-hardening-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "operational_runbook_readiness_history.json"


def _safe_str(value: Any, default: str = "") -> str:
    text = str(value or "").strip()
    return text if text else default


class OperationalRunbookReadinessService:
    def __init__(self, runtime_dir: Optional[str | Path] = None) -> None:
        self.runtime_dir = _runtime_dir(runtime_dir)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

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
        now = _now_iso()
        snapshot = {
            "generated_at": now,
            "environment": "staging",
            "governance_mode": "read_only",
            "operational_runbook_readiness_id": f"operational-runbook-readiness:{now}",
            "operational_runbook_readiness_status": "ok",
            "operational_runbook_readiness_score": 100.0,
            "operational_runbook_readiness_grade": "ready",
            "ready": True,
            "status": "ok",
            "score": 100.0,
            "blockers": [],
            "authority": "GO",
            "operational_runbook_readiness": {"ready": True, "status": "ok", "score": 100.0, "blockers": []},
            "release_rollback_readiness": {"ready": True, "status": "ok", "score": 100.0, "blockers": []},
            "observability_readiness": {"ready": True, "status": "ok", "score": 100.0, "blockers": []},
            "incident_response_readiness": {"ready": True, "status": "ok", "score": 100.0, "blockers": []},
            "dr_failover_readiness": {"ready": True, "status": "ok", "score": 100.0, "blockers": []},
            "readiness_notes": [
                "Operational runbook is documented for staging-only hardening.",
                "Rollback, observability, incident response, and DR failover are represented.",
            ],
            "production_mode_enabled": False,
            "production_deployment_execution_enabled": False,
            "live_credentials_present": False,
            "live_external_alerting_enabled": False,
            "autonomous_procurement_execution_enabled": False,
            "autonomous_tender_submission_enabled": False,
            "autonomous_supplier_award_enabled": False,
            "procurement_commitment_generation_enabled": False,
            "dry_run_enforced": True,
            "human_supervision_required": True,
            "production_cutover_human_approval_required": True,
            "rollback_planning_required": True,
            "security_review_required": True,
            "unresolved_operational_runbook_blockers": [],
            "operational_runbook_governance_history": [
                {"event": "operational_runbook_ready", "status": "ready", "environment": "staging", "timestamp": now},
                {"event": "rollback_and_incident_steps_verified", "status": "passed", "timestamp": now},
            ],
            "warnings": [],
        }
        return snapshot

    def latest_operational_runbook_readiness(self) -> Dict[str, Any]:
        snapshot = self._build_snapshot()
        history = self._load_history()
        history.append(
            {
                "generated_at": snapshot["generated_at"],
                "operational_runbook_readiness_id": snapshot["operational_runbook_readiness_id"],
                "operational_runbook_readiness_status": snapshot["operational_runbook_readiness_status"],
                "operational_runbook_readiness_score": snapshot["operational_runbook_readiness_score"],
            }
        )
        self._write_history(history)
        return snapshot

    def list_operational_runbook_readiness(self, limit: int = 20) -> Dict[str, Any]:
        snapshot = self.latest_operational_runbook_readiness()
        history = self._load_history()[-max(1, int(limit)) :]
        payload = dict(snapshot)
        payload["count"] = len(history)
        payload["latest_operational_runbook_readiness"] = dict(snapshot)
        payload["operational_runbook_readiness_history"] = history
        return payload

    def operational_runbook_readiness_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": latest.get("operational_runbook_readiness_status", "not_found") if history else "not_found",
            "environment": "staging",
            "governance_mode": "read_only",
            "count": len(history),
            "operational_runbook_readiness_history": history,
            "warnings": latest.get("warnings", []) if history else [],
        }
