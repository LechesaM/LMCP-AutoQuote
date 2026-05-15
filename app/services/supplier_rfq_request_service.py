from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from app.services.email_submission_service import EmailSubmissionService

logger = logging.getLogger(__name__)


class SupplierRFQRequestService:
    @classmethod
    def _safe_str(cls, value: Any, default: str = "") -> str:
        if value is None:
            return default
        text = str(value).strip()
        return text if text else default

    @classmethod
    def _normalize_suppliers(cls, suppliers: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        normalized: List[Dict[str, Any]] = []

        for supplier in suppliers or []:
            if not isinstance(supplier, dict):
                continue

            email_address = cls._safe_str(
                supplier.get("email")
                or supplier.get("supplier_email")
                or supplier.get("address")
            )
            if "@" not in email_address:
                continue

            normalized.append(
                {
                    "name": cls._safe_str(supplier.get("name") or supplier.get("supplier_name")),
                    "company": cls._safe_str(supplier.get("company") or supplier.get("supplier_company")),
                    "email": email_address,
                    "cc_email": cls._safe_str(supplier.get("cc_email")),
                }
            )

        return normalized

    @classmethod
    def _build_subject(
        cls,
        *,
        buyer_rfq_number: str,
        lmcp_quote_number: str,
        buyer_title: str = "",
    ) -> str:
        title = cls._safe_str(buyer_title)
        if title:
            return f"Request for Supplier Quote - {buyer_rfq_number} - {lmcp_quote_number} - {title}"
        return f"Request for Supplier Quote - {buyer_rfq_number} - {lmcp_quote_number}"

    @classmethod
    def _build_body(
        cls,
        *,
        supplier_name: str,
        buyer_name: str,
        buyer_rfq_number: str,
        lmcp_quote_number: str,
        buyer_title: str,
        requested_items: Optional[List[str]] = None,
    ) -> str:
        greeting_name = supplier_name or "Supplier"
        buyer_name = cls._safe_str(buyer_name)
        buyer_title = cls._safe_str(buyer_title) or "RFQ"
        requested_items = requested_items or []

        lines = [
            f"Dear {greeting_name},",
            "",
            "Please provide a quotation based on the attached specification.",
            "",
            f"Buyer RFQ Number: {buyer_rfq_number}",
            f"LMCP Quote Number: {lmcp_quote_number}",
            f"Subject / Title: {buyer_title}",
        ]

        # Only include buyer name if it is a real value
        if buyer_name and buyer_name.lower() not in {
            "buyer / issuing entity",
            "buyer",
            "issuing entity",
            "client",
        }:
            lines.insert(4, f"Buyer: {buyer_name}")

        if requested_items:
            lines.append("")
            lines.append("Requested items:")
            for item in requested_items:
                if cls._safe_str(item):
                    lines.append(f"- {cls._safe_str(item)}")

        lines.extend(
            [
                "",
                "Please attach your quotation in PDF format and name the file using either our Buyer RFQ number or the LMCP quote number, where applicable.",
                "",
                "Regards,",
                "",
                "Lechesa Manaba Consulting and Projects (Pty) Ltd",
            ]
        )

        return "\n".join(lines)

    @classmethod
    def send_supplier_requests(
        cls,
        *,
        buyer_rfq_number: str,
        lmcp_quote_number: str,
        suppliers: List[Dict[str, Any]],
        buyer_name: str = "",
        buyer_title: str = "",
        requested_items: Optional[List[str]] = None,
        attachment_paths: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        normalized_suppliers = cls._normalize_suppliers(suppliers)

        results: List[Dict[str, Any]] = []

        if not normalized_suppliers:
            return {
                "success": False,
                "message": "No valid supplier emails provided.",
                "count": 0,
                "results": [],
            }

        # Suppress placeholder buyer names
        normalized_buyer_name = cls._safe_str(buyer_name)
        if normalized_buyer_name.lower() == "buyer / issuing entity":
            normalized_buyer_name = ""

        for supplier in normalized_suppliers:
            try:
                subject = cls._build_subject(
                    buyer_rfq_number=buyer_rfq_number,
                    lmcp_quote_number=lmcp_quote_number,
                    buyer_title=buyer_title,
                )
                body = cls._build_body(
                    supplier_name=supplier["name"],
                    buyer_name=normalized_buyer_name,
                    buyer_rfq_number=buyer_rfq_number,
                    lmcp_quote_number=lmcp_quote_number,
                    buyer_title=buyer_title,
                    requested_items=requested_items,
                )

                send_result = EmailSubmissionService.send_supplier_rfq_email(
                    to_email=supplier["email"],
                    subject=subject,
                    body=body,
                    buyer_rfq_number=buyer_rfq_number,
                    lmcp_quote_number=lmcp_quote_number,
                    supplier_name=supplier["name"],
                    supplier_company=supplier["company"],
                    buyer_name=normalized_buyer_name,
                    buyer_title=buyer_title,
                    requested_items=requested_items or [],
                    attachment_paths=attachment_paths,
                    cc_email=supplier["cc_email"] or None,
                )

                results.append(
                    {
                        "success": True,
                        "supplier_name": supplier["name"],
                        "supplier_company": supplier["company"],
                        "supplier_email": supplier["email"],
                        "result": send_result,
                    }
                )

            except Exception as exc:
                logger.exception("Failed sending supplier RFQ request to %s", supplier["email"])
                results.append(
                    {
                        "success": False,
                        "supplier_name": supplier["name"],
                        "supplier_company": supplier["company"],
                        "supplier_email": supplier["email"],
                        "error": str(exc),
                    }
                )

        success_count = sum(1 for item in results if item.get("success"))
        return {
            "success": success_count > 0,
            "message": f"Sent {success_count} supplier RFQ request(s) out of {len(results)}.",
            "count": success_count,
            "results": results,
        }
