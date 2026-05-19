from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from pydantic import Field

from app.core.runtime_paths import get_runtime_paths
from app.domain.base import StrictBaseModel, utc_now
from app.monitoring.metrics_service import get_metrics_snapshot
from app.persistence.repositories import TenderOutcomeRepository


class TenderOutcomeStatus(str, Enum):
    UNKNOWN = "unknown"
    SUBMITTED = "submitted"
    AWARDED = "awarded"
    LOST = "lost"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class TenderOutcomeRecord(StrictBaseModel):
    tender_id: str = ""
    workflow_stage: str = ""
    actor: str = ""
    operator: str = ""
    outcome_status: TenderOutcomeStatus = TenderOutcomeStatus.UNKNOWN
    quote_generated: bool = False
    reviewed: bool = False
    proof_captured: bool = False
    submitted_manually: bool = False
    manual_intervention: bool = False
    blocked: bool = False
    blockers: List[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Any = Field(default_factory=utc_now)
    updated_at: Any = Field(default_factory=utc_now)


def _log_path() -> Path:
    return get_runtime_paths().manual_production_file("tender_outcomes.jsonl")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            payload = json.loads(line)
            if isinstance(payload, dict):
                records.append(payload)
    except Exception:
        return []
    return records


def _write_jsonl(path: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record


def record_tender_outcome(record: Dict[str, Any]) -> Dict[str, Any]:
    payload = TenderOutcomeRecord.validate_payload(record).to_jsonable_dict()
    payload.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    payload.setdefault("updated_at", payload["created_at"])
    _write_jsonl(_log_path(), payload)
    try:
        TenderOutcomeRepository(jsonl_path=_log_path()).append_outcome(payload)
    except Exception:
        pass
    return payload


def get_tender_outcome_history(limit: int = 100) -> List[Dict[str, Any]]:
    return _read_jsonl(_log_path())[-max(1, int(limit or 100)) :]


def _per_tender(records: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    latest: Dict[str, Dict[str, Any]] = {}
    for record in records:
        tender_id = str(record.get("tender_id") or "")
        if tender_id and tender_id not in latest:
            latest[tender_id] = record
    return latest


def build_tender_success_analytics(limit: int = 500) -> Dict[str, Any]:
    records = get_tender_outcome_history(limit=limit)
    latest = _per_tender(records)
    processed = len(latest)
    statuses = Counter(str(item.get("outcome_status") or TenderOutcomeStatus.UNKNOWN.value) for item in latest.values())
    quotes_generated = len([item for item in latest.values() if item.get("quote_generated")])
    reviewed = len([item for item in latest.values() if item.get("reviewed")])
    proof_captured = len([item for item in latest.values() if item.get("proof_captured")])
    submitted_manually = len([item for item in latest.values() if item.get("submitted_manually")])
    eligible = len([item for item in latest.values() if not item.get("blocked") and str(item.get("outcome_status")) != TenderOutcomeStatus.CANCELLED.value])
    refused = len([item for item in latest.values() if item.get("blocked") or str(item.get("outcome_status")) == TenderOutcomeStatus.LOST.value])
    outcome_statuses = {status.value: statuses.get(status.value, 0) for status in TenderOutcomeStatus}
    blockers = Counter(blocker for item in latest.values() for blocker in item.get("blockers", []))
    metrics = get_metrics_snapshot().get("metrics", {})
    operator_interventions = int(metrics.get("manual_interventions", 0)) + int(metrics.get("operator_overrides", 0))
    analytics = {
        "status": "ok",
        "checked_at": utc_now(),
        "tender_outcome_summary": {
            "processed": processed,
            "eligible": eligible,
            "refused": refused,
            "quotes_generated": quotes_generated,
            "reviewed_packs": reviewed,
            "proof_captured": proof_captured,
            "submitted_manually": submitted_manually,
            "won": outcome_statuses.get(TenderOutcomeStatus.AWARDED.value, 0),
            "lost": outcome_statuses.get(TenderOutcomeStatus.LOST.value, 0),
            "unknown": outcome_statuses.get(TenderOutcomeStatus.UNKNOWN.value, 0),
            "cancelled": outcome_statuses.get(TenderOutcomeStatus.CANCELLED.value, 0),
            "expired": outcome_statuses.get(TenderOutcomeStatus.EXPIRED.value, 0),
        },
        "quote_conversion_rate": round(quotes_generated / eligible, 4) if eligible else 0.0,
        "submission_completion_rate": round(submitted_manually / max(quotes_generated, 1), 4) if quotes_generated else 0.0,
        "refusal_rate": round(refused / max(processed, 1), 4) if processed else 0.0,
        "blocker_frequency": [{"blocker": blocker, "count": count} for blocker, count in blockers.most_common()],
        "operator_intervention_rate": round(operator_interventions / max(processed, 1), 4) if processed else 0.0,
        "records": list(latest.values()),
    }
    return analytics


def render_tender_success_text(report: Optional[Dict[str, Any]] = None) -> str:
    report = report or build_tender_success_analytics()
    summary = report.get("tender_outcome_summary", {})
    return "\n".join(
        [
            f"RFQs processed: {summary.get('processed', 0)}",
            f"RFQs eligible: {summary.get('eligible', 0)}",
            f"RFQs refused: {summary.get('refused', 0)}",
            f"Quotes generated: {summary.get('quotes_generated', 0)}",
            f"Reviewed packs: {summary.get('reviewed_packs', 0)}",
            f"Proof captured: {summary.get('proof_captured', 0)}",
            f"Submitted manually: {summary.get('submitted_manually', 0)}",
            f"Quote conversion rate: {report.get('quote_conversion_rate', 0.0)}",
            f"Submission completion rate: {report.get('submission_completion_rate', 0.0)}",
            f"Refusal rate: {report.get('refusal_rate', 0.0)}",
        ]
    )
