from __future__ import annotations

import json
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


BASE_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

LIVE_RFQ_FILE = RUNTIME_DIR / "live_rfqs.json"


class LiveRFQStore:
    _lock = threading.Lock()

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _empty_store(cls) -> Dict[str, Any]:
        return {
            "updated_at": cls._now_iso(),
            "count": 0,
            "items": [],
        }

    @classmethod
    def _read_store(cls) -> Dict[str, Any]:
        if not LIVE_RFQ_FILE.exists():
            return cls._empty_store()

        try:
            raw = LIVE_RFQ_FILE.read_text(encoding="utf-8").strip()
            if not raw:
                return cls._empty_store()

            data = json.loads(raw)
            if not isinstance(data, dict):
                return cls._empty_store()

            items = data.get("items", [])
            if not isinstance(items, list):
                items = []

            return {
                "updated_at": data.get("updated_at") or cls._now_iso(),
                "count": len(items),
                "items": items,
            }
        except Exception:
            return cls._empty_store()

    @classmethod
    def _write_store(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        payload = {
            "updated_at": cls._now_iso(),
            "count": len(items),
            "items": items,
        }

        with cls._lock:
            LIVE_RFQ_FILE.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        return payload

    @staticmethod
    def _safe_str(value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @classmethod
    def _extract_text_blob(cls, rfq: Dict[str, Any]) -> str:
        parts = [
            cls._safe_str(rfq.get("title")),
            cls._safe_str(rfq.get("description")),
            cls._safe_str(rfq.get("category")),
            cls._safe_str(rfq.get("subcategory")),
            cls._safe_str(rfq.get("buyer_name")),
            cls._safe_str(rfq.get("issuing_entity")),
            cls._safe_str(rfq.get("submission_type")),
            cls._safe_str(rfq.get("raw_text")),
            cls._safe_str(rfq.get("buyer_rfq_number")),
            cls._safe_str(rfq.get("rfq_number")),
            cls._safe_str(rfq.get("reference_number")),
            cls._safe_str(rfq.get("reference_no")),
            cls._safe_str(rfq.get("tender_id")),
            cls._safe_str(rfq.get("notice_number")),
            cls._safe_str(rfq.get("external_id")),
        ]

        raw = rfq.get("raw")
        if isinstance(raw, dict):
            for value in raw.values():
                if isinstance(value, (str, int, float, bool)):
                    parts.append(str(value))

        raw_data = rfq.get("raw_data")
        if isinstance(raw_data, dict):
            for value in raw_data.values():
                if isinstance(value, (str, int, float, bool)):
                    parts.append(str(value))

        source_rfq = rfq.get("source_rfq")
        if isinstance(source_rfq, dict):
            for value in source_rfq.values():
                if isinstance(value, (str, int, float, bool)):
                    parts.append(str(value))

        return " ".join(parts).strip()

    @classmethod
    def _normalize_identifier(cls, value: Any) -> str:
        text = cls._safe_str(value).upper()
        if not text:
            return ""
        return re.sub(r"[^A-Z0-9]", "", text)

    @classmethod
    def _extract_rfq_number(cls, rfq: Dict[str, Any]) -> str:
        """
        Final RFQ identity engine.

        Priority:
        1. Explicit RFQ/reference fields
        2. Nested/raw/source payload fields
        3. Text blob regex extraction
        4. UNKNOWN-RFQ fallback
        """
        direct_candidates = [
            rfq.get("buyer_rfq_number"),
            rfq.get("rfq_number"),
            rfq.get("reference_number"),
            rfq.get("reference_no"),
            rfq.get("tender_id"),
            rfq.get("notice_number"),
            rfq.get("external_id"),
            rfq.get("bid_number"),
            rfq.get("tender_number"),
            rfq.get("document_number"),
            rfq.get("id"),
            rfq.get("rfq_id"),
        ]

        nested_sources = [
            rfq.get("raw"),
            rfq.get("raw_data"),
            rfq.get("source_rfq"),
            rfq.get("buyer"),
        ]

        for source in nested_sources:
            if isinstance(source, dict):
                direct_candidates.extend(
                    [
                        source.get("buyer_rfq_number"),
                        source.get("rfq_number"),
                        source.get("reference_number"),
                        source.get("reference_no"),
                        source.get("tender_id"),
                        source.get("notice_number"),
                        source.get("external_id"),
                        source.get("bid_number"),
                        source.get("tender_number"),
                        source.get("document_number"),
                        source.get("id"),
                        source.get("rfq_id"),
                    ]
                )

        for candidate in direct_candidates:
            value = cls._safe_str(candidate)
            if len(value) >= 4:
                return value

        text_blob = cls._extract_text_blob(rfq)

        patterns = [
            r"\b(RFQ[-\s_/]?\d{3,})\b",
            r"\b(RFQ[-\s_/]?[A-Z0-9]{3,})\b",
            r"\b(REQ[-\s_/]?[A-Z0-9]{3,})\b",
            r"\b(TENDER[-\s_/]?[A-Z0-9]{3,})\b",
            r"\b(BID[-\s_/]?[A-Z0-9]{3,})\b",
            r"\b(Q\d{4,})\b",
            r"\b(T\d{4,})\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text_blob, re.IGNORECASE)
            if match:
                return cls._safe_str(match.group(1)).upper()

        return "UNKNOWN-RFQ"

    @classmethod
    def _normalize_rfq_identity(cls, rfq: Dict[str, Any]) -> Dict[str, Any]:
        item = deepcopy(rfq)

        rfq_number = cls._extract_rfq_number(item)

        item["buyer_rfq_number"] = rfq_number
        if not cls._safe_str(item.get("rfq_number")):
            item["rfq_number"] = rfq_number
        if not cls._safe_str(item.get("reference_number")) and rfq_number != "UNKNOWN-RFQ":
            item["reference_number"] = rfq_number

        return item

    @classmethod
    def _normalize_key(cls, rfq: Dict[str, Any]) -> str:
        normalized_rfq = cls._normalize_rfq_identity(rfq)

        for key in (
            "buyer_rfq_number",
            "rfq_number",
            "rfq_id",
            "external_id",
            "id",
            "tender_id",
            "reference_number",
            "reference_no",
            "notice_number",
        ):
            value = cls._safe_str(normalized_rfq.get(key))
            if value:
                return value.lower()

        title = cls._safe_str(normalized_rfq.get("title")).lower()
        buyer = cls._safe_str(normalized_rfq.get("buyer_name") or normalized_rfq.get("issuing_entity")).lower()
        source = cls._safe_str(normalized_rfq.get("source_name") or normalized_rfq.get("source")).lower()
        closing = cls._safe_str(normalized_rfq.get("closing_at") or normalized_rfq.get("closing_date")).lower()
        return f"{title}|{buyer}|{source}|{closing}"

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        return cls._read_store()

    @classmethod
    def clear(cls) -> Dict[str, Any]:
        return cls._write_store([])

    @classmethod
    def bulk_upsert(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        current = cls._read_store()
        existing_items = current.get("items", [])
        merged: Dict[str, Dict[str, Any]] = {}

        for item in existing_items:
            if isinstance(item, dict):
                normalized_item = cls._normalize_rfq_identity(item)
                merged[cls._normalize_key(normalized_item)] = deepcopy(normalized_item)

        for item in items:
            if isinstance(item, dict):
                normalized_item = cls._normalize_rfq_identity(item)
                merged[cls._normalize_key(normalized_item)] = deepcopy(normalized_item)

        return cls._write_store(list(merged.values()))

    @classmethod
    def upsert(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        return cls.bulk_upsert([item])

    @classmethod
    def upsert_rfq(cls, rfq: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compatibility wrapper for pipeline.
        Ensures RFQ is inserted into live store with identity lock.
        """
        if not isinstance(rfq, dict):
            return cls.get_all()

        rfq_copy = cls._normalize_rfq_identity(rfq)
        return cls.upsert(rfq_copy)

    @classmethod
    def _extract_estimated_value(cls, rfq: Dict[str, Any]) -> float:
        candidates = [
            rfq.get("estimated_value"),
            (rfq.get("raw") or {}).get("estimated_value") if isinstance(rfq.get("raw"), dict) else None,
            (rfq.get("raw_data") or {}).get("estimated_value") if isinstance(rfq.get("raw_data"), dict) else None,
        ]

        for candidate in candidates:
            try:
                if candidate is None or candidate == "":
                    continue
                return float(candidate)
            except (TypeError, ValueError):
                continue

        return 0.0

    @classmethod
    def _briefing_required(cls, rfq: Dict[str, Any]) -> bool:
        flags = rfq.get("flags") or {}
        if isinstance(flags, dict) and flags.get("compulsory_briefing") is True:
            return True

        for key in ("briefing_required", "compulsory_briefing"):
            value = rfq.get(key)
            if value is True:
                return True
            if isinstance(value, str) and value.strip().lower() in {"true", "yes", "required", "compulsory"}:
                return True

        text = cls._extract_text_blob(rfq).lower()
        phrases = [
            "compulsory briefing",
            "mandatory briefing",
            "compulsory site briefing",
            "mandatory site briefing",
            "compulsory briefing session",
            "mandatory briefing session",
            "briefing session compulsory",
        ]
        return any(phrase in text for phrase in phrases)

    @classmethod
    def _is_supply_and_delivery(cls, rfq: Dict[str, Any]) -> bool:
        text = cls._extract_text_blob(rfq).lower()
        positive_phrases = [
            "supply and delivery",
            "supply & delivery",
            "supply, delivery",
            "supply of",
            "delivery of",
            "supply and install",
            "supply",
        ]
        return any(phrase in text for phrase in positive_phrases)

    @classmethod
    def _is_excluded_category(cls, rfq: Dict[str, Any]) -> bool:
        text = cls._extract_text_blob(rfq).lower()
        excluded_keywords = [
            "medical consumables",
            "medical supply",
            "medical supplies",
            "medical equipment",
            "it equipment",
            "information technology equipment",
            "computer equipment",
            "laptop",
            "laptops",
            "desktop computer",
            "server hardware",
            "petrol",
            "diesel",
            "fuel supply",
            "fuel delivery",
        ]
        return any(keyword in text for keyword in excluded_keywords)

    @classmethod
    def _estimated_profit(cls, rfq: Dict[str, Any]) -> float:
        estimated_value = cls._extract_estimated_value(rfq)
        if estimated_value <= 0:
            return 0.0
        return estimated_value * 0.25

    @classmethod
    def is_profitable_supply_rfq(cls, rfq: Dict[str, Any]) -> bool:
        if not isinstance(rfq, dict):
            return False
        if not cls._is_supply_and_delivery(rfq):
            return False
        if cls._is_excluded_category(rfq):
            return False
        if cls._briefing_required(rfq):
            return False
        return cls._estimated_profit(rfq) >= 30000

    @classmethod
    def get_filtered_live_rfqs(cls, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        filtered_items: List[Dict[str, Any]] = []

        for rfq in items:
            try:
                if isinstance(rfq, dict) and cls.is_profitable_supply_rfq(rfq):
                    filtered_items.append(cls._normalize_rfq_identity(deepcopy(rfq)))
            except Exception:
                continue

        return {
            "updated_at": cls._now_iso(),
            "count": len(filtered_items),
            "items": filtered_items,
        }

    @classmethod
    def get_filtered_from_store(cls) -> Dict[str, Any]:
        data = cls.get_all()
        items = data.get("items", [])
        if not isinstance(items, list):
            items = []
        return cls.get_filtered_live_rfqs(items)

    @classmethod
    def _score_single_rfq(cls, rfq: Dict[str, Any]) -> Dict[str, Any]:
        item = cls._normalize_rfq_identity(deepcopy(rfq))
        text = cls._extract_text_blob(item).lower()
        score = 0.0
        reasoning: List[str] = []

        estimated_value = cls._extract_estimated_value(item)
        estimated_profit = cls._estimated_profit(item)

        if estimated_value >= 500000:
            score += 30
            reasoning.append("High estimated tender value.")
        elif estimated_value >= 250000:
            score += 22
            reasoning.append("Mid-to-high estimated tender value.")
        elif estimated_value >= 120000:
            score += 15
            reasoning.append("Moderate estimated tender value.")
        else:
            score += 8
            reasoning.append("Lower estimated tender value.")

        if estimated_profit >= 100000:
            score += 25
            reasoning.append("Estimated profit is strongly above threshold.")
        elif estimated_profit >= 60000:
            score += 18
            reasoning.append("Estimated profit is comfortably above threshold.")
        elif estimated_profit >= 30000:
            score += 12
            reasoning.append("Estimated profit meets minimum threshold.")

        if "municipality" in text or "metro" in text or "department" in text:
            score += 8
            reasoning.append("Public-sector buyer identified.")

        if "pipe" in text or "valve" in text or "fitting" in text or "plumbing" in text:
            score += 8
            reasoning.append("Good fit for LMCP supply profile.")

        if "furniture" in text or "office" in text or "stationery" in text:
            score += 6
            reasoning.append("General supply-and-delivery category detected.")

        if cls._safe_str(item.get("closing_at") or item.get("closing_date")):
            score += 5
            reasoning.append("Closing date available.")

        if cls._safe_str(item.get("contact_email")) or cls._safe_str(item.get("contact_phone")):
            score += 5
            reasoning.append("Contact details available.")

        priority_band = "low"
        if score >= 70:
            priority_band = "high"
        elif score >= 45:
            priority_band = "medium"

        item["scoring"] = {
            "score": round(score, 2),
            "priority_band": priority_band,
            "estimated_profit": round(estimated_profit, 2),
            "reasoning": reasoning,
        }
        return item

    @classmethod
    def get_scored_from_store(cls) -> Dict[str, Any]:
        filtered = cls.get_filtered_from_store()
        items = filtered.get("items", [])

        scored_items: List[Dict[str, Any]] = []
        recommended_items: List[Dict[str, Any]] = []

        for rfq in items:
            if not isinstance(rfq, dict):
                continue

            scored = cls._score_single_rfq(rfq)
            scored_items.append(scored)

            scoring = scored.get("scoring", {})
            if isinstance(scoring, dict) and scoring.get("priority_band") in {"high", "medium"}:
                recommended_items.append(scored)

        scored_items.sort(
            key=lambda x: float(((x.get("scoring") or {}).get("score") or 0.0)),
            reverse=True,
        )
        recommended_items.sort(
            key=lambda x: float(((x.get("scoring") or {}).get("score") or 0.0)),
            reverse=True,
        )

        return {
            "updated_at": cls._now_iso(),
            "count": len(scored_items),
            "items": scored_items,
            "recommended_count": len(recommended_items),
            "recommended_items": recommended_items,
        }

    @classmethod
    def get_live_rfqs_for_api(cls) -> Dict[str, Any]:
        return cls.get_filtered_from_store()


def get_live_rfqs_for_api() -> Dict[str, Any]:
    return LiveRFQStore.get_live_rfqs_for_api()
