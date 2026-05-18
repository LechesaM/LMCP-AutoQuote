import os
import re
from typing import Any, Dict, Iterable, List, Tuple

# ---------------------------------------------------------
# Smart filtering for LMCP: keep only relevant opportunities
# ---------------------------------------------------------
# You can override these via environment variables:
#
#   INCLUDE_KEYWORDS="construction,civil,building,road,stormwater"
#   EXCLUDE_KEYWORDS="security guarding,catering,cleaning"
#   FILTER_MIN_MATCH="1"
#
# If INCLUDE_KEYWORDS is empty, everything passes through.
# ---------------------------------------------------------

DEFAULT_INCLUDE = [
    # Construction / Built environment
    "construction", "building", "general building", "maintenance", "refurbishment",
    "renovation", "repairs", "roof", "painting", "tiling", "carpentry", "joinery",
    # Civil / Roads / Earthworks
    "civil", "road", "roads", "paving", "asphalt", "reseal", "surfacing",
    "earthworks", "excavation", "trenching", "stormwater", "drainage", "culvert",
    "kerb", "sidewalk", "walkway", "pavement",
    # Water / Plumbing / Reticulation
    "plumbing", "water", "reticulation", "pipeline", "pipe", "valve", "pump",
    "reservoir", "borehole", "wastewater", "sewer", "sanitation", "treatment",
    # Electrical (lightly)
    "electrical", "wiring", "distribution board", "db board", "cable",
    "solar", "inverter", "generator",
    # Supply & delivery (LMCP supply side)
    "supply", "supply and delivery", "supply & delivery", "delivery",
    "materials", "building materials", "hardware", "cement", "bricks", "sand", "stone",
    # Signs / traffic accommodation (you do SANRAL-type work)
    "road signs", "signage", "traffic accommodation", "traffic control", "temporary signage",
]

DEFAULT_EXCLUDE = [
    # Common “noise” categories you probably don’t want for LMCP auto-quoting
    "catering", "security guarding", "guarding", "cleaning", "janitorial",
    "travel", "accommodation", "conference", "events management",
    "printing", "promotional", "branding",
    "medical", "pharmaceutical",
]

def _split_csv(value: str) -> List[str]:
    parts = [p.strip() for p in value.split(",")]
    return [p for p in parts if p]

def _normalize(text: str) -> str:
    # Lowercase + collapse whitespace
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _flatten_text(opportunity: Any) -> str:
    """
    Tries to extract useful searchable text from an opportunity record that could be:
    - dict (common)
    - pydantic model (has dict())
    - any object (fallback to str)
    """
    try:
        if hasattr(opportunity, "dict"):
            opportunity = opportunity.dict()  # pydantic
    except Exception:
        pass

    if isinstance(opportunity, dict):
        # Prefer common fields, then fallback to whole dict string
        fields = []
        for k in [
            "title", "name", "description", "summary",
            "buyer", "procuring_entity", "procuringEntity",
            "department", "org", "entity",
            "category", "classification",
        ]:
            v = opportunity.get(k)
            if v:
                fields.append(str(v))

        # include nested structures if present
        for k in ["tender", "planning", "parties"]:
            v = opportunity.get(k)
            if v:
                fields.append(str(v))

        blob = " | ".join(fields) if fields else str(opportunity)
        return _normalize(blob)

    return _normalize(str(opportunity))

def get_keywords() -> Tuple[List[str], List[str], int]:
    include_raw = os.getenv("INCLUDE_KEYWORDS", "").strip()
    exclude_raw = os.getenv("EXCLUDE_KEYWORDS", "").strip()
    min_match_raw = os.getenv("FILTER_MIN_MATCH", "1").strip()

    include = _split_csv(include_raw) if include_raw else DEFAULT_INCLUDE[:]
    exclude = _split_csv(exclude_raw) if exclude_raw else DEFAULT_EXCLUDE[:]

    try:
        min_match = int(min_match_raw)
    except Exception:
        min_match = 1

    # Normalize keyword lists
    include = [_normalize(k) for k in include if k.strip()]
    exclude = [_normalize(k) for k in exclude if k.strip()]

    return include, exclude, max(0, min_match)

def is_relevant(opportunity: Any) -> bool:
    include, exclude, min_match = get_keywords()
    text = _flatten_text(opportunity)

    # Exclusions: if any excluded phrase appears, drop it
    for bad in exclude:
        if bad and bad in text:
            return False

    # If include list is empty, pass everything
    if not include:
        return True

    # Inclusion: require at least min_match keyword hits
    hits = 0
    for good in include:
        if good and good in text:
            hits += 1
            if hits >= max(1, min_match):
                return True

    return False

def filter_opportunities(opportunities: Iterable[Any]) -> List[Any]:
    kept: List[Any] = []
    for op in opportunities:
        if is_relevant(op):
            kept.append(op)
    return kept
