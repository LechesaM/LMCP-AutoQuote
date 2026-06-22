from __future__ import annotations

from datetime import datetime, timezone
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple


MIN_DOCUMENT_CONFIDENCE = 0.75
MIN_PROFIT = 30000.0
MIN_MARGIN = 0.25
VALIDATION_SUBTYPE_NONE = "NONE"
VALIDATION_SUBTYPE_METADATA = "METADATA_COMPLETENESS"
VALIDATION_SUBTYPE_QUALIFICATION = "QUALIFICATION_EXCLUSION"
VALIDATION_SUBTYPE_TECHNICAL = "TECHNICAL_VALIDATION"
VALIDATION_SUBTYPE_BUSINESS = "BUSINESS_RULE"
TEXT_PROVENANCE_SUFFIXES = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".jsonl",
    ".yaml",
    ".yml",
    ".xml",
    ".log",
    ".html",
    ".htm",
}

VALID_SUPPLY_TERMS = {
    "supply",
    "delivery",
    "deliver",
    "goods",
    "materials",
    "consumables",
    "stationery",
    "ppe",
    "office",
}

EXCLUDED_CATEGORIES = {
    "catering",
    "medical consumables",
    "medical supplies",
    "medical",
    "it equipment",
    "ict equipment",
    "fuel",
    "petrol",
    "diesel",
}

BRIEFING_MARKERS = ("briefing", "site inspection", "site meeting")

WEIGHTS = {
    "missing_closing_date": 35,
    "invalid_closing_date": 30,
    "closing_date_passed": 35,
    "missing_rfq_number": 20,
    "missing_buyer_name": 15,
    "missing_submission_method": 15,
    "not_supply_and_delivery": 25,
    "excluded_category": 30,
    "briefing_session_excluded": 30,
    "profit_below_threshold": 30,
    "margin_below_threshold": 25,
    "missing_source_or_detail_url": 10,
    "missing_document_confidence": 10,
    "document_confidence_below_threshold": 10,
    "technical_validation_required": 10,
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _infer_submission_method(text: str) -> str:
    lower = _clean(text).lower()
    if "portal" in lower or "online submission" in lower or "e-tender" in lower:
        return "portal"
    if "hand delivery" in lower or "tender box" in lower:
        return "physical_delivery"
    if "courier" in lower:
        return "courier_hand_delivery"
    if "email" in lower or "e-mail" in lower:
        return "email"
    return "unknown"


def _normalize_category(category: str) -> str:
    text = _clean(category).lower().replace("&", " and ")
    mapping = {
        "catering": "catering",
        "medical consumables": "medical_consumables",
        "medical supplies": "medical_consumables",
        "medical": "medical_consumables",
        "it equipment": "it_equipment",
        "ict equipment": "it_equipment",
        "fuel": "fuel",
        "petrol": "fuel",
        "diesel": "fuel",
        "household products": "household_products",
        "household_product": "household_products",
        "building materials": "building_materials",
        "technical fabrication": "technical_fabrication",
        "equipment supply": "equipment_supply",
        "supply and delivery": "supply_and_delivery",
        "consumables": "consumables",
    }
    return mapping.get(text, text.replace(" ", "_"))


def _closing_date_value(payload: Dict[str, Any]) -> str:
    for key in ("closing_date", "closing", "close_date", "deadline", "closing_datetime"):
        value = _clean(payload.get(key))
        if value:
            return value
    source_payload = payload.get("source_payload") if isinstance(payload.get("source_payload"), dict) else {}
    for key in ("closing_date", "closing", "close_date", "deadline", "closing_datetime"):
        value = _clean(source_payload.get(key))
        if value:
            return value
    return ""


def _closing_date_status(payload: Dict[str, Any]) -> Tuple[bool, str]:
    value = _closing_date_value(payload)
    if not value:
        return False, "missing_closing_date"

    raw = value.replace("Z", "+00:00").strip()
    candidates = [raw, raw[:10]]
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d %b %Y",
        "%d %B %Y",
        "%Y-%m-%d %H:%M:%S",
    ]

    parsed = None
    for candidate in candidates:
        if not candidate:
            continue
        try:
            parsed = datetime.fromisoformat(candidate)
            break
        except Exception:
            parsed = None
        for fmt in formats:
            try:
                parsed = datetime.strptime(candidate, fmt)
                break
            except Exception:
                parsed = None
        if parsed is not None:
            break

    if parsed is None:
        return False, "invalid_closing_date"

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    if parsed < datetime.now(timezone.utc):
        return False, "closing_date_passed"
    return True, value


