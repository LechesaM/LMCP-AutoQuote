from __future__ import annotations

import logging
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =========================================================
# Business rules
# =========================================================
MIN_ESTIMATED_PROFIT = 30_000.0
DEFAULT_SUPPLY_MARGIN_PERCENT = 25.0
MIN_ESTIMATED_CONTRACT_VALUE = MIN_ESTIMATED_PROFIT / (DEFAULT_SUPPLY_MARGIN_PERCENT / 100.0)

QUALIFIED_STATUS = "qualified"
REVIEW_STATUS = "review_required"
REJECTED_STATUS = "rejected"

ALLOWED_PROVINCES = {
    "eastern cape",
    "free state",
    "gauteng",
    "kwazulu-natal",
    "kzn",
    "limpopo",
    "mpumalanga",
    "north west",
    "northern cape",
    "western cape",
}

SUPPLY_AND_DELIVERY_KEYWORDS = [
    "supply and delivery",
    "supply & delivery",
    "supply, delivery",
    "supply of",
    "delivery of",
    "supply, install",
    "supply and install",
    "supply only",
    "deliver",
    "delivery",
    "supply",
    "procurement of",
    "provision of goods",
    "goods and services - supply",
    "supply chain",
    "bulk supply",
    "supply to",
    "supply materials",
    "supply of materials",
    "supply and distribute",
]

EXCLUDED_MEDICAL_KEYWORDS = [
    "medical consumables",
    "medical supply",
    "pharmaceutical",
    "pharmaceuticals",
    "syringe",
    "syringes",
    "bandage",
    "bandages",
    "hospital consumables",
    "clinical consumables",
    "medicine",
    "medication",
    "drugs",
    "laboratory reagents",
    "reagent",
    "iv set",
    "surgical gloves",
    "surgical mask",
    "catheter",
    "diagnostic kits",
    "test kits",
]

EXCLUDED_IT_KEYWORDS = [
    "it equipment",
    "ict equipment",
    "laptop",
    "laptops",
    "desktop",
    "desktops",
    "computer",
    "computers",
    "printer",
    "printers",
    "server",
    "servers",
    "network switch",
    "switches",
    "router",
    "routers",
    "scanner",
    "scanners",
    "tablet",
    "tablets",
    "monitor",
    "monitors",
    "software license",
    "software licences",
    "software subscription",
    "licensing",
    "photocopier",
    "photocopiers",
]

EXCLUDED_FUEL_KEYWORDS = [
    "petrol",
    "diesel",
    "fuel",
    "bulk fuel",
    "unleaded",
    "automotive gas oil",
    "paraffin",
    "lubricants",
    "lubricant",
    "fleet fuel",
    "refuelling",
    "refueling",
]

BRIEFING_COMPULSORY_KEYWORDS = [
    "compulsory briefing",
    "briefing session compulsory",
    "compulsory site meeting",
    "mandatory briefing",
    "mandatory site meeting",
    "mandatory clarification meeting",
    "mandatory briefing session",
    "non-attendance will lead to disqualification",
    "site inspection compulsory",
    "attendance is compulsory",
    "briefing compulsory",
    "site meeting compulsory",
    "compulsory clarification meeting",
]

BRIEFING_GENERAL_KEYWORDS = [
    "briefing session",
    "site meeting",
    "site inspection",
    "clarification meeting",
    "briefing",
]

OPTIONAL_BRIEFING_KEYWORDS = [
    "optional briefing",
    "non-compulsory briefing",
    "briefing is optional",
    "optional site meeting",
    "site meeting is optional",
    "voluntary briefing",
]

PHYSICAL_SUBMISSION_KEYWORDS = [
    "tender box",
    "hand delivery",
    "physical submission",
    "deposit in tender box",
    "deliver to",
]

EMAIL_SUBMISSION_KEYWORDS = [
    "email submission",
    "submit by email",
    "e-mail submission",
    "emailed to",
    "email to",
]

PORTAL_SUBMISSION_KEYWORDS = [
    "etender",
    "e-tender",
    "portal submission",
    "online submission",
    "electronic submission",
    "submit online",
]

HARD_REJECT_WORDS = [
    "construction",
    "civil works",
    "road works",
    "building works",
    "professional services",
    "consulting services",
    "maintenance of building",
    "refurbishment works",
    "plumbing works",
    "electrical works",
]

