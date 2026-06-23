from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional
import json


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"
REVIEW_WINDOW_DAYS = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    try:
        text = str(value or "").strip()
        return text if text else default
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _parse_iso(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(_safe_str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except Exception:
        return None


def _age_hours(value: Any) -> float:
    parsed = _parse_iso(value)
    if parsed is None:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0)


def _run_dirs(root: Path, marker: str) -> List[Path]:
    if not root.exists():
        return []
    runs = [path for path in root.iterdir() if path.is_dir() and (path / marker).exists()]
    runs.sort(
        key=lambda path: (
            _parse_iso((_read_json(path / marker, {}) or {}).get("generated_at")) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
            path.name,
        ),
        reverse=True,
    )
    return runs


def _cycle_summary(path: Path) -> Dict[str, Any]:
    payload = _read_json(path / "pilot_cycle_summary.json", {})
    return payload if isinstance(payload, dict) else {}


def _governance_export(path: Path) -> Dict[str, Any]:
    payload = _read_json(path / "pilot_rehearsal_summary.json", {})
    return payload if isinstance(payload, dict) else {}


def _classification(spec: Dict[str, Any]) -> Dict[str, Any]:
    category = spec["category"]
    source = spec["source"]
    message = spec["message"]
    remediation_action = spec["remediation_action"]
    status = spec["status"]
    severity = spec["severity"]
    open_issue = spec["open_issue"]
    return {
        "category": category,
        "source": source,
        "message": message,
        "status": status,
        "severity": severity,
        "open_issue": open_issue,
        "remediation_action": remediation_action,
    }


def _classify_check(check: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    status = _safe_str(check.get("status"), "PASS").upper()
    if status == "PASS":
        return None
    name = _safe_str(check.get("name"), "unknown check").lower()
    remediation = _safe_str(check.get("remediation"), "Review the staging evidence and regenerate the pilot cycle.")
    if "evidence pack" in name:
        return _classification(
            {
                "category": "transient_failure",
                "source": "evidence_pack_verification",
                "message": _safe_str(check.get("message"), "Evidence pack verification failed."),
                "status": "FAIL",
                "severity": "low",
                "open_issue": True,
                "remediation_action": remediation,
            }
        )
    if "operator acknowledgment" in name:
        return _classification(
            {
                "category": "operator_intervention_anomaly",
                "source": "operator_acknowledgment",
                "message": _safe_str(check.get("message"), "Operator acknowledgement is missing or invalid."),
                "status": "FAIL",
                "severity": "medium",
                "open_issue": True,
                "remediation_action": remediation,
            }
        )
    if "governance export" in name or "readiness" in name:
        return _classification(
            {
                "category": "governance_compliance_failure",
                "source": name,
                "message": _safe_str(check.get("message"), "Governance export verification failed."),
                "status": "FAIL",
                "severity": "high",
                "open_issue": True,
                "remediation_action": remediation,
            }
        )
    if "rehearsal cadence" in name:
        return _classification(
            {
                "category": "governance_compliance_failure",
                "source": "rehearsal_cadence",
                "message": _safe_str(check.get("message"), "Rehearsal cadence check failed."),
                "status": "FAIL",
                "severity": "high",
                "open_issue": True,
                "remediation_action": remediation,
            }
        )
    if "concurrency limit" in name:
        return _classification(
            {
                "category": "governance_compliance_failure",
                "source": "concurrency_limit",
                "message": _safe_str(check.get("message"), "Concurrency limit check failed."),
                "status": "FAIL",
                "severity": "high",
                "open_issue": True,
                "remediation_action": remediation,
            }
        )
    return _classification(
        {
            "category": "transient_failure",
            "source": name,
            "message": _safe_str(check.get("message"), "A staging pilot check failed."),
            "status": "FAIL",
            "severity": "low",
            "open_issue": True,
            "remediation_action": remediation,
        }
    )


def _classify_evidence_section(section_name: str, section: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    status = _safe_str(section.get("status"), "PASS").upper()
    if status == "PASS":
        return None
    if section_name == "queue_stability_evidence":
        category = "queue_instability"
        severity = "medium"
        source = "queue_stability"
    elif section_name == "worker_stability_evidence":
        category = "systemic_failure"
        severity = "high"
        source = "worker_stability"
    elif section_name == "telemetry_health_evidence":
        category = "telemetry_degradation"
        severity = "high"
        source = "telemetry_health"
    elif section_name == "retry_recovery_evidence":
        category = "retry_exhaustion"
        severity = "high"
        source = "retry_recovery"
    elif section_name == "rollback_evidence":
        category = "systemic_failure"
        severity = "high"
        source = "rollback"
    elif section_name == "operator_intervention_summary":
        category = "operator_intervention_anomaly"
        severity = "medium"
        source = "operator_intervention"
    elif section_name == "submission_lock_verification":
        category = "governance_compliance_failure"
        severity = "critical"
        source = "submission_lock"
    elif section_name == "dry_run_enforcement_verification":
        category = "governance_compliance_failure"
        severity = "critical"
        source = "dry_run_enforcement"
    else:
        category = "transient_failure"
        severity = "low"
        source = section_name
    return _classification(
        {
            "category": category,
            "source": source,
            "message": f"{section_name} reported {status}.",
            "status": "FAIL",
            "severity": severity,
            "open_issue": True,
            "remediation_action": _safe_list(section.get("notes"))[0] if _safe_list(section.get("notes")) else "Review the staging evidence and regenerate the pilot cycle.",
        }
    )


class OperationalExceptionService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
        review_window_days: int = REVIEW_WINDOW_DAYS,
    ) -> None:
        self.cycle_root = cycle_root or PILOT_CYCLE_ROOT
        self.export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.review_window_days = max(1, review_window_days)

    def _cycles(self) -> List[Path]:
        return _run_dirs(self.cycle_root, "pilot_cycle_summary.json")

    def _exports(self) -> List[Path]:
        return _run_dirs(self.export_root, "pilot_rehearsal_summary.json")

    def _cycle_exceptions(self, cycle: Dict[str, Any]) -> List[Dict[str, Any]]:
        generated_at = _safe_str(cycle.get("generated_at"), _now_iso())
        cycle_id = _safe_str(cycle.get("cycle_id"), "unknown")
        checks = [_classify_check(check) for check in _safe_list(cycle.get("checks")) if isinstance(check, dict)]
        checks = [check for check in checks if check is not None]

        evidence_pack = _safe_dict(cycle.get("evidence_pack"))
        sections = {
            "queue_stability_evidence": _safe_dict(evidence_pack.get("queue_stability_evidence")),
            "worker_stability_evidence": _safe_dict(evidence_pack.get("worker_stability_evidence")),
            "telemetry_health_evidence": _safe_dict(evidence_pack.get("telemetry_health_evidence")),
            "retry_recovery_evidence": _safe_dict(evidence_pack.get("retry_recovery_evidence")),
            "rollback_evidence": _safe_dict(evidence_pack.get("rollback_evidence")),
            "operator_intervention_summary": _safe_dict(evidence_pack.get("operator_intervention_summary")),
            "submission_lock_verification": _safe_dict(evidence_pack.get("submission_lock_verification")),
            "dry_run_enforcement_verification": _safe_dict(evidence_pack.get("dry_run_enforcement_verification")),
        }
        section_exceptions = [
            _classify_evidence_section(name, section)
            for name, section in sections.items()
            if section
        ]
        section_exceptions = [section for section in section_exceptions if section is not None]

        no_go = _safe_dict(cycle.get("no_go_condition_summary"))
        if _safe_str(no_go.get("status"), "PASS") != "PASS":
            section_exceptions.append(
                _classification(
                    {
                        "category": "governance_compliance_failure",
                        "source": "no_go_condition_summary",
                        "message": "NO-GO condition summary is not PASS.",
                        "status": "FAIL",
                        "severity": "critical",
                        "open_issue": True,
                        "remediation_action": "Review the no-go indicators and restore staging readiness before the next cycle.",
                    }
                )
            )

        readiness = _safe_dict(_safe_dict(cycle.get("governance_export")).get("readiness_summary"))
        readiness_score = _safe_float(readiness.get("readiness_score"), 0.0)
        threshold = _safe_float(_safe_dict(readiness.get("thresholds")).get("readiness_score"), 70.0)
        if readiness_score < threshold:
            section_exceptions.append(
                _classification(
                    {
                        "category": "governance_compliance_failure",
                        "source": "readiness_score",
                        "message": f"Readiness score {readiness_score:.2f} is below threshold {threshold:.2f}.",
                        "status": "FAIL",
                        "severity": "high",
                        "open_issue": True,
                        "remediation_action": "Regenerate controlled pilot evidence until the readiness score returns to threshold.",
                    }
                )
            )

        records: List[Dict[str, Any]] = []
        for index, exception in enumerate(checks + section_exceptions, start=1):
            if not exception:
                continue
            records.append(
                {
                    "exception_id": f"{cycle_id}:{index}:{exception['category']}",
                    "cycle_id": cycle_id,
                    "generated_at": generated_at,
                    "detected_at": generated_at,
                    "category": exception["category"],
                    "source": exception["source"],
                    "message": exception["message"],
                    "status": "open" if exception["open_issue"] else "resolved",
                    "remediation_status": "open",
                    "remediation_action": exception["remediation_action"],
                    "severity": exception["severity"],
                    "risk_level": "high" if exception["severity"] in {"high", "critical"} else "medium" if exception["severity"] == "medium" else "low",
                    "open_issue": exception["open_issue"],
                    "evidence_state": _safe_dict(cycle.get("summary_counts")),
                    "resolved_at": "",
                    "resolved_by_cycle_id": "",
                }
            )
        return records

    def _all_cycle_exceptions(self, limit: int = 20) -> List[Dict[str, Any]]:
        exceptions: List[Dict[str, Any]] = []
        for path in self._cycles()[: max(1, int(limit))]:
            payload = _cycle_summary(path)
            if payload:
                exceptions.extend(self._cycle_exceptions(payload))
        return exceptions

    def _latest_cycle(self) -> Dict[str, Any]:
        cycles = self._cycles()
        if not cycles:
            return {}
        return _cycle_summary(cycles[0])

    def _latest_cycle_categories(self) -> Dict[str, Dict[str, Any]]:
        latest = self._latest_cycle()
        if not latest:
            return {}
        categories: Dict[str, Dict[str, Any]] = {}
        for record in self._cycle_exceptions(latest):
            categories[record["category"]] = record
        return categories

    def _latest_governance_export(self) -> Dict[str, Any]:
        exports = self._exports()
        if not exports:
            return {}
        return _governance_export(exports[0])

    def _resolve_history(self, exceptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        latest_categories = self._latest_cycle_categories()
        latest_cycle = self._latest_cycle()
        latest_generated_at = _safe_str(latest_cycle.get("generated_at"), _now_iso())
        resolved: List[Dict[str, Any]] = []
        for record in exceptions:
            if record["category"] in latest_categories:
                continue
            resolved.append(
                {
                    **record,
                    "status": "resolved",
                    "remediation_status": "resolved",
                    "resolved_at": latest_generated_at,
                    "resolved_by_cycle_id": _safe_str(latest_cycle.get("cycle_id"), ""),
                }
            )
        return resolved

    def _unresolved(self, exceptions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        latest_categories = self._latest_cycle_categories()
        unresolved: List[Dict[str, Any]] = []
        for category, record in latest_categories.items():
            unresolved.append(
                {
                    **record,
                    "status": "open",
                    "remediation_status": "open",
                    "resolved_at": "",
                    "resolved_by_cycle_id": "",
                }
            )
        return unresolved

    def _risk_indicators(self, exceptions: List[Dict[str, Any]], unresolved: List[Dict[str, Any]]) -> Dict[str, Any]:
        category_counts: Dict[str, int] = {}
        for record in exceptions:
            category_counts[record["category"]] = category_counts.get(record["category"], 0) + 1
        repeated_categories = [category for category, count in category_counts.items() if count > 1]
        latest_export = self._latest_governance_export()
        readiness_score = _safe_float(_safe_dict(latest_export.get("readiness_summary")).get("readiness_score"), 0.0)
        return {
            "open_exception_count": len(unresolved),
            "resolved_exception_count": len(exceptions) - len(unresolved),
            "transient_failure_risk": category_counts.get("transient_failure", 0) > 1,
            "systemic_failure_risk": category_counts.get("systemic_failure", 0) > 0 or category_counts.get("governance_compliance_failure", 0) > 0,
            "retry_exhaustion_risk": category_counts.get("retry_exhaustion", 0) > 0,
            "telemetry_degradation_risk": category_counts.get("telemetry_degradation", 0) > 0,
            "queue_instability_risk": category_counts.get("queue_instability", 0) > 0,
            "operator_intervention_risk": category_counts.get("operator_intervention_anomaly", 0) > 0,
            "governance_compliance_risk": category_counts.get("governance_compliance_failure", 0) > 0 or readiness_score < 85.0,
            "repeated_exception_types": repeated_categories,
            "latest_readiness_score": readiness_score,
            "latest_readiness_grade": _safe_str(_safe_dict(latest_export.get("readiness_summary")).get("readiness_grade"), "watch"),
            "latest_exception_age_hours": round(_age_hours(unresolved[0]["generated_at"]) if unresolved else 0.0, 2),
        }

    def _remediation_summary(self, exceptions: List[Dict[str, Any]], unresolved: List[Dict[str, Any]]) -> Dict[str, Any]:
        category_counts: Dict[str, int] = {}
        for record in exceptions:
            category_counts[record["category"]] = category_counts.get(record["category"], 0) + 1
        unresolved_categories = [record["category"] for record in unresolved]
        return {
            "status": "PASS" if not unresolved else "WARN",
            "unresolved_count": len(unresolved),
            "resolved_count": len(exceptions) - len(unresolved),
            "open_categories": unresolved_categories,
            "resolved_categories": [category for category, count in category_counts.items() if count and category not in unresolved_categories],
            "category_counts": category_counts,
        }

    def _anomaly_summary(self, exceptions: List[Dict[str, Any]]) -> Dict[str, Any]:
        category_counts: Dict[str, int] = {}
        for record in exceptions:
            category_counts[record["category"]] = category_counts.get(record["category"], 0) + 1
        latest_exception = exceptions[0] if exceptions else {}
        trends = {
            "transient_failure": category_counts.get("transient_failure", 0),
            "systemic_failure": category_counts.get("systemic_failure", 0),
            "retry_exhaustion": category_counts.get("retry_exhaustion", 0),
            "telemetry_degradation": category_counts.get("telemetry_degradation", 0),
            "queue_instability": category_counts.get("queue_instability", 0),
            "operator_intervention_anomaly": category_counts.get("operator_intervention_anomaly", 0),
            "governance_compliance_failure": category_counts.get("governance_compliance_failure", 0),
        }
        return {
            "status": "PASS" if not category_counts else "WARN",
            "category_counts": category_counts,
            "latest_exception_type": _safe_str(latest_exception.get("category"), "none"),
            "latest_exception_at": _safe_str(latest_exception.get("generated_at"), ""),
            "most_common_exception_type": max(category_counts, key=category_counts.get) if category_counts else "none",
            "recurring_anomaly_counts": trends,
            "history_window_days": self.review_window_days,
        }

    def list_exceptions(self, limit: int = 20) -> Dict[str, Any]:
        exceptions = self._all_cycle_exceptions(limit=limit)
        resolved = self._resolve_history(exceptions)
        unresolved = self._unresolved(exceptions)
        if unresolved:
            unresolved = unresolved
        else:
            unresolved = []
        remediation = self._remediation_summary(exceptions, unresolved)
        risk = self._risk_indicators(exceptions, unresolved)
        anomalies = self._anomaly_summary(exceptions)
        latest_cycle = self._latest_cycle()
        latest_export = self._latest_governance_export()
        status = "not_found" if not exceptions else ("ok" if not unresolved and not risk["repeated_exception_types"] and not risk["governance_compliance_risk"] else "watch")
        return {
            "status": status,
            "generated_at": _now_iso(),
            "latest_cycle": {
                "cycle_id": _safe_str(latest_cycle.get("cycle_id"), ""),
                "generated_at": _safe_str(latest_cycle.get("generated_at"), ""),
            },
            "latest_governance_export": {
                "export_id": _safe_str(latest_export.get("export_id"), ""),
                "generated_at": _safe_str(latest_export.get("generated_at"), ""),
            },
            "exception_status": status,
            "exception_summary": {
                "total_exception_count": len(exceptions),
                "open_exception_count": len(unresolved),
                "resolved_exception_count": len(resolved),
                "transient_failure_count": len([exc for exc in exceptions if exc["category"] == "transient_failure"]),
                "systemic_failure_count": len([exc for exc in exceptions if exc["category"] == "systemic_failure"]),
                "retry_exhaustion_count": len([exc for exc in exceptions if exc["category"] == "retry_exhaustion"]),
                "telemetry_degradation_count": len([exc for exc in exceptions if exc["category"] == "telemetry_degradation"]),
                "queue_instability_count": len([exc for exc in exceptions if exc["category"] == "queue_instability"]),
                "operator_intervention_anomaly_count": len([exc for exc in exceptions if exc["category"] == "operator_intervention_anomaly"]),
                "governance_compliance_failure_count": len([exc for exc in exceptions if exc["category"] == "governance_compliance_failure"]),
            },
            "remediation_status_summary": remediation,
            "unresolved_exception_tracking": unresolved,
            "resolved_exception_history": resolved,
            "operational_risk_indicators": risk,
            "recurring_anomaly_summary": anomalies,
            "classification_history": exceptions,
            "warning_indicators": {
                "open_exception_warning": bool(unresolved),
                "repeated_exception_warning": bool(risk["repeated_exception_types"]),
                "governance_compliance_warning": risk["governance_compliance_risk"],
                "telemetry_degradation_warning": risk["telemetry_degradation_risk"],
                "queue_instability_warning": risk["queue_instability_risk"],
                "retry_exhaustion_warning": risk["retry_exhaustion_risk"],
                "operator_intervention_warning": risk["operator_intervention_risk"],
                "systemic_failure_warning": risk["systemic_failure_risk"],
            },
            "warnings": [
                "open_exception_warning" if unresolved else "",
                "repeated_exception_warning" if risk["repeated_exception_types"] else "",
                "governance_compliance_warning" if risk["governance_compliance_risk"] else "",
                "telemetry_degradation_warning" if risk["telemetry_degradation_risk"] else "",
                "queue_instability_warning" if risk["queue_instability_risk"] else "",
                "retry_exhaustion_warning" if risk["retry_exhaustion_risk"] else "",
                "operator_intervention_warning" if risk["operator_intervention_risk"] else "",
                "systemic_failure_warning" if risk["systemic_failure_risk"] else "",
            ],
        }

    def latest_exceptions(self) -> Dict[str, Any]:
        response = self.list_exceptions(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No operational exceptions have been recorded yet.",
                "exceptions": {},
            }
        return {
            "status": response.get("status", "ok"),
            "latest_cycle": response.get("latest_cycle", {}),
            "latest_governance_export": response.get("latest_governance_export", {}),
            "exception_status": response.get("exception_status", "watch"),
            "exception_summary": response.get("exception_summary", {}),
            "remediation_status_summary": response.get("remediation_status_summary", {}),
            "operational_risk_indicators": response.get("operational_risk_indicators", {}),
            "recurring_anomaly_summary": response.get("recurring_anomaly_summary", {}),
            "unresolved_exception_tracking": response.get("unresolved_exception_tracking", []),
            "resolved_exception_history": response.get("resolved_exception_history", []),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def exceptions_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_exceptions(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("classification_history", [])),
            "classification_history": response.get("classification_history", []),
            "unresolved_exception_tracking": response.get("unresolved_exception_tracking", []),
            "resolved_exception_history": response.get("resolved_exception_history", []),
            "exception_summary": response.get("exception_summary", {}),
            "remediation_status_summary": response.get("remediation_status_summary", {}),
            "operational_risk_indicators": response.get("operational_risk_indicators", {}),
            "recurring_anomaly_summary": response.get("recurring_anomaly_summary", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
