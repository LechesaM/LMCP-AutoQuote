from __future__ import annotations

import json
import re
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


import os

DEFAULT_BASE_DIR = "/Users/Shared/LMCP-AutoQuote-Server"

BASE_DIR = Path(
    os.getenv("LMCP_BASE_DIR", DEFAULT_BASE_DIR)
)

MONTHLY_QUOTES_DIR = Path(
    os.getenv(
        "MONTHLY_QUOTES_ROOT",
        str(BASE_DIR / "monthly_quotes")
    )
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _slug(value: str, default: str = "ITEM") -> str:
    text = _safe_str(value, default)
    text = re.sub(r"[^A-Za-z0-9._-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("._-")
    return text or default


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    return str(value)


class MonthlyQuotesStorageService:
    @classmethod
    def _resolve_month_folder(cls, result: Dict[str, Any]) -> str:
        date_candidates = [
            result.get("issue_date"),
            result.get("updated_at"),
            result.get("pipeline_processed_at"),
            result.get("submitted_at"),
        ]
        for candidate in date_candidates:
            text = _safe_str(candidate)
            if len(text) >= 7:
                return text[:7]
        return datetime.now(timezone.utc).strftime("%Y-%m")

    @classmethod
    def _resolve_rfq_reference(cls, result: Dict[str, Any]) -> str:
        source_rfq = _safe_dict(result.get("source_rfq"))
        candidates = [
            result.get("buyer_rfq_number"),
            result.get("rfq_id"),
            result.get("rfq_number"),
            result.get("tender_number"),
            result.get("reference_number"),
            source_rfq.get("buyer_rfq_number"),
            source_rfq.get("rfq_id"),
            source_rfq.get("rfq_number"),
            source_rfq.get("tender_number"),
            source_rfq.get("reference_number"),
            source_rfq.get("bid_number"),
            source_rfq.get("notice_id"),
        ]
        for candidate in candidates:
            text = _safe_str(candidate)
            if text:
                return text
        return "RFQ-UNKNOWN"

    @classmethod
    def _resolve_quote_reference(cls, result: Dict[str, Any]) -> str:
        candidates = [
            result.get("quote_number"),
            result.get("document_number"),
            (_safe_dict(result.get("pdf_result"))).get("quote_number"),
            (_safe_dict(result.get("quote_pack_result"))).get("quote_number"),
        ]
        for candidate in candidates:
            text = _safe_str(candidate)
            if text:
                return text
        return "LMCP-QUOTE"

    @classmethod
    def build_workspace_path(cls, result: Dict[str, Any]) -> Path:
        month_folder = _slug(cls._resolve_month_folder(result), "0000-00")
        rfq_ref = _slug(cls._resolve_rfq_reference(result), "RFQ-UNKNOWN")
        quote_ref = _slug(cls._resolve_quote_reference(result), "LMCP-QUOTE")
        workspace_name = f"{rfq_ref}__{quote_ref}"
        return MONTHLY_QUOTES_DIR / month_folder / workspace_name

    @classmethod
    def ensure_workspace(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        payload = deepcopy(result)
        workspace = cls.build_workspace_path(payload)
        workspace.mkdir(parents=True, exist_ok=True)

        payload["monthly_quotes_folder"] = str(workspace)
        payload["monthly_quotes_month"] = workspace.parent.name
        payload["monthly_quotes_workspace"] = workspace.name
        return payload

    @classmethod
    def copy_file_into_workspace(
        cls,
        result: Dict[str, Any],
        source_file: str,
        target_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = cls.ensure_workspace(result)
        workspace = Path(payload["monthly_quotes_folder"])

        src = Path(source_file)
        if not src.exists() or not src.is_file():
            raise FileNotFoundError(f"Source file not found: {source_file}")

        filename = _slug(target_name or src.name, src.name)
        dest = workspace / filename
        shutil.copy2(src, dest)

        stored_files = _safe_list(payload.get("stored_files"))
        stored_files.append(str(dest))
        payload["stored_files"] = stored_files
        return payload

    @classmethod
    def write_json_snapshot(
        cls,
        result: Dict[str, Any],
        filename: str,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:
        payload = cls.ensure_workspace(result)
        workspace = Path(payload["monthly_quotes_folder"])

        target = workspace / _slug(filename, "snapshot.json")
        with target.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=_json_default)

        stored_files = _safe_list(payload.get("stored_files"))
        stored_files.append(str(target))
        payload["stored_files"] = stored_files
        return payload

    @classmethod
    def persist_pipeline_artifacts(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        payload = cls.ensure_workspace(result)

        source_rfq = _safe_dict(payload.get("source_rfq"))
        quote_data = _safe_dict(payload.get("quote_data"))
        pdf_path = _safe_str(payload.get("final_pdf_path") or payload.get("pdf_path"))

        if source_rfq:
            payload = cls.write_json_snapshot(
                payload,
                "rfq_original.json",
                source_rfq,
            )

        if quote_data:
            payload = cls.write_json_snapshot(
                payload,
                "lmcp_quote_data.json",
                quote_data,
            )

        summary = {
            "rfq_reference": cls._resolve_rfq_reference(payload),
            "quote_reference": cls._resolve_quote_reference(payload),
            "submission_method": _safe_str(payload.get("submission_method"), "unknown"),
            "submission_status": _safe_str(payload.get("submission_status"), "not_submitted"),
            "quote_generated": bool(payload.get("quote_generated")),
            "pdf_generated": bool(payload.get("pdf_generated")),
            "pdf_path": pdf_path,
            "buyer_name": _safe_str(
                (_safe_dict(payload.get("buyer"))).get("company_name")
                or payload.get("buyer_name"),
                "Client",
            ),
            "updated_at": _safe_str(payload.get("updated_at"), _now_iso()),
        }
        payload = cls.write_json_snapshot(
            payload,
            "quote_summary.json",
            summary,
        )

        if pdf_path:
            pdf_source = Path(pdf_path)
            if pdf_source.exists() and pdf_source.is_file():
                payload = cls.copy_file_into_workspace(
                    payload,
                    source_file=pdf_path,
                    target_name="lmcp_quote_pack.pdf",
                )

        return payload

    @classmethod
    def create_empty_comparison_json(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        payload = cls.ensure_workspace(result)

        comparison = {
            "rfq_reference": cls._resolve_rfq_reference(payload),
            "quote_reference": cls._resolve_quote_reference(payload),
            "created_at": _now_iso(),
            "supplier_quotes": [],
            "recommended_supplier": None,
            "comparison_status": "pending_supplier_quotes",
        }

        payload = cls.write_json_snapshot(
            payload,
            "quote_comparison.json",
            comparison,
        )
        return payload
