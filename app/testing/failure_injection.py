from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from pydantic import Field

from app.domain.base import StrictBaseModel, utc_now


class FailureInjection(StrictBaseModel):
    tender_id: str = ""
    blockers: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    injected_failure: str = ""
    interrupted: bool = False
    updated_at: Any = None


def simulate_missing_source_file(tender_id: str, path: str) -> Dict[str, Any]:
    blockers = []
    if not Path(path).exists():
        blockers.append("source file missing")
    return FailureInjection(tender_id=tender_id, blockers=blockers, injected_failure="missing_source_file", updated_at=utc_now()).to_jsonable_dict()


def simulate_missing_pricing_file(tender_id: str, path: str) -> Dict[str, Any]:
    blockers = []
    if not Path(path).exists():
        blockers.append("pricing file missing")
    return FailureInjection(tender_id=tender_id, blockers=blockers, injected_failure="missing_pricing_file", updated_at=utc_now()).to_jsonable_dict()


def simulate_db_write_unavailable(tender_id: str) -> Dict[str, Any]:
    return FailureInjection(tender_id=tender_id, blockers=["db write unavailable"], injected_failure="db_write_unavailable", updated_at=utc_now()).to_jsonable_dict()


def simulate_malformed_json_fixture(tender_id: str) -> Dict[str, Any]:
    return FailureInjection(tender_id=tender_id, blockers=["malformed json fixture"], injected_failure="malformed_json_fixture", updated_at=utc_now()).to_jsonable_dict()


def simulate_invalid_transition(tender_id: str) -> Dict[str, Any]:
    return FailureInjection(tender_id=tender_id, blockers=["invalid workflow transition"], injected_failure="invalid_transition", updated_at=utc_now()).to_jsonable_dict()


def simulate_interrupted_lifecycle(tender_id: str) -> Dict[str, Any]:
    return FailureInjection(tender_id=tender_id, blockers=["interrupted lifecycle"], interrupted=True, injected_failure="interrupted_lifecycle", updated_at=utc_now()).to_jsonable_dict()


def simulate_missing_quote_pack(tender_id: str) -> Dict[str, Any]:
    return FailureInjection(tender_id=tender_id, blockers=["quote pack missing"], injected_failure="missing_quote_pack", updated_at=utc_now()).to_jsonable_dict()
