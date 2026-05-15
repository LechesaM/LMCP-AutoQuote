from __future__ import annotations

import json
import logging
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class SupplierQuoteSelectionService:
    """
    Selects the preferred supplier from ingested supplier quote emails/files.

    Current scoring model is metadata-based and safe:
    - earlier response gets a better score
    - valid PDF attachment gets a better score
    - supplier name/email presence gets a better score

    This is designed to work immediately with the current ingestion output.
    Later, we can extend it with actual price extraction from PDFs/Excel files.
    """

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _safe_str(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @classmethod
    def _parse_received_date_sort_key(cls, value: Any) -> str:
        text = cls._safe_str(value)
        if not text:
            return "9999"

        # keep as text fallback; email date strings still sort deterministically enough for now
        return text

    @classmethod
    def _score_supplier_quote(cls, quote: Dict[str, Any], rank_index: int) -> Dict[str, Any]:
        score = 0
        reasons: List[str] = []

        supplier_name = cls._safe_str(quote.get("supplier_name"))
        supplier_email = cls._safe_str(quote.get("supplier_email"))
        saved_path = cls._safe_str(quote.get("saved_path"))
        content_type = cls._safe_str(quote.get("content_type")).lower()
        subject = cls._safe_str(quote.get("subject"))

        if supplier_name:
            score += 10
            reasons.append("Supplier name present")

        if "@" in supplier_email:
            score += 10
            reasons.append("Supplier email present")

        if saved_path.lower().endswith(".pdf"):
            score += 20
            reasons.append("PDF quote attached")

        if content_type == "application/pdf":
            score += 10
            reasons.append("PDF content type confirmed")

        if subject:
            score += 5
            reasons.append("Email subject present")

        # earlier response gets slightly more weight
        score += max(0, 20 - rank_index)
        reasons.append("Response timing priority applied")

        return {
            "supplier_name": supplier_name or "Unknown Supplier",
            "supplier_email": supplier_email,
            "email_id": cls._safe_str(quote.get("email_id")),
            "subject": subject,
            "saved_path": saved_path,
            "received_date": cls._safe_str(quote.get("received_date")),
            "content_type": content_type,
            "score": score,
            "score_reasons": reasons,
            "rank_index": rank_index,
        }

    @classmethod
    def select_best_supplier(cls, result: Dict[str, Any]) -> Dict[str, Any]:
        payload = deepcopy(result)

        quotes = payload.get("supplier_quote_emails") or []
        if not isinstance(quotes, list) or not quotes:
            payload["supplier_selection"] = {
                "success": False,
                "message": "No supplier quotes available for selection.",
                "selected_supplier": None,
                "ranked_suppliers": [],
                "generated_at": cls._now_iso(),
            }
            payload["selected_supplier"] = None
            payload["supplier_selection_json"] = None
            return payload

        ranked_input = sorted(
            quotes,
            key=lambda q: cls._parse_received_date_sort_key(q.get("received_date")),
        )

        ranked_suppliers: List[Dict[str, Any]] = []
        for index, quote in enumerate(ranked_input, start=1):
            ranked_suppliers.append(cls._score_supplier_quote(quote, index))

        ranked_suppliers.sort(key=lambda x: x["score"], reverse=True)
        selected_supplier = ranked_suppliers[0] if ranked_suppliers else None

        selection_summary = {
            "success": True,
            "message": f"Selected preferred supplier from {len(ranked_suppliers)} supplier quote(s).",
            "selected_supplier": selected_supplier,
            "ranked_suppliers": ranked_suppliers,
            "generated_at": cls._now_iso(),
        }

        payload["supplier_selection"] = selection_summary
        payload["selected_supplier"] = selected_supplier

        selection_json_path = cls._write_selection_json(payload, selection_summary)
        payload["supplier_selection_json"] = selection_json_path

        return payload

    @classmethod
    def _write_selection_json(
        cls,
        payload: Dict[str, Any],
        selection_summary: Dict[str, Any],
    ) -> Optional[str]:
        folder = cls._safe_str(payload.get("supplier_quotes_folder"))
        if not folder:
            return None

        try:
            folder_path = Path(folder)
            folder_path.mkdir(parents=True, exist_ok=True)

            output_path = folder_path / "supplier_selection.json"
            output_path.write_text(
                json.dumps(selection_summary, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            return str(output_path)
        except Exception as exc:
            logger.exception("Failed writing supplier_selection.json: %s", exc)
            return None
