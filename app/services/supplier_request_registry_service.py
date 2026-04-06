from __future__ import annotations

import json
import logging
import os
import re
import uuid
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from email.utils import parseaddr
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now_utc().isoformat()


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _normalize_text(value: str) -> str:
    value = _safe_str(value).lower()
    value = re.sub(r"[\r\n\t]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _normalize_for_compare(value: str) -> str:
    value = _normalize_text(value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", _normalize_for_compare(value))


def _extract_email_domain(email_address: str) -> str:
    address = parseaddr(_safe_str(email_address))[1].lower().strip()
    if "@" not in address:
        return ""
    return address.split("@", 1)[1]


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    text = _safe_str(value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


@dataclass
class SupplierRequestRecord:
    registry_id: str
    buyer_rfq_number: str
    lmcp_quote_number: str
    supplier_name: str
    supplier_email: str
    supplier_domain: str
    supplier_company: str
    sent_subject: str
    sent_body_excerpt: str
    sent_at: str
    outbound_message_id: str
    thread_reference: str
    buyer_name: str
    buyer_title: str
    requested_items: List[str] = field(default_factory=list)
    status: str = "sent"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SupplierRequestRegistryService:
    DEFAULT_REGISTRY_DIR = "runtime/supplier_registry"
    DEFAULT_REGISTRY_FILE = "supplier_requests.json"
    DEFAULT_MATCH_WINDOW_HOURS = 168  # 7 days

    @classmethod
    def register_supplier_request(
        cls,
        *,
        buyer_rfq_number: str,
        lmcp_quote_number: str,
        supplier_email: str,
        supplier_name: str = "",
        supplier_company: str = "",
        sent_subject: str = "",
        sent_body: str = "",
        buyer_name: str = "",
        buyer_title: str = "",
        requested_items: Optional[List[str]] = None,
        outbound_message_id: str = "",
        thread_reference: str = "",
    ) -> Dict[str, Any]:
        records = cls._load_registry()

        address = parseaddr(_safe_str(supplier_email))[1]
        domain = _extract_email_domain(address)

        record = SupplierRequestRecord(
            registry_id=str(uuid.uuid4()),
            buyer_rfq_number=_safe_str(buyer_rfq_number),
            lmcp_quote_number=_safe_str(lmcp_quote_number),
            supplier_name=_safe_str(supplier_name),
            supplier_email=address,
            supplier_domain=domain,
            supplier_company=_safe_str(supplier_company),
            sent_subject=_safe_str(sent_subject),
            sent_body_excerpt=_safe_str(sent_body)[:1000],
            sent_at=_now_iso(),
            outbound_message_id=_safe_str(outbound_message_id),
            thread_reference=_safe_str(thread_reference),
            buyer_name=_safe_str(buyer_name),
            buyer_title=_safe_str(buyer_title),
            requested_items=[_safe_str(x) for x in (requested_items or []) if _safe_str(x)],
            status="sent",
        )

        records.append(record.to_dict())
        cls._save_registry(records)

        return {
            "success": True,
            "message": "Supplier request registered.",
            "registry_id": record.registry_id,
            "record": record.to_dict(),
        }

    @classmethod
    def register_bulk_supplier_requests(
        cls,
        *,
        buyer_rfq_number: str,
        lmcp_quote_number: str,
        suppliers: List[Dict[str, Any]],
        sent_subject: str,
        sent_body: str = "",
        buyer_name: str = "",
        buyer_title: str = "",
        requested_items: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        created: List[Dict[str, Any]] = []

        for supplier in suppliers or []:
            email_address = _safe_str(
                supplier.get("email")
                or supplier.get("supplier_email")
                or supplier.get("address")
            )
            if not email_address or "@" not in email_address:
                continue

            response = cls.register_supplier_request(
                buyer_rfq_number=buyer_rfq_number,
                lmcp_quote_number=lmcp_quote_number,
                supplier_email=email_address,
                supplier_name=_safe_str(
                    supplier.get("name") or supplier.get("supplier_name")
                ),
                supplier_company=_safe_str(
                    supplier.get("company") or supplier.get("supplier_company")
                ),
                sent_subject=sent_subject,
                sent_body=sent_body,
                buyer_name=buyer_name,
                buyer_title=buyer_title,
                requested_items=requested_items,
                outbound_message_id=_safe_str(supplier.get("outbound_message_id")),
                thread_reference=_safe_str(supplier.get("thread_reference")),
            )
            if response.get("success"):
                created.append(response["record"])

        return {
            "success": True,
            "count": len(created),
            "records": created,
        }

    @classmethod
    def find_candidate_requests_for_reply(
        cls,
        *,
        from_email: str,
        from_name: str = "",
        subject: str = "",
        body_text: str = "",
        received_at: Optional[str] = None,
        attachment_names: Optional[List[str]] = None,
        buyer_rfq_number: str = "",
        lmcp_quote_number: str = "",
    ) -> Dict[str, Any]:
        records = cls._load_registry()
        if not records:
            return {
                "success": True,
                "matches": [],
                "best_match": None,
            }

        reply_email = parseaddr(_safe_str(from_email))[1]
        reply_domain = _extract_email_domain(reply_email)
        normalized_subject = _normalize_for_compare(subject)
        normalized_body = _normalize_for_compare(body_text)
        compact_subject = _compact(subject)
        compact_body = _compact(body_text)
        received_dt = _parse_iso_datetime(received_at) or _now_utc()
        attachment_names = [_safe_str(x) for x in (attachment_names or []) if _safe_str(x)]

        target_rfq = _safe_str(buyer_rfq_number)
        target_quote = _safe_str(lmcp_quote_number)

        scored_matches: List[Dict[str, Any]] = []

        for record in records:
            score = 0
            reasons: List[str] = []

            record_email = _safe_str(record.get("supplier_email"))
            record_domain = _safe_str(record.get("supplier_domain"))
            record_subject = _safe_str(record.get("sent_subject"))
            record_rfq = _safe_str(record.get("buyer_rfq_number"))
            record_quote = _safe_str(record.get("lmcp_quote_number"))
            record_sent_at = _parse_iso_datetime(record.get("sent_at"))

            if target_quote and record_quote == target_quote:
                score += 50
                reasons.append("Exact quote number match")

            if target_rfq and record_rfq == target_rfq:
                score += 40
                reasons.append("Exact RFQ number match")

            if reply_email and record_email and reply_email == record_email:
                score += 35
                reasons.append("Exact supplier email match")

            if reply_domain and record_domain and reply_domain == record_domain:
                score += 20
                reasons.append("Supplier domain match")

            if record_quote:
                compact_record_quote = _compact(record_quote)
                if compact_record_quote and (
                    compact_record_quote in compact_subject
                    or compact_record_quote in compact_body
                ):
                    score += 45
                    reasons.append("Quote number found in reply content")

            if record_rfq:
                compact_record_rfq = _compact(record_rfq)
                if compact_record_rfq and (
                    compact_record_rfq in compact_subject
                    or compact_record_rfq in compact_body
                ):
                    score += 35
                    reasons.append("RFQ number found in reply content")

            if record_subject:
                compact_record_subject = _compact(record_subject)
                if compact_record_subject and compact_record_subject in compact_subject:
                    score += 15
                    reasons.append("Reply subject similar to sent subject")

            requested_items = record.get("requested_items") or []
            for item in requested_items:
                token = _normalize_for_compare(item)
                if token and (token in normalized_subject or token in normalized_body):
                    score += 5
                    reasons.append(f"Requested item mention: {item}")
                    break

            for name in attachment_names:
                compact_name = _compact(name)
                if record_quote and _compact(record_quote) in compact_name:
                    score += 20
                    reasons.append("Attachment filename contains quote number")
                    break
                if record_rfq and _compact(record_rfq) in compact_name:
                    score += 15
                    reasons.append("Attachment filename contains RFQ number")
                    break

            if record_sent_at:
                delta = received_dt - record_sent_at
                if timedelta(hours=0) <= delta <= timedelta(hours=cls._get_match_window_hours()):
                    score += 10
                    reasons.append("Reply within expected time window")

            if score > 0:
                scored_matches.append(
                    {
                        "registry_id": record.get("registry_id"),
                        "supplier_email": record_email,
                        "supplier_domain": record_domain,
                        "supplier_name": record.get("supplier_name"),
                        "buyer_rfq_number": record_rfq,
                        "lmcp_quote_number": record_quote,
                        "sent_subject": record_subject,
                        "sent_at": record.get("sent_at"),
                        "score": score,
                        "reasons": reasons,
                        "record": deepcopy(record),
                    }
                )

        scored_matches.sort(key=lambda x: x["score"], reverse=True)

        best_match = scored_matches[0] if scored_matches else None
        return {
            "success": True,
            "matches": scored_matches,
            "best_match": best_match,
        }

    @classmethod
    def list_records(cls) -> Dict[str, Any]:
        records = cls._load_registry()
        return {
            "success": True,
            "count": len(records),
            "records": records,
        }

    @classmethod
    def mark_record_status(
        cls,
        registry_id: str,
        status: str,
    ) -> Dict[str, Any]:
        records = cls._load_registry()
        updated = False

        for record in records:
            if _safe_str(record.get("registry_id")) == _safe_str(registry_id):
                record["status"] = _safe_str(status, "updated")
                record["updated_at"] = _now_iso()
                updated = True
                break

        cls._save_registry(records)

        return {
            "success": updated,
            "registry_id": registry_id,
            "status": status,
        }

    @classmethod
    def _registry_path(cls) -> Path:
        base_dir = Path(cls._get_env("SUPPLIER_REQUEST_REGISTRY_DIR", cls.DEFAULT_REGISTRY_DIR))
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / cls._get_env("SUPPLIER_REQUEST_REGISTRY_FILE", cls.DEFAULT_REGISTRY_FILE)

    @classmethod
    def _load_registry(cls) -> List[Dict[str, Any]]:
        path = cls._registry_path()
        if not path.exists():
            return []

        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.exception("Failed loading supplier request registry: %s", exc)
            return []

    @classmethod
    def _save_registry(cls, records: List[Dict[str, Any]]) -> None:
        path = cls._registry_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def _get_match_window_hours(cls) -> int:
        try:
            return int(os.getenv("SUPPLIER_REPLY_MATCH_WINDOW_HOURS", str(cls.DEFAULT_MATCH_WINDOW_HOURS)))
        except Exception:
            return cls.DEFAULT_MATCH_WINDOW_HOURS

    @classmethod
    def _get_env(cls, key: str, default: str) -> str:
        value = os.getenv(key)
        return _safe_str(value, default)
