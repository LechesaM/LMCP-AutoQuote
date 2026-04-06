from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.services.direct_portal_harvesters import harvest_etenders_web, harvest_generic_portal

logger = logging.getLogger(__name__)


def harvest_from_source(source: Dict[str, Any]) -> List[Dict[str, Any]]:
    source_type = str(source.get("type") or "").strip().lower()
    source_name = str(source.get("name") or "Unknown Source").strip()

    logger.info("Routing harvest for source=%s type=%s", source_name, source_type)

    try:
        if source_type == "web":
            return harvest_etenders_web()

        if source_type == "generic_portal":
            return harvest_generic_portal(source)

        logger.info("No direct parser route for source=%s type=%s", source_name, source_type)
        return []
    except Exception as exc:
        logger.warning("Harvest route failed for source=%s: %s", source_name, exc)
        return []
