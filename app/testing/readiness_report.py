from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now
from app.testing.e2e_rfq_harness import E2ERFQHarness
from app.testing.rfq_fixture_loader import load_fixture_folder


class ReadinessReport(StrictBaseModel):
    production_readiness_score: float = 0.0
    total_fixtures: int = 0
    passed_fixtures: int = 0
    refused_fixtures: int = 0
    failed_fixtures: int = 0
    workflow_correctness_rate: float = 0.0
    persistence_verification_rate: float = 0.0
    audit_verification_rate: float = 0.0
    common_blockers: List[Dict[str, Any]] = Field(default_factory=list)
    manual_production_safety_status: str = "unknown"
    updated_at: Any = None


def build_readiness_report(folder_path: str) -> Dict[str, Any]:
    fixtures = load_fixture_folder(folder_path)
    harness = E2ERFQHarness()
    results = [harness.run_lifecycle(fixture) for fixture in fixtures]
    total = len(results)
    passed = len([item for item in results if item.get("passed")])
    refused = len([item for item in results if item.get("final_stage") == "refused"])
    failed = total - passed - refused
    correctness_rate = (passed / total) if total else 0.0
    persistence_rate = (len([item for item in results if item.get("persistence_verified")]) / total) if total else 0.0
    audit_rate = (len([item for item in results if item.get("audit_verified")]) / total) if total else 0.0
    blocker_counter = Counter()
    for item in results:
        for blocker in item.get("blockers", []):
            blocker_counter[str(blocker)] += 1
    report = ReadinessReport(
        production_readiness_score=round((correctness_rate * 0.5 + persistence_rate * 0.25 + audit_rate * 0.25) * 100, 2),
        total_fixtures=total,
        passed_fixtures=passed,
        refused_fixtures=refused,
        failed_fixtures=failed,
        workflow_correctness_rate=round(correctness_rate, 4),
        persistence_verification_rate=round(persistence_rate, 4),
        audit_verification_rate=round(audit_rate, 4),
        common_blockers=[{"blocker": blocker, "count": count} for blocker, count in blocker_counter.most_common()],
        manual_production_safety_status="safe" if all(item.get("manual_submission_preserved", True) for item in results) else "unsafe",
        updated_at=utc_now(),
    )
    return report.to_jsonable_dict()


def render_readiness_report_text(report: Optional[Dict[str, Any]] = None) -> str:
    report = report or {}
    lines = [
        f"Production readiness score: {report.get('production_readiness_score', 0.0)}",
        f"Total fixtures: {report.get('total_fixtures', 0)}",
        f"Passed fixtures: {report.get('passed_fixtures', 0)}",
        f"Refused fixtures: {report.get('refused_fixtures', 0)}",
        f"Failed fixtures: {report.get('failed_fixtures', 0)}",
        f"Workflow correctness rate: {report.get('workflow_correctness_rate', 0.0)}",
        f"Persistence verification rate: {report.get('persistence_verification_rate', 0.0)}",
        f"Audit verification rate: {report.get('audit_verification_rate', 0.0)}",
        f"Manual-production safety status: {report.get('manual_production_safety_status', 'unknown')}",
    ]
    return "\n".join(lines)
