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
    return _runtime_dir(runtime_dir) / "executive_decision_queue_history.json"


class ExecutiveDecisionQueueService:
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

    def _build_queue(self) -> Dict[str, Any]:
        workspace = self.workspace_service.analyze_executive_decision_workspace(record_history=False)
        blockers = list(workspace.get("unresolved_executive_blockers") or [])
        queue_items = []
        for index, blocker in enumerate(blockers[:8], start=1):
            queue_items.append(
                {
                    "queue_id": f"executive-queue-{index}",
                    "priority": "high" if index <= 3 else "medium",
                    "item_type": "executive_escalation",
                    "status": "queued",
                    "summary": blocker,
                }
            )
        if not queue_items:
            queue_items.append(
                {
                    "queue_id": "executive-queue-ready",
                    "priority": "low",
                    "item_type": "readiness_confirmation",
                    "status": "ready",
                    "summary": "No unresolved executive blockers remain.",
                }
            )
        score = float(workspace.get("executive_decision_queue_readiness", {}).get("score", 0.0))
        return {
            "analysis_id": f"executive-decision-queue:{workspace.get('analysis_id', 'sample')}",
            "generated_at": _now_iso(),
            "executive_decision_queue_status": "ok" if queue_items and not blockers else "watch" if score >= 55.0 else "blocked",
            "executive_decision_queue_score": score,
            "executive_decision_queue_ready": bool(workspace.get("executive_decision_queue_readiness", {}).get("ready")),
            "queue_items": queue_items,
            "unresolved_executive_blockers": blockers,
            "warnings": list(workspace.get("warnings") or []),
        }

    def latest_executive_decision_queue(self) -> Dict[str, Any]:
        analysis = self._build_queue()
        history = self._load_history()
        history.append(
            {
                "analysis_id": analysis["analysis_id"],
                "generated_at": analysis["generated_at"],
                "executive_decision_queue_status": analysis["executive_decision_queue_status"],
                "executive_decision_queue_score": analysis["executive_decision_queue_score"],
            }
        )
        self._write_history(history)
        return {
            "status": analysis["executive_decision_queue_status"],
            "executive_decision_queue_status": analysis["executive_decision_queue_status"],
            "executive_decision_queue_score": analysis["executive_decision_queue_score"],
            "latest_executive_decision_queue": analysis,
            "executive_decision_queue_history": history,
            "executive_decision_queue_history_summary": {"analysis_count": len(history)},
            "warnings": analysis["warnings"],
        }

    def executive_decision_queue_history(self, limit: int = 20) -> Dict[str, Any]:
        history = self._load_history()[-max(1, int(limit)) :]
        latest = history[-1] if history else {}
        return {
            "status": "ok" if history else "not_found",
            "count": len(history),
            "executive_decision_queue_status": latest.get("executive_decision_queue_status", "not_found") if history else "not_found",
            "executive_decision_queue_score": latest.get("executive_decision_queue_score", 0.0) if history else 0.0,
            "latest_executive_decision_queue": latest,
            "executive_decision_queue_history": history,
            "executive_decision_queue_history_summary": {"analysis_count": len(history)},
            "warnings": [],
        }


executive_decision_queue_service = ExecutiveDecisionQueueService()
