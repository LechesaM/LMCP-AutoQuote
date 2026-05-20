from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List

from app.harvest.source_models import ProcurementSourceRecord
from app.harvest.source_registry import SourceRegistry
from app.harvest.startup_scope import should_activate_seed_source
from app.harvest.source_tiers import HarvestTier


def load_seed_sources() -> List[ProcurementSourceRecord]:
    seeds = [
        {"id": "national_treasury_etender", "name": "National Treasury eTender Portal", "entity_type": "National Treasury", "source_tier": HarvestTier.TIER_1, "base_url": "https://etenders.gov.za", "harvest_url": "https://etenders.gov.za/content/advertisement", "parser_type": "etenders", "is_active": should_activate_seed_source("National Treasury eTender Portal", HarvestTier.TIER_1), "requires_browser": False, "requires_login": False, "province": "", "metadata_json": {"seed": True, "startup_scope": "active"}},
        {"id": "gcommerce", "name": "gCommerce", "entity_type": "National procurement platform", "source_tier": HarvestTier.TIER_2, "base_url": "https://gcommerce.co.za", "harvest_url": "https://gcommerce.co.za/tenders", "parser_type": "html", "is_active": should_activate_seed_source("gCommerce", HarvestTier.TIER_2), "requires_browser": False, "requires_login": False, "metadata_json": {"seed": True, "startup_scope": "active"}},
        {"id": "eskom", "name": "Eskom", "entity_type": "PFMA Schedule 2", "source_tier": HarvestTier.TIER_2, "base_url": "https://www.eskom.co.za", "harvest_url": "https://www.eskom.co.za/tenders", "parser_type": "html", "is_active": should_activate_seed_source("Eskom", HarvestTier.TIER_2), "metadata_json": {"seed": True, "startup_scope": "active"}},
        {"id": "transnet", "name": "Transnet", "entity_type": "PFMA Schedule 2", "source_tier": HarvestTier.TIER_2, "base_url": "https://www.transnet.net", "harvest_url": "https://www.transnet.net/tenders", "parser_type": "html", "is_active": should_activate_seed_source("Transnet", HarvestTier.TIER_2), "metadata_json": {"seed": True, "startup_scope": "active"}},
        {"id": "sanral", "name": "SANRAL", "entity_type": "PFMA Schedule 3", "source_tier": HarvestTier.TIER_2, "base_url": "https://www.nra.co.za", "harvest_url": "https://www.nra.co.za/tenders", "parser_type": "html", "is_active": should_activate_seed_source("SANRAL", HarvestTier.TIER_2), "metadata_json": {"seed": True, "startup_scope": "active"}},
        {"id": "prasa", "name": "PRASA", "entity_type": "PFMA Schedule 3", "source_tier": HarvestTier.TIER_3, "base_url": "https://www.prasa.com", "harvest_url": "https://www.prasa.com/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "off_initially"}},
        {"id": "acsa", "name": "ACSA", "entity_type": "PFMA Schedule 2", "source_tier": HarvestTier.TIER_3, "base_url": "https://www.airports.co.za", "harvest_url": "https://www.airports.co.za/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "off_initially"}},
        {"id": "sita", "name": "SITA", "entity_type": "PFMA Schedule 2", "source_tier": HarvestTier.TIER_3, "base_url": "https://www.sita.co.za", "harvest_url": "https://www.sita.co.za/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "staged_for_later"}},
        {"id": "dbsa", "name": "DBSA", "entity_type": "PFMA Schedule 2", "source_tier": HarvestTier.TIER_3, "base_url": "https://www.dbsa.org", "harvest_url": "https://www.dbsa.org/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "off_initially"}},
        {"id": "idc", "name": "IDC", "entity_type": "PFMA Schedule 2", "source_tier": HarvestTier.TIER_3, "base_url": "https://www.idc.co.za", "harvest_url": "https://www.idc.co.za/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "off_initially"}},
        {"id": "rand_water", "name": "Rand Water", "entity_type": "Water Board", "source_tier": HarvestTier.TIER_3, "base_url": "https://www.randwater.co.za", "harvest_url": "https://www.randwater.co.za/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "off_initially"}},
        {"id": "water_board_1", "name": "Water Board 1", "entity_type": "Water Board", "source_tier": HarvestTier.TIER_4, "base_url": "https://waterboard.example", "harvest_url": "https://waterboard.example/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "passive_only"}},
        {"id": "municipality_1", "name": "Selected Municipality", "entity_type": "Municipality", "source_tier": HarvestTier.TIER_4, "base_url": "https://municipality.example", "harvest_url": "https://municipality.example/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "passive_only"}},
        {"id": "pfma_schedule2_1", "name": "PFMA Schedule 2 Example", "entity_type": "PFMA Schedule 2", "source_tier": HarvestTier.TIER_3, "base_url": "https://pfma2.example", "harvest_url": "https://pfma2.example/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "off_initially"}},
        {"id": "pfma_schedule3_1", "name": "PFMA Schedule 3 Example", "entity_type": "PFMA Schedule 3", "source_tier": HarvestTier.TIER_3, "base_url": "https://pfma3.example", "harvest_url": "https://pfma3.example/tenders", "parser_type": "html", "is_active": False, "metadata_json": {"seed": True, "startup_scope": "off_initially"}},
    ]
    return [ProcurementSourceRecord.validate_payload(seed) for seed in seeds]


def import_sources_from_csv(path: str | Path, registry: SourceRegistry | None = None) -> Dict[str, Any]:
    registry = registry or SourceRegistry()
    rows: List[Dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows.extend(reader)
    return registry.bulk_import_sources(rows)


def import_sources_from_json(path: str | Path, registry: SourceRegistry | None = None) -> Dict[str, Any]:
    registry = registry or SourceRegistry()
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("sources") or payload.get("items") or []
    if not isinstance(payload, list):
        payload = []
    return registry.bulk_import_sources(payload)
