from __future__ import annotations

from typing import Any, Dict, List

from app.data.lmcp_municipal_registry import get_municipal_registry
from app.data.lmcp_soe_registry import get_soe_registry


COMMON_PROVINCIAL_DEPARTMENTS = [
    "Office of the Premier",
    "Provincial Treasury",
    "Department of Health",
    "Department of Education",
    "Department of Public Works",
    "Department of Human Settlements",
    "Department of Transport",
    "Department of Agriculture and Rural Development",
]

PROVINCES = [
    "Eastern Cape",
    "Free State",
    "Gauteng",
    "KwaZulu-Natal",
    "Limpopo",
    "Mpumalanga",
    "North West",
    "Northern Cape",
    "Western Cape",
]

NATIONAL_DEPARTMENTS = [
    "Department of Agriculture",
    "Department of Basic Education",
    "Department of Communications and Digital Technologies",
    "Department of Cooperative Governance",
    "Department of Correctional Services",
    "Department of Defence",
    "Department of Employment and Labour",
    "Department of Forestry, Fisheries and the Environment",
    "Department of Health",
    "Department of Higher Education and Training",
    "Department of Home Affairs",
    "Department of Human Settlements",
    "Department of International Relations and Cooperation",
    "Department of Justice and Constitutional Development",
    "Department of Mineral and Petroleum Resources",
    "Department of Planning, Monitoring and Evaluation",
    "Department of Police",
    "Department of Public Enterprises",
    "Department of Public Service and Administration",
    "Department of Public Works and Infrastructure",
    "Department of Science, Technology and Innovation",
    "Department of Small Business Development",
    "Department of Social Development",
    "Department of Sport, Arts and Culture",
    "Department of Tourism",
    "Department of Trade, Industry and Competition",
    "Department of Transport",
    "Department of Water and Sanitation",
    "Department of Women, Youth and Persons with Disabilities",
    "National Treasury",
    "South African Revenue Service",
]

PUBLIC_ENTITIES = [
    {
        "entity_code": "PUB-CSIR",
        "entity_name": "Council for Scientific and Industrial Research",
        "entity_type": "public_entity",
        "owner_type": "public_entity",
        "province": "National",
        "country": "South Africa",
        "website": "https://www.csir.co.za",
        "tender_page": "https://www.csir.co.za/tenders",
        "enabled": True,
        "source_type": "website",
        "priority_tier": 2,
        "crawl_frequency_minutes": 60,
    },
    {
        "entity_code": "PUB-NHLS",
        "entity_name": "National Health Laboratory Service",
        "entity_type": "public_entity",
        "owner_type": "public_entity",
        "province": "National",
        "country": "South Africa",
        "website": "https://www.nhls.ac.za",
        "tender_page": "https://www.nhls.ac.za/supply-chain-management/",
        "enabled": True,
        "source_type": "website",
        "priority_tier": 2,
        "crawl_frequency_minutes": 60,
    },
    {
        "entity_code": "PUB-SABS",
        "entity_name": "South African Bureau of Standards",
        "entity_type": "public_entity",
        "owner_type": "public_entity",
        "province": "National",
        "country": "South Africa",
        "website": "https://www.sabs.co.za",
        "tender_page": "https://www.sabs.co.za/tenders/",
        "enabled": True,
        "source_type": "website",
        "priority_tier": 2,
        "crawl_frequency_minutes": 60,
    },
]


def _slugify(text: str) -> str:
    value = (text or "").strip().lower()
    allowed = []
    for ch in value:
        if ch.isalnum():
            allowed.append(ch)
        elif ch in {" ", "-", "/", "&", ","}:
            allowed.append("-")
    slug = "".join(allowed)
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug.strip("-")


def _make_national_department(name: str) -> Dict[str, Any]:
    slug = _slugify(name)
    return {
        "entity_code": f"NAT-{slug[:18].upper()}",
        "entity_name": name,
        "entity_type": "national_department",
        "owner_type": "national",
        "province": "National",
        "country": "South Africa",
        "website": "",
        "tender_page": "",
        "enabled": True,
        "source_type": "aggregated_only",
        "priority_tier": 1,
        "crawl_frequency_minutes": 30,
    }