# =========================================================
# Result model
# =========================================================
@dataclass
class TenderQualificationResult:
    qualification_status: str
    qualified: bool
    review_required: bool
    rejected: bool

    is_supply_delivery: bool
    province_ok: bool
    has_valid_submission_method: bool

    has_briefing_session: bool
    briefing_compulsory: bool

    excluded_medical: bool
    excluded_it: bool
    excluded_fuel: bool
    excluded_other: bool
    excluded_by_business_rules: bool

    estimated_contract_value: Optional[float]
    assumed_margin_percent: float
    estimated_profit_value: Optional[float]
    meets_profit_threshold: bool

    score_total: Optional[float]
    auto_quote_recommended: bool

    reasons: List[str]
    rejection_reasons: List[str]
    review_reasons: List[str]
    risk_flags: List[str]

    exclusion_reason: str
    commodity_class: str
    province: str
    submission_method: str
    days_to_deadline: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# =========================================================
# Public API
# =========================================================
def qualify_opportunity(opportunity: Any) -> TenderQualificationResult:
    title = _get_first_attr(opportunity, ["title", "name"], "")
    description = _get_first_attr(opportunity, ["description", "summary"], "")
    category = _get_first_attr(opportunity, ["category"], "")
    buyer_name = _get_first_attr(opportunity, ["buyer_name", "entity_name", "issuer_name"], "")
    province = _get_first_attr(opportunity, ["province"], "")
    city = _get_first_attr(opportunity, ["city"], "")
    submission_method = _get_first_attr(opportunity, ["submission_method"], "")
    source_url = _get_first_attr(opportunity, ["source_url", "notice_url"], "")
    contact_email = _get_first_attr(opportunity, ["contact_email"], "")
    contact_phone = _get_first_attr(opportunity, ["contact_phone"], "")
    tender_number = _get_first_attr(opportunity, ["tender_number", "reference_number"], "")
    value_band = _get_first_attr(opportunity, ["value_band"], "")
    raw_payload_text = _get_first_attr(
        opportunity,
        ["raw_payload_json", "raw_json", "metadata_json"],
        "",
    )
    score_total = _get_float_attr(opportunity, ["score_total"], None)
    auto_quote_recommended = _get_bool_attr(opportunity, ["auto_quote_recommended"], False)
    days_to_deadline = _get_float_attr(opportunity, ["days_to_deadline"], None)
    document_count = _get_int_attr(opportunity, ["document_count"], 0)
    closing_at = _get_first_datetime_attr(opportunity, ["closing_at", "deadline_at"])
    estimated_contract_value = _get_float_attr(
        opportunity,
        ["estimated_contract_value", "estimated_value", "contract_value"],
        None,
    )
    if days_to_deadline is None and closing_at is not None:
        delta_days = (closing_at - utcnow()).total_seconds() / 86400.0
        days_to_deadline = round(delta_days, 2)

    full_text = " ".join(
        [
            title,
            description,
            category,
            buyer_name,
            province,
            city,
            source_url,
            raw_payload_text,
            tender_number,
            value_band,
        ]
    ).lower()

    reasons: List[str] = []
    rejection_reasons: List[str] = []
    review_reasons: List[str] = []
    risk_flags: List[str] = []

    is_supply_delivery, commodity_class, supply_reason = detect_supply_delivery(
        title=title,
        description=description,
        category=category,
        full_text=full_text,
    )
    if supply_reason:
        reasons.extend(supply_reason)

    excluded_medical = contains_any_keyword(full_text, EXCLUDED_MEDICAL_KEYWORDS)
    excluded_it = contains_any_keyword(full_text, EXCLUDED_IT_KEYWORDS)
    excluded_fuel = contains_any_keyword(full_text, EXCLUDED_FUEL_KEYWORDS)
    excluded_other = detect_non_supply_execution_scope(full_text)

    excluded_by_business_rules = any(
        [excluded_medical, excluded_it, excluded_fuel, excluded_other]
    )

    exclusion_reason = build_exclusion_reason(
        excluded_medical=excluded_medical,
        excluded_it=excluded_it,
        excluded_fuel=excluded_fuel,
        excluded_other=excluded_other,
    )

    has_briefing_session, briefing_compulsory = detect_briefing_status(full_text)

    if has_briefing_session:
        risk_flags.append("Tender includes a briefing or site-meeting reference")
    if briefing_compulsory:
        rejection_reasons.append("Compulsory briefing or site meeting detected")

    province_ok, normalized_province = validate_province(province=province, full_text=full_text)
    if province_ok:
        reasons.append("Province is acceptable within South Africa")
    else:
        review_reasons.append("Province is unclear or not confidently identified")

    has_valid_submission_method, normalized_submission_method, submission_reason = validate_submission_method(
        submission_method=submission_method,
        full_text=full_text,
        source_url=source_url,
        contact_email=contact_email,
        contact_phone=contact_phone,
    )
    if submission_reason:
        reasons.extend(submission_reason)
    if not has_valid_submission_method:
        rejection_reasons.append("No valid submission route identified")

    estimated_contract_value = estimate_contract_value_if_missing(
        estimated_contract_value=estimated_contract_value,
        full_text=full_text,
        document_count=document_count,
    )

    assumed_margin_percent = DEFAULT_SUPPLY_MARGIN_PERCENT
    estimated_profit_value = (
        round(estimated_contract_value * (assumed_margin_percent / 100.0), 2)
        if estimated_contract_value is not None
        else None
    )

    meets_profit_threshold = (
        estimated_profit_value is not None and estimated_profit_value >= MIN_ESTIMATED_PROFIT
    )

    if estimated_contract_value is not None:
        reasons.append(
            f"Estimated contract value ≈ R{estimated_contract_value:,.2f}"
        )
        reasons.append(
            f"Estimated profit at {assumed_margin_percent:.0f}% margin ≈ R{estimated_profit_value:,.2f}"
        )
    else:
        review_reasons.append("Estimated contract value is unclear")
        risk_flags.append("Could not confidently estimate contract value")

    if estimated_profit_value is not None and not meets_profit_threshold:
        rejection_reasons.append(
            f"Estimated profit below R{MIN_ESTIMATED_PROFIT:,.0f}"
        )

    if excluded_medical:
        rejection_reasons.append("Medical consumables tender excluded")
    if excluded_it:
        rejection_reasons.append("IT equipment tender excluded")
    if excluded_fuel:
        rejection_reasons.append("Petrol, diesel, or fuel tender excluded")
    if excluded_other:
        rejection_reasons.append("Non-supply or execution-based scope excluded")

    if not is_supply_delivery:
        rejection_reasons.append("Tender is not clearly supply and delivery")

    if closing_at is not None:
        deadline_review, deadline_reject, deadline_reason, deadline_risks = evaluate_deadline(closing_at)
        if deadline_reason:
            reasons.extend(deadline_reason)
        risk_flags.extend(deadline_risks)
        if deadline_review:
            review_reasons.append("Deadline is tight and may require manual review")
        if deadline_reject:
            rejection_reasons.append("Deadline is too close or already expired")
    else:
        review_reasons.append("Deadline not clearly identified")

    if score_total is not None:
        reasons.append(f"Opportunity score = {score_total:.2f}")

    # Hard qualification logic
    hard_reject = any(
        [
            not is_supply_delivery,
            excluded_by_business_rules,
            briefing_compulsory,
            not has_valid_submission_method,
            estimated_profit_value is not None and not meets_profit_threshold,
        ]
    )

    # Province unclear should not auto-reject if SA tender is otherwise good
    needs_review = any(
        [
            not province_ok,
            estimated_contract_value is None,
            estimated_profit_value is None,
            has_briefing_session and not briefing_compulsory,
            days_to_deadline is None,
        ]
    )

    if hard_reject:
        qualification_status = REJECTED_STATUS
    elif needs_review:
        qualification_status = REVIEW_STATUS
    else:
        qualification_status = QUALIFIED_STATUS

    result = TenderQualificationResult(
        qualification_status=qualification_status,
        qualified=qualification_status == QUALIFIED_STATUS,
        review_required=qualification_status == REVIEW_STATUS,
        rejected=qualification_status == REJECTED_STATUS,

        is_supply_delivery=is_supply_delivery,
        province_ok=province_ok,
        has_valid_submission_method=has_valid_submission_method,

        has_briefing_session=has_briefing_session,
        briefing_compulsory=briefing_compulsory,

        excluded_medical=excluded_medical,
        excluded_it=excluded_it,
        excluded_fuel=excluded_fuel,
        excluded_other=excluded_other,
        excluded_by_business_rules=excluded_by_business_rules,

        estimated_contract_value=estimated_contract_value,
        assumed_margin_percent=assumed_margin_percent,
        estimated_profit_value=estimated_profit_value,
        meets_profit_threshold=meets_profit_threshold,

        score_total=score_total,
        auto_quote_recommended=auto_quote_recommended,

        reasons=_dedupe_preserve_order(reasons),
        rejection_reasons=_dedupe_preserve_order(rejection_reasons),
        review_reasons=_dedupe_preserve_order(review_reasons),
        risk_flags=_dedupe_preserve_order(risk_flags),

        exclusion_reason=exclusion_reason,
        commodity_class=commodity_class,
        province=normalized_province,
        submission_method=normalized_submission_method,
        days_to_deadline=days_to_deadline,
    )
    return result


