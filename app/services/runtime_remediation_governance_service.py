from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from app.services.operational_exception_service import _read_json, _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_ENDURANCE_VALIDATION_ROOT = PROJECT_ROOT / "runtime" / "staging" / "runtime-endurance-validations"
LATEST_RUNTIME_ENDURANCE_VALIDATION_FILE = RUNTIME_ENDURANCE_VALIDATION_ROOT / "latest_runtime_endurance_validation.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _status_from_score(score: float) -> str:
    if score >= 85.0:
        return "ok"
    if score >= 70.0:
        return "watch"
    return "blocked"


def _authority_from_status(status: str) -> str:
    normalized = _safe_str(status, "watch").lower()
    if normalized == "ok":
        return "GO"
    if normalized == "watch":
        return "WATCH"
    return "NO_GO"


def _history_points(values: List[float]) -> Dict[str, Any]:
    if not values:
        return {"trend": "unknown", "delta": 0.0, "average": 0.0, "latest": 0.0, "previous": 0.0, "points": []}
    latest = values[0]
    previous = values[1] if len(values) > 1 else latest
    delta = round(latest - previous, 2)
    if delta > 2.0:
        trend = "improving"
    elif delta < -2.0:
        trend = "declining"
    else:
        trend = "stable"
    return {
        "trend": trend,
        "delta": delta,
        "average": round(mean(values), 2),
        "latest": latest,
        "previous": previous,
        "points": values,
    }


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "ok", "pass", "ready", "certified"}
    return bool(value)


def _deadline_for(category: str, detected_at: str) -> str:
    parsed = _parse_iso(detected_at) or datetime.now(timezone.utc)
    offsets = {
        "critical": timedelta(hours=12),
        "high": timedelta(days=1),
        "medium": timedelta(days=2),
        "low": timedelta(days=3),
    }
    severity = {
        "governance_lock_failure": "critical",
        "dry_run_failure": "critical",
        "supervision_failure": "high",
        "service_health_degradation": "high",
        "observability_failure": "medium",
        "escalation_gap": "high",
        "continuity_instability": "high",
        "governance_degradation": "high",
        "runtime_degradation": "medium",
    }.get(category, "medium")
    return (parsed + offsets.get(severity, timedelta(days=2))).isoformat()


def _owner_for_category(category: str) -> str:
    return {
        "governance_lock_failure": "governance",
        "dry_run_failure": "governance",
        "supervision_failure": "supervision",
        "service_health_degradation": "platform-reliability",
        "observability_failure": "observability",
        "escalation_gap": "release-governance",
        "continuity_instability": "continuity",
        "governance_degradation": "executive-governance",
        "runtime_degradation": "runtime-operations",
    }.get(category, "runtime-operations")


def _remediation_action_for(category: str) -> str:
    return {
        "governance_lock_failure": "Restore the staged submission lock and regenerate the runtime endurance validation.",
        "dry_run_failure": "Re-enable dry-run protections and rerun the endurance validation.",
        "supervision_failure": "Re-establish mandatory supervision coverage and rerun the control window.",
        "service_health_degradation": "Restore the affected service health and rerun staged validation.",
        "observability_failure": "Restore observability endpoints and confirm the next control window.",
        "escalation_gap": "Restore release/governance escalation readiness and confirm the next control window.",
        "continuity_instability": "Restore continuity readiness and confirm no freeze indicators remain active.",
        "governance_degradation": "Resolve degraded governance signals and regenerate the evidence bundle.",
        "runtime_degradation": "Review runtime degradation evidence and restore the staged runtime posture.",
    }.get(category, "Review the staged runtime endurance evidence and remediate the finding.")


def _severity_for_check(level: str, category: str) -> str:
    if category in {"governance_lock_failure", "dry_run_failure"}:
        return "critical"
    if category in {"supervision_failure"}:
        return "high"
    if category in {"service_health_degradation", "observability_failure", "escalation_gap", "continuity_instability", "governance_degradation", "runtime_degradation"}:
        return "medium"
    normalized = _safe_str(level, "WARN").upper()
    return "high" if normalized == "FAIL" else "medium"


def _accepted_risk_classification(open_issue: bool, severity: str) -> str:
    if not open_issue:
        return "closed"
    if severity in {"high", "critical"}:
        return "not_accepted"
    return "accepted"


