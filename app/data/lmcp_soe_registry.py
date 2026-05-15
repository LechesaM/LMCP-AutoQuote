from __future__ import annotations

from typing import Any, Dict, List


def _slugify(value: str) -> str:
    text = (value or "").strip().lower()
    out = []
    for ch in text:
        if ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    slug = "".join(out)
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug.strip("_")


def _build_entry(
    *,
    entity_name: str,
    entity_group: str,
    source_url: str,
    source_type: str = "portal",
    source_key: str | None = None,
    priority_tier: int = 3,
    crawl_zone: str = "warm",
    crawl_interval_minutes: int = 60,
    expected_submission_method: str = "mixed",
    fit_supply_delivery: str = "medium",
    province: str = "National",
    notes: str = "",
    is_direct_priority: bool = False,
) -> Dict[str, Any]:
    return {
        "entity_name": entity_name,
        "sphere": "national_public_entity",
        "entity_type": "SOE_or_public_entity",
        "entity_group": entity_group,
        "province": province,
        "source_type": source_type,
        "source_url": source_url,
        "source_key": source_key or f"soe_{_slugify(entity_name)}",
        "priority_tier": priority_tier,
        "crawl_zone": crawl_zone,
        "crawl_interval_minutes": crawl_interval_minutes,
        "confidence_score": 0.90 if not is_direct_priority else 0.96,
        "expected_submission_method": expected_submission_method,
        "typical_document_type": "tender_notice",
        "fit_supply_delivery": fit_supply_delivery,
        "exclude_if_compulsory_briefing": True,
        "portal_health_status": "unknown",
        "is_active": True,
        "is_direct_priority": is_direct_priority,
        "notes": notes,
    }


DIRECT_PRIORITY_ISSUERS: List[Dict[str, Any]] = [
    _build_entry(
        entity_name="Eskom Holdings SOC Ltd",
        entity_group="Energy",
        source_url="https://tenderbulletin.eskom.co.za/",
        source_key="eskom_tenders",
        priority_tier=1,
        crawl_zone="hot",
        crawl_interval_minutes=15,
        expected_submission_method="portal",
        fit_supply_delivery="high",
        notes="Direct tender bulletin; top-priority national issuer.",
        is_direct_priority=True,
    ),
    _build_entry(
        entity_name="Transnet SOC Ltd",
        entity_group="Transport and Logistics",
        source_url="https://esupplierportal.transnet.net/portal/advertisedTenders",
        source_key="transnet_tenders",
        priority_tier=1,
        crawl_zone="hot",
        crawl_interval_minutes=15,
        expected_submission_method="portal",
        fit_supply_delivery="high",
        notes="Direct supplier portal; top-priority national issuer.",
        is_direct_priority=True,
    ),
    _build_entry(
        entity_name="Airports Company South Africa SOC Ltd",
        entity_group="Aviation",
        source_url="https://www.airports.co.za/Pages/Tender-Bulletin.aspx",
        source_key="acsa_tenders",
        priority_tier=1,
        crawl_zone="hot",
        crawl_interval_minutes=20,
        expected_submission_method="portal",
        fit_supply_delivery="high",
        notes="Direct tender bulletin; top-priority national issuer.",
        is_direct_priority=True,
    ),
    _build_entry(
        entity_name="Development Bank of Southern Africa",
        entity_group="Development Finance",
        source_url="https://www.dbsa.org/procurement",
        source_key="dbsa_procurement",
        priority_tier=1,
        crawl_zone="warm",
        crawl_interval_minutes=30,
        expected_submission_method="mixed",
        fit_supply_delivery="medium",
        notes="Direct procurement page; important national issuer.",
        is_direct_priority=True,
    ),
    _build_entry(
        entity_name="Rand Water",
        entity_group="Water Board",
        source_url="https://www.randwater.co.za/availabletenders.php",
        source_key="randwater_bids",
        priority_tier=1,
        crawl_zone="warm",
        crawl_interval_minutes=30,
        expected_submission_method="portal",
        fit_supply_delivery="high",
        province="Gauteng",
        notes="Direct tenders page; important water-sector issuer.",
        is_direct_priority=True,
    ),
]

