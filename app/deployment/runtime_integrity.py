from __future__ import annotations

import json
from typing import Any

from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.domain.workflow import WorkflowStage


def _paths(paths: RuntimePaths | None) -> RuntimePaths:
    return paths or get_runtime_paths()


def run_integrity_checks(*, paths: RuntimePaths | None = None) -> dict[str, Any]:
    resolved = _paths(paths)
    issues = []
    event_file = resolved.manual_production_dir / "workflow_events.jsonl"
    if event_file.exists():
        for line in event_file.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except Exception:
                issues.append({"code": "invalid_json"})
                continue
            to_stage = str(payload.get("to_stage", ""))
            valid_stages = {stage.value for stage in WorkflowStage}
            if to_stage and to_stage not in valid_stages:
                issues.append({"code": "invalid_workflow_stage", "value": to_stage})
    return {"status": "unhealthy" if issues else "healthy", "workflow_issues": issues}
