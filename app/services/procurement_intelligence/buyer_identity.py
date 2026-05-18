import re
from typing import Dict, Optional

from app.services.procurement_intelligence.normalizer import (
    normalize_buyer_name,
    normalize_province,
)


def build_buyer_code(buyer_name: Optional[str], province: Optional[str] = None) -> str:
    normalized_name = normalize_buyer_name(buyer_name)
    normalized_province = normalize_province(province)

    base = normalized_name.lower()
    base = re.sub(r"[^a-z0-9]+", "_", base).strip("_")

    if normalized_province:
        province_code = re.sub(r"[^a-z0-9]+", "_", normalized_province.lower()).strip("_")
        return f"{base}__{province_code}"

    return base or "unknown_buyer"


def identify_buyer(
    buyer_name: Optional[str],
    province: Optional[str] = None,
    portal_source: Optional[str] = None,
) -> Dict[str, Optional[str]]:
    normalized_buyer_name = normalize_buyer_name(buyer_name)
    normalized_province = normalize_province(province)
    buyer_code = build_buyer_code(normalized_buyer_name, normalized_province)

    buyer_type = "public_entity"
    name_lower = normalized_buyer_name.lower()

    if "municipality" in (buyer_name or "").lower() or "metro" in name_lower:
        buyer_type = "municipality"
    elif "dept" in name_lower or "department" in (buyer_name or "").lower():
        buyer_type = "department"
    elif any(x in name_lower for x in ["eskom", "transnet", "sanral", "dbsa", "prasa", "idc"]):
        buyer_type = "soe"

    return {
        "buyer_code": buyer_code,
        "buyer_name": normalized_buyer_name,
        "province": normalized_province,
        "buyer_type": buyer_type,
        "portal_source": portal_source,
    }
