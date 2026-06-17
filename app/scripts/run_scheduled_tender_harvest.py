from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.harvest_scheduler_service import run_scheduled_tender_harvest

SMOKE_SOURCE_FILE = Path(__file__).resolve().parents[1] / "data" / "smoke_harvest_sources.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a bounded scheduled tender harvest.")
    parser.add_argument("--duration-minutes", type=int, default=60)
    parser.add_argument("--sleep-seconds", type=int, default=600)
    parser.add_argument("--max-total", type=int, default=20)
    parser.add_argument("--max-per-source", type=int, default=3)
    parser.add_argument("--max-sources-per-cycle", type=int, default=10)
    parser.add_argument("--source-file", type=str, default=None)
    parser.add_argument("--smoke-fixture", action="store_true", help="Use the bundled local smoke source fixture.")
    parser.add_argument("--controlled-mode", action="store_true", help="Force fixture-only execution with no live persistence or browser scraping.")
    parser.add_argument("--runtime-dir", type=str, default=None, help="Override the runtime directory for scheduled-harvest artifacts.")
    parser.add_argument("--source-timeout-seconds", type=int, default=8, help="Per-source request timeout for live acquisition.")
    parser.add_argument("--playwright-timeout-ms", type=int, default=18000, help="Per-source Playwright timeout for live acquisition.")
    parser.add_argument("--include-bad-sources", action="store_true")
    parser.add_argument("--headless", action="store_true", default=True)
    parser.add_argument("--auto-quote", action="store_true")
    parser.add_argument("--true-autonomous", action="store_true")
    parser.add_argument(
        "--persist-to-live-store",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Persist harvested items to the live store. Defaults to off for smoke runs and on otherwise.",
    )
    parser.add_argument("--minimum-margin-pct", type=float, default=25.0)
    parser.add_argument("--minimum-profit", type=float, default=30000.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    controlled_mode = bool(args.controlled_mode or args.smoke_fixture)
    source_file = args.source_file or (str(SMOKE_SOURCE_FILE) if controlled_mode else None)
    persist_to_live_store = args.persist_to_live_store if args.persist_to_live_store is not None else not controlled_mode
    result = run_scheduled_tender_harvest(
        duration_minutes=args.duration_minutes,
        sleep_seconds=args.sleep_seconds,
        max_total=args.max_total,
        max_per_source=args.max_per_source,
        max_sources_per_cycle=args.max_sources_per_cycle,
        headless=args.headless,
        include_bad_sources=args.include_bad_sources,
        source_file=source_file,
        enable_auto_quote=args.auto_quote,
        true_autonomous=args.true_autonomous,
        persist_to_live_store=persist_to_live_store,
        minimum_margin_pct=args.minimum_margin_pct,
        minimum_profit=args.minimum_profit,
        controlled_mode=controlled_mode,
        runtime_dir=args.runtime_dir,
        source_timeout_seconds=args.source_timeout_seconds,
        playwright_timeout_ms=args.playwright_timeout_ms,
    )
    print(json.dumps(result, indent=2, default=str))
    return 0 if result.get("stop_reason") != "cycle_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