SOE_AND_PUBLIC_ENTITY_REGISTRY: List[Dict[str, Any]] = [
    _build_entry(
        entity_name="Alexkor SOC Ltd",
        entity_group="Mining / State-Owned Company",
        source_url="https://www.gov.za/about-government/contact-directory/soe-s",
        notes="Use eTender first, then direct site if active.",
    ),
    _build_entry(
        entity_name="Broadband Infraco SOC Ltd",
        entity_group="ICT Infrastructure",
        source_url="https://www.infraco.co.za/",
        notes="Public broadband infrastructure entity.",
    ),
    _build_entry(
        entity_name="Central Energy Fund SOC Ltd",
        entity_group="Energy",
        source_url="https://www.cefgroup.co.za/",
        notes="Energy-sector public entity.",
    ),
    _build_entry(
        entity_name="PetroSA",
        entity_group="Energy",
        source_url="https://www.petrosa.co.za/",
        notes="Energy-sector public entity.",
    ),
    _build_entry(
        entity_name="South African Nuclear Energy Corporation SOC Ltd",
        entity_group="Energy / Nuclear",
        source_url="https://www.nnec.co.za/",
        notes="Nuclear energy public entity.",
    ),
    _build_entry(
        entity_name="South African National Energy Development Institute",
        entity_group="Energy",
        source_url="https://sanedi.org.za/",
        notes="Energy development public entity.",
    ),
    _build_entry(
        entity_name="Air Traffic and Navigation Services SOC Ltd",
        entity_group="Aviation",
        source_url="https://www.atns.co.za/",
        notes="Aviation public entity; monitor procurement notices.",
    ),
    _build_entry(
        entity_name="Passenger Rail Agency of South Africa",
        entity_group="Rail Transport",
        source_url="https://www.prasa.com/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=45,
        fit_supply_delivery="high",
        notes="Major transport issuer; add direct procurement parser when stable.",
    ),
    _build_entry(
        entity_name="South African National Roads Agency SOC Ltd",
        entity_group="Roads",
        source_url="https://www.nra.co.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=45,
        fit_supply_delivery="high",
        notes="Major national roads issuer.",
    ),
    _build_entry(
        entity_name="South African Airways SOC Ltd",
        entity_group="Aviation",
        source_url="https://www.flysaa.com/",
        notes="National airline entity.",
    ),
    _build_entry(
        entity_name="Road Traffic Management Corporation",
        entity_group="Transport Regulation",
        source_url="https://www.rtmc.co.za/",
        notes="Transport-sector public entity.",
    ),
    _build_entry(
        entity_name="Railway Safety Regulator",
        entity_group="Transport Regulation",
        source_url="https://www.rsr.org.za/",
        notes="Transport-sector public entity.",
    ),
    _build_entry(
        entity_name="Cross-Border Road Transport Agency",
        entity_group="Transport",
        source_url="https://www.cbrta.co.za/",
        notes="Transport-sector public entity.",
    ),
    _build_entry(
        entity_name="Ports Regulator of South Africa",
        entity_group="Transport Regulation",
        source_url="https://portsregulator.org/",
        notes="Ports regulator.",
    ),
    _build_entry(
        entity_name="Trans-Caledon Tunnel Authority",
        entity_group="Water Infrastructure",
        source_url="https://www.tcta.co.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=45,
        fit_supply_delivery="high",
        notes="Important infrastructure issuer.",
    ),
    _build_entry(
        entity_name="Denel SOC Ltd",
        entity_group="Defence",
        source_url="https://www.denel.co.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=60,
        fit_supply_delivery="medium",
        notes="Defence-related public issuer.",
    ),
    _build_entry(
        entity_name="Armaments Corporation of South Africa",
        entity_group="Defence",
        source_url="https://www.armscor.co.za/",
        notes="State defence procurement entity.",
    ),
    _build_entry(
        entity_name="SENTECH SOC Ltd",
        entity_group="Broadcast / ICT Infrastructure",
        source_url="https://www.sentech.co.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=60,
        fit_supply_delivery="medium",
        notes="National signal distribution / ICT infrastructure entity.",
    ),
    _build_entry(
        entity_name="South African Post Office SOC Ltd",
        entity_group="Postal / Logistics",
        source_url="https://www.postoffice.co.za/",
        notes="Postal public entity.",
    ),
    _build_entry(
        entity_name="Independent Communications Authority of South Africa",
        entity_group="ICT Regulation",
        source_url="https://www.icasa.org.za/",
        notes="ICT regulator.",
    ),
    _build_entry(
        entity_name="Land Bank",
        entity_group="Development Finance",
        source_url="https://www.landbank.co.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=60,
        fit_supply_delivery="medium",
        notes="Agricultural development finance institution.",
    ),
    _build_entry(
        entity_name="Industrial Development Corporation",
        entity_group="Development Finance",
        source_url="https://www.idc.co.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=60,
        fit_supply_delivery="medium",
        notes="Large development finance institution.",
    ),
    _build_entry(
        entity_name="Public Investment Corporation",
        entity_group="Finance",
        source_url="https://www.pic.gov.za/",
        notes="State asset manager.",
    ),
    _build_entry(
        entity_name="Export Credit Insurance Corporation of South Africa",
        entity_group="Insurance / Trade Finance",
        source_url="https://www.ecic.co.za/",
        notes="Trade-related public entity.",
    ),
    _build_entry(
        entity_name="Amatola Water",
        entity_group="Water Board",
        source_url="https://www.amatolawater.co.za/",
        province="Eastern Cape",
        notes="Water board / utility.",
    ),
    _build_entry(
        entity_name="Bloem Water",
        entity_group="Water Board",
        source_url="https://www.bloemwater.co.za/",
        province="Free State",
        notes="Water board / utility.",
    ),
    _build_entry(
        entity_name="Lepelle Northern Water",
        entity_group="Water Board",
        source_url="https://www.lepelle.co.za/",
        province="Limpopo",
        notes="Water board / utility.",
    ),
    _build_entry(
        entity_name="Magalies Water",
        entity_group="Water Board",
        source_url="https://www.magalieswater.co.za/",
        province="North West",
        notes="Water board / utility.",
    ),
    _build_entry(
        entity_name="Mhlathuze Water",
        entity_group="Water Board",
        source_url="https://www.mhlathuzewater.co.za/",
        province="KwaZulu-Natal",
        notes="Water board / utility.",
    ),
    _build_entry(
        entity_name="Overberg Water",
        entity_group="Water Board",
        source_url="https://www.overbergwater.co.za/",
        province="Western Cape",
        notes="Water board / utility.",
    ),
    _build_entry(
        entity_name="Sedibeng Water",
        entity_group="Water Board",
        source_url="https://www.sedibengwater.co.za/",
        notes="Water board / utility.",
    ),
    _build_entry(
        entity_name="Umgeni Water",
        entity_group="Water Board",
        source_url="https://www.umgeni.co.za/",
        province="KwaZulu-Natal",
        notes="Water board / utility.",
    ),
    _build_entry(
        entity_name="Agricultural Research Council",
        entity_group="Research Council",
        source_url="https://www.arc.agric.za/",
        notes="Research council.",
    ),
    _build_entry(
        entity_name="Council for Scientific and Industrial Research",
        entity_group="Research Council",
        source_url="https://www.csir.co.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=60,
        fit_supply_delivery="medium",
        notes="Large research council with procurement activity.",
    ),
    _build_entry(
        entity_name="Council for Geoscience",
        entity_group="Research Council",
        source_url="https://www.geoscience.org.za/",
        notes="Research council.",
    ),
    _build_entry(
        entity_name="Human Sciences Research Council",
        entity_group="Research Council",
        source_url="https://www.hsrc.ac.za/",
        notes="Research council.",
    ),
    _build_entry(
        entity_name="Medical Research Council",
        entity_group="Research Council",
        source_url="https://www.samrc.ac.za/",
        fit_supply_delivery="low",
        notes="Research council; lower fit for LMCP due to medical scope.",
    ),
    _build_entry(
        entity_name="National Research Foundation",
        entity_group="Research / Science",
        source_url="https://www.nrf.ac.za/",
        notes="Research funding public entity.",
    ),
    _build_entry(
        entity_name="South African Bureau of Standards",
        entity_group="Standards / Testing",
        source_url="https://www.sabs.co.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=60,
        fit_supply_delivery="medium",
        notes="Standards body with procurement relevance.",
    ),
    _build_entry(
        entity_name="Housing Development Agency",
        entity_group="Human Settlements",
        source_url="https://thehda.co.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=60,
        fit_supply_delivery="high",
        notes="Human settlements public entity.",
    ),
    _build_entry(
        entity_name="National Home Builders Registration Council",
        entity_group="Human Settlements / Built Environment",
        source_url="https://www.nhbrc.org.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=60,
        fit_supply_delivery="medium",
        notes="Built-environment public entity.",
    ),
    _build_entry(
        entity_name="National Development Agency",
        entity_group="Social Development",
        source_url="https://www.nda.org.za/",
        notes="Social development public entity.",
    ),
    _build_entry(
        entity_name="National Empowerment Fund",
        entity_group="Finance / Development",
        source_url="https://www.nefcorp.co.za/",
        notes="Development finance public entity.",
    ),
    _build_entry(
        entity_name="South African Tourism",
        entity_group="Tourism",
        source_url="https://www.southafrica.net/",
        notes="Tourism public entity.",
    ),
    _build_entry(
        entity_name="Brand South Africa",
        entity_group="National Branding",
        source_url="https://brandsouthafrica.com/",
        notes="National brand entity.",
    ),
    _build_entry(
        entity_name="Border Management Authority",
        entity_group="Security / Border Management",
        source_url="https://www.bma.gov.za/",
        priority_tier=2,
        crawl_zone="warm",
        crawl_interval_minutes=60,
        fit_supply_delivery="high",
        notes="Important national issuer for goods, systems and services.",
    ),
]


