from __future__ import annotations

import math
import re
from typing import Any, Dict, List, Optional


DEFAULT_MIN_PROFIT_ZAR = 30000.0
DEFAULT_MIN_MARGIN_PERCENT = 25.0


EXCLUDED_CATEGORY_KEYWORDS: List[str] = [
    "medical consumable",
    "medical consumables",
    "medical supplies",
    "pharmaceutical",
    "pharmaceuticals",
    "medicine",
    "medicines",
    "drugs",
    "syringe",
    "syringes",
    "needle",
    "needles",
    "hospital consumables",
    "it equipment",
    "information technology equipment",
    "laptop",
    "laptops",
    "desktop computer",
    "desktop computers",
    "computer equipment",
    "server",
    "servers",
    "printer",
    "printers",
    "network equipment",
    "router",
    "routers",
    "switches",
    "petrol",
    "diesel",
    "fuel",
    "lubricants",
]


SUPPLY_KEYWORDS: List[str] = [
    "supply",
    "supply and delivery",
    "delivery",
    "supply, delivery",
    "appointment of a service provider for supply",
    "appointment of service provider for supply",
    "procurement of",
    "purchase of",
    "supply of",
    "delivery of",
    "supply and install",
    "supply and installation",
    "supply, deliver and offload",
    "supply and offloading",
    "supply and distribute",
]


DISALLOWED_WORKS_KEYWORDS: List[str] = [
    "construction",
    "building works",
    "civil works",
    "roadworks",
    "road works",
    "maintenance of roads",
    "rehabilitation",
    "upgrading of road",
    "refurbishment",
    "plumbing works",
    "electrical works",
    "installation only",
    "professional services",
    "consulting services",
    "consultancy",
    "security services",
    "cleaning services",
    "guarding",
]


PRIORITY_SECTOR_KEYWORDS: Dict[str, List[str]] = {
    "ppe": [
        "ppe",
        "personal protective equipment",
        "gloves",
        "helmets",
        "gumboots",
        "overalls",
        "reflective vest",
        "safety boots",
        "face shield",
        "mask",
    ],
    "stationery_office": [
        "stationery",
        "office supplies",
        "paper",
        "a4 paper",
        "toner",
        "printer cartridge",
        "pen",
        "pencil",
        "files",
        "notebooks",
        "lever arch",
    ],
    "plumbing_water_materials": [
        "pipes",
        "pipe",
        "hdpe",
        "upvc",
        "valves",
        "valve",
        "fittings",
        "hydrant",
        "water meter",
        "water tank",
        "plumbing material",
    ],
    "electrical_materials": [
        "cable",
        "cables",
        "electrical material",
        "distribution board",
        "light fitting",
        "led",
        "socket outlet",
        "circuit breaker",
        "transformer",
    ],
    "building_materials": [
        "cement",
        "brick",
        "bricks",
        "roof sheeting",
        "timber",
        "door frame",
        "window frame",
        "paint",
        "aggregate",
        "sand",
    ],
    "furniture_appliances": [
        "furniture",
        "desk",
        "chair",
        "filing cabinet",
        "bed",
        "mattress",
        "appliance",
        "fridge",
        "microwave",
        "stove",
    ],
    "general_bulk_supply": [
        "consumables",
        "materials",
        "supply and delivery",
        "bulk supply",
        "procurement of goods",
        "supply of goods",
    ],
}


