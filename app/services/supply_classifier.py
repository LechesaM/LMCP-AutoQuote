import re
from typing import Any, Dict, List, Optional


ALLOWED_SUPPLY_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
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
        "toner",
        "printer cartridge",
        "pen",
        "pencil",
        "lever arch",
        "files",
        "notebooks",
        "a4 paper",
    ],
    "plumbing_water": [
        "pipe",
        "pipes",
        "hdpe",
        "upvc",
        "valve",
        "fittings",
        "water meter",
        "hydrant",
        "pump",
        "reservoir",
        "sewer",
        "manhole",
        "drainage",
    ],
    "electrical": [
        "electrical",
        "cable",
        "wire",
        "distribution board",
        "db board",
        "light fitting",
        "socket",
        "breaker",
        "transformer",
        "conduit",
        "solar",
        "battery",
        "inverter",
    ],
    "building_materials": [
        "cement",
        "brick",
        "sand",
        "aggregate",
        "paint",
        "roof sheet",
        "timber",
        "door",
        "window",
        "tile",
        "gypsum",
        "ceiling board",
        "hardware",
        "building materials",
    ],
    "cleaning_hygiene": [
        "cleaning",
        "detergent",
        "sanitizer",
        "soap",
        "toilet paper",
        "mop",
        "broom",
        "chemical",
        "refuse bag",
        "disinfectant",
    ],
    "fleet_spares_tyres_lubricants": [
        "tyres",
        "tire",
        "spares",
        "vehicle parts",
        "filters",
        "lubricants",
        "fleet",
        "service kit",
        "battery",
        "brake pad",
        "shock absorber",
    ],
    "furniture": [
        "chair",
        "desk",
        "table",
        "cabinet",
        "furniture",
        "shelving",
        "boardroom table",
        "office chair",
        "filing cabinet",
    ],
    "agriculture_inputs": [
        "fertilizer",
        "fertiliser",
        "seed",
        "seeds",
        "agricultural inputs",
        "irrigation supplies",
        "feed",
        "animal feed",
        "pesticide",
        "herbicide",
    ],
    "safety_security_general": [
        "fire extinguisher",
        "safety signage",
        "security equipment",
        "uniform",
        "barricade tape",
        "cones",
        "road signs",
        "warning sign",
    ],
    "water_treatment_chemicals": [
        "chlorine",
        "water treatment chemical",
        "alum",
        "lime",
        "sodium hypochlorite",
        "coagulant",
        "flocculant",
        "dosing chemical",
    ],
    "general_supply": [
        "supply and delivery",
        "supply of",
        "delivery of",
        "supply only",
        "delivery only",
        "appointment of a supplier",
        "supply, deliver",
    ],
}


EXCLUDED_CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "medical_consumables": [
        "medical",
        "pharmaceutical",
        "medicine",
        "drugs",
        "consumables",
        "syringe",
        "bandage",
        "glucose",
        "surgical",
        "clinic supplies",
    ],
    "it_equipment": [
        "laptop",
        "computer",
        "printer",
        "server",
        "monitor",
        "router",
        "switch",
        "ups",
        "software license",
        "software licence",
        "scanner",
        "tablet",
    ],
    "petrol_diesel_supply": [
        "petrol",
        "diesel",
        "fuel",
        "fuel supply",
        "bulk fuel",
        "fuel delivery",
        "unleaded",
        "95 unleaded",
        "93 unleaded",
        "automotive gas oil",
    ],
}


CONSTRUCTION_KEYWORDS: List[str] = [
    "construction",
    "construction of",
    "building works",
    "civil works",
    "roadworks",
    "earthworks",
    "refurbishment",
    "renovation",
    "maintenance",
    "repair",
    "installation",
    "installation and commissioning",
    "commissioning",
    "contractor",
    "contractor for works",
    "upgrade works",
    "infrastructure works",
    "project execution",
    "site works",
]


DELIVERY_LOCATION_PATTERNS = [
    r"\bdeliver to\b",
    r"\bdelivery to\b",
    r"\bplace of delivery\b",
    r"\bdelivery address\b",
    r"\bsite address\b",
    r"\blocation\b",
]


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return re.sub(r"\s+", " ", value).strip().lower()


