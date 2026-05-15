import re
from typing import Optional


PROVINCE_MAP = {
    "eastern cape": "Eastern Cape",
    "free state": "Free State",
    "gauteng": "Gauteng",
    "kwa-zulu natal": "KwaZulu-Natal",
    "kwazulu natal": "KwaZulu-Natal",
    "kwazulu-natal": "KwaZulu-Natal",
    "limpopo": "Limpopo",
    "mpumalanga": "Mpumalanga",
    "north west": "North West",
    "northern cape": "Northern Cape",
    "western cape": "Western Cape",
}

NOTICE_TYPE_MAP = {
    "tender": "tender",
    "rfq": "rfq",
    "request for quotation": "rfq",
    "quotation": "rfq",
    "bid": "bid",
    "request for proposal": "rfp",
    "rfp": "rfp",
}

CATEGORY_KEYWORDS = {
    "water infrastructure materials": [
        "pipe",
        "pipes",
        "hdpe",
        "valve",
        "valves",
        "fittings",
        "water meter",
        "water meters",
        "water",
        "sewer",
        "wastewater",
        "reticulation",
        "pump",
        "pumps",
    ],
    "electrical materials": [
        "electrical",
        "cable",
        "cables",
        "transformer",
        "transformers",
        "switchgear",
        "meter box",
        "meter boxes",
        "lighting",
        "led",
    ],
    "road and civil materials": [
        "asphalt",
        "bitumen",
        "road",
        "roads",
        "paving",
        "kerb",
        "kerbs",
        "stormwater",
        "culvert",
        "culverts",
        "traffic signs",
        "road signs",
    ],
    "building materials": [
        "cement",
        "brick",
        "bricks",
        "roof",
        "roofing",
        "paint",
        "doors",
        "windows",
        "plumbing",
        "hardware",
    ],
    "ict and office equipment": [
        "laptop",
        "laptops",
        "printer",
        "printers",
        "computer",
        "computers",
        "server",
        "servers",
        "software",
        "licences",
        "license",
        "network",
    ],
    "medical supplies": [
        "medical",
        "hospital",
        "medicine",
        "drugs",
        "pharmaceutical",
        "consumables",
        "ppe",
        "gloves",
        "syringes",
    ],
    "fleet and transport": [
        "vehicle",
        "vehicles",
        "truck",
        "trucks",
        "tyres",
        "fuel",
        "transport",
        "bus",
        "buses",
    ],
    "general supply and delivery": [
        "supply",
        "delivery",
        "procurement",
        "goods",
        "materials",
        "equipment",
    ],
}


def _clean_text(value: Optional[str]) -> str:
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"&", " and ", value)
    value = re.sub(r"[^a-z0-9\s\-\/]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def normalize_buyer_name(buyer_name: Optional[str]) -> str:
    value = _clean_text(buyer_name)

    replacements = [
        (" municipality", ""),
        (" local municipality", ""),
        (" metropolitan municipality", ""),
        (" metro municipality", ""),
        (" district municipality", ""),
        (" soc ltd", ""),
        (" soc limited", ""),
        (" ltd", ""),
        (" limited", ""),
        (" south africa", ""),
        (" republic of south africa", ""),
        (" department of ", "dept "),
    ]

    for old, new in replacements:
        value = value.replace(old, new)

    value = re.sub(r"\bthe\b", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value.title()


def normalize_province(province: Optional[str]) -> Optional[str]:
    value = _clean_text(province)
    if not value:
        return None
    return PROVINCE_MAP.get(value, province.strip() if province else None)


def normalize_notice_type(notice_type: Optional[str], title: Optional[str] = None) -> str:
    base = _clean_text(notice_type)
    title_text = _clean_text(title)

    if base in NOTICE_TYPE_MAP:
        return NOTICE_TYPE_MAP[base]

    for key, normalized in NOTICE_TYPE_MAP.items():
        if key in title_text:
            return normalized

    return "tender"


def normalize_category(title: Optional[str], description: Optional[str] = None) -> str:
    haystack = f"{_clean_text(title)} {_clean_text(description)}".strip()

    if not haystack:
        return "general supply and delivery"

    best_category = "general supply and delivery"
    best_hits = 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in haystack)
        if hits > best_hits:
            best_hits = hits
            best_category = category

    return best_category
