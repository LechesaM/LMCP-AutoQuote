from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[2]
RUNTIME_DIR = BASE_DIR / "runtime"
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

LIVE_RFQ_FILE = str(RUNTIME_DIR / "live_rfqs.json")


class LiveRFQStore:
    _lock = threading.Lock()

    @classmethod
    def _now_iso(cls) -> str:
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def is_profitable_supply_rfq(cls, rfq: dict) -> bool:
        if not isinstance(rfq, dict):
            return False

        title = (rfq.get("title") or "").lower()
        description = (rfq.get("description") or "").lower()
        category = (rfq.get("category") or "").lower()

        if "supply" not in category and "delivery" not in category:
            return False

        excluded_keywords = [
            "medical",
            "pharmaceutical",
            "it equipment",
            "laptop",
            "computer",
            "diesel",
            "petrol",
            "fuel",
        ]
        for word in excluded_keywords:
            if word in title or word in description:
                return False

        briefing = str(rfq.get("briefing_required") or "").lower()
        if briefing in ["true", "yes", "required"]:
            return False

        estimated_value = 150000
        estimated_profit = estimated_value * 0.25
        return estimated_profit >= 30000

    def get_live_rfqs_for_api():
        rfqs = list(LIVE_RFQS.values())

    # 🔥 APPLY FILTER HERE (CRITICAL FIX)
    filtered_rfqs = [r for r in rfqs if is_profitable_supply_rfq(r)]

    return {
        "updated_at": datetime.utcnow().isoformat(),
        "count": len(filtered_rfqs),
        "items": filtered_rfqs,
    }

    def is_profitable_supply_rfq(cls, rfq: dict) -> bool:
    title = (rfq.get("title") or "").lower()
    description = (rfq.get("description") or "").lower()
    category = (rfq.get("category") or "").lower()

    # Must be supply
    if "supply" not in category and "delivery" not in category:
        return False

    # Exclusions
    excluded_keywords = [
        "medical",
        "pharmaceutical",
        "it equipment",
        "laptop",
        "computer",
        "diesel",
        "petrol",
        "fuel",
    ]
    for word in excluded_keywords:
        if word in title or word in description:
            return False

    # No briefing
    briefing = str(rfq.get("briefing_required") or "").lower()
    if briefing in ["true", "yes", "required"]:
        return False

    # Profit rule
    estimated_value = 150000
    estimated_profit = estimated_value * 0.25

    return estimated_profit >= 30000@classmethod
    def _safe_read(cls) -> Dict[str, Any]:
        file_path = Path(LIVE_RFQ_FILE)

        if not file_path.exists():
            data = cls._default_data()
            cls._safe_write(data)
            return data

        try:
            raw = file_path.read_text(encoding="utf-8").strip()
            if not raw:
                data = cls._default_data()
                cls._safe_write(data)
                return data

            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                data = cls._default_data()
                cls._safe_write(data)
                return data

            parsed.setdefault("updated_at", cls._now_iso())
            parsed.setdefault("count", 0)
            parsed.setdefault("items", [])

            if not isinstance(parsed["items"], list):
                parsed["items"] = []

            parsed["count"] = len(parsed["items"])
            return parsed

        except Exception:
            data = cls._default_data()
            cls._safe_write(data)
            return data

    def get_live_rfqs_for_api(cls)

    @classmethod
    def _safe_write(cls, data: Dict[str, Any]) -> None:
        file_path = Path(LIVE_RFQ_FILE)
        file_path.parent.mkdir(parents=True, exist_ok=True)

        data["updated_at"] = cls._now_iso()
        data["count"] = len(data.get("items", []))

        tmp_path = file_path.with_suffix(".tmp")
        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        tmp_path.replace(file_path)

    @classmethod
    def _as_plain_dict(cls, value: Any) -> Dict[str, Any]:
        if value is None:
            return {}

        if isinstance(value, dict):
            return deepcopy(value)

        if hasattr(value, "model_dump"):
            try:
                dumped = value.model_dump(mode="python")
                if isinstance(dumped, dict):
                    return deepcopy(dumped)
            except Exception:
                pass

        if hasattr(value, "dict"):
            try:
                dumped = value.dict()
                if isinstance(dumped, dict):
                    return deepcopy(dumped)
            except Exception:
                pass

        if hasattr(value, "__dict__"):
            try:
                dumped = {
                    k: v for k, v in vars(value).items()
                    if not k.startswith("_")
                }
                if isinstance(dumped, dict):
                    return deepcopy(dumped)
            except Exception:
                pass

        return {"value": str(value)}

    @classmethod
    def _pick_first_non_empty(cls, *values: Any) -> Any:
        for value in values:
            if value is None:
                continue
            if isinstance(value, str) and not value.strip():
                continue
            if isinstance(value, list) and len(value) == 0:
                continue
            if isinstance(value, dict) and len(value) == 0:
                continue
            return value
        return None

    @classmethod
    def _as_list(cls, value: Any) -> List[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    @classmethod
    def _extract_contact_email(cls, rfq: Dict[str, Any]) -> Optional[str]:
        direct = cls._pick_first_non_empty(
            rfq.get("contact_email"),
            rfq.get("submission_email"),
            rfq.get("email"),
        )
        if direct:
            return str(direct)

        contacts = cls._as_list(rfq.get("contacts"))
        for contact in contacts:
            if isinstance(contact, dict):
                email = cls._pick_first_non_empty(
                    contact.get("email"),
                    contact.get("contact_email"),
                )
                if email:
                    return str(email)
        return None

    @classmethod
    def _extract_contact_phone(cls, rfq: Dict[str, Any]) -> Optional[str]:
        direct = cls._pick_first_non_empty(
            rfq.get("contact_phone"),
            rfq.get("submission_phone"),
            rfq.get("phone"),
            rfq.get("telephone"),
        )
        if direct:
            return str(direct)

        contacts = cls._as_list(rfq.get("contacts"))
        for contact in contacts:
            if isinstance(contact, dict):
                phone = cls._pick_first_non_empty(
                    contact.get("phone"),
                    contact.get("telephone"),
                    contact.get("mobile"),
                )
                if phone:
                    return str(phone)
        return None

    @classmethod
    def _extract_document_urls(cls, rfq: Dict[str, Any]) -> List[str]:
        urls: List[str] = []

        direct_urls = cls._as_list(rfq.get("document_urls"))
        for value in direct_urls:
            if value:
                urls.append(str(value))

        documents = cls._as_list(rfq.get("documents"))
        for doc in documents:
            if not isinstance(doc, dict):
                continue
            url = cls._pick_first_non_empty(
                doc.get("url"),
                doc.get("document_url"),
                doc.get("download_url"),
                doc.get("href"),
            )
            if url:
                urls.append(str(url))

        seen = set()
        unique_urls: List[str] = []
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        return unique_urls

    @classmethod
    def _normalize_rfq(cls, rfq: Any) -> Dict[str, Any]:
        raw = cls._as_plain_dict(rfq)

        title = cls._pick_first_non_empty(
            raw.get("title"),
            raw.get("tender_title"),
            raw.get("name"),
        )

        description = cls._pick_first_non_empty(
            raw.get("description"),
            raw.get("scope_summary"),
            raw.get("summary"),
        )

        source_url = cls._pick_first_non_empty(
            raw.get("source_url"),
            raw.get("notice_url"),
            raw.get("url"),
            raw.get("detail_url"),
        )

        published_at = cls._pick_first_non_empty(
            raw.get("published_at"),
            raw.get("published_date"),
            raw.get("advert_date"),
        )

        closing_at = cls._pick_first_non_empty(
            raw.get("closing_at"),
            raw.get("closing_date"),
            raw.get("deadline"),
            raw.get("tender_closing"),
        )

        briefing_required = cls._pick_first_non_empty(
            raw.get("briefing_required"),
            raw.get("briefing_requirement"),
        )

        if isinstance(briefing_required, str):
            lowered = briefing_required.strip().lower()
            if lowered in {"compulsory", "required", "yes", "true"}:
                briefing_required = True
            elif lowered in {"optional", "no", "false", "none"}:
                briefing_required = False

        normalized = {
            "rfq_id": cls._pick_first_non_empty(
                raw.get("rfq_id"),
                raw.get("tender_id"),
                raw.get("id"),
                raw.get("external_id"),
            ),
            "external_id": cls._pick_first_non_empty(
                raw.get("external_id"),
                raw.get("reference_number"),
                raw.get("tender_number"),
                raw.get("bid_number"),
            ),
            "title": title,
            "description": description,
            "buyer_name": cls._pick_first_non_empty(
                raw.get("buyer_name"),
                raw.get("issuing_entity"),
                raw.get("organ_of_state"),
                raw.get("entity"),
            ),
            "province": cls._pick_first_non_empty(
                raw.get("province"),
                raw.get("region"),
            ),
            "category": cls._pick_first_non_empty(
                raw.get("category"),
                raw.get("commodity"),
                raw.get("tender_type"),
            ),
            "submission_type": cls._pick_first_non_empty(
                raw.get("submission_type"),
                raw.get("submission_method"),
                raw.get("method"),
            ),
            "briefing_required": briefing_required,
            "published_at": published_at,
            "closing_at": closing_at,
            "source_name": cls._pick_first_non_empty(
                raw.get("source_name"),
                raw.get("source"),
                raw.get("portal_name"),
            ),
            "source_url": source_url,
            "portal_slug": cls._pick_first_non_empty(
                raw.get("portal_slug"),
                raw.get("source_type"),
            ),
            "contact_email": cls._extract_contact_email(raw),
            "contact_phone": cls._extract_contact_phone(raw),
            "document_urls": cls._extract_document_urls(raw),
            "raw": raw,
            "status": cls._pick_first_non_empty(
                raw.get("status"),
                "live",
            ),
            "created_at": cls._pick_first_non_empty(
                raw.get("created_at"),
                raw.get("harvested_at"),
                cls._now_iso(),
            ),
            "updated_at": cls._now_iso(),
        }

        if normalized["rfq_id"] is None:
            fallback_bits = [
                str(normalized["external_id"] or ""),
                str(normalized["title"] or ""),
                str(normalized["buyer_name"] or ""),
                str(normalized["closing_at"] or ""),
                str(normalized["source_url"] or ""),
            ]
            fallback = "|".join(bit.strip() for bit in fallback_bits)
            normalized["rfq_id"] = fallback if fallback.strip() else f"rfq-{int(datetime.now().timestamp())}"

        return normalized

    @classmethod
    def upsert_rfq(cls, rfq: Any) -> Dict[str, Any]:
        normalized = cls._normalize_rfq(rfq)

        with cls._lock:
            data = cls._safe_read()
    items = data.get("items", [])

    # 🔥 APPLY FILTER HERE
    items = [item for item in items if cls.is_profitable_supply_rfq(item)]

            match_index: Optional[int] = None
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue

                same_rfq_id = item.get("rfq_id") == normalized.get("rfq_id")
                same_external_id = (
                    normalized.get("external_id")
                    and item.get("external_id") == normalized.get("external_id")
                )
                same_source_url = (
                    normalized.get("source_url")
                    and item.get("source_url") == normalized.get("source_url")
                )

                if same_rfq_id or same_external_id or same_source_url:
                    match_index = index
                    break

            if match_index is not None:
                existing = items[match_index]
                merged = deepcopy(existing)
                merged.update(normalized)
                merged["created_at"] = existing.get("created_at", normalized["created_at"])
                merged["updated_at"] = cls._now_iso()
                items[match_index] = merged
                normalized = merged
            else:
                items.insert(0, normalized)

            data["items"] = items
            data["count"] = len(items)
            cls._safe_write(data)

        return normalized

    @classmethod
    def bulk_upsert(cls, rfqs: List[Any]) -> Dict[str, Any]:
        written = 0
        for rfq in rfqs:
            cls.upsert_rfq(rfq)
            written += 1

        return {
            "ok": True,
            "written": written,
            "file": LIVE_RFQ_FILE,
        }

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        with cls._lock:
            return cls._safe_read()

    @classmethod
    def clear(cls) -> Dict[str, Any]:
        with cls._lock:
            data = {
                "updated_at": cls._now_iso(),
                "count": 0,
                "items": [],
            }
            cls._safe_write(data)
            return data
