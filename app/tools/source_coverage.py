from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.services.source_coverage_certificate import (
    failure_records_from_summary,
    format_summary_lines,
    load_daily_summary,
    load_latest_summary,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Read-only LMCP source coverage certificate viewer.")
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument("--today", action="store_true", help="Print today's daily aggregate certificate.")
    group.add_argument("--date", help="Print the daily aggregate certificate for YYYY-MM-DD.")
    group.add_argument("--latest", action="store_true", help="Print the latest run certificate.")
    parser.add_argument("--failures", action="store_true", help="List failed source records for the selected scope.")
    parser.add_argument(
        "--runtime-root",
        default=None,
        help="Override the runtime/source_coverage root used for reads.",
    )
    return parser


def _select_summary(args: argparse.Namespace) -> Dict[str, Any]:
    if args.today:
        return load_daily_summary(datetime.now(timezone.utc).date().isoformat(), runtime_root=args.runtime_root)
    if args.date:
        return load_daily_summary(args.date, runtime_root=args.runtime_root)
    return load_latest_summary(runtime_root=args.runtime_root)


def _print_no_certificate_recorded() -> None:
    print("no certificate recorded")


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary = _select_summary(args)
    except FileNotFoundError:
        _print_no_certificate_recorded()
        return 0

    for line in format_summary_lines(summary):
        print(line)
    if args.failures:
        failures = failure_records_from_summary(summary)
        if failures:
            print("FAILURES")
            for record in failures:
                print(
                    json.dumps(
                        {
                            "source_name": record.get("source_name"),
                            "source_url": record.get("source_url"),
                            "source_type": record.get("source_type"),
                            "error_reason": record.get("error_reason"),
                            "http_status": record.get("http_status"),
                        },
                        sort_keys=True,
                    )
                )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
