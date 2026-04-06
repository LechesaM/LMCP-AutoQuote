from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# =========================================================
# Dynamic model import helpers
# =========================================================
def _import_opportunity_model():
    """
    Resolve Opportunity model from whichever module currently owns it.
    This makes the service more resilient while the codebase is being cleaned.
    """
    tried: List[str] = []

    try:
        from app.models.opportunity import Opportunity  # type: ignore
        return Opportunity
    except Exception as e:
        tried.append(f"app.models.opportunity.Opportunity -> {e}")

    try:
        from app.models.core import Opportunity  # type: ignore
        return Opportunity
    except Exception as e:
        tried.append(f"app.models.core.Opportunity -> {e}")

    raise ImportError(
        "Could not import Opportunity model. Tried:\n" + "\n".join(tried)
    )


Opportunity = _import_opportunity_model()


# =========================================================
# Public API
# =========================================================
def upsert_harvested_opportunity(
    db: Session,
    harvested_item: Dict[str, Any],
) -> Any:
    """
    Convert a harvested tender/RFQ item into a normalized opportunity row.

    Flow:
    1. Build normalized payload
    2. Compute fingerprint
    3. Find existing opportunity by fingerprint / source URL / tender number
    4. Update or insert
    5. Commit and return the Opportunity instance
    """
    if not isinstance(harvested_item, dict):
        raise ValueError("harvested_item must be a dictionary")

    payload = build_opportunity_payload(harvested_item)
    fingerprint = payload.get("rfq_fingerprint") or fingerprint_opportunity(harvested_item)
    payload["rfq_fingerprint"] = fingerprint

    existing = find_existing_opportunity(db=db, payload=payload)

    if existing:
        logger.info(
            "Updating existing opportunity id=%s fingerprint=%s",
            getattr(existing, "id", None),
            fingerprint,
        )
        _apply_payload_to_model(existing, payload)
        _touch_updated_timestamp(existing)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    logger.info("Creating new opportunity fingerprint=%s", fingerprint)
    obj = Opportunity()
    _apply_payload_to_model(obj, payload)
    _touch_created_timestamp(obj)
    _touch_updated_timestamp(obj)

    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def build_opportunity_payload(harvested_item: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize a raw harvested item into a clean payload that can be written to
    Opportunity regardless of which exact scraper/source produced it.
    """
    title = _first_non_empty(
        harvested_item.get("title"),
        harvested_item.get("tender_title"),
        harvested_item.get("opportunity_title"),
        harvested_item.get("name"),
        harvested_item.get("description"),
        default="Untitled Opportunity",
    )

    description = _clean_text(
        _first_non_empty(
            harvested_item.get("description"),
            harvested_item.get("summary"),
            harvested_item.get("scope"),
            harvested_item.get("brief"),
            default="",
        )
    )

    buyer_name = _first_non_empty(
        harvested_item.get("buyer_name"),
        harvested_item.get("entity_name"),
        harvested_item.get("department"),
        harvested_item.get("issuer"),
        harvested_item.get("organisation"),
        harvested_item.get("organization"),
        default="",
    )

    source_url = _first_non_empty(
        harvested_item.get("source_url"),
        harvested_item.get("url"),
        harvested_item.get("notice_url"),
        harvested_item.get("detail_url"),
        harvested_item.get("link"),
        default="",
    )

    portal_name = _first_non_empty(
        harvested_item.get("portal_name"),
        harvested_item.get("source_name"),
        harvested_item.get("portal"),
        harvested_item.get("source"),
        _hostname_from_url(source_url),
        default="unknown",
    )

    portal_slug = _slugify(
        _first_non_empty(
            harvested_item.get("portal_slug"),
            harvested_item.get("source_slug"),
            portal_name,
            default="unknown",
        )
    )

    tender_number = _first_non_empty(
        harvested_item.get("tender_number"),
        harvested_item.get("reference_number"),
        harvested_item.get("bid_number"),
        harvested_item.get("rfq_number"),
        harvested_item.get("notice_number"),
        harvested_item.get("quote_number"),
        default="",
    )

    category = infer_category(harvested_item)
    submission_method = infer_submission_method(harvested_item)
    province = infer_province(harvested_item)
    city = infer_city(harvested_item)

    published_at = parse_datetime_any(
        harvested_item.get("published_at")
        or harvested_item.get("publication_date")
        or harvested_item.get("date_published")
        or harvested_item.get("advert_date")
    )

    closing_at = parse_datetime_any(
        harvested_item.get("closing_at")
        or harvested_item.get("closing_date")
        or harvested_item.get("deadline")
        or harvested_item.get("submission_deadline")
        or harvested_item.get("bid_closing_date")
    )

    compulsory_briefing_at = parse_datetime_any(
        harvested_item.get("briefing_at")
        or harvested_item.get("briefing_date")
        or harvested_item.get("site_meeting_date")
        or harvested_item.get("compulsory_briefing_date")
    )

    document_urls = collect_document_urls(harvested_item)
    contact_email = infer_contact_email(harvested_item)
    contact_phone = infer_contact_phone(harvested_item)
    contact_person = _first_non_empty(
        harvested_item.get("contact_person"),
        harvested_item.get("contact_name"),
        harvested_item.get("buyer_contact"),
        default="",
    )

    estimated_value = infer_estimated_contract_value(harvested_item)
    value_band = infer_value_band(estimated_value, harvested_item)
    source_confidence = infer_source_confidence(harvested_item, source_url, document_urls)

    keywords = extract_keywords(
        text=" ".join(
            [
                title or "",
                description or "",
                category or "",
                buyer_name or "",
                province or "",
                city or "",
            ]
        )
    )

    raw_json = json.dumps(harvested_item, ensure_ascii=False, default=str)
    rfq_fingerprint = fingerprint_opportunity(harvested_item)

    payload: Dict[str, Any] = {
        # core identity
        "title": title,
        "name": title,
        "description": description,
        "summary": description[:5000] if description else "",
        "buyer_name": buyer_name,
        "entity_name": buyer_name,
        "issuer_name": buyer_name,
        "tender_number": tender_number,
        "reference_number": tender_number,
        "source_url": source_url,
        "notice_url": source_url,
        "portal_name": portal_name,
        "portal_slug": portal_slug,
        "source_name": portal_name,
        "source_slug": portal_slug,
        # classification
        "category": category,
        "submission_method": submission_method,
        "province": province,
        "city": city,
        "country": "South Africa",
        "document_urls": document_urls,
        "document_count": len(document_urls),
        "keywords": keywords,
        # dates
        "published_at": published_at,
        "closing_at": closing_at,
        "deadline_at": closing_at,
        "briefing_at": compulsory_briefing_at,
        # contacts
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "contact_person": contact_person,
        # value / scoring helpers
        "estimated_contract_value": estimated_value,
        "value_band": value_band,
        "source_confidence": source_confidence,
        # automation / pipeline defaults
        "rfq_fingerprint": rfq_fingerprint,
        "last_harvested_at": utcnow(),
        "harvest_status": "written",
        "pipeline_stage": "harvest_written",
        "qualification_status": "pending",
        "auto_quote_triggered": False,
        # raw source preservation
        "raw_payload_json": raw_json,
        "raw_json": raw_json,
        "metadata_json": raw_json,
    }

    return payload


def fingerprint_opportunity(harvested_item: Dict[str, Any]) -> str:
    """
    Generate a stable fingerprint from the strongest identifying fields.
    """
    title = _normalize_for_hash(
        _first_non_empty(
            harvested_item.get("title"),
            harvested_item.get("tender_title"),
            harvested_item.get("name"),
            default="",
        )
    )
    tender_number = _normalize_for_hash(
        _first_non_empty(
            harvested_item.get("tender_number"),
            harvested_item.get("reference_number"),
            harvested_item.get("bid_number"),
            harvested_item.get("rfq_number"),
            default="",
        )
    )
    buyer_name = _normalize_for_hash(
        _first_non_empty(
            harvested_item.get("buyer_name"),
            harvested_item.get("entity_name"),
            harvested_item.get("department"),
            harvested_item.get("issuer"),
            default="",
        )
    )
    source_url = _normalize_for_hash(
        _first_non_empty(
            harvested_item.get("source_url"),
            harvested_item.get("url"),
            harvested_item.get("detail_url"),
            harvested_item.get("notice_url"),
            default="",
        )
    )
    deadline = _normalize_for_hash(
        str(
            parse_datetime_any(
                harvested_item.get("closing_at")
                or harvested_item.get("closing_date")
                or harvested_item.get("deadline")
                or harvested_item.get("submission_deadline")
            )
            or ""
        )
    )

    composite = "||".join([title, tender_number, buyer_name, source_url, deadline])
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()


def find_existing_opportunity(db: Session, payload: Dict[str, Any]) -> Optional[Any]:
    """
    Best-effort dedupe against existing opportunities.

    Tries, in order:
    1. rfq_fingerprint
    2. source_url / notice_url
    3. tender_number + buyer_name
    4. title + closing_at
    """
    query = db.query(Opportunity)

    rfq_fingerprint = payload.get("rfq_fingerprint")
    if rfq_fingerprint and hasattr(Opportunity, "rfq_fingerprint"):
        obj = query.filter(Opportunity.rfq_fingerprint == rfq_fingerprint).first()
        if obj:
            return obj

    source_url = payload.get("source_url") or payload.get("notice_url")
    if source_url:
        for field_name in ("source_url", "notice_url"):
            if hasattr(Opportunity, field_name):
                field = getattr(Opportunity, field_name)
                obj = query.filter(field == source_url).first()
                if obj:
                    return obj

    tender_number = payload.get("tender_number") or payload.get("reference_number")
    buyer_name = payload.get("buyer_name") or payload.get("entity_name")
    if tender_number:
        if hasattr(Opportunity, "tender_number"):
            obj = query.filter(getattr(Opportunity, "tender_number") == tender_number).first()
            if obj:
                return obj
        if hasattr(Opportunity, "reference_number"):
            obj = query.filter(getattr(Opportunity, "reference_number") == tender_number).first()
            if obj:
                return obj

    if tender_number and buyer_name:
        # safer fallback loop when exact model fields differ
        candidates = query.limit(2000).all()
        for row in candidates:
            row_tender = _string_attr(row, "tender_number") or _string_attr(row, "reference_number")
            row_buyer = _string_attr(row, "buyer_name") or _string_attr(row, "entity_name")
            if _norm_eq(row_tender, tender_number) and _norm_eq(row_buyer, buyer_name):
                return row

    title = payload.get("title") or payload.get("name")
    closing_at = payload.get("closing_at") or payload.get("deadline_at")
    if title and closing_at:
        candidates = query.limit(2000).all()
        for row in candidates:
            row_title = _string_attr(row, "title") or _string_attr(row, "name")
            row_deadline = getattr(row, "closing_at", None) or getattr(row, "deadline_at", None)
            if _norm_eq(row_title, title) and _datetime_eq(row_deadline, closing_at):
                return row

    return None


# =========================================================
# Inference helpers
# =========================================================
def infer_category(item: Dict[str, Any]) -> str:
    text = " ".join(
        [
            str(item.get("category") or ""),
            str(item.get("title") or ""),
            str(item.get("description") or ""),
            str(item.get("summary") or ""),
        ]
    ).lower()

    rules: List[Tuple[str, Iterable[str]]] = [
        ("civil_engineering", ["road", "stormwater", "sewer", "water reticulation", "pipeline", "earthworks", "concrete", "culvert", "bridge"]),
        ("general_building", ["building", "renovation", "refurbishment", "construction", "roof", "brickwork", "plaster", "painting"]),
        ("plumbing", ["plumbing", "pipe leak", "valve", "pump station", "water tank", "borehole"]),
        ("electrical", ["electrical", "substation", "transformer", "cable", "lighting", "solar"]),
        ("supply_delivery", ["supply and delivery", "supply, delivery", "supply of", "deliver", "delivery of"]),
        ("professional_services", ["consulting", "professional services", "design", "engineering services", "project management"]),
        ("it_telecoms", ["software", "system", "ict", "computer", "laptop", "telecom", "network"]),
        ("plant_equipment", ["plant hire", "equipment", "machinery", "grader", "excavator", "tippers"]),
    ]

    for category, needles in rules:
        if any(n in text for n in needles):
            return category

    return "unclassified"


def infer_submission_method(item: Dict[str, Any]) -> str:
    text = " ".join(
        [
            str(item.get("submission_method") or ""),
            str(item.get("submission_instructions") or ""),
            str(item.get("description") or ""),
            str(item.get("summary") or ""),
        ]
    ).lower()

    if "etender" in text or "electronic" in text or "online" in text or "portal" in text:
        return "portal"
    if "email" in text or "e-mail" in text:
        return "email"
    if "hand delivery" in text or "physical" in text or "deposit in tender box" in text or "tender box" in text:
        return "physical"
    return "unknown"


def infer_province(item: Dict[str, Any]) -> str:
    text = " ".join(
        [
            str(item.get("province") or ""),
            str(item.get("location") or ""),
            str(item.get("address") or ""),
            str(item.get("description") or ""),
        ]
    ).lower()

    provinces = {
        "eastern cape": "Eastern Cape",
        "free state": "Free State",
        "gauteng": "Gauteng",
        "kwazulu-natal": "KwaZulu-Natal",
        "kwa-zulu natal": "KwaZulu-Natal",
        "kzn": "KwaZulu-Natal",
        "limpopo": "Limpopo",
        "mpumalanga": "Mpumalanga",
        "north west": "North West",
        "northern cape": "Northern Cape",
        "western cape": "Western Cape",
    }

    for needle, proper in provinces.items():
        if needle in text:
            return proper

    return ""


def infer_city(item: Dict[str, Any]) -> str:
    return _first_non_empty(
        item.get("city"),
        item.get("town"),
        item.get("municipality"),
        default="",
    )


def infer_contact_email(item: Dict[str, Any]) -> str:
    email = _first_non_empty(
        item.get("contact_email"),
        item.get("email"),
        default="",
    )
    if email:
        return email

    text = " ".join(
        [
            str(item.get("description") or ""),
            str(item.get("summary") or ""),
            str(item.get("submission_instructions") or ""),
        ]
    )

    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    return emails[0] if emails else ""


def infer_contact_phone(item: Dict[str, Any]) -> str:
    phone = _first_non_empty(
        item.get("contact_phone"),
        item.get("phone"),
        item.get("telephone"),
        default="",
    )
    if phone:
        return phone

    text = " ".join(
        [
            str(item.get("description") or ""),
            str(item.get("summary") or ""),
        ]
    )
    matches = re.findall(r"(\+?\d[\d\s().-]{7,}\d)", text)
    return matches[0].strip() if matches else ""


def infer_estimated_contract_value(item: Dict[str, Any]) -> Optional[float]:
    """
    Best-effort extraction of monetary value from structured fields or text.
    """
    direct_candidates = [
        item.get("estimated_contract_value"),
        item.get("estimated_value"),
        item.get("contract_value"),
        item.get("budget"),
        item.get("tender_value"),
    ]
    for candidate in direct_candidates:
        value = _to_float(candidate)
        if value and value > 0:
            return value

    text = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("description") or ""),
            str(item.get("summary") or ""),
        ]
    )
    return _extract_money_from_text(text)


def infer_value_band(estimated_value: Optional[float], item: Dict[str, Any]) -> str:
    """
    LMCP-oriented high-level value band.
    """
    if estimated_value is not None:
        if estimated_value >= 20_000_000:
            return "strategic"
        if estimated_value >= 5_000_000:
            return "high"
        if estimated_value >= 500_000:
            return "medium"
        return "low"

    text = " ".join(
        [
            str(item.get("title") or ""),
            str(item.get("description") or ""),
            str(item.get("summary") or ""),
        ]
    ).lower()

    high_signals = [
        "framework agreement",
        "three year",
        "3 year",
        "construction",
        "upgrade",
        "rehabilitation",
        "bulk water",
        "housing project",
        "infrastructure",
    ]
    medium_signals = [
        "supply and delivery",
        "maintenance",
        "repairs",
        "refurbishment",
    ]

    if any(s in text for s in high_signals):
        return "high"
    if any(s in text for s in medium_signals):
        return "medium"
    return "unknown"


def infer_source_confidence(
    item: Dict[str, Any],
    source_url: str,
    document_urls: List[str],
) -> float:
    """
    Rough source confidence score from 0.0 to 1.0.
    """
    score = 0.25

    if source_url:
        score += 0.20

    if source_url and (
        "gov.za" in source_url
        or "municipality" in source_url
        or "etenders" in source_url
        or "sanral" in source_url
        or "org.za" in source_url
    ):
        score += 0.20

    if document_urls:
        score += 0.20

    title = str(item.get("title") or "")
    description = str(item.get("description") or "")
    if len(title) >= 12:
        score += 0.05
    if len(description) >= 50:
        score += 0.10

    closing_at = parse_datetime_any(
        item.get("closing_at")
        or item.get("closing_date")
        or item.get("deadline")
        or item.get("submission_deadline")
    )
    if closing_at:
        score += 0.10

    return round(min(score, 1.0), 2)


def collect_document_urls(item: Dict[str, Any]) -> List[str]:
    urls: List[str] = []

    for key in ("document_urls", "attachments", "files", "documents"):
        val = item.get(key)
        if isinstance(val, list):
            for entry in val:
                if isinstance(entry, str) and entry.startswith(("http://", "https://")):
                    urls.append(entry)
                elif isinstance(entry, dict):
                    candidate = _first_non_empty(
                        entry.get("url"),
                        entry.get("link"),
                        entry.get("download_url"),
                        default="",
                    )
                    if candidate.startswith(("http://", "https://")):
                        urls.append(candidate)

    for key in ("document_url", "download_url", "attachment_url", "pdf_url"):
        candidate = str(item.get(key) or "").strip()
        if candidate.startswith(("http://", "https://")):
            urls.append(candidate)

    return _unique_preserve_order(urls)


def extract_keywords(text: str, max_keywords: int = 20) -> List[str]:
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "into", "your", "their",
        "will", "shall", "must", "are", "you", "our", "its", "all", "any", "but",
        "have", "has", "had", "not", "bid", "tender", "rfq", "request", "quotation",
        "quote", "of", "to", "in", "on", "at", "by", "or", "be", "as", "is", "an", "a",
    }
    words = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    freq: Dict[str, int] = {}
    for w in words:
        if w in stopwords:
            continue
        freq[w] = freq.get(w, 0) + 1

    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:max_keywords]]


# =========================================================
# Internal model field application
# =========================================================
def _apply_payload_to_model(obj: Any, payload: Dict[str, Any]) -> None:
    """
    Only assign fields that actually exist on the model.
    """
    for key, value in payload.items():
        if hasattr(obj, key):
            try:
                setattr(obj, key, value)
            except Exception as e:
                logger.warning("Could not set %s=%r on %s: %s", key, value, obj, e)

    # Common fallback mappings where field names may differ
    fallback_pairs = [
        ("title", ["name"]),
        ("name", ["title"]),
        ("description", ["summary"]),
        ("summary", ["description"]),
        ("buyer_name", ["entity_name", "issuer_name"]),
        ("entity_name", ["buyer_name", "issuer_name"]),
        ("tender_number", ["reference_number"]),
        ("reference_number", ["tender_number"]),
        ("source_url", ["notice_url"]),
        ("notice_url", ["source_url"]),
        ("closing_at", ["deadline_at"]),
        ("deadline_at", ["closing_at"]),
    ]

    for primary, alternates in fallback_pairs:
        if hasattr(obj, primary):
            current = getattr(obj, primary, None)
            if _is_empty(current):
                for alt in alternates:
                    if alt in payload and not _is_empty(payload[alt]):
                        try:
                            setattr(obj, primary, payload[alt])
                            break
                        except Exception:
                            continue


def _touch_created_timestamp(obj: Any) -> None:
    for field_name in ("created_at", "inserted_at"):
        if hasattr(obj, field_name) and _is_empty(getattr(obj, field_name, None)):
            try:
                setattr(obj, field_name, utcnow())
            except Exception:
                pass


def _touch_updated_timestamp(obj: Any) -> None:
    for field_name in ("updated_at", "modified_at", "last_seen_at", "last_harvested_at"):
        if hasattr(obj, field_name):
            try:
                setattr(obj, field_name, utcnow())
            except Exception:
                pass


# =========================================================
# Utilities
# =========================================================
def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_datetime_any(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    s = str(value).strip()
    if not s:
        return None

    s = s.replace("Z", "+00:00")

    fmts = [
        None,  # try fromisoformat first
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%d %B %Y",
        "%d %b %Y",
        "%d %B %Y %H:%M",
        "%d %b %Y %H:%M",
    ]

    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    for fmt in fmts[1:]:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


def _extract_money_from_text(text: str) -> Optional[float]:
    """
    Best-effort extraction of ZAR-ish values from free text.
    """
    if not text:
        return None

    patterns = [
        r"R\s?([\d][\d\s,\.]{3,})",
        r"ZAR\s?([\d][\d\s,\.]{3,})",
        r"budget\s*(?:of|:)?\s*R?\s?([\d][\d\s,\.]{3,})",
        r"value\s*(?:of|:)?\s*R?\s?([\d][\d\s,\.]{3,})",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for match in matches:
            value = _to_float(match)
            if value and value > 0:
                return value

    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if not s:
        return None

    s = s.replace("R", "").replace("ZAR", "")
    s = s.replace(" ", "")

    # Handle "1,234,567.89" and "1.234.567,89"
    if s.count(",") > 0 and s.count(".") > 0:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        if s.count(",") > 0 and s.count(".") == 0:
            s = s.replace(",", "")
        else:
            s = s.replace(",", "")

    try:
        return float(s)
    except Exception:
        return None


def _hostname_from_url(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _slugify(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-{2,}", "-", value).strip("-")
    return value or "unknown"


def _first_non_empty(*values: Any, default: str = "") -> str:
    for v in values:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            return s
    return default


def _clean_text(text: str) -> str:
    text = str(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_for_hash(value: str) -> str:
    value = _clean_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", " ", value).strip()
    return value


def _unique_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for v in values:
        if v not in seen:
            seen.add(v)
            result.append(v)
    return result


def _string_attr(obj: Any, field_name: str) -> str:
    try:
        value = getattr(obj, field_name, "")
        return str(value or "").strip()
    except Exception:
        return ""


def _norm_eq(a: Any, b: Any) -> bool:
    return _normalize_for_hash(str(a or "")) == _normalize_for_hash(str(b or ""))


def _datetime_eq(a: Any, b: Any) -> bool:
    da = parse_datetime_any(a)
    db = parse_datetime_any(b)
    if not da or not db:
        return False
    return da == db


def _is_empty(value: Any) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())