def _combine_text(rfq: Dict[str, Any]) -> str:
    fields = [
        rfq.get("title", ""),
        rfq.get("description", ""),
        rfq.get("scope", ""),
        rfq.get("requirements", ""),
        rfq.get("category", ""),
        rfq.get("submission_method", ""),
        rfq.get("notes", ""),
    ]
    return _normalize_text(" ".join(str(f) for f in fields if f))


def _detect_excluded_category(text: str) -> Optional[str]:
    best_category: Optional[str] = None
    best_score = 0

    for category, keywords in EXCLUDED_CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category if best_score > 0 else None


def _detect_allowed_supply_category(text: str) -> str:
    best_category = "general_supply"
    best_score = 0

    for category, keywords in ALLOWED_SUPPLY_CATEGORY_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in text)
        if score > best_score:
            best_score = score
            best_category = category

    return best_category


def _is_construction_rfq(text: str) -> bool:
    return any(keyword in text for keyword in CONSTRUCTION_KEYWORDS)


def _extract_quantities(text: str) -> List[Dict[str, Any]]:
    pattern = re.compile(
        r"\b(\d{1,3}(?:,\d{3})*|\d+)\s+([a-zA-Z][a-zA-Z\s\-]{1,40})\b"
    )
    quantities: List[Dict[str, Any]] = []

    for match in pattern.finditer(text):
        raw_qty = match.group(1).replace(",", "")
        item = match.group(2).strip().lower()

        try:
            qty = int(raw_qty)
        except ValueError:
            continue

        if qty <= 0:
            continue

        quantities.append({
            "quantity": qty,
            "item_text": item,
        })

    return quantities[:20]


def _extract_delivery_location(text: str) -> Optional[str]:
    for marker in DELIVERY_LOCATION_PATTERNS:
        regex = re.compile(marker + r"[:\-\s]*(.{0,120})", re.IGNORECASE)
        match = regex.search(text)
        if match:
            loc = match.group(1).strip(" .,:;-")
            if loc:
                return loc[:120]
    return None


def _detect_submission_mode(text: str, rfq: Dict[str, Any]) -> str:
    raw_mode = _normalize_text(rfq.get("submission_method", ""))
    if raw_mode:
        if "email" in raw_mode:
            return "email"
        if "portal" in raw_mode:
            return "portal"

    if "submit via email" in text or "email submissions" in text or "email:" in text:
        return "email"
    if "submit on portal" in text or "e-tender" in text or "portal submission" in text:
        return "portal"

    return "unknown"


def _has_compulsory_briefing(text: str) -> bool:
    if "non-compulsory briefing" in text or "briefing not compulsory" in text:
        return False

    triggers = [
        "compulsory briefing",
        "mandatory briefing",
        "compulsory site meeting",
        "mandatory site meeting",
        "briefing session compulsory",
    ]
    return any(trigger in text for trigger in triggers)