def apply_qualification_to_opportunity(opportunity: Any, result: TenderQualificationResult) -> Any:
    field_values = {
        "qualification_status": result.qualification_status,
        "qualification_reason": "; ".join(result.reasons)[:4000],
        "qualification_reasons": result.reasons,
        "qualification_review_reasons": result.review_reasons,
        "qualification_rejection_reasons": result.rejection_reasons,
        "risk_flags": result.risk_flags,
        "excluded_by_business_rules": result.excluded_by_business_rules,
        "exclusion_reason": result.exclusion_reason,
        "is_supply_delivery": result.is_supply_delivery,
        "has_briefing_session": result.has_briefing_session,
        "briefing_compulsory": result.briefing_compulsory,
        "assumed_margin_percent": result.assumed_margin_percent,
        "estimated_profit_value": result.estimated_profit_value,
        "meets_profit_threshold": result.meets_profit_threshold,
        "submission_method": result.submission_method,
        "province": result.province or _get_first_attr(opportunity, ["province"], ""),
        "pipeline_stage": "qualified" if result.qualified else "qualification_review" if result.review_required else "rejected",
        "auto_quote_triggered": False,
        "qualification_result_json": result.to_dict(),
    }

    for field_name, value in field_values.items():
        if hasattr(opportunity, field_name):
            try:
                setattr(opportunity, field_name, value)
            except Exception as e:
                logger.warning("Could not set %s on opportunity: %s", field_name, e)

    if hasattr(opportunity, "updated_at"):
        try:
            setattr(opportunity, "updated_at", utcnow())
        except Exception:
            pass

    return opportunity


