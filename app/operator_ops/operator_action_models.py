from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional


@dataclass
class OperatorActionRequest:
    operator_id: str
    tender_id: str
    action: str
    note: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    target_operator_id: str = ""

    @classmethod
    def validate_payload(cls, payload: Mapping[str, Any]) -> "OperatorActionRequest":
        data = dict(payload or {})
        operator_id = str(data.get("operator_id") or "").strip()
        tender_id = str(data.get("tender_id") or "").strip()
        action = str(data.get("action") or "").strip()
        if not operator_id:
            raise ValueError("operator_id is required")
        if not tender_id:
            raise ValueError("tender_id is required")
        if not action:
            raise ValueError("action is required")
        return cls(
            operator_id=operator_id,
            tender_id=tender_id,
            action=action,
            note=str(data.get("note") or "").strip(),
            details=dict(data.get("details") or {}),
            target_operator_id=str(data.get("target_operator_id") or "").strip(),
        )

    def model_dump(self) -> Dict[str, Any]:
        return {
            "operator_id": self.operator_id,
            "tender_id": self.tender_id,
            "action": self.action,
            "note": self.note,
            "details": dict(self.details or {}),
            "target_operator_id": self.target_operator_id,
        }