_BLOCKING_REMEDIATION_CATEGORIES = {
    "governance_lock_failure",
    "dry_run_failure",
    "supervision_failure",
}


class RuntimeRemediationGovernanceService:
    def __init__(self, validation_root: Optional[Path] = None) -> None:
        self.validation_root = validation_root or RUNTIME_ENDURANCE_VALIDATION_ROOT

    def _bundle_files(self) -> List[Path]:
        if not self.validation_root.exists():
            return []
        bundles = [
            path / "runtime_endurance_validation.json"
            for path in self.validation_root.iterdir()
            if path.is_dir() and (path / "runtime_endurance_validation.json").exists()
        ]
        bundles.sort(
            key=lambda path: (
                _parse_iso((_read_json(path, {}) or {}).get("generated_at")) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
                path.name,
            ),
            reverse=True,
        )
        return bundles

    def _load_validation_payloads(self, limit: int = 20) -> List[Dict[str, Any]]:
        payloads: List[Dict[str, Any]] = []
        for bundle_path in self._bundle_files()[: max(1, int(limit))]:
            payload = _read_json(bundle_path, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(bundle_path)
                payloads.append(payload)
        if not payloads and LATEST_RUNTIME_ENDURANCE_VALIDATION_FILE.exists():
            payload = _read_json(LATEST_RUNTIME_ENDURANCE_VALIDATION_FILE, {})
            if isinstance(payload, dict):
                payload["artifact_path"] = str(LATEST_RUNTIME_ENDURANCE_VALIDATION_FILE)
                payloads.append(payload)
        return payloads

    @staticmethod
    def _findings_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        summary = _safe_dict(payload.get("runtime_endurance_summary"))
        checks = _safe_list(payload.get("checks"))
        sample_history = _safe_list(payload.get("sample_history"))
        latest_sample = _safe_dict(sample_history[-1] if sample_history else {})
        latest_sources = _safe_dict(latest_sample.get("sources"))
        release_bundle = _safe_dict(latest_sources.get("release_bundle"))
        release_certification = _safe_dict(latest_sources.get("release_certification"))
        executive_status = _safe_str(latest_sources.get("executive_governance_index_status"), "BLOCKED").upper()
        continuity_status = _safe_str(_safe_dict(latest_sources.get("continuity_readiness")).get("continuity_governance_status"), "blocked").lower()
        incident_status = _safe_str(_safe_dict(latest_sources.get("incident_severity")).get("incident_governance_status"), "blocked").lower()

        findings: List[Dict[str, Any]] = []
        finding_specs = [
            (
                "governance_lock_failure",
                not _truthy(summary.get("governance_locks_active")),
                "submission_lock_enforcement",
                "governance lock enforcement remains active",
            ),
            (
                "dry_run_failure",
                not _truthy(summary.get("dry_run_enabled")),
                "dry_run_mode",
                "dry-run protections remain enabled",
            ),
            (
                "supervision_failure",
                not _truthy(summary.get("supervision_mandatory")),
                "mandatory_supervision",
                "supervision remains mandatory",
            ),
            (
                "service_health_degradation",
                not _truthy(summary.get("services_healthy")),
                "runtime_service_health",
                "runtime services remain healthy",
            ),
            (
                "observability_failure",
                not _truthy(summary.get("observability_endpoints_reachable")),
                "observability_endpoints",
                "observability endpoints remain reachable",
            ),
            (
                "escalation_gap",
                not _truthy(summary.get("escalation_readiness_intact")),
                "escalation_readiness",
                "escalation readiness remains intact",
            ),
            (
                "continuity_instability",
                not _truthy(summary.get("continuity_indicators_stable")),
                "continuity_indicators",
                "continuity indicators remain stable",
            ),
            (
                "governance_degradation",
                not _truthy(summary.get("no_governance_degradation_occurs")),
                "governance_degradation",
                "no governance degradation occurs",
            ),
        ]
        for category, open_issue, source_check, description in finding_specs:
            severity = _severity_for_check("FAIL" if open_issue else "PASS", category)
            findings.append(
                {
                    "remediation_id": f"{_safe_str(payload.get('validation_id'), 'runtime-endurance') }:{category}",
                    "category": category,
                    "source_check": source_check,
                    "description": description,
                    "open_issue": bool(open_issue),
                    "severity": severity,
                    "owner": _owner_for_category(category),
                    "remediation_action": _remediation_action_for(category),
                    "accepted_operational_risk_classification": _accepted_risk_classification(bool(open_issue), severity),
                    "deadline_at": _deadline_for(category, _safe_str(payload.get("generated_at"), _now_iso())),
                    "detected_at": _safe_str(payload.get("generated_at"), _now_iso()),
                    "finding_status": "open" if open_issue else "resolved",
                    "finding_level": "FAIL" if open_issue else "PASS",
                    "finding_score": 0.0 if open_issue else 100.0,
                    "notes": [
                        f"Source check: {source_check}.",
                        f"Latest release authority: {_safe_str(release_bundle.get('overall_authority'), 'WATCH').upper()}",
                        f"Latest release certification: {_safe_str(release_certification.get('status'), _safe_str(release_certification.get('release_governance_status'), 'WATCH')).upper()}",
                        f"Executive readiness: {executive_status}",
                        f"Continuity status: {continuity_status}",
                        f"Incident status: {incident_status}",
                    ],
                }
            )
        for check in checks:
            level = _safe_str(check.get("level"), "WARN").upper()
            if level == "PASS":
                continue
            category = {
                "governance locks remain active": "governance_lock_failure",
                "dry-run remains enabled": "dry_run_failure",
                "supervision remains mandatory": "supervision_failure",
                "services remain healthy": "service_health_degradation",
                "observability endpoints remain reachable": "observability_failure",
                "escalation readiness remains intact": "escalation_gap",
                "continuity indicators remain stable": "continuity_instability",
                "no governance degradation occurs": "governance_degradation",
            }.get(_safe_str(check.get("name")), "runtime_degradation")
            severity = _severity_for_check(level, category)
            findings.append(
                {
                    "remediation_id": f"{_safe_str(payload.get('validation_id'), 'runtime-endurance')}:{category}:check",
                    "category": category,
                    "source_check": _safe_str(check.get("name"), "unknown"),
                    "description": _safe_str(check.get("message"), ""),
                    "open_issue": True,
                    "severity": severity,
                    "owner": _owner_for_category(category),
                    "remediation_action": _remediation_action_for(category),
                    "accepted_operational_risk_classification": _accepted_risk_classification(True, severity),
                    "deadline_at": _deadline_for(category, _safe_str(payload.get("generated_at"), _now_iso())),
                    "detected_at": _safe_str(payload.get("generated_at"), _now_iso()),
                    "finding_status": "open",
                    "finding_level": level,
                    "finding_score": _safe_float(check.get("score"), 0.0),
                    "notes": [
                        _safe_str(check.get("remediation"), ""),
                        f"Endurance status: {_safe_str(summary.get('runtime_endurance_status'), 'WARN')}",
                    ],
                }
            )
        return findings

    @staticmethod
    def _history_summary(records: List[Dict[str, Any]]) -> Dict[str, Any]:
        scores = [float(record.get("remediation_readiness_score", 0.0)) for record in records]
        statuses = [record.get("runtime_remediation_status", "watch") for record in records]
        category_counts: Dict[str, int] = {}
        for record in records:
            category_counts[record["category"]] = category_counts.get(record["category"], 0) + 1
        return {
            "status": "PASS" if statuses and all(_safe_str(status, "watch").lower() == "ok" for status in statuses) else ("WARN" if statuses else "not_found"),
            "remediation_count": len(records),
            "category_counts": category_counts,
            "latest_remediation_id": records[0]["remediation_id"] if records else "",
            "latest_deadline_at": records[0]["deadline_at"] if records else "",
            "latest_owner": records[0]["owner"] if records else "",
            "score_history": _history_points(scores),
        }

    def _record(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        summary = _safe_dict(payload.get("runtime_endurance_summary"))
        findings = self._findings_from_payload(payload)
        open_findings = [finding for finding in findings if finding["open_issue"]]
        resolved_findings = [finding for finding in findings if not finding["open_issue"]]
        blockers = [
            finding
            for finding in open_findings
            if finding["category"] in _BLOCKING_REMEDIATION_CATEGORIES
        ]
        warnings = [finding["category"] for finding in findings if finding["open_issue"]]
        latest_sample = _safe_dict((_safe_list(payload.get("sample_history"))[-1] if _safe_list(payload.get("sample_history")) else {}))
        latest_sources = _safe_dict(latest_sample.get("sources"))
        continuity = _safe_dict(latest_sources.get("continuity_readiness"))
        incident = _safe_dict(latest_sources.get("incident_severity"))
        executive_status = _safe_str(latest_sources.get("executive_governance_index_status"), "BLOCKED").upper()
        runtime_status = _safe_str(summary.get("runtime_endurance_status"), "WARN").upper()
        runtime_score = _safe_float(summary.get("runtime_endurance_score"), 0.0)
        remediation_score = round(max(0.0, min(100.0, runtime_score - (len(open_findings) * 6.5) - (len(blockers) * 8.0))), 2)
        if not open_findings and runtime_status == "PASS":
            status = "ok"
        elif blockers or runtime_status == "FAIL":
            status = "blocked"
        else:
            status = "watch"
        authority = _authority_from_status(status)
        grade = "ready" if status == "ok" else "watch" if status == "watch" else "blocked"
        governance_recovery_tracking = {
            "governance_recovery_ready": not open_findings and runtime_status == "PASS",
            "escalation_gap_resolved": not any(finding["category"] == "escalation_gap" and finding["open_issue"] for finding in findings),
            "continuity_gap_resolved": _truthy(summary.get("continuity_indicators_stable")),
            "recovery_readiness_intact": _truthy(summary.get("escalation_readiness_intact")) and _truthy(summary.get("continuity_indicators_stable")),
            "latest_continuity_status": _safe_str(continuity.get("continuity_governance_status"), "blocked"),
            "latest_incident_status": _safe_str(incident.get("incident_governance_status"), "blocked"),
            "latest_executive_status": executive_status,
        }
        remediation_escalation_indicators = {
            "endurance_degradation_found": runtime_status != "PASS",
            "escalation_gap_found": any(finding["category"] == "escalation_gap" and finding["open_issue"] for finding in findings),
            "continuity_instability_found": any(finding["category"] == "continuity_instability" and finding["open_issue"] for finding in findings),
            "governance_degradation_found": any(finding["category"] == "governance_degradation" and finding["open_issue"] for finding in findings),
            "supervision_failure_found": any(finding["category"] == "supervision_failure" and finding["open_issue"] for finding in findings),
            "observability_failure_found": any(finding["category"] == "observability_failure" and finding["open_issue"] for finding in findings),
            "service_health_degradation_found": any(finding["category"] == "service_health_degradation" and finding["open_issue"] for finding in findings),
        }
        unresolved_blockers = [finding for finding in blockers if finding["open_issue"]]
        remediation_rationale = [
            f"Runtime endurance status: {runtime_status}.",
            f"Runtime endurance score: {runtime_score:.2f}.",
            f"Open remediation findings: {len(open_findings)}.",
            f"Blocking remediation findings: {len(blockers)}.",
            f"Continuity stable: {str(bool(summary.get('continuity_indicators_stable'))).lower()}.",
            f"Escalation ready: {str(bool(summary.get('escalation_readiness_intact'))).lower()}.",
            f"Governance degradation: {str(bool(summary.get('no_governance_degradation_occurs'))).lower()}.",
        ]
        return {
            "analysis_id": _safe_str(payload.get("validation_id"), f"runtime-remediation:{_now_iso()}"),
            "generated_at": _safe_str(payload.get("generated_at"), _now_iso()),
            "source_validation_id": _safe_str(payload.get("validation_id"), ""),
            "runtime_endurance_status": runtime_status,
            "runtime_endurance_score": runtime_score,
            "runtime_remediation_status": status,
            "runtime_remediation_authority": authority,
            "runtime_remediation_grade": grade,
            "remediation_readiness_score": remediation_score,
            "remediation_readiness_status": "PASS" if status == "ok" else "WARN" if status == "watch" else "FAIL",
            "remediation_readiness_grade": grade,
            "endurance_degradation_findings": [finding for finding in findings if finding["open_issue"]],
            "remediation_classifications": findings,
            "open_remediation_tracking": open_findings,
            "resolved_remediation_history": resolved_findings,
            "unresolved_remediation_blockers": unresolved_blockers,
            "remediation_escalation_indicators": remediation_escalation_indicators,
            "governance_recovery_tracking": governance_recovery_tracking,
            "remediation_governance_history": {
                "status": status,
                "remediation_count": len(findings),
                "open_count": len(open_findings),
                "resolved_count": len(resolved_findings),
                "blocking_count": len(blockers),
                "latest_remediation_id": findings[0]["remediation_id"] if findings else "",
                "latest_deadline_at": findings[0]["deadline_at"] if findings else "",
                "latest_owner": findings[0]["owner"] if findings else "",
                "score_history": _history_points([remediation_score]),
            },
            "remediation_rationale_summary": remediation_rationale,
            "warnings": warnings,
            "latest_runtime_endurance": payload,
            "summary_counts": {
                "PASS": 0 if open_findings else 1,
                "WARN": 1 if open_findings and not blockers else 0,
                "FAIL": 1 if blockers else 0,
            },
        }

    def _history_entries(self, limit: int = 20) -> List[Dict[str, Any]]:
        entries = []
        for payload in self._load_validation_payloads(limit=limit):
            record = self._record(payload)
            entries.append(
                {
                    "analysis_id": record["analysis_id"],
                    "generated_at": record["generated_at"],
                    "runtime_remediation_status": record["runtime_remediation_status"],
                    "runtime_remediation_authority": record["runtime_remediation_authority"],
                    "runtime_remediation_grade": record["runtime_remediation_grade"],
                    "remediation_readiness_score": record["remediation_readiness_score"],
                    "remediation_readiness_status": record["remediation_readiness_status"],
                    "remediation_readiness_grade": record["remediation_readiness_grade"],
                    "open_remediation_count": len(record["open_remediation_tracking"]),
                    "resolved_remediation_count": len(record["resolved_remediation_history"]),
                    "blocking_remediation_count": len(record["unresolved_remediation_blockers"]),
                    "remediation_rationale_summary": record["remediation_rationale_summary"],
                    "remediation_escalation_indicators": record["remediation_escalation_indicators"],
                    "governance_recovery_tracking": record["governance_recovery_tracking"],
                    "runtime_endurance_status": record["runtime_endurance_status"],
                    "runtime_endurance_score": record["runtime_endurance_score"],
                }
            )
        return entries

    def list_runtime_remediation(self, limit: int = 20) -> Dict[str, Any]:
        records = self._history_entries(limit=limit)
        latest_payloads = self._load_validation_payloads(limit=1)
        latest_payload = latest_payloads[0] if latest_payloads else {}
        latest_record = self._record(latest_payload) if latest_payload else {}
        open_records = _safe_list(latest_record.get("open_remediation_tracking"))
        resolved_records = _safe_list(latest_record.get("resolved_remediation_history"))
        unresolved_blockers = _safe_list(latest_record.get("unresolved_remediation_blockers"))
        remediation_status = _safe_str(latest_record.get("runtime_remediation_status"), "watch")
        remediation_score = _safe_float(latest_record.get("remediation_readiness_score"), 0.0)
        if remediation_status == "blocked":
            status = "blocked"
        elif remediation_status == "watch":
            status = "watch"
        elif remediation_score >= 85.0:
            status = "ok"
        else:
            status = "watch" if open_records else "ok"
        return {
            "status": status,
            "generated_at": _safe_str(latest_record.get("generated_at"), _now_iso()),
            "latest_cycle": {
                "validation_id": _safe_str(latest_record.get("source_validation_id"), ""),
                "runtime_endurance_status": _safe_str(latest_record.get("runtime_endurance_status"), "WARN"),
                "runtime_endurance_score": _safe_float(latest_record.get("runtime_endurance_score"), 0.0),
            },
            "runtime_remediation_status": status,
            "remediation_readiness_score": remediation_score,
            "remediation_readiness_status": _safe_str(latest_record.get("remediation_readiness_status"), "WARN"),
            "remediation_readiness_grade": _safe_str(latest_record.get("remediation_readiness_grade"), "watch"),
            "runtime_remediation_summary": {
                "total_remediation_count": len(latest_record.get("remediation_classifications", [])),
                "open_remediation_count": len(open_records),
                "resolved_remediation_count": len(resolved_records),
                "blocking_remediation_count": len(unresolved_blockers),
                "remediation_readiness_score": remediation_score,
                "remediation_readiness_status": _safe_str(latest_record.get("remediation_readiness_status"), "WARN"),
            },
            "remediation_classifications": latest_record.get("remediation_classifications", []),
            "endurance_degradation_findings": latest_record.get("endurance_degradation_findings", []),
            "open_remediation_tracking": open_records,
            "resolved_remediation_history": resolved_records,
            "unresolved_remediation_blockers": unresolved_blockers,
            "remediation_escalation_indicators": latest_record.get("remediation_escalation_indicators", {}),
            "governance_recovery_tracking": latest_record.get("governance_recovery_tracking", {}),
            "remediation_governance_history": latest_record.get("remediation_governance_history", {}),
            "remediation_rationale_summary": latest_record.get("remediation_rationale_summary", []),
            "warning_indicators": {
                "endurance_degradation_warning": bool(latest_record.get("endurance_degradation_findings")),
                "observability_failure_warning": bool(latest_record.get("remediation_escalation_indicators", {}).get("observability_failure_found")),
                "escalation_gap_warning": bool(latest_record.get("remediation_escalation_indicators", {}).get("escalation_gap_found")),
                "continuity_instability_warning": bool(latest_record.get("remediation_escalation_indicators", {}).get("continuity_instability_found")),
                "governance_degradation_warning": bool(latest_record.get("remediation_escalation_indicators", {}).get("governance_degradation_found")),
                "open_blocker_warning": bool(unresolved_blockers),
            },
            "warnings": _safe_list(latest_record.get("warnings")),
            "latest_runtime_endurance": latest_payload,
        }

    def latest_runtime_remediation(self) -> Dict[str, Any]:
        response = self.list_runtime_remediation(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No runtime endurance remediation records have been generated yet.",
                "runtime_remediation": {},
            }
        return {
            "status": response.get("status", "ok"),
            "latest_cycle": response.get("latest_cycle", {}),
            "runtime_remediation_status": response.get("runtime_remediation_status", "watch"),
            "remediation_readiness_score": response.get("remediation_readiness_score", 0.0),
            "remediation_readiness_status": response.get("remediation_readiness_status", "WARN"),
            "remediation_readiness_grade": response.get("remediation_readiness_grade", "watch"),
            "runtime_remediation_summary": response.get("runtime_remediation_summary", {}),
            "remediation_classifications": response.get("remediation_classifications", []),
            "endurance_degradation_findings": response.get("endurance_degradation_findings", []),
            "open_remediation_tracking": response.get("open_remediation_tracking", []),
            "resolved_remediation_history": response.get("resolved_remediation_history", []),
            "unresolved_remediation_blockers": response.get("unresolved_remediation_blockers", []),
            "remediation_escalation_indicators": response.get("remediation_escalation_indicators", {}),
            "governance_recovery_tracking": response.get("governance_recovery_tracking", {}),
            "remediation_governance_history": response.get("remediation_governance_history", {}),
            "remediation_rationale_summary": response.get("remediation_rationale_summary", []),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def runtime_remediation_history(self, limit: int = 20) -> Dict[str, Any]:
        records = self._history_entries(limit=limit)
        return {
            "status": "not_found" if not records else "ok",
            "count": len(records),
            "runtime_remediation_history": records,
            "runtime_remediation_summary": {
                "status": "PASS" if not records else "WARN",
                "remediation_count": len(records),
                "open_remediation_count": sum(1 for record in records if record.get("open_remediation_count", 0)),
                "resolved_remediation_count": sum(1 for record in records if record.get("resolved_remediation_count", 0)),
                "blocking_remediation_count": sum(1 for record in records if record.get("blocking_remediation_count", 0)),
            },
            "remediation_governance_history": {
                "analysis_count": len(records),
                "latest_analysis_id": records[0]["analysis_id"] if records else "",
                "latest_score": records[0]["remediation_readiness_score"] if records else 0.0,
                "score_history": _history_points([_safe_float(record.get("remediation_readiness_score"), 0.0) for record in records]),
            },
            "warnings": [] if records else ["not_found"],
        }
