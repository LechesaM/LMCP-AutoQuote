from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

try:
    from pydantic import BaseModel, ConfigDict
    from pydantic import Field
    from pydantic import field_validator

    PYDANTIC_V2 = True
except ImportError:  # pragma: no cover
    from pydantic import BaseModel, Field, validator

    ConfigDict = dict  # type: ignore
    PYDANTIC_V2 = False


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_string(value: Any) -> str:
    return str(value or "").strip()


def normalize_amount(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return float(default)
    if isinstance(value, str):
        value = value.replace("R", "").replace("ZAR", "").replace("zar", "").replace(",", "").strip()
    try:
        return round(float(value), 2)
    except Exception:
        return round(float(default), 2)


class StrictBaseModel(BaseModel):
    if PYDANTIC_V2:
        model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)  # type: ignore[arg-type]

    else:  # pragma: no cover
        class Config:
            extra = "forbid"
            anystr_strip_whitespace = True
            validate_assignment = True

    @classmethod
    def validate_payload(cls, payload: Dict[str, Any]) -> "StrictBaseModel":
        if hasattr(cls, "model_validate"):
            return cls.model_validate(payload)  # type: ignore[attr-defined]
        return cls.parse_obj(payload)

    def to_jsonable_dict(self) -> Dict[str, Any]:
        if hasattr(self, "model_dump"):
            return self.model_dump(mode="json")  # type: ignore[attr-defined]
        return self.dict()

    if PYDANTIC_V2:

        @field_validator("*", mode="before")
        @classmethod
        def _normalize_strings(cls, value: Any) -> Any:
            return value.strip() if isinstance(value, str) else value

    else:  # pragma: no cover

        @validator("*", pre=True)
        def _normalize_strings(cls, value: Any) -> Any:  # type: ignore[no-redef]
            return value.strip() if isinstance(value, str) else value
