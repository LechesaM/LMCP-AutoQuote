from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.executive_decision_workspace_service import ExecutiveDecisionWorkspaceService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RUNTIME_DIR = PROJECT_ROOT / "runtime" / "staging" / "executive-governance"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _runtime_dir(runtime_dir: Optional[str | Path] = None) -> Path:
    return Path(runtime_dir) if runtime_dir else DEFAULT_RUNTIME_DIR


def _history_file(runtime_dir: Optional[str | Path] = None) -> Path:
    return _runtime_dir(runtime_dir) / "executive_summary_history.json"


class ExecutiveSummaryService:
    def __init__(self, workspace_service: Optional[ExecutiveDecisionWorkspaceService] = None, runtime_dir: Optional[str | Path] = None) -> None:
        self.workspace_service = workspace_service or ExecutiveDecisionWorkspaceService(runtime_dir=runtime_dir)
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

    def _build(self) -> Dict[str, Any]:
        workspace = self.workspace_service.analyze_executive_decision_workspace(record_history=False)
        summary = {
            "analysis_id": f"executive-summary:{workspace.get('analysis_id', 'sample')}",
            "generated_at": _now_iso(),
            "executive_summary_status": workspace.get("executive_decision_workspace_status", "watch"),
            "executive_summary_score": workspace.get("executive_decision_workspace_score", 0.0),
            "executive_summary_ready": bool(workspace.get("executive_review_readiness", {}).get("ready")),
            "executive_summary": {
                "workspace_score": workspace.get("executive_decision_workspace_score", 0.0),
                "strategic_alignment_score": workspace.get("strategic_alignment_readiness", {}).get("score", 0.0),
                "queue_score": workspace.get("executive_decision_queue_readiness", {}).get("score", 0.0),
                "risk_escalations": workspace.get("risk_escalation_indicators", {}),
            },
            "unresolved_executive_blockers": list(workspace.get("unresolved_executive_blockers") or []),
            "executive_review_readiness": workspace.get("executive_review_readiness"),
            "governance_rules": workspace.get("governance_rules"),
            "warnings": list(workspace.get("warnings") or []),
        }
        return summary

    def latest_executive_summary(self) -> Dict[str, Any]:
        analysis = self._build()
        history = self._load_history()
        history.append(
            {
                "analysis_id": analysis["analysis_id"],
                "generated_at": analysis["generated_at"],
                "executive_summary_status": analysis["executive_summary_status"],
                "executive_summary_score": analysis["executive_summary_score"],
            }
        )
        self._write_history(history)
        return {
            "status": analysis["executive_summary_status"],
            "executive_summary_status": analysis["executive_summary_status"],
            "executive_summary_score": analysis["executive_summary_score"],
            "latest_executive_summary": analysis,
            "executive_summary_history": history,
            "executive_summary_history_summary": {"analysis_count": len(history)},
            "warnings": analysis["warnings"],
        }

    def executive_summary_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": "ok" if history else "not_found",
            "count": len(history),
            "executive_summary_status": latest.get("executive_summary_status", "not_found") if history else "not_found",
            "executive_summary_score": latest.get("executive_summary_score", 0.0) if history else 0.0,
            "latest_executive_summary": latest,
            "executive_summary_history": history,
            "executive_summary_history_summary": {"analysis_count": len(history)},
            "warnings": [],
        }


executive_summary_service = ExecutiveSummaryService()
