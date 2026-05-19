from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence
from urllib.parse import urlparse, urlunparse

from app.core.runtime_paths import get_runtime_paths
from app.harvest.source_models import ProcurementSourceRecord
from app.harvest.source_tiers import HarvestTier, is_passive_tier, max_active_sources_for_tier


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _registry_path() -> Path:
    try:
        get_runtime_paths.cache_clear()
    except Exception:
        pass
    return get_runtime_paths().manual_production_file("harvest_sources.jsonl")


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    records: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except Exception:
            continue
        if isinstance(record, dict):
            records.append(record)
    return records


def _append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def normalize_urls(*urls: str | None) -> tuple[str, ...]:
    normalized: list[str] = []
    for url in urls:
        value = str(url or "").strip()
        if not value:
            continue
        parsed = urlparse(value)
        scheme = (parsed.scheme or "https").lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        query = parsed.query
        normalized_url = urlunparse((scheme, netloc, path, "", query, ""))
        normalized.append(normalized_url)
    return tuple(normalized)


class SourceRegistry:
    def __init__(self, storage_path: Path | None = None) -> None:
        self.storage_path = storage_path or _registry_path()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)

    def _latest_records(self) -> Dict[str, Dict[str, Any]]:
        latest: Dict[str, Dict[str, Any]] = {}
        for record in _read_jsonl(self.storage_path):
            record_id = str(record.get("id") or "").strip()
            if record_id:
                latest[record_id] = record
        return latest

    def _coerce(self, payload: Dict[str, Any] | ProcurementSourceRecord) -> ProcurementSourceRecord:
        if isinstance(payload, ProcurementSourceRecord):
            record = payload.model_copy()
        else:
            record = ProcurementSourceRecord.validate_payload(dict(payload))
        normalized_base, normalized_harvest = normalize_urls(record.base_url, record.harvest_url)
        return record.model_copy(update={
            "base_url": normalized_base,
            "harvest_url": normalized_harvest or normalized_base,
            "source_tier": HarvestTier.from_value(record.source_tier),
            "updated_at": _now(),
        })

    def _existing_normalized_urls(self, exclude_source_id: str = "") -> Dict[str, str]:
        mapping: Dict[str, str] = {}
        for record in self._latest_records().values():
            if exclude_source_id and str(record.get("id") or "") == str(exclude_source_id):
                continue
            for url in normalize_urls(record.get("base_url"), record.get("harvest_url")):
                mapping[url] = str(record.get("id") or "")
        return mapping

    def validate_activation_limits(self, source: Dict[str, Any] | ProcurementSourceRecord) -> None:
        record = self._coerce(source)
        if is_passive_tier(record.source_tier) and record.is_active:
            raise ValueError("Tier 4 sources must remain passive and inactive by default")
        if not record.is_active:
            return
        active_records = self.list_active_sources()
        counts: Dict[HarvestTier, int] = {}
        for item in active_records:
            tier = HarvestTier.from_value(item.source_tier)
            counts[tier] = counts.get(tier, 0) + 1
        tier = HarvestTier.from_value(record.source_tier)
        if counts.get(tier, 0) >= max_active_sources_for_tier(tier):
            raise ValueError(f"Active source limit reached for {tier.value}")

    def add_source(self, source: Dict[str, Any] | ProcurementSourceRecord) -> ProcurementSourceRecord:
        record = self._coerce(source)
        duplicate_urls = self._existing_normalized_urls()
        for url in normalize_urls(record.base_url, record.harvest_url):
            if url and url in duplicate_urls and duplicate_urls[url] != record.id:
                raise ValueError(f"Duplicate source URL detected: {url}")
        self.validate_activation_limits(record)
        _append_jsonl(self.storage_path, record.to_jsonable_dict())
        return record

    def update_source(self, source_id: str, updates: Dict[str, Any]) -> ProcurementSourceRecord:
        latest = self._latest_records()
        existing = latest.get(str(source_id))
        if not existing:
            raise KeyError(f"Unknown source id: {source_id}")
        merged = {**existing, **dict(updates or {}), "id": source_id, "updated_at": _now()}
        record = self._coerce(merged)
        duplicate_urls = self._existing_normalized_urls(exclude_source_id=source_id)
        for url in normalize_urls(record.base_url, record.harvest_url):
            if url and url in duplicate_urls:
                raise ValueError(f"Duplicate source URL detected: {url}")
        self.validate_activation_limits(record)
        _append_jsonl(self.storage_path, record.to_jsonable_dict())
        return record

    def disable_source(self, source_id: str, reason: str = "") -> ProcurementSourceRecord:
        return self.update_source(source_id, {"is_active": False, "metadata_json": {"disabled_reason": reason}})

    def list_sources(self) -> List[ProcurementSourceRecord]:
        return [ProcurementSourceRecord.validate_payload(record) for record in self._latest_records().values()]

    def list_active_sources(self) -> List[ProcurementSourceRecord]:
        return [record for record in self.list_sources() if record.is_active]

    def list_sources_by_tier(self, tier: str | HarvestTier) -> List[ProcurementSourceRecord]:
        resolved = HarvestTier.from_value(tier)
        return [record for record in self.list_sources() if HarvestTier.from_value(record.source_tier) == resolved]

    def bulk_import_sources(self, sources: Iterable[Dict[str, Any] | ProcurementSourceRecord]) -> Dict[str, Any]:
        imported: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for source in sources:
            try:
                record = self.add_source(source)
                imported.append(record.to_jsonable_dict())
            except Exception as exc:
                errors.append({"source": dict(source or {}) if isinstance(source, dict) else source.to_jsonable_dict(), "error": str(exc)})
        return {
            "imported_count": len(imported),
            "error_count": len(errors),
            "imported": imported,
            "errors": errors,
        }


DEFAULT_SOURCE_REGISTRY = SourceRegistry()


def load_source_registry() -> SourceRegistry:
    return DEFAULT_SOURCE_REGISTRY
