from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Set
import json

from app.services.operational_exception_service import _safe_dict, _safe_float, _safe_int, _safe_list, _safe_str
from app.services.pilot_readiness_declaration_service import PilotReadinessDeclarationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_CYCLE_ROOT = PROJECT_ROOT / "runtime" / "staging" / "pilot-cycles"
GOVERNANCE_EXPORT_ROOT = PROJECT_ROOT / "runtime" / "staging" / "governance-exports"
SUPERVISION_WINDOW_HOURS = 24
SLA_HOURS = 12


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


def _age_hours(value: Any) -> float:
    parsed = _parse_iso(value)
    if parsed is None:
        return 0.0
    return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 3600.0)


def _read_json(path: Path, default: Any) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default
    return default


def _run_dirs(root: Path) -> List[Path]:
    if not root.exists():
        return []
    runs = [path for path in root.iterdir() if path.is_dir() and (path / "pilot_cycle_summary.json").exists()]
    runs.sort(
        key=lambda path: (
            _parse_iso((_read_json(path / "pilot_cycle_summary.json", {}) or {}).get("generated_at")) or datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc),
            path.name,
        ),
        reverse=True,
    )
    return runs


def _gather_rfq_ids(payload: Any, seen: Optional[Set[str]] = None) -> List[str]:
    seen = seen or set()
    results: List[str] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "rfq_id":
                rfq_id = _safe_str(value, "")
                if rfq_id and rfq_id not in seen:
                    seen.add(rfq_id)
                    results.append(rfq_id)
            else:
                results.extend(_gather_rfq_ids(value, seen))
    elif isinstance(payload, list):
        for item in payload:
            results.extend(_gather_rfq_ids(item, seen))
    return results


def _supervision_window(generated_at: str) -> Dict[str, Any]:
    started = _parse_iso(generated_at) or datetime.now(timezone.utc)
    ended = started + timedelta(hours=SUPERVISION_WINDOW_HOURS)
    return {
        "started_at": started.isoformat(),
        "ends_at": ended.isoformat(),
        "active": datetime.now(timezone.utc) <= ended,
        "window_hours": SUPERVISION_WINDOW_HOURS,
    }


def _checkpoint_from_check(check: Dict[str, Any]) -> Dict[str, Any]:
    status = _safe_str(check.get("status"), "WARN").upper()
    return {
        "name": _safe_str(check.get("name"), "checkpoint"),
        "status": status,
        "message": _safe_str(check.get("message"), ""),
        "remediation": _safe_str(check.get("remediation"), ""),
        "requires_acknowledgement": status != "PASS",
    }


def _approved_sequence() -> List[str]:
    return [
        "operator_review",
        "governance_checkpoint",
        "cadence_verification",
        "readiness_verification",
        "evidence_pack_validation",
    ]