PROVINCE_KEYWORDS = {
    "eastern cape": "EC",
    "free state": "FS",
    "gauteng": "GP",
    "kwazulu-natal": "KZN",
    "kwa-zulu natal": "KZN",
    "limpopo": "LP",
    "mpumalanga": "MP",
    "north west": "NW",
    "northern cape": "NC",
    "western cape": "WC",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip().replace(",", "")
        if not text:
            return default
        return float(text)
    except Exception:
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except Exception:
        return default


def _clean_text(*parts: Any) -> str:
    return " ".join(str(part or "") for part in parts).strip().lower()


def _contains_any(text: str, keywords: List[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _count_matches(text: str, keywords: List[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def detect_province(text: str) -> Optional[str]:
    for key, code in PROVINCE_KEYWORDS.items():
        if key in text:
            return code
    return None


def detect_priority_sector(text: str) -> Optional[str]:
    best_sector = None
    best_count = 0

    for sector, keywords in PRIORITY_SECTOR_KEYWORDS.items():
        count = _count_matches(text, keywords)
        if count > best_count:
            best_count = count
            best_sector = sector

    return best_sector


def has_briefing_session(rfq: Dict[str, Any]) -> bool:
    flags = [
        rfq.get("has_briefing_session"),
        rfq.get("briefing_session_required"),
        rfq.get("compulsory_briefing"),
        rfq.get("mandatory_briefing"),
        rfq.get("site_meeting_required"),
    ]

    if any(bool(flag) for flag in flags):
        return True

    text = _clean_text(
        rfq.get("title"),
        rfq.get("description"),
        rfq.get("scope"),
        rfq.get("briefing_details"),
        rfq.get("special_conditions"),
    )

    briefing_keywords = [
        "briefing session",
        "compulsory briefing",
        "mandatory briefing",
        "compulsory site meeting",
        "mandatory site meeting",
        "site briefing",
        "briefing meeting",
        "clarification meeting",
        "site inspection",
        "compulsory inspection",
    ]
    return _contains_any(text, briefing_keywords)


def is_supply_tender(rfq: Dict[str, Any]) -> bool:
    text = _clean_text(
        rfq.get("title"),
        rfq.get("description"),
        rfq.get("scope"),
        rfq.get("category"),
        rfq.get("industry"),
        rfq.get("tender_type"),
    )

    positive = _contains_any(text, SUPPLY_KEYWORDS)
    negative = _contains_any(text, DISALLOWED_WORKS_KEYWORDS)

    if positive and not negative:
        return True

    if rfq.get("industry") and "supply" in str(rfq.get("industry")).lower():
        return True

    if rfq.get("tender_type") and "goods" in str(rfq.get("tender_type")).lower():
        return True

    return False


def is_excluded_category(rfq: Dict[str, Any]) -> bool:
    text = _clean_text(
        rfq.get("title"),
        rfq.get("description"),
        rfq.get("scope"),
        rfq.get("category"),
        rfq.get("industry"),
    )
    return _contains_any(text, EXCLUDED_CATEGORY_KEYWORDS)


def estimate_contract_value_zar(rfq: Dict[str, Any]) -> float:
    direct_fields = [
        "estimated_value_zar",
        "estimated_contract_value",
        "budget_amount",
        "budget_zar",
        "contract_value",
        "estimated_value",
    ]

    for field in direct_fields:
        value = _safe_float(rfq.get(field), default=0.0)
        if value > 0:
            return value

    text = _clean_text(
        rfq.get("title"),
        rfq.get("description"),
        rfq.get("scope"),
        rfq.get("budget_notes"),
    )

    currency_patterns = [
        r"r\s?(\d[\d\s,\.]{3,})",
        r"zar\s?(\d[\d\s,\.]{3,})",
    ]

    extracted_values: List[float] = []
    for pattern in currency_patterns:
        matches = re.findall(pattern, text, flags=re.IGNORECASE)
        for match in matches:
            number_text = match.replace(" ", "").replace(",", "")
            try:
                extracted_values.append(float(number_text))
            except Exception:
                continue

    if extracted_values:
        return max(extracted_values)

    return 0.0


def estimate_margin_percent(rfq: Dict[str, Any], contract_value_zar: float) -> float:
    explicit_margin = _safe_float(rfq.get("estimated_margin_percent"), default=0.0)
    if explicit_margin > 0:
        return explicit_margin

    text = _clean_text(
        rfq.get("title"),
        rfq.get("description"),
        rfq.get("scope"),
        rfq.get("category"),
    )

    sector = detect_priority_sector(text)

    sector_margin_defaults = {
        "ppe": 28.0,
        "stationery_office": 26.0,
        "plumbing_water_materials": 27.0,
        "electrical_materials": 26.0,
        "building_materials": 25.0,
        "furniture_appliances": 25.0,
        "general_bulk_supply": 25.0,
    }

    if sector in sector_margin_defaults:
        return sector_margin_defaults[sector]

    if contract_value_zar >= 5_000_000:
        return 25.0
    if contract_value_zar >= 1_000_000:
        return 26.0
    if contract_value_zar >= 300_000:
        return 28.0
    if contract_value_zar > 0:
        return 30.0

    return DEFAULT_MIN_MARGIN_PERCENT


def estimate_profit_zar(contract_value_zar: float, margin_percent: float) -> float:
    if contract_value_zar <= 0:
        return 0.0
    return contract_value_zar * (margin_percent / 100.0)


def score_deadline(days_to_close: Optional[int]) -> float:
    if days_to_close is None:
        return 10.0
    if days_to_close < 0:
        return 0.0
    if days_to_close <= 1:
        return 4.0
    if days_to_close <= 3:
        return 8.0
    if days_to_close <= 7:
        return 15.0
    if days_to_close <= 14:
        return 18.0
    if days_to_close <= 30:
        return 14.0
    return 10.0


def score_value(contract_value_zar: float) -> float:
    if contract_value_zar <= 0:
        return 5.0
    if contract_value_zar < 100_000:
        return 6.0
    if contract_value_zar < 300_000:
        return 10.0
    if contract_value_zar < 1_000_000:
        return 16.0
    if contract_value_zar < 5_000_000:
        return 22.0
    if contract_value_zar < 20_000_000:
        return 26.0
    return 28.0


def score_profit(profit_zar: float) -> float:
    if profit_zar <= 0:
        return 0.0
    if profit_zar < 30_000:
        return 5.0
    if profit_zar < 75_000:
        return 12.0
    if profit_zar < 150_000:
        return 18.0
    if profit_zar < 300_000:
        return 24.0
    return 30.0


def score_margin(margin_percent: float) -> float:
    if margin_percent < 20:
        return 2.0
    if margin_percent < 25:
        return 8.0
    if margin_percent < 30:
        return 14.0
    if margin_percent < 35:
        return 18.0
    return 20.0


def score_sector_fit(text: str) -> float:
    sector = detect_priority_sector(text)
    if sector is None:
        return 6.0

    high_priority = {
        "ppe",
        "stationery_office",
        "plumbing_water_materials",
        "electrical_materials",
        "building_materials",
        "general_bulk_supply",
    }
    return 12.0 if sector in high_priority else 9.0


def score_issuing_entity(rfq: Dict[str, Any]) -> float:
    entity = _clean_text(
        rfq.get("issuing_entity"),
        rfq.get("buyer"),
        rfq.get("institution"),
        rfq.get("department"),
    )

    premium_buyers = [
        "municipality",
        "local municipality",
        "district municipality",
        "provincial government",
        "department of",
        "school",
        "hospital",
        "university",
        "eskom",
        "transnet",
        "sanral",
        "public works",
        "human settlements",
        "water board",
    ]

    matches = _count_matches(entity, premium_buyers)
    if matches >= 2:
        return 8.0
    if matches == 1:
        return 6.0
    return 3.0


class TenderScoringService:
    @classmethod
    def evaluate_rfq(cls, rfq: Dict[str, Any]) -> Dict[str, Any]:
        text = _clean_text(
            rfq.get("title"),
            rfq.get("description"),
            rfq.get("scope"),
            rfq.get("category"),
            rfq.get("industry"),
        )

        contract_value_zar = estimate_contract_value_zar(rfq)
        margin_percent = estimate_margin_percent(rfq, contract_value_zar)
        profit_zar = estimate_profit_zar(contract_value_zar, margin_percent)

        days_to_close = rfq.get("days_to_close")
        if days_to_close is not None:
            days_to_close = _safe_int(days_to_close, default=0)

        province_code = detect_province(text)
        sector = detect_priority_sector(text)

        supply_ok = is_supply_tender(rfq)
        category_excluded = is_excluded_category(rfq)
        briefing_present = has_briefing_session(rfq)
        profit_ok = profit_zar >= DEFAULT_MIN_PROFIT_ZAR
        margin_ok = margin_percent >= DEFAULT_MIN_MARGIN_PERCENT

        rejection_reasons: List[str] = []

        if not supply_ok:
            rejection_reasons.append("Not a supply-and-delivery tender")
        if category_excluded:
            rejection_reasons.append("Excluded category")
        if briefing_present:
            rejection_reasons.append("Has briefing/session requirement")
        if not profit_ok:
            rejection_reasons.append("Estimated profit below R30,000")
        if not margin_ok:
            rejection_reasons.append("Estimated margin below 25%")

        deadline_score = score_deadline(days_to_close)
        value_score = score_value(contract_value_zar)
        profit_score = score_profit(profit_zar)
        margin_score = score_margin(margin_percent)
        sector_fit_score = score_sector_fit(text)
        entity_score = score_issuing_entity(rfq)

        total_score = round(
            deadline_score
            + value_score
            + profit_score
            + margin_score
            + sector_fit_score
            + entity_score,
            2,
        )

        if total_score >= 80:
            grade = "A"
        elif total_score >= 65:
            grade = "B"
        elif total_score >= 50:
            grade = "C"
        else:
            grade = "D"

        recommended_for_quote = (
            supply_ok
            and not category_excluded
            and not briefing_present
            and profit_ok
            and margin_ok
            and total_score >= 65
        )

        evaluation = {
            "title": rfq.get("title"),
            "reference_number": rfq.get("reference_number"),
            "portal_slug": rfq.get("portal_slug"),
            "issuing_entity": rfq.get("issuing_entity"),
            "province_code": province_code,
            "priority_sector": sector,
            "estimated_contract_value_zar": round(contract_value_zar, 2),
            "estimated_margin_percent": round(margin_percent, 2),
            "estimated_profit_zar": round(profit_zar, 2),
            "days_to_close": days_to_close,
            "flags": {
                "is_supply_tender": supply_ok,
                "is_excluded_category": category_excluded,
                "has_briefing_session": briefing_present,
                "meets_min_profit": profit_ok,
                "meets_min_margin": margin_ok,
            },
            "score_breakdown": {
                "deadline_score": deadline_score,
                "value_score": value_score,
                "profit_score": profit_score,
                "margin_score": margin_score,
                "sector_fit_score": sector_fit_score,
                "issuing_entity_score": entity_score,
            },
            "tender_score": total_score,
            "tender_grade": grade,
            "recommended_for_quote": recommended_for_quote,
            "rejection_reasons": rejection_reasons,
        }

        merged = dict(rfq)
        merged["scoring"] = evaluation
        merged["recommended_for_quote"] = recommended_for_quote
        merged["tender_score"] = total_score
        merged["tender_grade"] = grade
        merged["estimated_profit_zar"] = round(profit_zar, 2)
        merged["estimated_margin_percent"] = round(margin_percent, 2)
        merged["estimated_contract_value_zar"] = round(contract_value_zar, 2)
        merged["priority_sector"] = sector
        merged["province_code"] = province_code
        merged["rejection_reasons"] = rejection_reasons

        return merged

    @classmethod
    def evaluate_many(cls, rfqs: List[Dict[str, Any]]) -> Dict[str, Any]:
        scored_items: List[Dict[str, Any]] = []

        for rfq in rfqs:
            try:
                scored_items.append(cls.evaluate_rfq(rfq))
            except Exception as exc:
                fallback = dict(rfq)
                fallback["scoring_error"] = str(exc)
                fallback["recommended_for_quote"] = False
                fallback["tender_score"] = 0.0
                fallback["tender_grade"] = "D"
                fallback["rejection_reasons"] = ["Scoring error"]
                scored_items.append(fallback)

        recommended_items = [item for item in scored_items if item.get("recommended_for_quote")]
        recommended_items = sorted(
            recommended_items,
            key=lambda x: (
                _safe_float(x.get("tender_score")),
                _safe_float(x.get("estimated_profit_zar")),
            ),
            reverse=True,
        )

        scored_items = sorted(
            scored_items,
            key=lambda x: (
                _safe_float(x.get("tender_score")),
                _safe_float(x.get("estimated_profit_zar")),
            ),
            reverse=True,
        )

        return {
            "count": len(scored_items),
            "recommended_count": len(recommended_items),
            "items": scored_items,
            "recommended_items": recommended_items,
        }
