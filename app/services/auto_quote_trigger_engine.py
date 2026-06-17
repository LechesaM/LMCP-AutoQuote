from __future__ import annotations

import copy
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class AutoQuoteTriggerEngine:
    EXCLUDED_KEYWORDS = [
        "medical",
        "pharmaceutical",
        "pharmacy",
        "clinic",
        "hospital",
        "syringe",
        "bandage",
        "medication",
        "medicine",
        "surgical",
        "vaccines",
        "laboratory reagents",
        "reagent",
        "diagnostic kits",
        "laptop",
        "computer",
        "desktop",
        "printer",
        "server",
        "router",
        "switch",
        "monitor",
        "ups",
        "tablet",
        "software",
        "software license",
        "licensing",
        "licence renewal",
        "it equipment",
        "ict",
        "information technology",
        "petrol",
        "diesel",
        "fuel",
        "lubricants",
        "catering",
        "meals",
        "refreshments",
        "food parcels",
        "cooked meals",
        "kitchen services",
        "construction",
        "civil works",
        "building works",
        "renovation",
        "maintenance of building",
        "paving",
        "plumbing works",
        "electrical works",
        "roof repairs",
        "painting works",
    ]

    SUPPLY_HINTS = [
        "supply",
        "supply and delivery",
        "delivery",
        "supply, delivery",
        "procurement of",
        "purchase of",
        "appointment for supply",
        "appointment of service provider for supply",
    ]

    @classmethod
    def process_batch(
        cls,
        rfqs: List[Dict[str, Any]],
        source_name: str = "unknown",
        trigger_quotes: bool = True,
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []

        for rfq in rfqs or []:
            if not isinstance(rfq, dict):
                continue

            processed = cls.process_single_rfq(
                rfq=rfq,
                source_name=source_name,
                trigger_quote=trigger_quotes,
            )
            results.append(processed)

        return results

    @classmethod
    def process_single_rfq(
        cls,
        rfq: Dict[str, Any],
        source_name: str = "unknown",
        trigger_quote: bool = True,
    ) -> Dict[str, Any]:
        payload = cls._normalize_rfq(rfq or {})
        payload["source_name"] = payload.get("source_name") or source_name

        eligibility = cls._evaluate_eligibility(payload)
        payload.update(eligibility)

        if payload.get("eligible") and payload.get("quote_ready"):
            if trigger_quote:
                trigger_result = cls._trigger_pipeline(payload)
                payload.update(trigger_result)
            else:
                payload.setdefault("pipeline_status", "quote_ready_not_triggered")
                payload.setdefault("submission_status", "pending")
                payload.setdefault("submission_message", "Auto-quote trigger disabled")
        else:
            payload.setdefault("quote_generated", False)
            payload.setdefault("pdf_generated", False)
            payload.setdefault("pipeline_status", "not_quote_ready")
            payload.setdefault("submission_status", "not_submitted")
            if not payload.get("submission_message"):
                payload["submission_message"] = payload.get(
                    "exclusion_reason",
                    "RFQ did not pass auto-quote eligibility",
                )

        return payload

    @classmethod
    def _normalize_rfq(cls, rfq: Dict[str, Any]) -> Dict[str, Any]:
        payload = copy.deepcopy(rfq or {})

        title = cls._clean(
            payload.get("title")
            or payload.get("tender_title")
            or payload.get("description")
            or payload.get("notice_title")
        )

        description = cls._clean(
            payload.get("description")
            or payload.get("scope")
            or payload.get("brief")
            or payload.get("summary")
        )

        buyer_name = cls._clean(
            payload.get("buyer_name")
            or payload.get("department")
            or payload.get("entity")
            or payload.get("organisation")
            or payload.get("organization")
        )

        buyer_rfq_number = cls._clean(
            payload.get("buyer_rfq_number")
            or payload.get("rfq_number")
            or payload.get("reference_number")
            or payload.get("tender_number")
            or payload.get("notice_number")
            or payload.get("bid_number")
        )

        submission_method = cls._clean(
            payload.get("submission_method")
            or payload.get("submission_channel")
            or payload.get("delivery_method")
            or "unknown"
        ).lower()

        recipient_email = cls._clean(
            payload.get("recipient_email")
            or payload.get("buyer_email")
            or payload.get("submission_email")
            or payload.get("email")
        )

        compulsory_briefing = cls._to_bool(
            payload.get("briefing_required")
            or payload.get("compulsory_briefing")
            or payload.get("mandatory_briefing")
        )

        estimated_value = cls._to_float(
            payload.get("estimated_value")
            or payload.get("budget")
            or payload.get("estimated_budget")
            or payload.get("contract_value")
        )

        items = payload.get("items") or payload.get("line_items") or []
        if not isinstance(items, list):
            items = []

        normalized = {
            **payload,
            "title": title or "Untitled RFQ",
            "description": description,
            "buyer_name": buyer_name,
            "buyer_rfq_number": buyer_rfq_number or "RFQ-MISSING",
            "rfq_number": buyer_rfq_number or "RFQ-MISSING",
            "reference_number": buyer_rfq_number or "RFQ-MISSING",
            "submission_method": submission_method or "unknown",
            "submission_channel": submission_method or "unknown",
            "recipient_email": recipient_email,
            "buyer_email": recipient_email,
            "compulsory_briefing": compulsory_briefing,
            "briefing_required": compulsory_briefing,
            "estimated_value": estimated_value,
            "items": items,
            "line_items": items,
            "eligible": False,
            "quote_ready": False,
            "quote_generated": False,
            "pdf_generated": False,
            "pipeline_status": "pending_eligibility",
            "submission_status": "pending",
            "submission_message": "",
            "priority_score": payload.get("priority_score", 0.0),
            "priority_band": payload.get("priority_band", "low"),
            "priority_reasons": payload.get("priority_reasons", []),
            "estimated_profit": payload.get("estimated_profit", 0.0),
            "_fingerprint": payload.get("_fingerprint"),
        }

        normalized["quote_number"] = cls._build_quote_number(normalized)
        normalized["document_number"] = normalized["buyer_rfq_number"]

        return normalized

    @classmethod
    def _evaluate_eligibility(cls, rfq: Dict[str, Any]) -> Dict[str, Any]:
        searchable = " ".join(
            [
                cls._clean(rfq.get("title")),
                cls._clean(rfq.get("description")),
                cls._clean(rfq.get("buyer_name")),
                cls._clean(rfq.get("category")),
            ]
        ).lower()

        if rfq.get("briefing_required") is True:
            return {
                "eligible": False,
                "quote_ready": False,
                "exclusion_reason": "Blocked: compulsory briefing detected",
                "pipeline_status": "blocked_compulsory_briefing",
                "submission_status": "not_submitted",
                "submission_message": "Compulsory briefing tenders are excluded",
            }

        for keyword in cls.EXCLUDED_KEYWORDS:
            if keyword in searchable:
                return {
                    "eligible": False,
                    "quote_ready": False,
                    "exclusion_reason": f"Blocked by exclusion keyword: {keyword}",
                    "pipeline_status": "blocked_by_exclusion",
                    "submission_status": "not_submitted",
                    "submission_message": f"Excluded tender category detected: {keyword}",
                }

        if not cls._looks_like_supply_tender(rfq):
            return {
                "eligible": False,
                "quote_ready": False,
                "exclusion_reason": "Not classified as supply/delivery tender",
                "pipeline_status": "blocked_not_supply",
                "submission_status": "not_submitted",
                "submission_message": "Only supply and delivery RFQs are allowed",
            }

        if not cls._acceptable_submission_method(rfq):
            return {
                "eligible": False,
                "quote_ready": False,
                "exclusion_reason": "Unsupported submission method",
                "pipeline_status": "blocked_submission_method",
                "submission_status": "not_submitted",
                "submission_message": "Only email, portal, or physical submission workflows are supported",
            }

        estimated_profit = cls._estimate_profit_floor(rfq)
        quote_ready = bool(
            (rfq.get("buyer_pack_downloaded") or rfq.get("buyer_pack_verified"))
            and rfq.get("boq_detected")
            and rfq.get("pricing_schedule_detected")
            and rfq.get("returnables_detected")
            and (rfq.get("quote_pack_generated") or rfq.get("quote_generated"))
        )
        if estimated_profit < 30000:
            return {
                "eligible": False,
                "quote_ready": False,
                "exclusion_reason": f"Estimated profit below threshold: {estimated_profit:.2f}",
                "pipeline_status": "blocked_low_profit",
                "submission_status": "not_submitted",
                "submission_message": "Estimated minimum profit is below R30,000 threshold",
                "estimated_profit": estimated_profit,
            }

        return {
            "eligible": True,
            "quote_ready": quote_ready,
            "exclusion_reason": "",
            "pipeline_status": "quote_ready" if quote_ready else "eligible_pending_acquisition",
            "submission_status": "pending_pipeline",
            "submission_message": "RFQ passed auto-quote trigger checks" if quote_ready else "RFQ eligible but waiting on acquisition/extraction gate",
            "estimated_profit": estimated_profit,
        }

    @classmethod
    def _trigger_pipeline(cls, rfq: Dict[str, Any]) -> Dict[str, Any]:
        try:
            from app.services.tender_pipeline import run_tender_pipeline_from_payload
        except Exception as exc:
            logger.exception("Unable to import tender pipeline")
            return {
                "quote_generated": False,
                "pdf_generated": False,
                "pipeline_status": "trigger_failed",
                "submission_status": "failed",
                "submission_message": f"Pipeline import failed: {exc}",
            }

        try:
            logger.info(
                "[AUTO_QUOTE_TRIGGER] Triggering pipeline | RFQ=%s | score=%s | band=%s | source=%s",
                rfq.get("buyer_rfq_number"),
                rfq.get("priority_score"),
                rfq.get("priority_band"),
                rfq.get("source_name"),
            )

            result = run_tender_pipeline_from_payload(
                payload=copy.deepcopy(rfq),
                source="auto_quote_trigger_engine",
                persist_to_live_store=True,
            )

            if not isinstance(result, dict):
                return {
                    "quote_generated": False,
                    "pdf_generated": False,
                    "pipeline_status": "trigger_failed",
                    "submission_status": "failed",
                    "submission_message": "Pipeline returned non-dict result",
                }

            merged = {
                "quote_generated": bool(result.get("quote_generated", False)),
                "pdf_generated": bool(result.get("pdf_generated", False)),
                "pipeline_status": result.get("pipeline_status", "pipeline_completed"),
                "submission_status": result.get("submission_status", "pending"),
                "submission_message": result.get("submission_message", "Pipeline completed"),
                "final_pdf_path": result.get("final_pdf_path") or result.get("pdf_path") or "",
                "pdf_path": result.get("pdf_path") or result.get("final_pdf_path") or "",
                "quote_pack_metadata_path": result.get("quote_pack_metadata_path", ""),
                "monthly_quote_folder": result.get("monthly_quote_folder", ""),
                "quote_folder": result.get("quote_folder", ""),
                "recipient_email": result.get("recipient_email") or rfq.get("recipient_email") or "",
                "submission_channel": result.get("submission_channel") or rfq.get("submission_method") or "unknown",
                "priority_score": rfq.get("priority_score", 0.0),
                "priority_band": rfq.get("priority_band", "low"),
                "priority_reasons": rfq.get("priority_reasons", []),
                "estimated_profit": rfq.get("estimated_profit", 0.0),
                "_fingerprint": rfq.get("_fingerprint"),
            }

            for key in [
                "quote_number",
                "buyer_rfq_number",
                "rfq_number",
                "reference_number",
                "document_number",
            ]:
                if result.get(key):
                    merged[key] = result.get(key)

            return merged

        except Exception as exc:
            logger.exception(
                "[AUTO_QUOTE_TRIGGER] Pipeline execution failed | RFQ=%s",
                rfq.get("buyer_rfq_number"),
            )
            return {
                "quote_generated": False,
                "pdf_generated": False,
                "pipeline_status": "trigger_failed",
                "submission_status": "failed",
                "submission_message": f"Pipeline execution failed: {exc}",
                "priority_score": rfq.get("priority_score", 0.0),
                "priority_band": rfq.get("priority_band", "low"),
                "priority_reasons": rfq.get("priority_reasons", []),
                "estimated_profit": rfq.get("estimated_profit", 0.0),
                "_fingerprint": rfq.get("_fingerprint"),
            }

    @classmethod
    def _looks_like_supply_tender(cls, rfq: Dict[str, Any]) -> bool:
        searchable = " ".join(
            [
                cls._clean(rfq.get("title")),
                cls._clean(rfq.get("description")),
                cls._clean(rfq.get("category")),
            ]
        ).lower()

        if any(hint in searchable for hint in cls.SUPPLY_HINTS):
            return True

        items = rfq.get("items") or rfq.get("line_items") or []
        if isinstance(items, list) and len(items) > 0:
            return True

        return False

    @classmethod
    def _acceptable_submission_method(cls, rfq: Dict[str, Any]) -> bool:
        method = cls._clean(rfq.get("submission_method")).lower()
        return method in {"email", "portal", "physical", "physical_via_email", "unknown"}

    @classmethod
    def _estimate_profit_floor(cls, rfq: Dict[str, Any]) -> float:
        estimated_value = cls._to_float(rfq.get("estimated_value"))
        if estimated_value <= 0:
            return 30000.0
        return estimated_value * 0.25

    @classmethod
    def _build_quote_number(cls, rfq: Dict[str, Any]) -> str:
        buyer_rfq_number = cls._clean(
            rfq.get("buyer_rfq_number")
            or rfq.get("rfq_number")
            or rfq.get("reference_number")
            or "RFQ-MISSING"
        )
        return f"LMCP-{buyer_rfq_number}"

    @staticmethod
    def _clean(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _to_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        text = str(value).strip().lower()
        return text in {"1", "true", "yes", "y", "required", "mandatory"}

    @staticmethod
    def _to_float(value: Any) -> float:
        try:
            text = str(value or "").replace(",", "").replace("R", "").strip()
            if not text:
                return 0.0
            return float(text)
        except Exception:
            return 0.0
