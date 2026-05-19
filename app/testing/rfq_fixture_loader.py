from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import Field

from app.domain.base import StrictBaseModel
from app.domain.rfq import RFQDocument, RFQLineItem, RFQRecord


class RFQFixture(StrictBaseModel):
    tender_id: str
    title: str = ""
    buyer_name: str = ""
    province: str = ""
    category: str = ""
    closing_date: str = ""
    source_files: List[str] = Field(default_factory=list)
    line_items: List[Dict[str, Any]] = Field(default_factory=list)
    extracted_text: str = ""
    submission_instructions: str = ""
    estimated_contract_value: float = 0.0
    estimated_profit: float = 0.0
    gross_margin_ratio: float = 0.0
    technical_validation_required: bool = False
    compliance_documents: List[str] = Field(default_factory=list)
    buyer_pricing_schedule: Dict[str, Any] = Field(default_factory=dict)
    expected_exclusion_status: str = ""
    expected_minimum_profit_result: str = ""
    expected_submission_ready: bool = False
    pricing_file: str = ""


def _read_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Fixture {path} must contain a JSON object")
    return data


def _resolve_source(base: Path, value: str) -> str:
    path = Path(str(value)).expanduser()
    if not path.is_absolute():
        path = (base / path).resolve()
    return str(path)


def load_fixture(fixture_path: Path | str) -> Dict[str, Any]:
    path = Path(fixture_path)
    if path.is_dir():
        json_files = sorted(path.glob("*.json"))
        if not json_files:
            raise FileNotFoundError(f"No JSON fixture found in {path}")
        path = json_files[0]
    payload = _read_json(path)
    source_files = [_resolve_source(path.parent, item) for item in payload.get("source_files", []) if str(item).strip()]
    rfq_record = RFQRecord.validate_payload(
        {
            "tender_id": payload.get("tender_id", ""),
            "title": payload.get("title", ""),
            "buyer_name": payload.get("buyer_name", ""),
            "province": payload.get("province", ""),
            "category": payload.get("category", ""),
            "closing_date": payload.get("closing_date") or None,
            "source_path": source_files[0] if source_files else "",
            "extracted_text": payload.get("extracted_text", ""),
            "submission_instructions": payload.get("submission_instructions", ""),
            "estimated_contract_value": payload.get("estimated_contract_value", 0.0),
            "estimated_profit": payload.get("estimated_profit", 0.0),
            "gross_margin_ratio": payload.get("gross_margin_ratio", 0.0),
            "technical_validation_required": bool(payload.get("technical_validation_required", False)),
            "compliance_documents": payload.get("compliance_documents", []),
            "documents": [
                RFQDocument.validate_payload(
                    {
                        "name": Path(source).name,
                        "source_path": source,
                        "source_url": "",
                        "document_type": Path(source).suffix.lstrip("."),
                    }
                ).to_jsonable_dict()
                for source in source_files
            ],
            "line_items": [
                RFQLineItem.validate_payload(item).to_jsonable_dict()
                for item in payload.get("line_items", [])
                if isinstance(item, dict)
            ],
        }
    ).to_jsonable_dict()
    fixture = RFQFixture.validate_payload(
        {
            **payload,
            "source_files": source_files,
        }
    ).to_jsonable_dict()
    fixture["rfq_record"] = rfq_record
    fixture["fixture_path"] = str(path)
    return fixture


def load_fixture_folder(folder_path: Path | str) -> List[Dict[str, Any]]:
    folder = Path(folder_path)
    fixtures: List[Dict[str, Any]] = []
    for path in sorted(folder.glob("*.json")):
        fixtures.append(load_fixture(path))
    return fixtures
