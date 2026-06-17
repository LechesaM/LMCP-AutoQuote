from __future__ import annotations

import json
from pathlib import Path


def test_queue_refresh_sources_contains_national_treasury_etenders() -> None:
    path = Path("/Users/cash/Documents/app/data/queue_refresh_sources.json")
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    sources = payload.get("sources")
    assert isinstance(sources, list)
    assert len(sources) == 1
    source = sources[0]
    assert source["name"] == "National Treasury eTenders"
    assert source["url"] == "https://www.etenders.gov.za/Home/opportunities"
    assert source["type"] == "web"
    assert source["source_group"] == "etenders"
    assert source["submission_method"] == "portal"