def qualify_and_apply(opportunity: Any) -> TenderQualificationResult:
    result = qualify_opportunity(opportunity)
    apply_qualification_to_opportunity(opportunity, result)
    return result


# =========================================================
# Core rule helpers
# =========================================================
def detect_supply_delivery(
    title: str,
    description: str,
    category: str,
    full_text: str,
) -> Tuple[bool, str, List[str]]:
    reasons: List[str] = []

    category_norm = (category or "").strip().lower()

    if category_norm == "supply_delivery":
        reasons.append("Category explicitly classified as supply and delivery")
        return True, "supply_delivery", reasons

    if contains_any_keyword(full_text, SUPPLY_AND_DELIVERY_KEYWORDS):
        reasons.append("Supply-and-delivery language detected")
        return True, "supply_delivery", reasons

    generic_supply_signals = [
        "supply of stationery",
        "supply of ppe",
        "supply of cleaning materials",
        "supply of furniture",
        "supply of hardware",
        "supply of building materials",
        "supply of plumbing materials",
        "supply of electrical materials",
        "supply of tools",
        "delivery of materials",
        "supply and distribute",
    ]
    if contains_any_keyword(full_text, generic_supply_signals):
        reasons.append("Goods supply pattern detected")
        return True, "supply_delivery", reasons

    return False, "unclear", reasons


