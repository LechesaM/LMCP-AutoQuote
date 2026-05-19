from __future__ import annotations

from typing import Any, Dict, Optional

from app.core.runtime_paths import RuntimePaths, get_runtime_paths
from app.deployment.environment_validator import get_environment_summary
from app.deployment.runtime_integrity import get_integrity_report
from app.deployment.startup_validator import generate_startup_report
from app.domain.base import StrictBaseModel, utc_now
from app.pilot.pilot_readiness_report import build_pilot_readiness_report
from app.persistence.repositories import get_persistence_health


class DeploymentReport(StrictBaseModel):
    status: str = "healthy"
    checked_at: Any = None
    startup_readiness: Dict[str, Any]
    runtime_integrity: Dict[str, Any]
    environment_summary: Dict[str, Any]
    persistence_health: Dict[str, Any]
    pilot_readiness: Dict[str, Any]
    risk_summary: Dict[str, Any]


def build_deployment_report(*, paths: Optional[RuntimePaths] = None) -> Dict[str, Any]:
    runtime_paths = paths or get_runtime_paths()
    startup = generate_startup_report(paths=runtime_paths)
    integrity = get_integrity_report(paths=runtime_paths)
    environment = get_environment_summary(paths=runtime_paths)
    persistence = get_persistence_health()
    pilot = build_pilot_readiness_report()
    risks = []
    for section in (startup.get("issues", []), integrity.get("issues", []), environment.get("issues", [])):
        for issue in section:
            risks.append(str(issue.get("message") or ""))
    for issue in pilot.get("warnings", []):
        risks.append(str(issue))
    status = "healthy"
    if startup.get("status") == "unhealthy" or integrity.get("status") == "unhealthy" or environment.get("status") == "unhealthy":
        status = "unhealthy"
    elif startup.get("status") == "degraded" or integrity.get("status") == "degraded" or environment.get("status") == "degraded":
        status = "degraded"
    return DeploymentReport(
        status=status,
        checked_at=utc_now(),
        startup_readiness=startup,
        runtime_integrity=integrity,
        environment_summary=environment,
        persistence_health=persistence,
        pilot_readiness=pilot,
        risk_summary={
            "risk_count": len([item for item in risks if item]),
            "risks": [item for item in risks if item],
        },
    ).to_jsonable_dict()


def render_deployment_report_text(report: Optional[Dict[str, Any]] = None) -> str:
    report = report or build_deployment_report()
    return "\n".join(
        [
            f"Deployment status: {report.get('status', 'unknown')}",
            f"Startup status: {report.get('startup_readiness', {}).get('status', 'unknown')}",
            f"Integrity status: {report.get('runtime_integrity', {}).get('status', 'unknown')}",
            f"Environment status: {report.get('environment_summary', {}).get('status', 'unknown')}",
            f"Persistence status: {report.get('persistence_health', {}).get('status', 'unknown')}",
            f"Pilot readiness score: {report.get('pilot_readiness', {}).get('pilot_readiness_score', 0.0)}",
            f"Risk count: {report.get('risk_summary', {}).get('risk_count', 0)}",
        ]
    )
