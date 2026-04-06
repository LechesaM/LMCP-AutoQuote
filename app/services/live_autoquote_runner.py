from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from app.services.autoquote_pipeline import AutoQuotePipelineService
from app.services.live_rfq_store import LiveRFQStore


class LiveAutoQuoteRunner:
    _processed_rfqs: Set[str] = set()

    @staticmethod
    def _rfq_key(rfq: Dict[str, Any]) -> str:
        return str(
            rfq.get("rfq_id")
            or rfq.get("id")
            or rfq.get("tender_number")
            or rfq.get("reference_number")
            or rfq.get("title")
            or ""
        ).strip()

    @staticmethod
    def _is_eligible(rfq: Dict[str, Any]) -> bool:
        title = str(rfq.get("title") or "").lower()
        description = str(rfq.get("description") or "").lower()
        text = f"{title} {description}"

        excluded_keywords = [
            "medical consumable",
            "it equipment",
            "laptop",
            "desktop",
            "printer",
            "petrol",
            "diesel",
            "fuel",
        ]

        if any(word in text for word in excluded_keywords):
            return False

        if rfq.get("briefing_required") is True:
            return False

        return True

    @classmethod
    def run(
        cls,
        recipient_email: str,
        company_data: Optional[Dict[str, Any]] = None,
        cc_email: Optional[str] = None,
        margin_percent: float = 25.0,
        include_docx: bool = True,
        include_pdf: bool = True,
        max_items: int = 10,
    ) -> Dict[str, Any]:
        live_data = LiveRFQStore.get_all()
        items: List[Dict[str, Any]] = live_data.get("items") or []

        results: List[Dict[str, Any]] = []
        checked = 0

        for rfq in items:
            if checked >= max_items:
                break

            checked += 1

            rfq_key = cls._rfq_key(rfq)
            if not rfq_key:
                continue

            if rfq_key in cls._processed_rfqs:
                continue

            if not cls._is_eligible(rfq):
                continue

            try:
                result = AutoQuotePipelineService.run_pipeline(
                    rfq_data=rfq,
                    recipient_email=recipient_email,
                    company_data=company_data,
                    cc_email=cc_email,
                    margin_percent=margin_percent,
                    include_docx=include_docx,
                    include_pdf=include_pdf,
                )

                results.append(
                    {
                        "rfq_key": rfq_key,
                        "title": rfq.get("title"),
                        "success": result.success,
                        "quote_pack_id": result.quote_pack_id,
                        "email_sent": result.email_sent,
                        "email_error": result.email_error,
                        "quote_summary": result.quote_summary,
                    }
                )

                if result.success or result.quote_pack_id:
                    cls._processed_rfqs.add(rfq_key)

            except Exception as exc:
                results.append(
                    {
                        "rfq_key": rfq_key,
                        "title": rfq.get("title"),
                        "success": False,
                        "email_sent": False,
                        "email_error": str(exc),
                    }
                )

        return {
            "success": True,
            "checked": checked,
            "processed": len(results),
            "timestamp": datetime.utcnow().isoformat(),
            "results": results,
        }
