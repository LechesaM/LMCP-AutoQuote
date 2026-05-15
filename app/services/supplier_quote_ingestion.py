from __future__ import annotations

import json
import mimetypes
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.monthly_quotes_storage import MonthlyQuotesStorageService


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


def _slug_filename(value: str, default: str = "file.pdf") -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in _safe_str(value, default))
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    cleaned = cleaned.strip("._")
    return cleaned or default


class SupplierQuoteIngestionService:
    @classmethod
    def ingest_supplier_quote_files(
        cls,
        result: Dict[str, Any],
        supplier_files: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        payload = MonthlyQuotesStorageService.ensure_workspace(result)
        workspace = Path(payload["monthly_quotes_folder"])

        ingested_quotes = _safe_list(payload.get("supplier_quotes"))
        created_files = _safe_list(payload.get("stored_files"))

        for index, supplier_file in enumerate(supplier_files, start=1):
            entry = _safe_dict(supplier_file)
            source_path = _safe_str(entry.get("file_path"))
            supplier_name = _safe_str(entry.get("supplier_name"), f"supplier_{index}")
            supplier_email = _safe_str(entry.get("supplier_email"))
            supplier_price = entry.get("quoted_total")
            notes = _safe_str(entry.get("notes"))

            if not source_path:
                continue

            src = Path(source_path)
            if not src.exists() or not src.is_file():
                continue

            original_ext = src.suffix or ".pdf"
            target_filename = _slug_filename(
                entry.get("target_name") or f"supplier_quote_{index}_{supplier_name}{original_ext}",
                f"supplier_quote_{index}{original_ext}",
            )
            dest = workspace / target_filename
            shutil.copy2(src, dest)

            content_type, _ = mimetypes.guess_type(str(dest))
            quote_record = {
                "index": len(ingested_quotes) + 1,
                "supplier_name": supplier_name,
                "supplier_email": supplier_email,
                "quoted_total": supplier_price,
                "notes": notes,
                "source_file": str(src),
                "stored_file": str(dest),
                "stored_filename": dest.name,
                "content_type": content_type or "application/octet-stream",
                "ingested_at": _now_iso(),
            }

            ingested_quotes.append(quote_record)
            created_files.append(str(dest))

        payload["supplier_quotes"] = ingested_quotes
        payload["stored_files"] = created_files

        cls._write_supplier_quotes_manifest(payload)
        cls._write_quote_comparison(payload)

        return payload

    @classmethod
    def _write_supplier_quotes_manifest(cls, result: Dict[str, Any]) -> None:
        workspace = Path(result["monthly_quotes_folder"])
        supplier_quotes = _safe_list(result.get("supplier_quotes"))

        manifest = {
            "created_at": _now_iso(),
            "supplier_quotes_count": len(supplier_quotes),
            "supplier_quotes": supplier_quotes,
        }

        target = workspace / "supplier_quotes_manifest.json"
        with target.open("w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

    @classmethod
    def _write_quote_comparison(cls, result: Dict[str, Any]) -> None:
        workspace = Path(result["monthly_quotes_folder"])
        supplier_quotes = _safe_list(result.get("supplier_quotes"))

        ranked_quotes = []
        for quote in supplier_quotes:
            entry = _safe_dict(quote)
            total = entry.get("quoted_total")
            ranked_quotes.append(
                {
                    "supplier_name": _safe_str(entry.get("supplier_name")),
                    "supplier_email": _safe_str(entry.get("supplier_email")),
                    "quoted_total": total,
                    "stored_filename": _safe_str(entry.get("stored_filename")),
                    "notes": _safe_str(entry.get("notes")),
                }
            )

        def _sort_key(item: Dict[str, Any]) -> float:
            try:
                return float(item.get("quoted_total"))
            except Exception:
                return 999999999.0

        ranked_quotes = sorted(ranked_quotes, key=_sort_key)

        recommended_supplier = ranked_quotes[0] if ranked_quotes else None

        comparison = {
            "created_at": _now_iso(),
            "rfq_reference": _safe_str(
                result.get("buyer_rfq_number") or result.get("rfq_id") or result.get("rfq_number"),
                "RFQ-UNKNOWN",
            ),
            "quote_reference": _safe_str(
                result.get("quote_number") or result.get("document_number"),
                "LMCP-QUOTE",
            ),
            "supplier_quotes_count": len(ranked_quotes),
            "supplier_quotes": ranked_quotes,
            "recommended_supplier": recommended_supplier,
            "comparison_status": "ready" if ranked_quotes else "pending_supplier_quotes",
        }

        target = workspace / "quote_comparison.json"
        with target.open("w", encoding="utf-8") as f:
            json.dump(comparison, f, indent=2, ensure_ascii=False)
