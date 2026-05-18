from __future__ import annotations

from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

from app.department_registry import DEPARTMENT_SOURCES as DEPARTMENT_REGISTRY


COMMON_PROCUREMENT_PATHS = [
    "/tenders",
    "/tender",
    "/procurement",
    "/procurement/",
    "/procurement/tenders",
    "/procurement/tender",
    "/procurement-opportunities",
    "/supply-chain-management",
    "/supply-chain-management/",
    "/supply-chain-management/tenders",
    "/supply-chain-management/bids",
    "/bids",
    "/bid",
    "/rfq",
    "/quotations",
    "/open-tenders",
    "/tenders-and-rfqs",
    "/available-tenders",
]


DEPARTMENT_DIRECT_OVERRIDES: Dict[str, List[str]] = {
    "National Treasury": [
        "https://www.treasury.gov.za/tenders/default.aspx",
        "https://www.etenders.gov.za/Home/opportunities",
    ],
    "Public Works and Infrastructure": [
        "https://www.publicworks.gov.za/tenders.html",
    ],
    "Health": [
        "https://www.health.gov.za/tenders/",
    ],
    "Transport": [
        "https://www.transport.gov.za/tenders",
    ],
    "Human Settlements": [
        "https://www.dhs.gov.za/content/tenders",
    ],
    "Correctional Services": [
        "https://www.dcs.gov.za/?page_id=512",
    ],
}


SOE_AND_PUBLIC_ENTITY_REGISTRY: List[Dict[str, Optional[str]]] = [
    {
        "name": "Eskom Holdings SOC Ltd",
        "homepage_url": "https://www.eskom.co.za/",
        "procurement_url": "https://www.eskom.co.za/procurement/",
        "entity_type": "soe",
    },
    {
        "name": "Transnet SOC Ltd",
        "homepage_url": "https://www.transnet.net/",
        "procurement_url": "https://www.transnet.net/TransnetTenders",
        "entity_type": "soe",
    },
    {
        "name": "South African National Roads Agency SOC Ltd (SANRAL)",
        "homepage_url": "https://www.sanral.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Passenger Rail Agency of South Africa (PRASA)",
        "homepage_url": "https://www.prasa.com/",
        "procurement_url": "https://www.prasa.com/Tenders/",
        "entity_type": "soe",
    },
    {
        "name": "South African National Parks (SANParks)",
        "homepage_url": "https://www.sanparks.org/",
        "procurement_url": "https://www.sanparks.org/corporate/tenders",
        "entity_type": "soe",
    },
    {
        "name": "Airports Company South Africa (ACSA)",
        "homepage_url": "https://www.acsa.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Rand Water",
        "homepage_url": "https://www.randwater.co.za/",
        "procurement_url": "https://www.randwater.co.za/",
        "entity_type": "soe",
    },
    {
        "name": "State Information Technology Agency (SITA)",
        "homepage_url": "https://www.sita.co.za/",
        "procurement_url": "https://www.sita.co.za/",
        "entity_type": "soe",
    },
    {
        "name": "Development Bank of Southern Africa (DBSA)",
        "homepage_url": "https://www.dbsa.org/",
        "procurement_url": "https://www.dbsa.org/procurement",
        "entity_type": "soe",
    },
    {
        "name": "Council for Scientific and Industrial Research (CSIR)",
        "homepage_url": "https://www.csir.co.za/",
        "procurement_url": "https://www.csir.co.za/work-with-us/tenders",
        "entity_type": "public_entity",
    },
    {
        "name": "South African Forestry Company SOC Ltd (SAFCOL)",
        "homepage_url": "https://www.safcol.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Denel SOC Ltd",
        "homepage_url": "https://www.denel.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "NECSA Group",
        "homepage_url": "https://www.necsa.co.za/",
        "procurement_url": "https://www.necsa.co.za/tenders/",
        "entity_type": "public_entity",
    },
    {
        "name": "Land and Agricultural Development Bank of South Africa (Land Bank)",
        "homepage_url": "https://landbank.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Broadband Infraco SOC Ltd",
        "homepage_url": "https://www.infraco.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "South African Broadcasting Corporation (SABC)",
        "homepage_url": "https://www.sabc.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Central Energy Fund (CEF) SOC Ltd",
        "homepage_url": "https://www.cefgroup.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "PetroSA",
        "homepage_url": "https://www.petrosa.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "SENTECH SOC Ltd",
        "homepage_url": "https://www.sentech.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Armaments Corporation of South Africa (ARMSCOR)",
        "homepage_url": "https://www.armscor.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Air Traffic and Navigation Services (ATNS)",
        "homepage_url": "https://www.atns.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Trans-Caledon Tunnel Authority (TCTA)",
        "homepage_url": "https://www.tcta.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Industrial Development Corporation (IDC)",
        "homepage_url": "https://www.idc.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
    {
        "name": "Alexkor SOC Ltd",
        "homepage_url": "https://alexkor.co.za/",
        "procurement_url": None,
        "entity_type": "soe",
    },
]


def _normalize_name(raw_name: str) -> str:
    return " ".join((raw_name or "").replace("[ Department of ]", "").split()).strip()


def _dedupe_keep_order(urls: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for url in urls:
        clean = (url or "").strip()
        if not clean:
            continue
        key = clean.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def _expand_entity_sources(
    name: str,
    homepage_url: str,
    entity_type: str,
    procurement_url: Optional[str] = None,
    direct_overrides: Optional[List[str]] = None,
) -> List[Dict[str, str]]:
    candidates: List[str] = []

    if direct_overrides:
        candidates.extend(direct_overrides)

    if procurement_url:
        candidates.append(procurement_url)

    if homepage_url:
        candidates.append(homepage_url)
        for path in COMMON_PROCUREMENT_PATHS:
            candidates.append(urljoin(homepage_url.rstrip("/") + "/", path.lstrip("/")))

    expanded = []
    for url in _dedupe_keep_order(candidates):
        expanded.append(
            {
                "name": name,
                "url": url,
                "entity_type": entity_type,
                "base_url": homepage_url,
            }
        )
    return expanded


def _build_department_sources() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []

    for record in DEPARTMENT_REGISTRY:
        name = _normalize_name(record.get("name", ""))
        homepage_url = (record.get("homepage_url") or "").strip()
        direct_overrides = DEPARTMENT_DIRECT_OVERRIDES.get(name, [])

        if not name or not homepage_url:
            continue

        items.extend(
            _expand_entity_sources(
                name=name,
                homepage_url=homepage_url,
                entity_type="department",
                procurement_url=record.get("rfq_url"),
                direct_overrides=direct_overrides,
            )
        )

    return items


def _build_soe_sources() -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []

    for record in SOE_AND_PUBLIC_ENTITY_REGISTRY:
        name = (record.get("name") or "").strip()
        homepage_url = (record.get("homepage_url") or "").strip()

        if not name or not homepage_url:
            continue

        items.extend(
            _expand_entity_sources(
                name=name,
                homepage_url=homepage_url,
                entity_type=(record.get("entity_type") or "soe").strip(),
                procurement_url=record.get("procurement_url"),
                direct_overrides=None,
            )
        )

    return items


def _dedupe_sources(items: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen: set[Tuple[str, str]] = set()
    result: List[Dict[str, str]] = []

    for item in items:
        key = (
            item["name"].strip().lower(),
            item["url"].strip().rstrip("/").lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)

    return result


DEPARTMENT_SOURCES = _dedupe_sources(
    _build_department_sources() + _build_soe_sources()
)
