from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, List, Optional

from app.quote_pack_models import AutoQuotePipelineResponse
from app.services.quote_pack_service import build_quote_pack

class AutoQuotePipelineService:
    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None or value == "":
                return default
            return float(value)
        except Exception:
            return default

    @classmethod
    def _generate_quote_from_rfq(
        cls,
        rfq_data: Dict[str, Any],
        margin_percent: float,
    ) -> Dict[str, Any]:
        items = rfq_data.get("items") or rfq_data.get("line_items") or []
        quoted_items: List[Dict[str, Any]] = []

        if items:
            for idx, item in enumerate(items, start=1):
                qty = cls._safe_float(item.get("quantity"), 1.0)

                base_cost = cls._safe_float(
                    item.get("base_cost")
                    or item.get("estimated_unit_price")
                    or item.get("market_price")
                    or item.get("unit_price"),
                    0.0,
                )

                quoted_unit_price = round(base_cost * (1 + (margin_percent / 100.0)), 2)
                total_price = round(qty * quoted_unit_price, 2)

                quoted_items.append(
                    {
                        "line_no": idx,
                        "description": item.get("description") or item.get("name") or f"Quoted item {idx}",
                        "quantity": qty,
                        "unit": item.get("unit") or "Item",
                        "unit_price": quoted_unit_price,
                        "total_price": total_price,
                        "notes": item.get("notes"),
                    }
                )
        else:
            qty = cls._safe_float(rfq_data.get("quantity"), 1.0)
            base_cost = cls._safe_float(
                rfq_data.get("base_cost")
                or rfq_data.get("estimated_unit_price")
                or rfq_data.get("market_price")
                or rfq_data.get("unit_price"),
                0.0,
            )
            quoted_unit_price = round(base_cost * (1 + (margin_percent / 100.0)), 2)
            total_price = round(qty * quoted_unit_price, 2)

            quoted_items.append(
                {
                    "line_no": 1,
                    "description": rfq_data.get("title") or rfq_data.get("description") or "Supply and delivery item",
                    "quantity": qty,
                    "unit": rfq_data.get("unit") or "Item",
                    "unit_price": quoted_unit_price,
                    "total_price": total_price,
                    "notes": rfq_data.get("specification_summary"),
                }
            )

        subtotal = round(sum(item["total_price"] for item in quoted_items), 2)
        vat_amount = round(subtotal * 0.15, 2)
        total_including_vat = round(subtotal + vat_amount, 2)

        return {
            "line_items": quoted_items,
            "subtotal": subtotal,
            "vat_amount": vat_amount,
            "total_including_vat": total_including_vat,
            "currency": "ZAR",
            "validity_days": 30,
            "delivery_period_days": rfq_data.get("delivery_period_days") or 7,
            "payment_terms": "30 days from statement",
            "pricing_notes": [
                f"Pricing generated using default margin assumption of {margin_percent:.2f}%",
                "VAT calculated at 15%",
            ],
        }

    @staticmethod
    def _send_email_with_attachments(
        recipient_email: str,
        subject: str,
        body: str,
        attachments: List[str],
        cc_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        smtp_host = os.getenv("SMTP_HOST")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        smtp_use_tls = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
        email_from = os.getenv("EMAIL_FROM") or smtp_username

        if not smtp_host or not smtp_username or not smtp_password or not email_from:
            return {
                "success": False,
                "error": "SMTP settings are missing. Please configure SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, and EMAIL_FROM."
            }

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = email_from
        msg["To"] = recipient_email
        if cc_email:
            msg["Cc"] = cc_email
        msg.set_content(body)

        for file_path in attachments:
            if not file_path:
                continue
            with open(file_path, "rb") as f:
                data = f.read()
            filename = os.path.basename(file_path)

            if filename.lower().endswith(".pdf"):
                maintype, subtype = "application", "pdf"
            elif filename.lower().endswith(".docx"):
                maintype, subtype = (
                    "application",
                    "vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            else:
                maintype, subtype = "application", "octet-stream"

            msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=filename)

        recipients = [recipient_email] + ([cc_email] if cc_email else [])

        try:
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_use_tls:
                    server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(msg, to_addrs=recipients)

            return {"success": True}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    @classmethod
    def run_pipeline(
        cls,
        rfq_data: Dict[str, Any],
        recipient_email: str,
        company_data: Optional[Dict[str, Any]] = None,
        cc_email: Optional[str] = None,
        margin_percent: float = 25.0,
        include_docx: bool = True,
        include_pdf: bool = True,
        email_subject: Optional[str] = None,
        email_body: Optional[str] = None,
    ) -> AutoQuotePipelineResponse:
        quote_data = cls._generate_quote_from_rfq(
            rfq_data=rfq_data,
            margin_percent=margin_percent,
        )

        pack_result = build_quote_pack(
            rfq_data=rfq_data,
            quote_data=quote_data,
            company_data=company_data,
            margin_percent=margin_percent,
            include_docx=include_docx,
            include_pdf=include_pdf,
        )

        subject = email_subject or (
            f"Quotation Submission: {pack_result.payload.rfq.tender_number or pack_result.payload.rfq.title}"
        )

        body = email_body or (
            "Dear Sir / Madam,\n\n"
            "Please find attached our quotation pack for your consideration.\n\n"
            f"Tender: {pack_result.payload.rfq.title}\n"
            f"Quote Pack ID: {pack_result.payload.pack_id}\n"
            f"Total Including VAT: R {pack_result.payload.pricing.total_including_vat:,.2f}\n\n"
            "Kind regards,\n"
            f"{pack_result.payload.company.contact_person or 'Lechesa Manaba'}\n"
            f"{pack_result.payload.company.company_name}"
        )

        attachments = []
        if pack_result.pdf_path:
            attachments.append(pack_result.pdf_path)

        email_result = cls._send_email_with_attachments(
            recipient_email=recipient_email,
            cc_email=cc_email,
            subject=subject,
            body=body,
            attachments=attachments,
        )

        return AutoQuotePipelineResponse(
            success=pack_result.success and email_result.get("success", False),
            message="RFQ → Quote → Pack → Email completed" if email_result.get("success") else "Quote pack generated but email failed",
            quote_pack_id=pack_result.payload.pack_id,
            docx_path=None,
            pdf_path=pack_result.pdf_path,
            email_sent=email_result.get("success", False),
            email_error=email_result.get("error"),
            quote_summary={
                "subtotal": pack_result.payload.pricing.subtotal,
                "vat_amount": pack_result.payload.pricing.vat_amount,
                "total_including_vat": pack_result.payload.pricing.total_including_vat,
                "currency": pack_result.payload.pricing.currency,
                "line_count": len(pack_result.payload.line_items),
            },
        )
