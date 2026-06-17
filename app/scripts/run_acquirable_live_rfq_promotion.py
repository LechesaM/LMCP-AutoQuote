from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve()
PROJECT_ROOT = SCRIPT_PATH.parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.runtime_paths import get_runtime_paths
from app.services.acquirable_live_rfq_promotion_service import DEFAULT_TIMEOUT_SECONDS, promote_acquirable_live_rfqs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Promote acquirable live RFQs into evidence-backed buyer-pack rows.")
    parser.add_argument("--limit", type=int, default=10, help="Maximum acquirable live RFQs to promote.")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Acquisition timeout per RFQ.")
    parser.add_argument(
        "--output",
        type=str,
        default=str(get_runtime_paths().manual_production_dir / "acquirable_live_rfq_promotion_report.json"),
        help="Path to the promotion audit report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    report = promote_acquirable_live_rfqs(
        limit=args.limit,
        timeout_seconds=args.timeout_seconds,
        output_path=args.output,
    )
    print(json.dumps(report, indent=2, ensure_ascii=False, default=str))
    return 0 if report.get("status") == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