def build_exclusion_reason(
    excluded_medical: bool,
    excluded_it: bool,
    excluded_fuel: bool,
    excluded_other: bool,
) -> str:
    reasons: List[str] = []
    if excluded_medical:
        reasons.append("medical_consumables")
    if excluded_it:
        reasons.append("it_equipment")
    if excluded_fuel:
        reasons.append("fuel")
    if excluded_other:
        reasons.append("non_supply_execution_scope")
    return ",".join(reasons)


def detect_non_supply_execution_scope(full_text: str) -> bool:
    """
    Keeps the system focused on goods supply tenders.
    We do not reject merely because the word 'installation' appears somewhere,
    but clear works/services tenders must fail.
    """
    if contains_any_keyword(full_text, HARD_REJECT_WORDS):
        if not contains_any_keyword(full_text, SUPPLY_AND_DELIVERY_KEYWORDS):
            return True

    strong_execution_signals = [
        "construction of",
        "appointment of contractor",
        "professional services",
        "consultancy services",
        "civil engineering works",
        "repair and maintenance of building",
        "refurbishment of offices",
        "road rehabilitation",
        "building construction",
    ]
    return contains_any_keyword(full_text, strong_execution_signals)


def detect_briefing_status(full_text: str) -> Tuple[bool, bool]:
    has_general = contains_any_keyword(full_text, BRIEFING_GENERAL_KEYWORDS)
    has_compulsory = contains_any_keyword(full_text, BRIEFING_COMPULSORY_KEYWORDS)
    has_optional = contains_any_keyword(full_text, OPTIONAL_BRIEFING_KEYWORDS)

    if has_compulsory:
        return True, True
    if has_general or has_optional:
        return True, False
    return False, False


def validate_province(province: str, full_text: str) -> Tuple[bool, str]:
    province_norm = normalize_province(province)

    if province_norm:
        return True, province_norm

    detected = detect_province_from_text(full_text)
    if detected:
        return True, detected

    # Nationwide system across South Africa.
    # Province uncertainty is review-worthy, not an automatic fail.
    if "south africa" in full_text or "republic of south africa" in full_text:
        return False, ""

    return False, ""


def validate_submission_method(
    submission_method: str,
    full_text: str,
    source_url: str,
    contact_email: str,
    contact_phone: str,
) -> Tuple[bool, str, List[str]]:
    reasons: List[str] = []
    method = (submission_method or "").strip().lower()

    if method in {"email", "portal"}:
        reasons.append(f"{method.title()} submission route identified")
        return True, method, reasons

    if method == "physical":
        reasons.append("Physical submission route identified")
        return True, "physical", reasons

    if contains_any_keyword(full_text, EMAIL_SUBMISSION_KEYWORDS) or contact_email:
        reasons.append("Email submission route inferred")
        return True, "email", reasons

    if contains_any_keyword(full_text, PORTAL_SUBMISSION_KEYWORDS) or "etenders" in (source_url or "").lower():
        reasons.append("Portal submission route inferred")
        return True, "portal", reasons

    if contains_any_keyword(full_text, PHYSICAL_SUBMISSION_KEYWORDS) or contact_phone:
        reasons.append("Physical/manual submission route inferred")
        return True, "physical", reasons

    return False, "unknown", reasons


def estimate_contract_value_if_missing(
    estimated_contract_value: Optional[float],
    full_text: str,
    document_count: int,
) -> Optional[float]:
    if estimated_contract_value is not None and estimated_contract_value > 0:
        return round(estimated_contract_value, 2)

    extracted = extract_money_from_text(full_text)
    if extracted is not None and extracted > 0:
        return round(extracted, 2)

    # Heuristic fallback for supply-and-delivery tenders
    high_value_signals = [
        "bulk supply",
        "framework agreement",
        "three year",
        "3 year",
        "district wide",
        "province wide",
        "municipality wide",
        "annual supply",
        "term contract",
    ]
    medium_value_signals = [
        "supply and delivery",
        "supply of materials",
        "supply and distribute",
        "bulk delivery",
        "scheduled delivery",
    ]

    if contains_any_keyword(full_text, high_value_signals):
        return 500_000.00

    if contains_any_keyword(full_text, medium_value_signals):
        if document_count >= 3:
            return 180_000.00
        return 150_000.00

    return None


