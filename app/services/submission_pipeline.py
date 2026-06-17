from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class SubmissionPipeline:
    @classmethod
    def run(cls) -> Dict[str, Any]:
        rfqs = cls._get_rfqs()

        filtered: List[Dict[str, Any]] = []
        for rfq in rfqs:
            try:
                if cls._is_valid_submission_rfq(rfq):
                    filtered.append(rfq)
            except Exception:
                continue

        results: List[Dict[str, Any]] = []

        for rfq in filtered:
            email_send_result: Dict[str, Any] = {}
            proof_artifacts: Dict[str, Any] = {}
            try:
                quote_data = cls.build_quote_data(rfq)
                pack = cls._generate_quote_pack(rfq, quote_data)
                email_send_result = cls._send_submission_email(rfq, pack)
                proof_artifacts = cls._build_submission_proof_artifacts(
                    rfq=rfq,
                    quote_data=quote_data,
                    pack=pack,
                    email_send_result=email_send_result,
                )
                cls._log_submission_history(
                    rfq,
                    quote_data,
                    pack,
                    status="submitted",
                    email_send_result=email_send_result,
                    proof_artifacts=proof_artifacts,
                )

                results.append(
                    {
                        "rfq": rfq.get("rfq_number") or rfq.get("reference") or rfq.get("id"),
                        "title": rfq.get("title", ""),
                        "status": "submitted",
                        "pdf_path": pack.get("pdf_path", ""),
                        "proof_path": proof_artifacts.get("submission_receipt_pdf_path", ""),
                    }
                )
            except Exception as e:
                try:
                    cls._log_submission_history(
                        rfq,
                        quote_data if "quote_data" in locals() else {},
                        pack if "pack" in locals() else {},
                        status="failed",
                        error=str(e),
                        email_send_result=email_send_result if isinstance(email_send_result, dict) else {},
                        proof_artifacts=proof_artifacts if isinstance(proof_artifacts, dict) else {},
                    )
                except Exception:
                    pass

                results.append(
                    {
                        "rfq": rfq.get("rfq_number") or rfq.get("reference") or rfq.get("id"),
                        "title": rfq.get("title", ""),
                        "status": "failed",
                        "error": str(e),
                        "proof_path": proof_artifacts.get("submission_receipt_pdf_path", ""),
                    }
                )

        submitted_count = len([r for r in results if r["status"] == "submitted"])

        return {
            "status": "success",
            "timestamp": cls._now_iso(),
            "total_rfqs_found": len(rfqs),
            "total_rfqs_filtered": len(filtered),
            "submitted": submitted_count,
            "failed": len(results) - submitted_count,
            "results": results,
        }

    @classmethod
    def _get_rfqs(cls) -> List[Dict[str, Any]]:
        """
        Pull RFQs from the existing LMCP system without assuming one specific harvester function.
        This avoids breaking the project if a previous module name/function changed.
        """
        try:
            from app.services.live_rfq_store import LiveRFQStore

            data = LiveRFQStore.get_all()
            if isinstance(data, dict):
                items = data.get("items", [])
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
        except Exception:
            pass

        try:
            from app.harvester import TenderHarvester  # type: ignore

            if hasattr(TenderHarvester, "fetch_opportunities"):
                items = TenderHarvester.fetch_opportunities()
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]

            if hasattr(TenderHarvester, "harvest"):
                items = TenderHarvester.harvest()
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
        except Exception:
            pass

        try:
            from app.services.tender_harvester import TenderHarvesterService  # type: ignore

            if hasattr(TenderHarvesterService, "harvest"):
                items = TenderHarvesterService.harvest()
                if isinstance(items, list):
                    return [item for item in items if isinstance(item, dict)]
        except Exception:
            pass

        return []

    @classmethod
    def _is_valid_submission_rfq(cls, rfq: Dict[str, Any]) -> bool:
        title = str(rfq.get("title", "")).lower()
        description = str(rfq.get("description", "")).lower()
        combined = f"{title} {description}"

        briefing_required = rfq.get("briefing_required", False)
        if briefing_required is True:
            return False

        submission_email = (
            rfq.get("submission_email")
            or rfq.get("email")
            or rfq.get("contact_email")
            or ""
        )
        if not str(submission_email).strip():
            return False

        supply_keywords = [
            "supply",
            "delivery",
            "supply and delivery",
            "supply & delivery",
            "procurement",
            "supply of",
        ]
        if not any(keyword in combined for keyword in supply_keywords):
            return False

        excluded_keywords = [
            "medical consumables",
            "medical",
            "pharmaceutical",
            "medicine",
            "it equipment",
            "laptop",
            "desktop",
            "server",
            "software",
            "petrol",
            "diesel",
            "fuel",
        ]
        if any(keyword in combined for keyword in excluded_keywords):
            return False

        estimated_profit = cls._estimate_profit(rfq)
        if estimated_profit < 30000:
            return False

        return True

    @classmethod
    def _estimate_profit(cls, rfq: Dict[str, Any]) -> float:
        """
        Uses existing values if available, otherwise estimates based on 25% margin rule.
        """
        for key in ["estimated_profit", "profit_estimate", "expected_profit"]:
            value = rfq.get(key)
            try:
                if value is not None:
                    return float(value)
            except Exception:
                pass

        contract_value = None
        for key in ["estimated_value", "budget", "amount", "contract_value", "total_value"]:
            value = rfq.get(key)
            try:
                if value is not None:
                    contract_value = float(value)
                    break
            except Exception:
                continue

        if contract_value is None:
            return 0.0

        assumed_cost = contract_value / 1.25
        profit = contract_value - assumed_cost
        return round(profit, 2)

    @classmethod
    def build_quote_data(cls, rfq: Dict[str, Any]) -> Dict[str, Any]:
        items = rfq.get("items", [])
        if not isinstance(items, list):
            items = []

        priced_items: List[Dict[str, Any]] = []

        if items:
            for item in items:
                if not isinstance(item, dict):
                    continue

                qty = cls._to_float(item.get("quantity", item.get("qty", 1)), default=1.0)
                base_price = cls._to_float(
                    item.get("estimated_price", item.get("unit_price", 100.0)),
                    default=100.0,
                )
                rate = round(base_price * 1.25, 2)

                priced_items.append(
                    {
                        "description": item.get("description", item.get("name", "Supply item")),
                        "qty": qty,
                        "rate": rate,
                    }
                )
        else:
            estimated_value = cls._to_float(
                rfq.get("estimated_value", rfq.get("budget", 0)),
                default=0.0,
            )

            if estimated_value > 0:
                rate = round(estimated_value, 2)
            else:
                rate = 100.0

            priced_items.append(
                {
                    "description": rfq.get("title", "Supply and delivery"),
                    "qty": 1,
                    "rate": rate,
                }
            )

        rfq_number = (
            str(rfq.get("rfq_number") or rfq.get("reference") or rfq.get("id") or "RFQ")
            .replace("/", "-")
            .replace("\\", "-")
        )

        estimated_revenue = cls._estimate_revenue_from_items(priced_items)
        estimated_cost = round(estimated_revenue / 1.25, 2) if estimated_revenue > 0 else 0.0
        estimated_profit = round(estimated_revenue - estimated_cost, 2) if estimated_revenue > 0 else 0.0
        estimated_margin = round((estimated_profit / estimated_revenue), 4) if estimated_revenue > 0 else 0.0

        return {
            "client_name": rfq.get("issuing_entity", rfq.get("department", "")),
            "rfq_number": rfq_number,
            "quote_number": f"LMCP-{rfq_number}",
            "issue_date": cls._today_str(),
            "subject": rfq.get("title", ""),
            "items": priced_items,
            "estimated_revenue": estimated_revenue,
            "estimated_cost": estimated_cost,
            "estimated_profit": estimated_profit,
            "estimated_margin": estimated_margin,
        }

    @classmethod
    def _estimate_revenue_from_items(cls, items: List[Dict[str, Any]]) -> float:
        total = 0.0
        for item in items:
            qty = cls._to_float(item.get("qty", 1), default=1.0)
            rate = cls._to_float(item.get("rate", 0), default=0.0)
            total += qty * rate
        return round(total, 2)

    @classmethod
    def _generate_quote_pack(
        cls,
        rfq_data: Dict[str, Any],
        quote_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from app.services.quote_pack_service import generate_branded_quote_pack

            pack = generate_branded_quote_pack(
                rfq_data=rfq_data,
                quote_data=quote_data,
            )
            if isinstance(pack, dict):
                pack.setdefault("estimated_revenue", quote_data.get("estimated_revenue", 0.0))
                pack.setdefault("estimated_cost", quote_data.get("estimated_cost", 0.0))
                pack.setdefault("estimated_profit", quote_data.get("estimated_profit", 0.0))
                pack.setdefault("estimated_margin", quote_data.get("estimated_margin", 0.0))
            return pack
        except Exception as e:
            raise RuntimeError(f"Quote pack generation failed: {e}") from e

    @classmethod
    def _send_submission_email(
        cls,
        rfq_data: Dict[str, Any],
        pack: Dict[str, Any],
    ) -> Dict[str, Any]:
        recipient = (
            rfq_data.get("submission_email")
            or rfq_data.get("email")
            or rfq_data.get("contact_email")
            or ""
        )
        if not recipient:
            raise ValueError("No submission email found for RFQ")

        subject = pack.get("email_subject", "Quotation Submission")
        body = pack.get("email_body", "Please find attached our quotation.")
        attachment_path = pack.get("pdf_path", "")
        if not attachment_path:
            raise ValueError("No PDF attachment found for RFQ")

        smtp_host = os.getenv("SMTP_HOST", "")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME", "")
        smtp_password = os.getenv("SMTP_PASSWORD", "")
        sender_email = os.getenv("SMTP_SENDER_EMAIL", smtp_username)
        use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() == "true"
        if not smtp_host:
            raise ValueError("SMTP_HOST is not configured")
        if not sender_email:
            raise ValueError("SMTP sender email is not configured")

        try:
            from app.email_utils import send_email_with_attachment

            message_id = send_email_with_attachment(
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_username=smtp_username,
                smtp_password=smtp_password,
                sender_email=sender_email,
                recipient_email=recipient,
                subject=subject,
                body=body,
                attachment_path=attachment_path,
                use_tls=use_tls,
            )
            return {
                "attempted": True,
                "message": "Email submission sent successfully.",
                "message_id": message_id,
                "used_sender_email": sender_email,
                "used_recipients": [recipient],
                "used_attachments": [attachment_path],
                "submission_channel": str(
                    rfq_data.get("submission_channel")
                    or rfq_data.get("submission_method")
                    or pack.get("submission_channel")
                    or pack.get("submission_method")
                    or "email"
                ).strip()
                or "email",
                "recipient_email": recipient,
                "sent_at_utc": cls._now_iso(),
            }
        except Exception as e:
            raise RuntimeError(f"Email send failed: {e}") from e

    @classmethod
    def _build_submission_proof_artifacts(
        cls,
        *,
        rfq: Dict[str, Any],
        quote_data: Dict[str, Any],
        pack: Dict[str, Any],
        email_send_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            from app.services.submission_proof_artifact_service import build_submission_proof_artifacts
        except Exception as exc:
            return {"status": "unavailable", "error": str(exc)}

        proof_payload: Dict[str, Any] = {
            "rfq_number": rfq.get("rfq_number") or rfq.get("reference") or rfq.get("id") or "",
            "buyer_name": rfq.get("buyer_name") or rfq.get("issuing_entity") or rfq.get("department") or "",
            "title": rfq.get("title") or "",
            "quote_reference": quote_data.get("quote_number") or pack.get("quote_number") or "",
            "submission_email_ready": bool(rfq.get("submission_email") or rfq.get("email") or rfq.get("contact_email")),
            "submission_email_sent": bool(email_send_result.get("attempted")),
            "submission_email_sent_at_utc": email_send_result.get("sent_at_utc") or cls._now_iso(),
            "email_send_result": email_send_result,
            "metadata": {
                "pdf_output_dir": pack.get("quote_folder") or pack.get("quote_pack_dir") or "",
            },
            "quote_pack_pdf_path": str(pack.get("pdf_path") or pack.get("final_pdf_path") or ""),
            "rendered_buyer_pdf_path": str(pack.get("pdf_path") or pack.get("final_pdf_path") or ""),
            "submission_pack_manifest_path": str(pack.get("quote_pack_metadata_path") or ""),
        }

        proof_file = str(pack.get("pdf_path") or pack.get("final_pdf_path") or "").strip()
        proof_payload["proof_file"] = proof_file

        artifacts = build_submission_proof_artifacts(proof_payload)
        proof_artifacts = dict(artifacts.get("submission_proof_artifacts") or {})
        proof_dir = str(artifacts.get("submission_proof_directory") or proof_artifacts.get("proof_directory") or "").strip()
        receipt_json_path = str(artifacts.get("submission_receipt_json_path") or proof_artifacts.get("receipt_json_path") or "").strip()
        receipt_txt_path = str(artifacts.get("submission_receipt_txt_path") or proof_artifacts.get("receipt_txt_path") or "").strip()
        receipt_pdf_path = str(artifacts.get("submission_receipt_pdf_path") or proof_artifacts.get("receipt_pdf_path") or "").strip()
        receipt_text = ""
        if receipt_txt_path:
            try:
                receipt_text = Path(receipt_txt_path).read_text(encoding="utf-8").strip()
            except Exception:
                receipt_text = ""

        submitted_files = [x for x in [
            str(pack.get("pdf_path") or "").strip(),
            str(pack.get("final_pdf_path") or "").strip(),
        ] if x]
        submitted_files.extend([str(x).strip() for x in email_send_result.get("used_attachments", []) if str(x).strip()])

        return {
            "status": "ok",
            "proof_directory": proof_dir,
            "submission_proof_directory": proof_dir,
            "submission_receipt_json_path": receipt_json_path,
            "submission_receipt_txt_path": receipt_txt_path,
            "submission_receipt_pdf_path": receipt_pdf_path,
            "proof_path": receipt_pdf_path or proof_file,
            "buyer_confirmation_reference": str(email_send_result.get("message_id") or "").strip(),
            "receipt_text": receipt_text or str(email_send_result.get("message") or "").strip(),
            "receipt_timestamp": str(email_send_result.get("sent_at_utc") or cls._now_iso()).strip(),
            "submitted_files": submitted_files,
            "submission_channel": str(email_send_result.get("submission_channel") or "").strip() or "email",
            "email_send_result": email_send_result,
            "proof_artifacts": proof_artifacts,
        }

    @classmethod
    def _log_submission_history(
        cls,
        rfq: Dict[str, Any],
        quote_data: Dict[str, Any],
        pack: Dict[str, Any],
        *,
        status: str,
        error: str = "",
        email_send_result: Optional[Dict[str, Any]] = None,
        proof_artifacts: Optional[Dict[str, Any]] = None,
    ) -> None:
        try:
            from app.services.submission_history_service import log_submission_event
        except Exception:
            return

        rfq_number = str(rfq.get("rfq_number") or rfq.get("reference") or rfq.get("id") or "").strip()
        quote_number = str(
            pack.get("quote_number")
            or quote_data.get("quote_number")
            or (f"LMCP-{rfq_number}" if rfq_number else "")
        ).strip()
        recipient = str(
            rfq.get("submission_email")
            or rfq.get("email")
            or rfq.get("contact_email")
            or ""
        ).strip()

        estimated_revenue = cls._to_float(
            pack.get("estimated_revenue", quote_data.get("estimated_revenue", rfq.get("estimated_value", 0.0))),
            default=0.0,
        )
        estimated_cost = cls._to_float(
            pack.get("estimated_cost", quote_data.get("estimated_cost", 0.0)),
            default=0.0,
        )
        estimated_profit = cls._to_float(
            pack.get("estimated_profit", quote_data.get("estimated_profit", 0.0)),
            default=0.0,
        )
        estimated_margin = cls._to_float(
            pack.get("estimated_margin", quote_data.get("estimated_margin", 0.0)),
            default=0.0,
        )

        email_send_result = email_send_result or {}
        proof_artifacts = proof_artifacts or {}
        proof_path = str(
            proof_artifacts.get("proof_path")
            or proof_artifacts.get("submission_receipt_pdf_path")
            or pack.get("proof_path")
            or ""
        ).strip()
        submission_channel = str(
            email_send_result.get("submission_channel")
            or rfq.get("submission_channel")
            or rfq.get("submission_method")
            or pack.get("submission_channel")
            or pack.get("submission_method")
            or "email"
        ).strip() or "email"
        buyer_confirmation_reference = str(
            email_send_result.get("message_id")
            or rfq.get("buyer_confirmation_reference")
            or ""
        ).strip()
        receipt_timestamp = str(email_send_result.get("sent_at_utc") or cls._now_iso()).strip()
        submitted_files = [
            str(x).strip()
            for x in (
                proof_artifacts.get("submitted_files")
                or email_send_result.get("used_attachments")
                or []
            )
            if str(x).strip()
        ]
        receipt_text = str(
            proof_artifacts.get("receipt_text")
            or email_send_result.get("message")
            or error
            or ""
        ).strip()

        if estimated_revenue > 0 and estimated_cost <= 0 and estimated_profit > 0:
            estimated_cost = round(estimated_revenue - estimated_profit, 2)

        if estimated_revenue > 0 and estimated_profit <= 0 and estimated_cost > 0:
            estimated_profit = round(estimated_revenue - estimated_cost, 2)

        if estimated_revenue > 0 and estimated_margin <= 0 and estimated_profit > 0:
            estimated_margin = round(estimated_profit / estimated_revenue, 4)

        payload = {
            "buyer_name": str(rfq.get("issuing_entity") or rfq.get("department") or "").strip(),
            "buyer_rfq_number": rfq_number,
            "quote_number": quote_number,
            "title": str(rfq.get("title") or "").strip(),
            "submission_method": submission_channel,
            "submission_channel": submission_channel,
            "recipient_email": recipient,
            "portal_name": "",
            "status": status,
            "status_message": error or ("Email submission sent successfully." if status == "submitted" else "Submission failed."),
            "document_path": str(pack.get("pdf_path") or "").strip(),
            "proof_path": proof_path,
            "buyer_confirmation_reference": buyer_confirmation_reference,
            "receipt_text": receipt_text,
            "receipt_timestamp": receipt_timestamp,
            "submitted_files": submitted_files,
            "submission_log_path": "",
            "attachments": [str(pack.get("pdf_path") or "").strip()] if str(pack.get("pdf_path") or "").strip() else [],
            "artifacts": [
                str(x).strip()
                for x in [
                    pack.get("pdf_path"),
                    pack.get("quote_pack_metadata_path"),
                ]
                if str(x or "").strip()
            ],
            "source": str(rfq.get("source") or "").strip(),
            "submitted_by": "system",
            "retry_count": 0,
            "raw_result": {
                "status": status,
                "estimated_revenue": estimated_revenue,
                "estimated_cost": estimated_cost,
                "estimated_profit": estimated_profit,
                "estimated_margin": estimated_margin,
                "quote_number": quote_number,
                "buyer_rfq_number": rfq_number,
                "pdf_path": str(pack.get("pdf_path") or "").strip(),
                "quote_pack_metadata_path": str(pack.get("quote_pack_metadata_path") or "").strip(),
                "proof_path": proof_path,
                "buyer_confirmation_reference": buyer_confirmation_reference,
                "receipt_text": receipt_text,
                "receipt_timestamp": receipt_timestamp,
                "submitted_files": submitted_files,
                "submission_channel": submission_channel,
                "error": error,
            },
            "metadata": {
                "submission_channel": submission_channel,
                "estimated_revenue": estimated_revenue,
                "estimated_cost": estimated_cost,
                "estimated_profit": estimated_profit,
                "estimated_margin": estimated_margin,
                "quote_folder": str(pack.get("quote_folder") or "").strip(),
                "quote_pack_dir": str(pack.get("quote_pack_dir") or "").strip(),
                "proof_path": proof_path,
                "buyer_confirmation_reference": buyer_confirmation_reference,
                "receipt_text": receipt_text,
                "receipt_timestamp": receipt_timestamp,
                "submitted_files": submitted_files,
            },
            "proof_artifacts": proof_artifacts,
            "email_send_result": email_send_result,
        }

        log_submission_event(payload)

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except Exception:
            return default

    @staticmethod
    def _today_str() -> str:
        return datetime.now().strftime("%Y-%m-%d")

    @staticmethod
    def _now_iso() -> str:
        return datetime.now().isoformat()

