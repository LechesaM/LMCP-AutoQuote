from __future__ import annotations

from datetime import datetime
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
            try:
                quote_data = cls.build_quote_data(rfq)
                pack = cls._generate_quote_pack(rfq, quote_data)
                cls._send_submission_email(rfq, pack)
                cls._log_submission_history(rfq, quote_data, pack, status="submitted")

                results.append(
                    {
                        "rfq": rfq.get("rfq_number") or rfq.get("reference") or rfq.get("id"),
                        "title": rfq.get("title", ""),
                        "status": "submitted",
                        "pdf_path": pack.get("pdf_path", ""),
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
                    )
                except Exception:
                    pass

                results.append(
                    {
                        "rfq": rfq.get("rfq_number") or rfq.get("reference") or rfq.get("id"),
                        "title": rfq.get("title", ""),
                        "status": "failed",
                        "error": str(e),
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
    ) -> None:
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

        try:
            from app.email_api import send_email_with_attachment  # type: ignore

            send_email_with_attachment(
                to=recipient,
                subject=subject,
                body=body,
                attachment_path=attachment_path,
            )
            return
        except Exception:
            pass

        try:
            from app.services.email_api import send_email_with_attachment  # type: ignore

            send_email_with_attachment(
                to=recipient,
                subject=subject,
                body=body,
                attachment_path=attachment_path,
            )
            return
        except Exception as e:
            raise RuntimeError(f"Email send failed: {e}") from e

    @classmethod
    def _log_submission_history(
        cls,
        rfq: Dict[str, Any],
        quote_data: Dict[str, Any],
        pack: Dict[str, Any],
        *,
        status: str,
        error: str = "",
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
            "submission_method": "email",
            "recipient_email": recipient,
            "portal_name": "",
            "status": status,
            "status_message": error or ("Email submission sent successfully." if status == "submitted" else "Submission failed."),
            "document_path": str(pack.get("pdf_path") or "").strip(),
            "proof_path": "",
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
                "error": error,
            },
            "metadata": {
                "submission_channel": "email",
                "estimated_revenue": estimated_revenue,
                "estimated_cost": estimated_cost,
                "estimated_profit": estimated_profit,
                "estimated_margin": estimated_margin,
                "quote_folder": str(pack.get("quote_folder") or "").strip(),
                "quote_pack_dir": str(pack.get("quote_pack_dir") or "").strip(),
            },
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


