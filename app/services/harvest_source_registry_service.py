from __future__ import annotations

from typing import Any, Dict, List


def get_harvest_sources() -> List[Dict[str, Any]]:
    """
    Central registry for harvest sources.
    Keep this lightweight and expandable.
    """
    return [
        {
            "name": "eTenders OCDS",
            "type": "ocds",
            "enabled": True,
            "priority": 1,
        },
        {
            "name": "eTenders Web",
            "type": "web",
            "enabled": True,
            "priority": 2,
            "url": "https://www.etenders.gov.za/Home/opportunities",
        },
        {
            "name": "National Treasury eTenders",
            "type": "generic_portal",
            "enabled": True,
            "priority": 3,
            "url": "https://www.etenders.gov.za",
        },
        {
            "name": "Eskom Tender Bulletins",
            "type": "generic_portal",
            "enabled": False,
            "priority": 10,
            "url": "https://www.eskom.co.za/tenderbulletin/",
        },
        {
            "name": "Transnet Tenders",
            "type": "generic_portal",
            "enabled": False,
            "priority": 11,
            "url": "https://transnetetenders.azurewebsites.net/",
        },
        {
            "name": "SANRAL Tenders",
            "type": "generic_portal",
            "enabled": False,
            "priority": 12,
            "url": "https://www.nra.co.za/service-provider-zone/tenders/",
        },
    ]


def get_enabled_harvest_sources() -> List[Dict[str, Any]]:
    sources = [s for s in get_harvest_sources() if bool(s.get("enabled", False))]
    return sorted(sources, key=lambda s: int(s.get("priority", 999)))
