from __future__ import annotations

from typing import Dict, List


def get_procurement_portals() -> List[Dict[str, str]]:
    """
    Central registry of procurement portals for LMCP AutoQuote.

    Structure:
    [
        {
            "name": "...",
            "url": "...",
            "category": "national_department|soe|municipality|provincial|public_entity|aggregator",
            "scope": "supply_delivery",
            "province": "National|Free State|Gauteng|...",
            "active": "true",
        }
    ]
    """
    return [
        # -----------------------------
        # National Aggregators / Core
        # -----------------------------
        {
            "name": "National Treasury eTenders",
            "url": "https://www.etenders.gov.za/",
            "category": "aggregator",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "National Treasury",
            "url": "https://www.treasury.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "CSD",
            "url": "https://secure.csd.gov.za/",
            "category": "aggregator",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },

        # -----------------------------
        # SOEs / Public Entities
        # -----------------------------
        {
            "name": "Eskom",
            "url": "https://www.eskom.co.za/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Transnet",
            "url": "https://www.transnet.net/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "SANRAL",
            "url": "https://www.nra.co.za/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "DBSA",
            "url": "https://www.dbsa.org/",
            "category": "public_entity",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "PRASA",
            "url": "https://www.prasa.com/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Denel",
            "url": "https://www.denel.co.za/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "NECSA",
            "url": "https://www.necsa.co.za/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "SAA",
            "url": "https://www.flysaa.com/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "SA Express",
            "url": "https://www.saexpress.co.za/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "false",
        },
        {
            "name": "Airports Company South Africa",
            "url": "https://www.airports.co.za/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Passenger Rail Agency of South Africa",
            "url": "https://www.prasa.com/",
            "category": "soe",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Rand Water",
            "url": "https://www.randwater.co.za/",
            "category": "public_entity",
            "scope": "supply_delivery",
            "province": "Gauteng",
            "active": "true",
        },
        {
            "name": "Lepelle Northern Water",
            "url": "https://www.lnw.co.za/",
            "category": "public_entity",
            "scope": "supply_delivery",
            "province": "Limpopo",
            "active": "true",
        },
        {
            "name": "Magalies Water",
            "url": "https://www.magalieswater.co.za/",
            "category": "public_entity",
            "scope": "supply_delivery",
            "province": "North West",
            "active": "true",
        },
        {
            "name": "Bloem Water",
            "url": "https://www.bloemwater.co.za/",
            "category": "public_entity",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Sedibeng Water",
            "url": "https://www.sedibengwater.co.za/",
            "category": "public_entity",
            "scope": "supply_delivery",
            "province": "North West",
            "active": "true",
        },
        {
            "name": "Umgeni Water",
            "url": "https://www.umgeni.co.za/",
            "category": "public_entity",
            "scope": "supply_delivery",
            "province": "KwaZulu-Natal",
            "active": "true",
        },

        # -----------------------------
        # National Departments
        # -----------------------------
        {
            "name": "Department of Public Works and Infrastructure",
            "url": "https://www.publicworks.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Health",
            "url": "https://www.health.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Basic Education",
            "url": "https://www.education.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Higher Education and Training",
            "url": "https://www.dhet.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Human Settlements",
            "url": "https://www.dhs.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Water and Sanitation",
            "url": "https://www.dws.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Transport",
            "url": "https://www.transport.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Agriculture",
            "url": "https://www.nda.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Forestry Fisheries and the Environment",
            "url": "https://www.dffe.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Mineral Resources and Energy",
            "url": "https://www.dmr.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Employment and Labour",
            "url": "https://www.labour.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Home Affairs",
            "url": "https://www.dha.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Correctional Services",
            "url": "https://www.dcs.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Defence",
            "url": "https://www.dod.mil.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Justice and Constitutional Development",
            "url": "https://www.justice.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Cooperative Governance",
            "url": "https://www.cogta.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "National Department of Tourism",
            "url": "https://www.tourism.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Small Business Development",
            "url": "https://www.dsbd.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },
        {
            "name": "Department of Communications and Digital Technologies",
            "url": "https://www.dcdt.gov.za/",
            "category": "national_department",
            "scope": "supply_delivery",
            "province": "National",
            "active": "true",
        },

        # -----------------------------
        # Provincial examples
        # -----------------------------
        {
            "name": "Free State Provincial Treasury",
            "url": "https://www.treasury.fs.gov.za/",
            "category": "provincial",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Gauteng Provincial Treasury",
            "url": "https://www.gauteng.gov.za/",
            "category": "provincial",
            "scope": "supply_delivery",
            "province": "Gauteng",
            "active": "true",
        },
        {
            "name": "KwaZulu-Natal Treasury",
            "url": "https://www.kzntreasury.gov.za/",
            "category": "provincial",
            "scope": "supply_delivery",
            "province": "KwaZulu-Natal",
            "active": "true",
        },
        {
            "name": "Western Cape Provincial Treasury",
            "url": "https://www.westerncape.gov.za/provincial-treasury",
            "category": "provincial",
            "scope": "supply_delivery",
            "province": "Western Cape",
            "active": "true",
        },
        {
            "name": "Eastern Cape Provincial Treasury",
            "url": "https://www.ectreasury.gov.za/",
            "category": "provincial",
            "scope": "supply_delivery",
            "province": "Eastern Cape",
            "active": "true",
        },

        # -----------------------------
        # Free State municipalities
        # -----------------------------
        {
            "name": "Mangaung Metropolitan Municipality",
            "url": "https://www.mangaung.co.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Kopanong Local Municipality",
            "url": "https://www.kopanong.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Setsoto Local Municipality",
            "url": "https://www.setsoto.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Dihlabeng Local Municipality",
            "url": "https://www.dihlabeng.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Mafube Local Municipality",
            "url": "https://www.mafube.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Matjhabeng Local Municipality",
            "url": "https://www.matjhabeng.co.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Mantsopa Local Municipality",
            "url": "https://www.mantsopa.fs.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Mohokare Local Municipality",
            "url": "https://www.mohokare.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Masilonyana Local Municipality",
            "url": "https://www.masilonyana.fs.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Ngwathe Local Municipality",
            "url": "https://www.ngwathe.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Nketoana Local Municipality",
            "url": "https://www.nketoana.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },
        {
            "name": "Phumelela Local Municipality",
            "url": "https://www.phumelela.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Free State",
            "active": "true",
        },

        # -----------------------------
        # Gauteng municipalities
        # -----------------------------
        {
            "name": "City of Johannesburg",
            "url": "https://www.joburg.org.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Gauteng",
            "active": "true",
        },
        {
            "name": "City of Tshwane",
            "url": "https://www.tshwane.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Gauteng",
            "active": "true",
        },
        {
            "name": "City of Ekurhuleni",
            "url": "https://www.ekurhuleni.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Gauteng",
            "active": "true",
        },

        # -----------------------------
        # Western Cape municipalities
        # -----------------------------
        {
            "name": "City of Cape Town",
            "url": "https://www.capetown.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Western Cape",
            "active": "true",
        },

        # -----------------------------
        # KwaZulu-Natal municipalities
        # -----------------------------
        {
            "name": "eThekwini Municipality",
            "url": "https://www.durban.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "KwaZulu-Natal",
            "active": "true",
        },

        # -----------------------------
        # Eastern Cape municipalities
        # -----------------------------
        {
            "name": "Buffalo City Metropolitan Municipality",
            "url": "https://www.buffalocity.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Eastern Cape",
            "active": "true",
        },
        {
            "name": "Nelson Mandela Bay Municipality",
            "url": "https://www.nelsonmandelabay.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Eastern Cape",
            "active": "true",
        },

        # -----------------------------
        # Limpopo / Mpumalanga / NW / NC
        # -----------------------------
        {
            "name": "Polokwane Local Municipality",
            "url": "https://www.polokwane.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Limpopo",
            "active": "true",
        },
        {
            "name": "Mbombela Local Municipality",
            "url": "https://www.mbombela.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Mpumalanga",
            "active": "true",
        },
        {
            "name": "Rustenburg Local Municipality",
            "url": "https://www.rustenburg.gov.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "North West",
            "active": "true",
        },
        {
            "name": "Sol Plaatje Local Municipality",
            "url": "https://www.solplaatje.org.za/",
            "category": "municipality",
            "scope": "supply_delivery",
            "province": "Northern Cape",
            "active": "true",
        },
    ]


def get_active_procurement_portals() -> List[Dict[str, str]]:
    return [portal for portal in get_procurement_portals() if portal.get("active") == "true"]


def get_active_supply_delivery_portals() -> List[Dict[str, str]]:
    return [
        portal
        for portal in get_active_procurement_portals()
        if portal.get("scope") == "supply_delivery"
    ]


def get_portals_by_category(category: str) -> List[Dict[str, str]]:
    wanted = (category or "").strip().lower()
    return [
        portal
        for portal in get_active_procurement_portals()
        if portal.get("category", "").strip().lower() == wanted
    ]


def get_portals_by_province(province: str) -> List[Dict[str, str]]:
    wanted = (province or "").strip().lower()
    return [
        portal
        for portal in get_active_procurement_portals()
        if portal.get("province", "").strip().lower() == wanted
    ]


def get_registry_summary() -> Dict[str, int]:
    portals = get_active_procurement_portals()

    summary: Dict[str, int] = {
        "total_active": len(portals),
        "aggregator": 0,
        "soe": 0,
        "public_entity": 0,
        "national_department": 0,
        "provincial": 0,
        "municipality": 0,
    }

    for portal in portals:
        category = portal.get("category", "").strip().lower()
        if category in summary:
            summary[category] += 1

    return summary

from typing import Any, Dict, List, Optional


def get_active_portals() -> List[Dict[str, Any]]:
    """
    Returns only portals that should be crawled now.
    Safe adapter for the national portal radar.
    Works with the existing richer registry in this file.
    """
    registry: List[Dict[str, Any]] = []

    if "get_default_portal_registry" in globals():
        try:
            registry = get_default_portal_registry()
        except Exception:
            registry = []

    elif "PORTAL_REGISTRY" in globals():
        try:
            registry = PORTAL_REGISTRY
        except Exception:
            registry = []

    elif "get_portal_registry" in globals():
        try:
            registry = get_portal_registry()
        except Exception:
            registry = []

    if not isinstance(registry, list):
        return []

    active_statuses = {"active", "planned", "enabled", "ready"}

    active_portals: List[Dict[str, Any]] = []
    for portal in registry:
        if not isinstance(portal, dict):
            continue

        status = str(portal.get("status", "")).strip().lower()

        if not status:
            active_portals.append(portal)
            continue

        if status in active_statuses:
            active_portals.append(portal)

    return active_portals


def get_portal_by_code(portal_code: str) -> Optional[Dict[str, Any]]:
    """
    Safe lookup helper for the existing registry.
    """
    if not portal_code:
        return None

    for portal in get_active_portals():
        code = str(portal.get("portal_code", "")).strip().lower()
        if code == str(portal_code).strip().lower():
            return portal

    registry: List[Dict[str, Any]] = []

    if "get_default_portal_registry" in globals():
        try:
            registry = get_default_portal_registry()
        except Exception:
            registry = []
    elif "PORTAL_REGISTRY" in globals():
        try:
            registry = PORTAL_REGISTRY
        except Exception:
            registry = []
    elif "get_portal_registry" in globals():
        try:
            registry = get_portal_registry()
        except Exception:
            registry = []

    for portal in registry:
        if not isinstance(portal, dict):
            continue

        code = str(portal.get("portal_code", "")).strip().lower()
        if code == str(portal_code).strip().lower():
            return portal

    return None

def get_portal_registry():
    """
    Returns the list of portals registered in the system.
    This function is used by the harvester and other services.
    """

    # If the registry is defined as a variable above
    try:
        return PORTAL_REGISTRY
    except NameError:
        return []

def get_portal_registry():
    """
    Returns the portal registry list for the harvester and related services.
    Tries common registry variable names safely.
    """

    if "PORTAL_REGISTRY" in globals() and isinstance(PORTAL_REGISTRY, list):
        return PORTAL_REGISTRY

    if "portal_registry" in globals() and isinstance(portal_registry, list):
        return portal_registry

    if "PORTALS" in globals() and isinstance(PORTALS, list):
        return PORTALS

    return []