def _make_provincial_department(province: str, department_name: str) -> Dict[str, Any]:
    slug = _slugify(f"{province}-{department_name}")
    return {
        "entity_code": f"PROV-{slug[:18].upper()}",
        "entity_name": f"{province} {department_name}",
        "entity_type": "provincial_department",
        "owner_type": "provincial",
        "province": province,
        "country": "South Africa",
        "website": "",
        "tender_page": "",
        "enabled": True,
        "source_type": "aggregated_only",
        "priority_tier": 2,
        "crawl_frequency_minutes": 60,
    }


def _build_sources(entity: Dict[str, Any]) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []

    if entity.get("source_type") == "ocds_api" and entity.get("api_url"):
        sources.append(
            {
                "source_key": f"{entity['entity_code']}:ocds",
                "entity_code": entity["entity_code"],
                "entity_name": entity["entity_name"],
                "owner_type": entity["owner_type"],
                "entity_type": entity["entity_type"],
                "province": entity.get("province", "National"),
                "source_type": "ocds_api",
                "base_url": entity["api_url"],
                "enabled": bool(entity.get("enabled", True)),
                "priority_tier": int(entity.get("priority_tier", 2)),
                "crawl_frequency_minutes": int(entity.get("crawl_frequency_minutes", 60)),
            }
        )

    if entity.get("tender_page"):
        sources.append(
            {
                "source_key": f"{entity['entity_code']}:website",
                "entity_code": entity["entity_code"],
                "entity_name": entity["entity_name"],
                "owner_type": entity["owner_type"],
                "entity_type": entity["entity_type"],
                "province": entity.get("province", "National"),
                "source_type": "website",
                "base_url": entity["tender_page"],
                "enabled": bool(entity.get("enabled", True)),
                "priority_tier": int(entity.get("priority_tier", 2)),
                "crawl_frequency_minutes": int(entity.get("crawl_frequency_minutes", 60)),
            }
        )

    return sources


def _normalize_entity(entity: Dict[str, Any]) -> Dict[str, Any]:
    normalized = dict(entity)
    normalized.setdefault("country", "South Africa")
    normalized.setdefault("enabled", True)
    normalized.setdefault("priority_tier", 2)
    normalized.setdefault("crawl_frequency_minutes", 60)
    normalized["sources"] = _build_sources(normalized)
    return normalized


def build_master_entity_seed() -> List[Dict[str, Any]]:
    national_entities = [_make_national_department(name) for name in NATIONAL_DEPARTMENTS]

    provincial_entities = [
        _make_provincial_department(province, department_name)
        for province in PROVINCES
        for department_name in COMMON_PROVINCIAL_DEPARTMENTS
    ]

    municipal_entities = get_municipal_registry()
    soe_entities = get_soe_registry()
    public_entities = [dict(item) for item in PUBLIC_ENTITIES]

    combined = national_entities + provincial_entities + municipal_entities + soe_entities + public_entities
    return [_normalize_entity(item) for item in combined]


LMCP_ENTITY_MASTER_SEED: List[Dict[str, Any]] = build_master_entity_seed()


def get_all_entities() -> List[Dict[str, Any]]:
    return [dict(item) for item in LMCP_ENTITY_MASTER_SEED]


def get_harvestable_entities() -> List[Dict[str, Any]]:
    return [dict(item) for item in LMCP_ENTITY_MASTER_SEED if item.get("enabled", True)]


def get_all_sources() -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []
    for entity in LMCP_ENTITY_MASTER_SEED:
        sources.extend(entity.get("sources", []))
    return sources


def summarize_by_owner() -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for entity in LMCP_ENTITY_MASTER_SEED:
        key = str(entity.get("owner_type", "unknown"))
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def summarize_by_entity_type() -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for entity in LMCP_ENTITY_MASTER_SEED:
        key = str(entity.get("entity_type", "unknown"))
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))


def summarize_by_province() -> Dict[str, int]:
    summary: Dict[str, int] = {}
    for entity in LMCP_ENTITY_MASTER_SEED:
        key = str(entity.get("province", "unknown"))
        summary[key] = summary.get(key, 0) + 1
    return dict(sorted(summary.items()))
