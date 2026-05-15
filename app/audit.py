from __future__ import annotations

import json
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models import AuditLog


def safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        return json.dumps({"raw": str(value)}, ensure_ascii=False)


def write_audit_log(
    db: Session,
    event_type: str,
    status: str,
    message: str = "",
    opportunity_id: Optional[int] = None,
    quote_id: Optional[int] = None,
    job_id: Optional[str] = None,
    source: Optional[str] = "autonomous_engine",
    detail: Any = None,
) -> AuditLog:
    row = AuditLog(
        event_type=event_type,
        status=status,
        message=message,
        opportunity_id=opportunity_id,
        quote_id=quote_id,
        job_id=job_id,
        source=source,
        detail_json=safe_json_dumps(detail) if detail is not None else None,
    )
    db.add(row)
    db.flush()
    return row
