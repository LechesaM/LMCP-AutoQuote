from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_impl() -> ModuleType:
    module_path = Path(__file__).resolve().parents[2] / "lmcp-core" / "services" / "acquisition" / "harvest_source_registry_service.py"
    spec = importlib.util.spec_from_file_location("lmcp_acquisition_harvest_source_registry_service", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load acquisition harvest source registry service from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_IMPL = _load_impl()

build_default_harvest_sources = _IMPL.build_default_harvest_sources
load_default_live_harvest_sources = _IMPL.load_default_live_harvest_sources
get_curated_live_source_file = _IMPL.get_curated_live_source_file
build_default_harvest_sources_payload = _IMPL.build_default_harvest_sources_payload
sync_default_registry_file = _IMPL.sync_default_registry_file
get_registry_path = _IMPL.get_registry_path
load_harvest_sources = _IMPL.load_harvest_sources

__all__ = [
    "build_default_harvest_sources",
    "load_default_live_harvest_sources",
    "get_curated_live_source_file",
    "build_default_harvest_sources_payload",
    "sync_default_registry_file",
    "get_registry_path",
    "load_harvest_sources",
]