def evaluate_deadline(closing_at: datetime) -> Tuple[bool, bool, List[str], List[str]]:
    reasons: List[str] = []
    risks: List[str] = []

    now = utcnow()
    delta_hours = (closing_at - now).total_seconds() / 3600.0

    if delta_hours < 0:
        return False, True, reasons, ["Opportunity already expired"]

    if delta_hours < 4:
        return False, True, reasons, ["Less than 4 hours remaining before deadline"]

    if delta_hours < 12:
        return True, False, reasons, ["Very limited time remaining before deadline"]

    reasons.append("Deadline remains workable")
    return False, False, reasons, risks


# =========================================================
# Utility helpers
# =========================================================
def contains_any_keyword(text: str, keywords: List[str]) -> bool:
    t = (text or "").lower()
    return any(k.lower() in t for k in keywords)


def normalize_province(province: str) -> str:
    p = (province or "").strip().lower()
    mapping = {
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
    return mapping.get(p, "")


def detect_province_from_text(full_text: str) -> str:
    text = (full_text or "").lower()
    detection_map = {
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
    for needle, proper in detection_map.items():
        if needle in text:
            return proper
    return ""


def extract_money_from_text(text: str) -> Optional[float]:
    if not text:
        return None

    patterns = [
        r"R\s?([\d][\d\s,\.]{3,})",
        r"ZAR\s?([\d][\d\s,\.]{3,})",
        r"budget\s*(?:of|:)?\s*R?\s?([\d][\d\s,\.]{3,})",
        r"value\s*(?:of|:)?\s*R?\s?([\d][\d\s,\.]{3,})",
        r"estimated\s*value\s*(?:of|:)?\s*R?\s?([\d][\d\s,\.]{3,})",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for match in matches:
            value = _to_float(match)
            if value is not None and value > 0:
                return value
    return None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_attr(obj: Any, field_name: str, default: Any = None) -> Any:
    try:
        return getattr(obj, field_name, default)
    except Exception:
        return default


def _get_first_attr(obj: Any, field_names: List[str], default: str = "") -> str:
    for field_name in field_names:
        try:
            value = obj.get(field_name) if isinstance(obj, dict) else getattr(obj, field_name, None)
            if value is None:
                continue
            s = str(value).strip()
            if s:
                return s
        except Exception:
            continue
    return default


def _get_float_attr(obj: Any, field_names: List[str], default: Optional[float] = None) -> Optional[float]:
    for field_name in field_names:
        try:
            value = obj.get(field_name) if isinstance(obj, dict) else getattr(obj, field_name, None)
            converted = _to_float(value)
            if converted is not None:
                return converted
        except Exception:
            continue
    return default


def _get_int_attr(obj: Any, field_names: List[str], default: int = 0) -> int:
    for field_name in field_names:
        try:
            value = obj.get(field_name) if isinstance(obj, dict) else getattr(obj, field_name, None)
            if value is None:
                continue
            return int(value)
        except Exception:
            continue
    return default


def _get_bool_attr(obj: Any, field_names: List[str], default: bool = False) -> bool:
    for field_name in field_names:
        try:
            value = obj.get(field_name) if isinstance(obj, dict) else getattr(obj, field_name, None)
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                if value.strip().lower() in {"true", "1", "yes", "y"}:
                    return True
                if value.strip().lower() in {"false", "0", "no", "n"}:
                    return False
            if isinstance(value, (int, float)):
                return bool(value)
        except Exception:
            continue
    return default


def _get_first_datetime_attr(obj: Any, field_names: List[str]) -> Optional[datetime]:
    for field_name in field_names:
        try:
            value = obj.get(field_name) if isinstance(obj, dict) else getattr(obj, field_name, None)
            dt = _parse_datetime_any(value)
            if dt is not None:
                return dt
        except Exception:
            continue
    return None


def _parse_datetime_any(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    s = str(value).strip()
    if not s:
        return None

    s = s.replace("Z", "+00:00")

    try:
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:
        pass

    formats = [
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
    for fmt in formats:
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    if isinstance(value, (int, float)):
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)

    s = str(value).strip()
    if not s:
        return None

    s = s.replace("R", "").replace("ZAR", "").replace(" ", "")

    if s.count(",") > 0 and s.count(".") > 0:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    else:
        s = s.replace(",", "")

    try:
        return float(s)
    except Exception:
        return None


def _dedupe_preserve_order(values: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for v in values:
        key = v.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out