def build_full_soe_registry() -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    seen = set()

    for row in DIRECT_PRIORITY_ISSUERS + SOE_AND_PUBLIC_ENTITY_REGISTRY:
        key = row["source_key"]
        if key in seen:
            continue
        seen.add(key)
        rows.append(row)

    rows = sorted(
        rows,
        key=lambda r: (
            int(r.get("priority_tier", 999)),
            int(r.get("crawl_interval_minutes", 9999)),
            str(r.get("entity_name", "")),
        ),
    )

    return {
        "version": "2026-03-30",
        "registry_name": "LMCP SOE and Public Entity Registry",
        "notes": [
            "This registry is procurement-oriented.",
            "It includes core SOEs plus broader national public entities relevant to tender harvesting.",
            "Use direct issuer portals where known; otherwise use eTender first and attach direct parsers later.",
        ],
        "entities": rows,
        "summary": {
            "total_entities": len(rows),
            "direct_priority_issuers": len([r for r in rows if r.get("is_direct_priority") is True]),
            "hot": len([r for r in rows if r.get("crawl_zone") == "hot"]),
            "warm": len([r for r in rows if r.get("crawl_zone") == "warm"]),
            "cold": len([r for r in rows if r.get("crawl_zone") == "cold"]),
            "high_fit_supply_delivery": len([r for r in rows if r.get("fit_supply_delivery") == "high"]),
        },
    }


LMCP_SOE_REGISTRY: Dict[str, Any] = build_full_soe_registry()


if __name__ == "__main__":
    import json
    print(json.dumps(LMCP_SOE_REGISTRY, indent=2))
