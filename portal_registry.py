from __future__ import annotations


PORTAL_REGISTRY = [
    {
        "portal_slug": "etenders",
        "portal_name": "South African eTenders",
        "base_url": "https://www.etenders.gov.za/",
        "category": "government",
        "region": "national",
    },
    {
        "portal_slug": "sanral",
        "portal_name": "SANRAL",
        "base_url": "https://www.nra.co.za/",
        "category": "soe",
        "region": "national",
    },
]


def get_portal_registry():
    """
    Returns the portal registry list for the harvester and related services.
    """
    return PORTAL_REGISTRY