def _extract_urls(payload: Dict[str, Any]) -> List[str]:
    urls: List[str] = []
    for key in ("source_url", "detail_url", "document_url", "download_url", "attachment_url", "tender_document_url"):
        value = _clean(payload.get(key))
        if value:
            urls.append(value)
    source_payload = payload.get("source_payload") if isinstance(payload.get("source_payload"), dict) else {}
    for key in ("source_url", "detail_url", "document_url", "download_url", "attachment_url", "tender_document_url"):
        value = _clean(source_payload.get(key))
        if value:
            urls.append(value)
    return urls


def _field_present(payload: Dict[str, Any], *keys: str) -> bool:
    if any(_clean(payload.get(key)) for key in keys):
        return True
    source_payload = payload.get("source_payload") if isinstance(payload.get("source_payload"), dict) else {}
    return any(_clean(source_payload.get(key)) for key in keys)


def _looks_like_provenance_path(text: str) -> bool:
    value = _clean(text)
    if not value:
        return False
    lower = value.lower()
    return lower.startswith("file://") or lower.startswith("/") or lower.startswith(".") or "/" in value or "\\" in value


def _candidate_provenance_paths(payload: Dict[str, Any]) -> List[Path]:
    candidates: List[str] = []

    def collect(value: Any, key_hint: str = "") -> None:
        if isinstance(value, dict):
            for key, inner in value.items():
                collect(inner, str(key).lower())
            return
        if isinstance(value, list):
            for inner in value:
                collect(inner, key_hint)
            return
        if not isinstance(value, str):
            return
        text = _clean(value)
        if not text:
            return
        if len(text) > 512:
            return
        hint = key_hint.lower()
        if any(token in hint for token in ("path", "file", "url", "document", "download", "source", "detail", "pricing", "manifest", "quote", "rfq")) or _looks_like_provenance_path(text):
            candidates.append(text)

    collect(payload)

    resolved: List[Path] = []
    for candidate in candidates:
        raw = candidate
        if raw.startswith("file://"):
            raw = raw[7:]
        path = Path(raw)
        try:
            if path.exists():
                resolved.append(path)
                continue
        except OSError:
            continue
        if not path.is_absolute():
            project_root = Path(__file__).resolve().parents[2]
            alt = project_root / path
            try:
                if alt.exists():
                    resolved.append(alt)
            except OSError:
                continue

    unique: List[Path] = []
    seen = set()
    for path in resolved:
        try:
            key = str(path.resolve())
        except Exception:
            key = str(path)
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def _read_text_fragment(path: Path, limit: int = 4096) -> str:
    try:
        if not path.exists() or not path.is_file():
            return ""
        if path.suffix.lower() not in TEXT_PROVENANCE_SUFFIXES:
            return ""
        return path.read_text(errors="ignore")[:limit]
    except Exception:
        return ""


def _provenance_blob(payload: Dict[str, Any], paths: List[Path]) -> str:
    blob_parts = [
        _clean(payload.get("title")),
        _clean(payload.get("description")),
        _clean(payload.get("submission_instructions")),
        _clean(payload.get("extracted_text")),
        _clean(payload.get("category")),
    ]
    for path in paths:
        blob_parts.append(str(path))
        fragment = _read_text_fragment(path)
        if fragment:
            blob_parts.append(fragment)
    return "\n".join(part for part in blob_parts if part)


