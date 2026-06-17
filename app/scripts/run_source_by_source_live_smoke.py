from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.tender_harvester import load_harvest_sources, run_national_tender_radar


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the live harvest one source at a time to isolate hanging portals.")
    parser.add_argument("--source-file", type=str, default=str(PROJECT_ROOT / "app" / "data" / "harvest_sources.json"))
    parser.add_argument("--source-name", type=str, default=None, help="Only run sources whose name contains this text.")
    parser.add_argument("--source-group", type=str, default=None, help="Only run sources whose group contains this text.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of sources to test. 0 means all matching sources.")
    parser.add_argument("--duration-minutes", type=int, default=1)
    parser.add_argument("--sleep-seconds", type=int, default=1)
    parser.add_argument("--max-total", type=int, default=10)
    parser.add_argument("--max-per-source", type=int, default=2)
    parser.add_argument("--runtime-dir", type=str, default=None)
    parser.add_argument("--source-timeout-seconds", type=int, default=8)
    parser.add_argument("--playwright-timeout-ms", type=int, default=12000)
    parser.add_argument("--fail-fast", action="store_true", help="Stop on the first source failure or timeout.")
    return parser


def _matches(source: Dict[str, Any], source_name: Optional[str], source_group: Optional[str]) -> bool:
    if source_name:
        haystack = str(source.get("name") or source.get("source_name") or "").lower()
        if source_name.lower() not in haystack:
            return False
    if source_group:
        haystack = str(source.get("source_group") or source.get("category_group") or "").lower()
        if source_group.lower() not in haystack:
            return False
    return True


def _write_single_source_file(source: Dict[str, Any], runtime_dir: Optional[str], index: int) -> Path:
    root = Path(runtime_dir).expanduser().resolve() if runtime_dir else Path(tempfile.gettempdir())
    root.mkdir(parents=True, exist_ok=True)
    temp_path = root / f"live_source_smoke_{index:03d}.json"
    temp_path.write_text(json.dumps([source], indent=2, default=str), encoding="utf-8")
    return temp_path


def run_source_by_source_live_smoke(
    source_file: str,
    source_name: Optional[str] = None,
    source_group: Optional[str] = None,
    limit: int = 0,
    runtime_dir: Optional[str] = None,
    source_timeout_seconds: int = 8,
    playwright_timeout_ms: int = 12000,
    fail_fast: bool = False,
    emit_progress: bool = False,
) -> Dict[str, Any]:
    all_sources = load_harvest_sources(source_file, controlled_mode=False)
    selected_sources = [source for source in all_sources if isinstance(source, dict) and _matches(source, source_name, source_group)]
    if limit and limit > 0:
        selected_sources = selected_sources[: limit]

    results: List[Dict[str, Any]] = []
    progress_events: List[Dict[str, Any]] = []
    stop_on_failure = bool(fail_fast)
    for index, source in enumerate(selected_sources, start=1):
        source_file_path = _write_single_source_file(source, runtime_dir, index)
        source_label = source.get("name") or source.get("source_name") or source.get("url") or f"source-{index}"
        source_started_at = time.monotonic()
        start_event = {
            "event": "source_start",
            "index": index,
            "source_name": source_label,
            "source_url": source.get("url") or source.get("list_url"),
            "source_file": str(source_file_path),
        }
        progress_events.append(start_event)
        if emit_progress:
            print(json.dumps(start_event, default=str, ensure_ascii=False), file=sys.stderr, flush=True)
        try:
            smoke_result = run_national_tender_radar(
                max_total=10,
                max_per_source=2,
                max_sources_per_cycle=1,
                source_file=str(source_file_path),
                include_bad_sources=True,
                headless=True,
                enable_auto_quote=False,
                true_autonomous=False,
                persist_to_live_store=False,
                controlled_mode=False,
                source_timeout_seconds=source_timeout_seconds,
                playwright_timeout_ms=playwright_timeout_ms,
            )
            results.append(
                {
                    "index": index,
                    "source_name": source_label,
                    "source_url": source.get("url") or source.get("list_url"),
                    "source_file": str(source_file_path),
                    "status": smoke_result.get("status"),
                    "harvested_total": smoke_result.get("harvested_total"),
                    "eligible_total": smoke_result.get("eligible_total"),
                    "quote_ready_total": smoke_result.get("quote_ready_total"),
                    "source_health_overview": smoke_result.get("source_health_overview"),
                    "browser_available": smoke_result.get("browser_available"),
                    "source_timeout_seconds": smoke_result.get("source_timeout_seconds"),
                    "playwright_timeout_ms": smoke_result.get("playwright_timeout_ms"),
                    "elapsed_ms": round((time.monotonic() - source_started_at) * 1000, 2),
                }
            )
            end_event = {
                "event": "source_end",
                "index": index,
                "source_name": source_label,
                "status": smoke_result.get("status"),
                "elapsed_ms": round((time.monotonic() - source_started_at) * 1000, 2),
                "harvested_total": smoke_result.get("harvested_total"),
                "eligible_total": smoke_result.get("eligible_total"),
                "quote_ready_total": smoke_result.get("quote_ready_total"),
            }
            progress_events.append(end_event)
            if emit_progress:
                print(json.dumps(end_event, default=str, ensure_ascii=False), file=sys.stderr, flush=True)
            if smoke_result.get("status") != "ok":
                fail_fast = True
                if stop_on_failure:
                    break
        except Exception as exc:
            results.append(
                {
                    "index": index,
                    "source_name": source_label,
                    "source_url": source.get("url") or source.get("list_url"),
                    "source_file": str(source_file_path),
                    "status": "failed",
                    "error": str(exc),
                    "elapsed_ms": round((time.monotonic() - source_started_at) * 1000, 2),
                }
            )
            end_event = {
                "event": "source_end",
                "index": index,
                "source_name": source_label,
                "status": "failed",
                "error": str(exc),
                "elapsed_ms": round((time.monotonic() - source_started_at) * 1000, 2),
            }
            progress_events.append(end_event)
            if emit_progress:
                print(json.dumps(end_event, default=str, ensure_ascii=False), file=sys.stderr, flush=True)
            fail_fast = True
            if stop_on_failure:
                break
        finally:
            try:
                source_file_path.unlink(missing_ok=True)  # type: ignore[arg-type]
            except Exception:
                pass

    return {
        "status": "failed" if fail_fast else "ok",
        "stage": "run_source_by_source_live_smoke",
        "source_file": source_file,
        "source_name_filter": source_name,
        "source_group_filter": source_group,
        "source_count": len(selected_sources),
        "source_timeout_seconds": source_timeout_seconds,
        "playwright_timeout_ms": playwright_timeout_ms,
        "progress_events": progress_events,
        "results": results,
    }


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    payload = run_source_by_source_live_smoke(
        source_file=args.source_file,
        source_name=args.source_name,
        source_group=args.source_group,
        limit=args.limit,
        runtime_dir=args.runtime_dir,
        source_timeout_seconds=args.source_timeout_seconds,
        playwright_timeout_ms=args.playwright_timeout_ms,
        fail_fast=args.fail_fast,
        emit_progress=True,
    )
    print(json.dumps(payload, indent=2, default=str, ensure_ascii=False))
    return 1 if payload.get("status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
