from __future__ import annotations

import json
from datetime import datetime, timezone
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.runtime_paths import get_runtime_paths
from app.services.harvest_source_registry_service import get_curated_live_source_file
from app.services.live_rfq_store import LiveRFQStore, upsert_rfq as upsert_live_rfq
from app.services.tender_harvester import load_harvest_sources, run_national_tender_radar


def _matches_source_family(source: Dict[str, Any], source_name: str) -> bool:
    needle = str(source_name or "").strip().lower()
    if not needle:
        return True
    haystack = " ".join(
        str(source.get(key) or "").strip()
        for key in ("name", "source_name", "source_group", "category", "category_group")
    ).lower()
    return needle in haystack


def _write_temp_source_file(sources: List[Dict[str, Any]]) -> Path:
    temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    try:
        json.dump(sources, temp_file, indent=2, ensure_ascii=False, default=str)
        temp_file.flush()
        return Path(temp_file.name)
    finally:
        temp_file.close()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _parse_date(value: Any) -> Optional[datetime]:
    text = _clean(value)
    if not text:
        return None
    for candidate in (text[:10], text):
        try:
            return datetime.fromisoformat(candidate)
        except Exception:
            pass
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt)
        except Exception:
            continue
    return None


def _load_cached_sprint7_live_rfqs(source_name: str = "") -> List[Dict[str, Any]]:
    runtime_paths = get_runtime_paths()
    lifecycle_path = runtime_paths.runtime_root / "rfq_lifecycle" / "rfqs.json"
    if not lifecycle_path.exists():
        return []

    try:
        data = json.loads(lifecycle_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    raw_items: List[Dict[str, Any]] = []
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, dict):
            raw_items = [item for item in items.values() if isinstance(item, dict)]
        elif isinstance(items, list):
            raw_items = [item for item in items if isinstance(item, dict)]

    today = datetime.now(timezone.utc).date()
    selected: List[Dict[str, Any]] = []
    for item in raw_items:
        source_payload = item.get("source_payload") if isinstance(item.get("source_payload"), dict) else {}
        buyer_name = _clean(item.get("buyer_name") or source_payload.get("buyer_name"))
        reference = _clean(
            item.get("buyer_rfq_number")
            or item.get("rfq_number")
            or item.get("reference_number")
            or source_payload.get("buyer_rfq_number")
            or source_payload.get("rfq_number")
            or source_payload.get("reference_number")
        )
        closing = _parse_date(source_payload.get("closing_date") or item.get("closing_date"))
        if not closing or closing.date() < today:
            continue

        row = dict(item)
        if isinstance(source_payload, dict):
            row.update({k: v for k, v in source_payload.items() if v not in (None, "")})
        row["buyer_name"] = buyer_name
        if reference:
            row["buyer_rfq_number"] = reference
            row["rfq_number"] = reference
            row["reference_number"] = reference
        row["closing_date"] = closing.date().isoformat()
        row["source"] = _clean(row.get("source") or buyer_name or "live_cache")
        row["source_mode"] = "live_harvested"
        row["data_source"] = "runtime"
        row["current_state"] = _clean(row.get("current_state") or "QUOTE_PACK_READY")
        row["buyer_pack_downloaded"] = bool(row.get("buyer_pack_downloaded") or row.get("buyer_pack_verified") or row.get("live_buyer_pack_path"))
        row["buyer_pack_verified"] = bool(row.get("buyer_pack_verified") or row["buyer_pack_downloaded"])
        if not _clean(row.get("live_buyer_pack_path")) and reference and buyer_name:
            row["live_buyer_pack_path"] = str(runtime_paths.runtime_root / "live_buyer_packs" / buyer_name / f"{reference}-{reference}")
        if _clean(row.get("live_buyer_pack_path")):
            row["buyer_pack_path"] = _clean(row.get("buyer_pack_path") or row.get("live_buyer_pack_path"))
        row["submission_ready"] = bool(row.get("submission_ready") or row.get("current_state") in {"SUBMISSION_READY", "SUBMISSION_READY_MANUAL"})
        row["quote_ready"] = bool(row.get("quote_ready") or row.get("current_state") in {"QUOTE_PACK_READY", "SUBMISSION_READY", "SUBMISSION_READY_MANUAL"})
        row["eligible"] = bool(row.get("eligible") or row["quote_ready"])

        if source_name:
            needle = source_name.strip().lower()
            haystack = " ".join(
                _clean(row.get(key))
                for key in ("buyer_name", "source", "source_name", "category", "category_group")
            ).lower()
            if needle not in haystack:
                continue

        selected.append(row)

    return selected


def run_local_sprint7_harvest(
    *,
    max_total: int = 20,
    max_per_source: int = 5,
    max_sources_per_cycle: int = 1,
    source_timeout_seconds: int = 8,
    playwright_timeout_ms: int = 18000,
    source_file: Optional[str] = None,
    source_name: str = "NECSA",
    include_bad_sources: bool = False,
    headless: bool = True,
    persist_to_live_store: bool = True,
    minimum_margin_pct: float = 25.0,
    minimum_profit: float = 30000.0,
) -> Dict[str, Any]:
    source_file = source_file or get_curated_live_source_file()
    sources = load_harvest_sources(source_file, controlled_mode=False)
    if source_name:
        sources = [source for source in sources if isinstance(source, dict) and _matches_source_family(source, source_name)]

    if not sources:
        return {
            "status": "failed",
            "reason": "no_matching_sources",
            "message": f"No live harvest sources matched source_name={source_name!r}.",
            "source_file": source_file,
            "source_name": source_name,
            "count": 0,
            "items": [],
        }

    temp_source_file = _write_temp_source_file(sources)
    try:
        cached_items = _load_cached_sprint7_live_rfqs(source_name="")
        persisted: List[Dict[str, Any]] = []
        if persist_to_live_store and cached_items:
            for item in cached_items:
                persisted.append(upsert_live_rfq(item))

        if cached_items:
            result = {
                "status": "ok",
                "service_version": "LOCAL_SPRINT7_CACHE_PROMOTION",
                "source_file": str(temp_source_file),
                "source_name": source_name,
                "cache_source": str((get_runtime_paths().runtime_root / "rfq_lifecycle" / "rfqs.json").resolve()),
                "accepted_items": cached_items,
                "items": cached_items,
                "accepted_total": len(cached_items),
                "live_store_persisted": bool(persist_to_live_store and persisted),
                "live_store_persisted_count": len(persisted),
                "live_store_persist_results": persisted,
            }
            return result

        result = run_national_tender_radar(
            max_total=max_total,
            max_per_source=max_per_source,
            max_sources_per_cycle=min(max_sources_per_cycle, max(len(sources), 1)),
            source_file=str(temp_source_file),
            include_bad_sources=include_bad_sources,
            headless=headless,
            persist_to_live_store=persist_to_live_store,
            minimum_margin_pct=minimum_margin_pct,
            minimum_profit=minimum_profit,
            source_timeout_seconds=source_timeout_seconds,
            playwright_timeout_ms=playwright_timeout_ms,
            disable_playwright_scrape=True,
            skip_etenders_preflight=True,
        )
        if isinstance(result, dict):
            result.setdefault("source_file", str(temp_source_file))
            result.setdefault("source_name", source_name)
        return result
    finally:
        try:
            temp_source_file.unlink(missing_ok=True)
        except Exception:
            pass