def _closing_date_from_text(text: str) -> str:
    blob = _clean(text)
    if not blob:
        return ""
    patterns = [
        r"closing\s+date\s*[:\-]\s*([0-9]{4}-[0-9]{2}-[0-9]{2}(?:[ t][0-9]{2}:[0-9]{2}(?::[0-9]{2})?)?(?:Z|[+-][0-9]{2}:?[0-9]{2})?)",
        r"deadline\s*[:\-]\s*([0-9]{4}-[0-9]{2}-[0-9]{2}(?:[ t][0-9]{2}:[0-9]{2}(?::[0-9]{2})?)?(?:Z|[+-][0-9]{2}:?[0-9]{2})?)",
        r"closing\s+date\s*[:\-]\s*([0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4})",
    ]
    for pattern in patterns:
        match = re.search(pattern, blob, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return ""


def _url_from_text(text: str, labels: Tuple[str, ...]) -> str:
    blob = _clean(text)
    if not blob:
        return ""

    patterns: List[str] = []
    for label in labels:
        escaped = re.escape(label)
        patterns.extend(
            [
                rf"{escaped}\s*[:\-]\s*(https?://[^\s\"'<>]+)",
                rf"{escaped}\s*[:\-]\s*(www\.[^\s\"'<>]+)",
                rf"{escaped}\s*[:\-]\s*([A-Za-z]:[^\s\"'<>]+)",
            ]
        )

    patterns.append(r"(https?://[^\s\"'<>]+)")
    patterns.append(r"(www\.[^\s\"'<>]+)")

    for pattern in patterns:
        match = re.search(pattern, blob, flags=re.IGNORECASE)
        if match:
            value = match.group(1).strip().rstrip(").,;")
            if value.startswith("www."):
                value = f"https://{value}"
            return value
    return ""


def _document_confidence_score(payload: Dict[str, Any]) -> float:
    scores = [
        _safe_float(payload.get("document_confidence_score"), 0.0),
        _safe_float(payload.get("document_acquisition_confidence"), 0.0),
        _safe_float(payload.get("confidence"), 0.0),
        _safe_float(payload.get("confidence_score"), 0.0),
    ]
    score = max(scores) if scores else 0.0
    if score > 1.0:
        score = score / 100.0 if score <= 100.0 else 1.0
    return round(max(0.0, min(score, 1.0)), 4)


def _recovery_signal_score(
    provenance_paths: List[Path],
    provenance_blob: str,
    closing_date_present: bool,
    submission_method_present: bool,
    source_url_present: bool,
    detail_url_present: bool,
) -> float:
    score = 0.0
    if provenance_paths:
        score += 0.25
    if provenance_blob:
        score += 0.15
    if closing_date_present:
        score += 0.15
    if submission_method_present:
        score += 0.15
    if source_url_present:
        score += 0.15
    if detail_url_present:
        score += 0.15
    return min(score, 1.0)


def _missing_document_signals(provenance_blob: str) -> List[str]:
    blob = _clean(provenance_blob).lower()
    if not blob:
        return []
    signals: List[str] = []
    markers = {
        "pricing_schedule": ("pricing schedule", "price schedule"),
        "sbd_or_returnables": ("sbd", "returnable", "returnables", "annexure"),
        "company_documents": ("company registration", "cipc", "tax clearance", "company documents"),
        "boq": ("boq", "bill of quantities"),
        "quote_pack": ("quote pack", "submission package", "submission pack"),
    }
    for code, terms in markers.items():
        if any(term in blob for term in terms):
            signals.append(code)
    return sorted(set(signals))


def _metadata_completeness(payload: Dict[str, Any], submission_method: str, closing_ok: bool, closing_reason: str, source_url_present: bool, detail_url_present: bool, document_confidence: float) -> Dict[str, Any]:
    closing_value = _closing_date_value(payload)
    rfq_number = _clean(
        payload.get("rfq_number")
        or payload.get("buyer_rfq_number")
        or payload.get("tender_id")
        or payload.get("reference_number")
    )
    buyer_name = _clean(payload.get("buyer_name") or payload.get("buyer"))

    missing_fields: List[str] = []
    issue_codes: List[str] = []
    checks = {
        "closing_date": bool(closing_value) and closing_ok,
        "rfq_number": bool(rfq_number),
        "buyer_name": bool(buyer_name),
        "submission_method": submission_method in {"email", "portal", "physical_delivery", "courier_hand_delivery"},
        "source_url": source_url_present,
        "detail_url": detail_url_present,
        "document_confidence": bool(document_confidence) and document_confidence >= MIN_DOCUMENT_CONFIDENCE,
    }

    if not closing_value:
        missing_fields.append("closing_date")
        issue_codes.append("metadata_missing_closing_date")
    elif closing_reason == "invalid_closing_date":
        issue_codes.append("metadata_invalid_closing_date")
    elif closing_reason == "closing_date_passed":
        issue_codes.append("metadata_closing_date_passed")

    if not checks["rfq_number"]:
        missing_fields.append("rfq_number")
        issue_codes.append("metadata_missing_rfq_number")
    if not checks["buyer_name"]:
        missing_fields.append("buyer_name")
        issue_codes.append("metadata_missing_buyer_name")
    if not checks["submission_method"]:
        missing_fields.append("submission_method")
        issue_codes.append("metadata_missing_submission_method")
    if not source_url_present:
        missing_fields.append("source_url")
        issue_codes.append("metadata_missing_source_url")
    if not detail_url_present:
        missing_fields.append("detail_url")
        issue_codes.append("metadata_missing_detail_url")
    if not source_url_present and not detail_url_present:
        issue_codes.append("metadata_missing_source_or_detail_url")
    if not document_confidence:
        missing_fields.append("document_confidence")
        issue_codes.append("metadata_missing_document_confidence")
    elif document_confidence < MIN_DOCUMENT_CONFIDENCE:
        issue_codes.append("metadata_document_confidence_below_threshold")

    present_count = sum(1 for passed in checks.values() if passed)
    completeness_score = round((present_count / max(len(checks), 1)) * 100)

    return {
        "state": "COMPLETE" if not issue_codes else "INCOMPLETE",
        "score": completeness_score,
        "checks": checks,
        "missing_fields": sorted(set(missing_fields)),
        "issue_codes": sorted(set(issue_codes)),
    }


def _validation_subtypes(metadata: Dict[str, Any], blocking_reason_codes: List[str], review_reason_codes: List[str]) -> List[str]:
    subtypes: List[str] = []
    metadata_issue_codes = set(metadata.get("issue_codes") or [])
    if metadata_issue_codes:
        subtypes.append(VALIDATION_SUBTYPE_METADATA)
    if any(code in blocking_reason_codes + review_reason_codes for code in ("not_supply_and_delivery", "excluded_category", "briefing_session_excluded")):
        subtypes.append(VALIDATION_SUBTYPE_QUALIFICATION)
    if "technical_validation_required" in review_reason_codes:
        subtypes.append(VALIDATION_SUBTYPE_TECHNICAL)
    if any(code in blocking_reason_codes + review_reason_codes for code in ("profit_below_threshold", "margin_below_threshold")):
        subtypes.append(VALIDATION_SUBTYPE_BUSINESS)
    return subtypes or [VALIDATION_SUBTYPE_NONE]


def _briefing_required(payload: Dict[str, Any]) -> bool:
    blob = " ".join(
        _clean(value)
        for value in (
            payload.get("title"),
            payload.get("description"),
            payload.get("submission_instructions"),
            payload.get("extracted_text"),
        )
        if _clean(value)
    ).lower()
    return "briefing" in blob and any(marker in blob for marker in ("compulsory", "mandatory", "required"))


def build_validation_readiness(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = dict(payload or {})
    text = " ".join(
        _clean(value)
        for value in (
            data.get("title"),
            data.get("description"),
            data.get("submission_instructions"),
            data.get("extracted_text"),
            data.get("category"),
        )
        if _clean(value)
    )

    rfq_number = _clean(
        data.get("rfq_number")
        or data.get("buyer_rfq_number")
        or data.get("tender_id")
        or data.get("reference_number")
    )
    buyer_name = _clean(data.get("buyer_name") or data.get("buyer"))
    submission_method = _clean(data.get("submission_method")).lower().replace(" ", "_")
    if not submission_method or submission_method == "unknown":
        submission_method = _infer_submission_method(text)

    category = _normalize_category(data.get("category") or "")
    urls = _extract_urls(data)
    provenance_paths = _candidate_provenance_paths(data)
    provenance_blob = _provenance_blob(data, provenance_paths)
    source_url = _clean(data.get("source_url") or data.get("document_url") or data.get("download_url") or data.get("attachment_url") or data.get("tender_document_url"))
    detail_url = _clean(data.get("detail_url"))
    source_url_present = bool(source_url)
    detail_url_present = bool(detail_url)
    has_document_url = bool(source_url or detail_url or urls or provenance_paths)
    document_confidence = _document_confidence_score(data)
    profit_value = _safe_float(data.get("estimated_profit"), 0.0)
    margin_value = _safe_float(data.get("gross_margin_ratio"), 0.0)

    recovered_closing_date = _closing_date_from_text(provenance_blob)
    recovered_source_url = source_url or _url_from_text(
        provenance_blob,
        ("source url", "document url", "download url", "attachment url", "tender document url"),
    )
    recovered_detail_url = detail_url or _url_from_text(
        provenance_blob,
        ("detail url", "detail", "tender detail url"),
    )
    if recovered_closing_date and not _clean(data.get("closing_date") or data.get("closing") or data.get("close_date") or data.get("deadline") or data.get("closing_datetime")):
        data["closing_date"] = recovered_closing_date
    if recovered_source_url and not source_url:
        source_url = recovered_source_url
        source_url_present = True
        data["source_url"] = recovered_source_url
    if recovered_detail_url and not detail_url:
        detail_url = recovered_detail_url
        detail_url_present = True
        data["detail_url"] = recovered_detail_url
    if provenance_paths:
        recovered_urls = []
        for path in provenance_paths:
            try:
                recovered_urls.append(path.resolve().as_uri())
            except Exception:
                recovered_urls.append(str(path))
        if not source_url_present:
            source_url_present = True
            source_url = recovered_urls[0]
            data.setdefault("source_url", source_url)
        if not detail_url_present:
            detail_url_present = True
            detail_url = recovered_urls[-1]
            data.setdefault("detail_url", detail_url)

    recovered_submission_method = submission_method
    if recovered_submission_method not in {"email", "portal", "physical_delivery", "courier_hand_delivery"}:
        recovered_submission_method = _infer_submission_method(f"{text}\n{provenance_blob}")
        if recovered_submission_method in {"email", "portal", "physical_delivery", "courier_hand_delivery"}:
            data["submission_method"] = recovered_submission_method
            submission_method = recovered_submission_method

    closing_ok, closing_reason = _closing_date_status(data)

    recovery_score = _recovery_signal_score(
        provenance_paths=provenance_paths,
        provenance_blob=provenance_blob,
        closing_date_present=bool(_closing_date_value(data)),
        submission_method_present=submission_method in {"email", "portal", "physical_delivery", "courier_hand_delivery"},
        source_url_present=source_url_present,
        detail_url_present=detail_url_present,
    )
    if recovery_score > 0.0:
        document_confidence = max(document_confidence, round(min(1.0, 0.55 + recovery_score), 4))

    reason_codes: List[str] = []
    blocking_reason_codes: List[str] = []
    review_reason_codes: List[str] = []
    validated_fields = {
        "rfq_number_present": bool(rfq_number),
        "buyer_name_present": bool(buyer_name),
        "closing_date_present": bool(_closing_date_value(data)),
        "source_url_present": source_url_present,
        "detail_url_present": detail_url_present,
        "submission_method_present": submission_method in {"email", "portal", "physical_delivery", "courier_hand_delivery"},
        "document_confidence_present": document_confidence > 0.0,
        "document_confidence_ok": document_confidence >= MIN_DOCUMENT_CONFIDENCE,
        "supply_and_delivery_scope": any(term in text.lower() for term in VALID_SUPPLY_TERMS),
    }

    closing_ok, closing_reason = _closing_date_status(data)
    metadata = _metadata_completeness(
        data,
        submission_method=submission_method,
        closing_ok=closing_ok,
        closing_reason=closing_reason,
        source_url_present=source_url_present,
        detail_url_present=detail_url_present,
        document_confidence=document_confidence,
    )
    if not closing_ok:
        blocking_reason_codes.append(closing_reason)

    if not rfq_number:
        blocking_reason_codes.append("missing_rfq_number")
    if not buyer_name:
        blocking_reason_codes.append("missing_buyer_name")
    if submission_method not in {"email", "portal", "physical_delivery", "courier_hand_delivery"}:
        blocking_reason_codes.append("missing_submission_method")
    if not any(term in text.lower() for term in VALID_SUPPLY_TERMS):
        blocking_reason_codes.append("not_supply_and_delivery")

    excluded_category = category in {
        "catering",
        "medical_consumables",
        "it_equipment",
        "fuel",
    }
    if excluded_category:
        blocking_reason_codes.append("excluded_category")

    if _briefing_required(data):
        blocking_reason_codes.append("briefing_session_excluded")

    if profit_value and profit_value < MIN_PROFIT:
        blocking_reason_codes.append("profit_below_threshold")
    if margin_value and margin_value < MIN_MARGIN:
        blocking_reason_codes.append("margin_below_threshold")

    if not has_document_url:
        review_reason_codes.append("missing_source_or_detail_url")
    if not document_confidence:
        review_reason_codes.append("missing_document_confidence")
    elif document_confidence < MIN_DOCUMENT_CONFIDENCE:
        review_reason_codes.append("document_confidence_below_threshold")

    technical_validation_required = category in {"equipment_supply", "technical_fabrication", "building_materials"}
    if technical_validation_required:
        review_reason_codes.append("technical_validation_required")

    reason_codes = sorted(set(blocking_reason_codes + review_reason_codes))
    if blocking_reason_codes:
        readiness_state = "NOT_READY"
    elif review_reason_codes:
        readiness_state = "REVIEW_REQUIRED"
    else:
        readiness_state = "READY"

    score = 100
    for code in reason_codes:
        score -= WEIGHTS.get(code, 5)
    score = max(0, min(score, 100))

    next_operator_action = {
        "READY": "proceed with governed approval steps",
        "REVIEW_REQUIRED": "review metadata and document quality before approval",
        "NOT_READY": "resolve validation blockers before approval",
    }[readiness_state]

    return {
        "readiness_state": readiness_state,
        "validation_readiness_state": readiness_state,
        "compliance_readiness_score": score,
        "confidence_score": round(score / 100.0, 4),
        "document_confidence_score": document_confidence,
        "reason_codes": reason_codes,
        "blocking_reason_codes": sorted(set(blocking_reason_codes)),
        "review_reason_codes": sorted(set(review_reason_codes)),
        "validated_fields": validated_fields,
        "metadata_completeness_state": metadata["state"],
        "metadata_completeness_score": metadata["score"],
        "metadata_missing_fields": metadata["missing_fields"],
        "metadata_issue_codes": metadata["issue_codes"],
        "metadata_recovery_paths": [str(path) for path in provenance_paths],
        "metadata_recovered_closing_date": recovered_closing_date or _closing_date_value(data),
        "metadata_recovered_submission_method": submission_method if submission_method in {"email", "portal", "physical_delivery", "courier_hand_delivery"} else "",
        "metadata_recovered_source_url": source_url,
        "metadata_recovered_detail_url": detail_url,
        "metadata_recovered_document_confidence": document_confidence,
        "metadata_recovery_score": round(recovery_score, 4),
        "metadata_recovery_signals": _missing_document_signals(provenance_blob),
        "validation_subtype": _validation_subtypes(metadata, blocking_reason_codes, review_reason_codes)[0],
        "validation_subtypes": _validation_subtypes(metadata, blocking_reason_codes, review_reason_codes),
        "next_operator_action": next_operator_action,
        "validation_family": "VALIDATION" if readiness_state != "READY" else "NONE",
    }