class PilotOperatorSessionService:
    def __init__(
        self,
        cycle_root: Optional[Path] = None,
        export_root: Optional[Path] = None,
    ) -> None:
        self.cycle_root = cycle_root or PILOT_CYCLE_ROOT
        self.export_root = export_root or GOVERNANCE_EXPORT_ROOT
        self.readiness = PilotReadinessDeclarationService(cycle_root=self.cycle_root, export_root=self.export_root)

    def _latest_acknowledgement(self) -> Dict[str, Any]:
        ack_path = self.cycle_root / "operator_acknowledgement.json"
        payload = _read_json(ack_path, {})
        return payload if isinstance(payload, dict) else {}

    def _session_for_cycle(self, cycle_path: Path, declaration_latest: Dict[str, Any], ack: Dict[str, Any]) -> Dict[str, Any]:
        cycle = _read_json(cycle_path / "pilot_cycle_summary.json", {})
        cycle = cycle if isinstance(cycle, dict) else {}
        generated_at = _safe_str(cycle.get("generated_at"), _now_iso())
        status = _safe_str(cycle.get("status"), "WATCH")
        checks = [_checkpoint_from_check(check) for check in _safe_list(cycle.get("checks")) if isinstance(check, dict)]
        approvals_pending = [checkpoint for checkpoint in checks if checkpoint["status"] != "PASS"]
        rfq_ids = _gather_rfq_ids(cycle)
        if not rfq_ids:
            rfq_ids = _gather_rfq_ids(cycle.get("evidence_pack", {}))
        if not rfq_ids:
            rfq_ids = [f"{_safe_str(cycle.get('cycle_id'), 'cycle')}:RFQ-1"]
        supervision_window = _supervision_window(generated_at)
        readiness_status = _safe_str(declaration_latest.get("declaration_status"), "WATCH")
        cycle_ack = _safe_dict(cycle.get("operator_acknowledgement"))
        effective_ack = ack if ack else cycle_ack
        coverage = 100.0 if _safe_dict(effective_ack).get("acknowledged") and checks else 0.0
        supervision_score = round(
            mean([
                100.0 if status == "PASS" else 65.0,
                100.0 if _safe_dict(effective_ack).get("acknowledged") else 60.0,
                100.0 if not approvals_pending else 70.0,
                100.0 if supervision_window["active"] else 70.0,
                100.0 if readiness_status == "READY_FOR_CONTROLLED_PILOT" else 65.0 if readiness_status == "WATCH" else 0.0,
            ]),
            2,
        )
        if not supervision_window["active"] or status != "PASS":
            session_status = "blocked"
        elif approvals_pending or not _safe_dict(effective_ack).get("acknowledged"):
            session_status = "watch"
        else:
            session_status = "active"
        pending_escalations = [
            {
                "name": checkpoint["name"],
                "message": checkpoint["message"],
                "remediation": checkpoint["remediation"],
            }
            for checkpoint in approvals_pending
        ]
        unattended_warnings = []
        if not _safe_dict(effective_ack).get("acknowledged"):
            unattended_warnings.append("operator_acknowledgement_missing")
        if not supervision_window["active"]:
            unattended_warnings.append("supervision_window_closed")
        if readiness_status == "NO_GO":
            unattended_warnings.append("readiness_declaration_no_go")
        if pending_escalations:
            unattended_warnings.append("pending_approval_checkpoints")

        return {
            "operator_session_id": f"{_safe_str(cycle.get('cycle_id'), 'cycle')}:operator-session",
            "cycle_id": _safe_str(cycle.get("cycle_id"), ""),
            "generated_at": generated_at,
            "status": session_status,
            "operator_name": _safe_str(ack.get("operator_name"), "staging-governance-operator"),
            "operator_role": _safe_str(ack.get("operator_role"), "governance_reviewer"),
            "operator_acknowledgement": {
                "acknowledged": bool(_safe_dict(effective_ack).get("acknowledged", False)),
                "approved_at": _safe_str(_safe_dict(effective_ack).get("approved_at"), ""),
                "approved_rehearsal_sequence": _safe_list(_safe_dict(effective_ack).get("approved_rehearsal_sequence")) or _approved_sequence(),
                "notes": _safe_list(_safe_dict(effective_ack).get("notes")),
            },
            "approved_rehearsal_sequence": _safe_list(_safe_dict(effective_ack).get("approved_rehearsal_sequence")) or _approved_sequence(),
            "active_operator_session": session_status == "active",
            "supervised_rfq_assignments": [
                {
                    "rfq_id": rfq_id,
                    "source_cycle_id": _safe_str(cycle.get("cycle_id"), ""),
                    "assigned_at": generated_at,
                    "supervision_state": "assigned",
                }
                for rfq_id in rfq_ids[:20]
            ],
            "assigned_rfq_count": len(rfq_ids),
            "active_rfq_count": len(rfq_ids) if session_status == "active" else 0,
            "approval_checkpoints": checks,
            "pending_approval_checkpoints": pending_escalations,
            "escalation_acknowledgements": [
                {
                    "checkpoint": item["name"],
                    "acknowledged": False,
                    "status": "pending" if item["name"] else "unknown",
                }
                for item in approvals_pending
            ],
            "supervision_window": supervision_window,
            "operator_supervision_score": supervision_score,
            "unattended_rfq_warnings": unattended_warnings,
            "supervision_lapse_indicators": {
                "operator_acknowledgement_missing": not bool(_safe_dict(effective_ack).get("acknowledged", False)),
                "supervision_window_closed": not supervision_window["active"],
                "approval_backlog_present": bool(approvals_pending),
                "readiness_not_ready": readiness_status != "READY_FOR_CONTROLLED_PILOT",
                "no_go_history_present": bool(_safe_list(declaration_latest.get("no_go_history"))),
            },
            "escalation_sla_tracking": {
                "sla_hours": SLA_HOURS,
                "cycle_age_hours": round(_age_hours(generated_at), 2),
                "within_sla": _age_hours(generated_at) <= SLA_HOURS,
            },
            "supervision_coverage": {
                "coverage_percentage": coverage,
                "operator_acknowledged": bool(_safe_dict(effective_ack).get("acknowledged", False)),
                "approved_sequence_matches": _safe_list(_safe_dict(effective_ack).get("approved_rehearsal_sequence")) == _approved_sequence(),
                "readiness_declaration_status": readiness_status,
            },
            "readiness_declaration_status": readiness_status,
            "readiness_declaration_grade": _safe_str(declaration_latest.get("declaration_grade"), "watch"),
            "readiness_declaration_score": _safe_float(declaration_latest.get("declaration_score"), 0.0),
            "latest_declaration": declaration_latest,
            "operator_acknowledgement_required": bool(cycle.get("operator_acknowledgment_required", True)),
            "safety_guarantees": _safe_dict(cycle.get("safety_guarantees")),
            "source_paths": _safe_dict(cycle.get("source_paths")),
            "generated_cycle_status": status,
            "warning_indicators": {
                "unattended_rfq_warning": bool(unattended_warnings),
                "supervision_lapse_warning": any(_safe_dict(value) is not None for value in []),
                "escalation_sla_warning": _age_hours(generated_at) > SLA_HOURS,
            },
            "warnings": unattended_warnings,
        }

    def _sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        ack = self._latest_acknowledgement()
        declaration_latest = self.readiness.latest_declaration()
        if declaration_latest.get("status") == "not_found":
            declaration_latest = {}
        sessions = [
            self._session_for_cycle(cycle_path, declaration_latest, ack)
            for cycle_path in _run_dirs(self.cycle_root)
        ]
        sessions.sort(key=lambda item: (_safe_str(item.get("generated_at"), ""), _safe_str(item.get("operator_session_id"), "")), reverse=True)
        return sessions[: max(1, limit)]

    def list_operator_sessions(self, limit: int = 20) -> Dict[str, Any]:
        sessions = self._sessions(limit=limit)
        latest = sessions[0] if sessions else {}
        active_sessions = [session for session in sessions if session.get("active_operator_session")]
        unattended_warnings = [warning for session in sessions for warning in _safe_list(session.get("warnings"))]
        supervision_scores = [_safe_float(session.get("operator_supervision_score"), 0.0) for session in sessions]
        if not sessions:
            status = "not_found"
        elif latest.get("status") == "blocked":
            status = "blocked"
        elif latest.get("status") == "active" and not unattended_warnings:
            status = "ok"
        else:
            status = "watch"
        return {
            "status": status,
            "generated_at": _now_iso(),
            "operator_session_status": status,
            "active_operator_session_count": len(active_sessions),
            "active_operator_sessions": active_sessions,
            "operator_sessions": sessions,
            "operator_session_history": sessions,
            "supervision_score": round(mean(supervision_scores), 2) if supervision_scores else 0.0,
            "supervision_grade": "ready" if supervision_scores and mean(supervision_scores) >= 90.0 else "watch" if supervision_scores and mean(supervision_scores) >= 75.0 else "blocked",
            "supervision_coverage": {
                "active_session_count": len(active_sessions),
                "session_count": len(sessions),
                "coverage_rate": round((len(active_sessions) / len(sessions)) * 100.0, 2) if sessions else 0.0,
            },
            "operator_workload": {
                "assigned_rfq_count": sum(_safe_int(session.get("assigned_rfq_count"), 0) for session in sessions),
                "pending_approval_count": sum(len(_safe_list(session.get("pending_approval_checkpoints"))) for session in sessions),
                "open_escalation_count": sum(1 for session in sessions for item in _safe_list(session.get("pending_approval_checkpoints")) if item),
            },
            "active_sessions_summary": {
                "latest_operator_session_id": _safe_str(latest.get("operator_session_id"), ""),
                "latest_cycle_id": _safe_str(latest.get("cycle_id"), ""),
                "latest_readiness_declaration_status": _safe_str(latest.get("readiness_declaration_status"), "WATCH"),
                "latest_supervision_score": _safe_float(latest.get("operator_supervision_score"), 0.0),
            },
            "warning_indicators": {
                "unattended_rfq_warning": bool(unattended_warnings),
                "supervision_lapse_warning": any(any(_safe_dict(session.get("supervision_lapse_indicators")).values()) for session in sessions),
                "escalation_sla_warning": any(not _safe_dict(session.get("escalation_sla_tracking")).get("within_sla", True) for session in sessions),
                "readiness_declaration_warning": _safe_str(latest.get("readiness_declaration_status"), "WATCH") != "READY_FOR_CONTROLLED_PILOT",
            },
            "warnings": unattended_warnings,
        }

    def latest_operator_session(self) -> Dict[str, Any]:
        response = self.list_operator_sessions(limit=20)
        if response.get("status") == "not_found":
            return {
                "status": "not_found",
                "message": "No supervised operator sessions have been recorded yet.",
                "operator_session": {},
            }
        latest = response.get("operator_sessions", [{}])[0]
        return {
            "status": response.get("status", "ok"),
            "operator_session_status": response.get("operator_session_status", "watch"),
            "operator_session": latest,
            "active_operator_sessions": response.get("active_operator_sessions", []),
            "active_operator_session_count": response.get("active_operator_session_count", 0),
            "supervision_score": response.get("supervision_score", 0.0),
            "supervision_grade": response.get("supervision_grade", "watch"),
            "supervision_coverage": response.get("supervision_coverage", {}),
            "operator_workload": response.get("operator_workload", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }

    def operator_session_history(self, limit: int = 20) -> Dict[str, Any]:
        response = self.list_operator_sessions(limit=limit)
        return {
            "status": response.get("status", "ok"),
            "count": len(response.get("operator_session_history", [])),
            "operator_session_history": response.get("operator_session_history", []),
            "supervision_score": response.get("supervision_score", 0.0),
            "supervision_grade": response.get("supervision_grade", "watch"),
            "operator_workload": response.get("operator_workload", {}),
            "warning_indicators": response.get("warning_indicators", {}),
            "warnings": response.get("warnings", []),
        }