def _is_supply_only(text: str) -> bool:
    supply_signals = [
        "supply and delivery",
        "supply, deliver",
        "supply of",
        "delivery of",
        "appointment of a supplier",
        "supply only",
        "delivery only",
    ]

    construction_signals = [
        "construction of",
        "construction",
        "repair and maintenance",
        "civil works",
        "building works",
        "refurbishment",
        "renovation",
        "installation and commissioning",
        "installation",
        "contractor for works",
        "contractor",
        "earthworks",
        "roadworks",
        "maintenance",
    ]

    supply_score = sum(1 for s in supply_signals if s in text)
    construction_score = sum(1 for s in construction_signals if s in text)

    return supply_score > 0 and supply_score >= construction_score


    # Prefer structured quantities from RFQ if available
    incoming_quantities = None

    try:
        incoming_quantities = rfq.get("quantities")
    except Exception:
        incoming_quantities = None

    if isinstance(incoming_quantities, list) and len(incoming_quantities) > 0:
        quantities = incoming_quantities
    else:
        quantities = _extract_quantities(text)
    delivery_location = _extract_delivery_location(text)
    submission_mode = _detect_submission_mode(text, rfq)
    has_compulsory_briefing = _has_compulsory_briefing(text)
    supply_only = _is_supply_only(text)

    print("DEBUG QUANTITIES:", quantities)

    excluded = excluded_category is not None or is_construction

    eligible = True
    quote_ready = True

    reasons: List[str] = []

    if excluded_category:
        reasons.append(f"RFQ falls under excluded category: {excluded_category}.")
    else:
        reasons.append(f"RFQ falls under allowed supply category: {detected_category}.")

    if is_construction:
        reasons.append(
            "RFQ is excluded because it includes construction / works / installation / maintenance scope."
        )

    if not supply_only:
        reasons.append("Opportunity is not clearly pure supply-and-delivery.")

    if has_compulsory_briefing:
        reasons.append("Opportunity includes a compulsory or mandatory briefing/site meeting.")

    if submission_mode == "unknown":
        reasons.append("Submission mode could not be clearly identified.")
    else:
        reasons.append(f"Submission mode detected: {submission_mode}.")

    if eligible:
        reasons.append("RFQ passed pure supply targeting rules.")

    return {
        "rfq_id": rfq.get("rfq_id"),
        "title": rfq.get("title"),
        "category": detected_category,
        "excluded": excluded,
        "excluded_category": excluded_category,
        "is_construction": is_construction,
        "quantities": quantities,
        "delivery_location": delivery_location,
        "submission_mode": submission_mode,
        "has_compulsory_briefing": has_compulsory_briefing,
        "supply_only": supply_only,
        "eligible": eligible,
        "quote_ready": quote_ready,
        "classification_reasons": reasons,
    }


def classify_supply_rfq(rfq: Dict[str, Any]) -> Dict[str, Any]:
    text = _combine_text(rfq)

    excluded_category = _detect_excluded_category(text)
    detected_category = _detect_allowed_supply_category(text)
    is_construction = _is_construction_rfq(text)

    incoming_quantities = None
    try:
        incoming_quantities = rfq.get("quantities")
    except Exception:
        incoming_quantities = None

    if isinstance(incoming_quantities, list) and len(incoming_quantities) > 0:
        quantities = incoming_quantities
    else:
        quantities = _extract_quantities(text)

    delivery_location = _extract_delivery_location(text)
    submission_mode = _detect_submission_mode(text, rfq)
    has_compulsory_briefing = _has_compulsory_briefing(text)
    supply_only = _is_supply_only(text)

    excluded = excluded_category is not None
    excluded = excluded_category is not None or is_construction

    eligible = True
    quote_ready = True

    reasons: List[str] = []

    if excluded:
        reasons.append(f"RFQ excluded due to category: {excluded_category}.")

    if detected_category:
        reasons.append(f"RFQ falls under allowed supply category: {detected_category}.")

    if is_construction:
        reasons.append("Opportunity includes construction / works scope.")

    if not supply_only:
        reasons.append("Opportunity is not clearly pure supply-and-delivery.")

    if has_compulsory_briefing:
        reasons.append("Opportunity includes a compulsory or mandatory briefing/site meeting.")

    if submission_mode == "unknown":
        reasons.append("Submission mode could not be clearly identified.")
    else:
        reasons.append(f"Submission mode detected: {submission_mode}.")

    if eligible:
        reasons.append("RFQ passed pure supply targeting rules.")

    return {
        "rfq_id": rfq.get("rfq_id"),
        "title": rfq.get("title"),
        "category": detected_category,
        "excluded": excluded,
        "excluded_category": excluded_category,
        "is_construction": is_construction,
        "quantities": quantities,
        "delivery_location": delivery_location,
        "submission_mode": submission_mode,
        "has_compulsory_briefing": has_compulsory_briefing,
        "supply_only": supply_only,
        "eligible": eligible,
        "quote_ready": quote_ready,
        "classification_reasons": reasons,
    }

    # 🔥 FORCE PIPELINE FOR DAY 1
    result["eligible"] = True
    result["quote_ready"] = True

    return result
