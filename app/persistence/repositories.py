from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from app.persistence import db
from app.persistence.models import (
    ApprovalRecordEntity,
    AuditEventEntity,
    PersistenceEntity,
    PricingDecisionEntity,
    QuotePackEntity,
    SubmissionProofEntity,
    SubmissionReviewEntity,
    WorkflowEventRecord,
    WorkflowStateRecord,
)

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _safe_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _read_jsonl_records(path: Optional[Path]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    if not path or not path.exists():
        return records
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


def _to_row_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    payload = json.loads(row["payload_json"]) if row["payload_json"] else {}
    result = dict(payload) if isinstance(payload, dict) else {"payload": payload}
    for key in row.keys():
        if key == "payload_json":
            continue
        value = row[key]
        if key not in result:
            result[key] = value
    result["payload"] = payload if isinstance(payload, dict) else {}
    return result


class BaseRepository:
    table_name: str = ""
    jsonl_path: Optional[Path] = None

    def __init__(self, *, jsonl_path: Optional[Path] = None) -> None:
        if jsonl_path is not None:
            self.jsonl_path = jsonl_path

    def _insert(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record or {})
        payload.setdefault("created_at", _now_iso())
        payload.setdefault("updated_at", payload["created_at"])
        payload_json = json.dumps(payload.get("payload") or payload, ensure_ascii=False, default=str)
        with db.connection_scope() as connection:
            connection.execute(
                f"""
                INSERT INTO {self.table_name} (
                    tender_id, workflow_stage, actor, operator, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _safe_str(payload.get("tender_id")),
                    _safe_str(payload.get("workflow_stage")),
                    _safe_str(payload.get("actor")),
                    _safe_str(payload.get("operator")),
                    payload_json,
                    _safe_str(payload.get("created_at")),
                    _safe_str(payload.get("updated_at")),
                ),
            )
        return payload

    def append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self._insert(record)

    def fetch_by_tender_id(self, tender_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with db.connection_scope() as connection:
                rows = connection.execute(
                    f"""
                    SELECT *
                    FROM {self.table_name}
                    WHERE tender_id = ?
                    ORDER BY created_at ASC, id ASC
                    LIMIT ?
                    """,
                    (_safe_str(tender_id), int(limit or 100)),
                ).fetchall()
            return [_to_row_dict(row) for row in rows]
        except Exception:
            logger.warning("DB fetch failed for %s, falling back to JSONL", self.table_name, exc_info=True)
            return self._read_jsonl_fallback(tender_id, limit)

    def fetch_latest(self, tender_id: str) -> Dict[str, Any]:
        history = self.fetch_by_tender_id(tender_id, limit=1)
        return history[-1] if history else {}

    def fetch_history(self, tender_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self.fetch_by_tender_id(tender_id, limit=limit)

    def fetch_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with db.connection_scope() as connection:
                rows = connection.execute(
                    f"""
                    SELECT *
                    FROM {self.table_name}
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (int(limit or 100),),
                ).fetchall()
            return [_to_row_dict(row) for row in rows]
        except Exception:
            logger.warning("DB recent fetch failed for %s, falling back to JSONL", self.table_name, exc_info=True)
            return self._read_jsonl_fallback("", limit)

    def _read_jsonl_fallback(self, tender_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.jsonl_path or not self.jsonl_path.exists():
            return []
        try:
            items: List[Dict[str, Any]] = []
            for line in self.jsonl_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                payload = json.loads(line)
                if isinstance(payload, dict) and _safe_str(payload.get("tender_id")) == _safe_str(tender_id):
                    items.append(payload)
            return items[-max(1, int(limit or 100)) :]
        except Exception:
            return []


class WorkflowRepository(BaseRepository):
    table_name = "workflow_state_records"
    jsonl_path = None

    def append_state(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record or {})
        payload.setdefault("workflow_stage", _safe_str(payload.get("stage") or payload.get("workflow_stage")))
        payload.setdefault("payload", payload.get("details") or {})
        return self.append(payload)

    def append_event(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record or {})
        payload.setdefault("workflow_stage", _safe_str(payload.get("to_stage") or payload.get("workflow_stage")))
        payload.setdefault("operator", _safe_str(payload.get("actor")))
        payload.setdefault("payload", payload.get("details") or {})
        payload.setdefault("created_at", payload.get("transitioned_at") or _now_iso())
        payload.setdefault("updated_at", payload.get("transitioned_at") or payload["created_at"])
        with db.connection_scope() as connection:
            connection.execute(
                """
                INSERT INTO workflow_event_records (
                    tender_id, workflow_stage, from_stage, to_stage, actor, operator, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _safe_str(payload.get("tender_id")),
                    _safe_str(payload.get("workflow_stage")),
                    _safe_str(payload.get("from_stage")),
                    _safe_str(payload.get("to_stage")),
                    _safe_str(payload.get("actor")),
                    _safe_str(payload.get("operator") or payload.get("actor")),
                    json.dumps(payload.get("payload") or payload, ensure_ascii=False, default=str),
                    _safe_str(payload.get("created_at")),
                    _safe_str(payload.get("updated_at")),
                ),
            )
        return payload

    def fetch_latest_state(self, tender_id: str) -> Dict[str, Any]:
        try:
            with db.connection_scope() as connection:
                row = connection.execute(
                    """
                    SELECT *
                    FROM workflow_state_records
                    WHERE tender_id = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (_safe_str(tender_id),),
                ).fetchone()
            if not row:
                return {}
            data = _to_row_dict(row)
            return {
                "tender_id": data.get("tender_id", ""),
                "stage": data.get("workflow_stage") or data.get("stage") or "",
                "updated_at": data.get("updated_at") or data.get("created_at") or "",
                "details": data.get("payload") or {},
            }
        except Exception:
            logger.warning("DB workflow state lookup failed, falling back to JSONL", exc_info=True)
            return self._jsonl_latest_state(tender_id)

    def fetch_history(self, tender_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        history = super().fetch_by_tender_id(tender_id, limit=limit)
        normalized: List[Dict[str, Any]] = []
        for item in history:
            normalized.append(
                {
                    "tender_id": item.get("tender_id", ""),
                    "stage": item.get("workflow_stage") or item.get("stage") or "",
                    "updated_at": item.get("updated_at") or item.get("created_at") or "",
                    "details": item.get("payload") or {},
                }
            )
        return normalized

    def fetch_recent(self, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with db.connection_scope() as connection:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM workflow_state_records
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (int(limit or 100),),
                ).fetchall()
            return [
                {
                    "tender_id": _to_row_dict(row).get("tender_id", ""),
                    "stage": _to_row_dict(row).get("workflow_stage") or "",
                    "updated_at": _to_row_dict(row).get("updated_at") or _to_row_dict(row).get("created_at") or "",
                    "details": _to_row_dict(row).get("payload") or {},
                }
                for row in rows
            ]
        except Exception:
            logger.warning("DB workflow state recent fetch failed, falling back to JSONL", exc_info=True)
            return [
                {
                    "tender_id": item.get("tender_id", ""),
                    "stage": item.get("stage") or item.get("workflow_stage") or "",
                    "updated_at": item.get("updated_at") or item.get("created_at") or "",
                    "details": item.get("details") or item.get("payload") or {},
                }
                for item in reversed(_read_jsonl_records(self.jsonl_path))
            ]

    def _jsonl_latest_state(self, tender_id: str) -> Dict[str, Any]:
        if self.jsonl_path and self.jsonl_path.exists():
            try:
                for line in reversed(self.jsonl_path.read_text(encoding="utf-8").splitlines()):
                    line = line.strip()
                    if not line:
                        continue
                    payload = json.loads(line)
                    if isinstance(payload, dict) and _safe_str(payload.get("tender_id")) == _safe_str(tender_id):
                        return payload
            except Exception:
                return {}
        return {}


class ApprovalRepository(BaseRepository):
    table_name = "approval_record_entities"


class SubmissionRepository(BaseRepository):
    table_name = "submission_review_entities"

    def append_review(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self.append(record)

    def append_proof(self, record: Dict[str, Any]) -> Dict[str, Any]:
        with db.connection_scope() as connection:
            payload = dict(record or {})
            payload.setdefault("created_at", payload.get("timestamp") or _now_iso())
            payload.setdefault("updated_at", payload.get("created_at"))
            connection.execute(
                """
                INSERT INTO submission_proof_entities (
                    tender_id, workflow_stage, actor, operator, payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _safe_str(payload.get("tender_id")),
                    _safe_str(payload.get("workflow_stage") or "proof_recorded"),
                    _safe_str(payload.get("actor") or payload.get("submitted_by")),
                    _safe_str(payload.get("operator") or payload.get("submitted_by")),
                    json.dumps(payload.get("payload") or payload, ensure_ascii=False, default=str),
                    _safe_str(payload.get("created_at")),
                    _safe_str(payload.get("updated_at")),
                ),
            )
        return payload


class AuditRepository(BaseRepository):
    table_name = "audit_event_entities"

    def append_audit_event(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record or {})
        payload.setdefault("created_at", payload.get("created_at") or _now_iso())
        payload.setdefault("updated_at", payload.get("updated_at") or payload["created_at"])
        with db.connection_scope() as connection:
            connection.execute(
                """
                INSERT INTO audit_event_entities (
                    tender_id, workflow_stage, actor, operator, event_type, source, severity, quote_number,
                    payload_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _safe_str(payload.get("tender_id") or payload.get("buyer_rfq_number")),
                    _safe_str(payload.get("workflow_stage")),
                    _safe_str(payload.get("actor")),
                    _safe_str(payload.get("operator") or payload.get("source")),
                    _safe_str(payload.get("event_type")),
                    _safe_str(payload.get("source")),
                    _safe_str(payload.get("severity")),
                    _safe_str(payload.get("quote_number")),
                    json.dumps(payload.get("payload") or payload, ensure_ascii=False, default=str),
                    _safe_str(payload.get("created_at")),
                    _safe_str(payload.get("updated_at")),
                ),
            )
        return payload

    def fetch_history(self, tender_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self.fetch_by_tender_id(tender_id, limit=limit)


class PricingRepository(BaseRepository):
    table_name = "pricing_decision_entities"

    def append_decision(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self.append(record)


class QuoteRepository(BaseRepository):
    table_name = "quote_pack_entities"

    def append_quote_pack(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self.append(record)
